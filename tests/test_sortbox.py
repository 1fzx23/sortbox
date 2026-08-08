#!/usr/bin/env python3
"""sortbox 核心功能 smoke test（零依赖，仅用标准库）。

运行: python -m tests.test_sortbox  或  python tests/test_sortbox.py
"""

import sys
import tempfile
import shutil
from pathlib import Path

# 让测试能 import 到上层的 sortbox 模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sortbox as sb  # noqa: E402


def _make_files(base: Path, names: list[str]) -> None:
    for n in names:
        p = base / n
        p.write_text("content", encoding="utf-8")


def test_classify_by_ext():
    assert sb.classify_by_ext(Path("a.png"), sb.DEFAULT_CATEGORY_MAP) == "Images"
    assert sb.classify_by_ext(Path("b.zip"), sb.DEFAULT_CATEGORY_MAP) == "Archives"
    assert sb.classify_by_ext(Path("c.unknownext"), sb.DEFAULT_CATEGORY_MAP) == "Others"


def test_classify_by_date():
    # 用临时文件，验证返回格式为 YYYY-MM
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.txt"
        f.write_text("hi")
        out = sb.classify_by_date(f)
        assert len(out) == 7 and out[4] == "-"


def test_plan_basic():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        _make_files(base, ["a.png", "b.pdf", "c.zip"])
        plan = sb.build_plan(base, mode=sb.MODE_EXT)
        # 全部 3 个文件都应被规划移动
        assert plan.total == 3
        assert plan.skipped == 0
        folders = {m.dst.parent.name for m in plan.moves}
        assert folders == {"Images", "Documents", "Archives"}


def test_dry_run_does_not_move():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        _make_files(base, ["a.png"])
        plan = sb.build_plan(base, mode=sb.MODE_EXT)
        assert (base / "a.png").exists()
        sb.execute(plan, dry_run=True)
        # dry-run 后原文件仍在
        assert (base / "a.png").exists()
        assert not (base / "Images").exists()


def test_execute_moves_and_undo():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        _make_files(base, ["a.png", "b.pdf"])
        target = base / "sorted"
        plan = sb.build_plan(base, target=target, mode=sb.MODE_EXT)
        undo = base / "undo.sh"
        sb.execute(plan, dry_run=False, undo_path=undo)
        # 文件应已移动到分类目录
        assert (target / "Images" / "a.png").exists()
        assert (target / "Documents" / "b.pdf").exists()
        # 原位置已空
        assert not (base / "a.png").exists()
        # 回退脚本已生成且含 mv 命令
        assert undo.exists()
        assert "mv" in undo.read_text(encoding="utf-8")


def test_collision_renames():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        _make_files(base, ["a.png"])
        target = base / "sorted"
        (target / "Images").mkdir(parents=True)
        # 预先放一个同名文件，制造冲突
        (target / "Images" / "a.png").write_text("old", encoding="utf-8")
        plan = sb.build_plan(base, target=target, mode=sb.MODE_EXT)
        assert plan.moves[0].collision is True
        sb.execute(plan, dry_run=False)
        # 新文件被重命名为 a_1.png，旧文件保留
        assert (target / "Images" / "a_1.png").exists()
        assert (target / "Images" / "a.png").read_text(encoding="utf-8") == "old"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
