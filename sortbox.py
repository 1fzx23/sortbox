#!/usr/bin/env python3
"""sortbox — 零依赖的命令行文件整理工具。

把指定目录里散落的文件按「扩展名分类」或「修改日期」自动移动到子目录，
支持 dry-run 预览、生成 undo 回退脚本、递归处理、自定义目标目录，
并安全地解决重名冲突（绝不静默覆盖）。

只使用 Python 标准库，兼容 Windows / macOS / Linux。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# 默认分类规则：扩展名(小写) -> 分类目录名
# ---------------------------------------------------------------------------
DEFAULT_CATEGORY_MAP: dict[str, str] = {
    # 图片
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images",
    ".bmp": "Images", ".webp": "Images", ".svg": "Images", ".ico": "Images",
    ".tiff": "Images", ".heic": "Images",
    # 文档
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".txt": "Documents", ".md": "Documents", ".rtf": "Documents",
    ".odt": "Documents", ".ppt": "Documents", ".pptx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".csv": "Documents",
    ".epub": "Documents", ".tex": "Documents",
    # 代码 / 文本源码
    ".py": "Code", ".js": "Code", ".ts": "Code", ".tsx": "Code",
    ".jsx": "Code", ".java": "Code", ".c": "Code", ".cpp": "Code",
    ".h": "Code", ".hpp": "Code", ".cs": "Code", ".go": "Code",
    ".rs": "Code", ".rb": "Code", ".php": "Code", ".sh": "Code",
    ".bash": "Code", ".ps1": "Code", ".sql": "Code", ".html": "Code",
    ".css": "Code", ".scss": "Code", ".json": "Code", ".yaml": "Code",
    ".yml": "Code", ".toml": "Code", ".xml": "Code", ".ini": "Code",
    # 压缩包
    ".zip": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".bz2": "Archives", ".xz": "Archives", ".7z": "Archives",
    ".rar": "Archives", ".tgz": "Archives",
    # 音频
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".aac": "Audio",
    ".ogg": "Audio", ".m4a": "Audio",
    # 视频
    ".mp4": "Video", ".mkv": "Video", ".mov": "Video", ".avi": "Video",
    ".webm": "Video", ".flv": "Video", ".wmv": "Video",
}

# 归类模式
MODE_EXT = "ext"
MODE_DATE = "date"


@dataclass
class MovePlan:
    """一条移动计划：从 src 移动到 dst；collision 标记目标是否已存在。"""

    src: Path
    dst: Path
    collision: bool = False


@dataclass
class OrganizationResult:
    moves: list[MovePlan] = field(default_factory=list)
    skipped: int = 0  # 目录、隐藏文件等被跳过的数量

    @property
    def total(self) -> int:
        return len(self.moves)


def classify_by_ext(path: Path, category_map: dict[str, str]) -> str:
    """根据扩展名返回分类目录名，未知类型归入 Others。"""
    return category_map.get(path.suffix.lower(), "Others")


def classify_by_date(path: Path) -> str:
    """根据修改时间返回 `YYYY-MM` 形式的日期目录名。"""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y-%m")


def _unique_dst(dst: Path) -> tuple[Path, bool]:
    """若 dst 已存在，返回追加序号的新路径，并标记是否存在冲突。"""
    if not dst.exists():
        return dst, False
    stem = dst.stem
    suffix = dst.suffix
    i = 1
    while True:
        candidate = dst.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate, True
        i += 1


def build_plan(
    root: Path,
    *,
    target: Path | None = None,
    recursive: bool = False,
    mode: str = MODE_EXT,
    category_map: dict[str, str] | None = None,
) -> OrganizationResult:
    """扫描 root，生成移动计划（不真正移动文件）。

    - 目录会被跳过
    - 目标分类目录本身不会被当作源文件移动
    - 默认不处理隐藏文件（以 . 开头）
    """
    if category_map is None:
        category_map = DEFAULT_CATEGORY_MAP

    result = OrganizationResult()
    base_target = target if target is not None else root

    def iter_files() -> Iterable[Path]:
        if recursive:
            # 自下而上，优先处理深层，避免移动过程中路径失效
            for p in sorted(root.rglob("*"), reverse=True):
                if p.is_file():
                    yield p
        else:
            for p in sorted(root.iterdir()):
                if p.is_file():
                    yield p

    existing_categories = {c.lower() for c in category_map.values()}
    existing_categories.add("others")

    for f in iter_files():
        # 跳过隐藏文件
        if f.name.startswith("."):
            result.skipped += 1
            continue
        # 避免把“目标分类目录里的文件”再规划一次（递归时）
        # 用 target in f.parents 兼容 Python 3.8+（is_relative_to 是 3.9+）
        if target is not None and target in f.parents:
            continue

        if mode == MODE_DATE:
            folder = classify_by_date(f)
        else:
            folder = classify_by_ext(f, category_map)

        dst_dir = base_target / folder
        desired = dst_dir / f.name
        unique, collision = _unique_dst(desired)
        result.moves.append(MovePlan(src=f, dst=unique, collision=collision))

    return result


def execute(
    plan: OrganizationResult,
    *,
    dry_run: bool = False,
    undo_path: Path | None = None,
    log_path: Path | None = None,
) -> list[str]:
    """执行移动计划。

    返回实际执行的动作描述列表（用于日志/回显）。
    若 dry_run=True 只模拟、不改动文件系统，但仍可写 undo 脚本（基于计划）。
    """
    actions: list[str] = []
    undo_lines: list[str] = ["#!/usr/bin/env bash", "# sortbox undo script — 反向移动恢复文件", ""]

    for mv in plan.moves:
        rel_src = mv.src
        rel_dst = mv.dst
        if dry_run:
            tag = "重名→重命名" if mv.collision else "移动"
            actions.append(f"[dry-run] {tag}: {rel_src}  ->  {rel_dst}")
            # 即使是预览，也记录回退命令，方便用户事后反悔
            undo_lines.append(f'# mv "{rel_dst}" "{rel_src}"')
            continue

        rel_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(rel_src), str(rel_dst))
        actions.append(f"移动: {rel_src}  ->  {rel_dst}")
        # undo：把目标移回原处（用绝对路径更稳妥）
        undo_lines.append(f'mv "{rel_dst.resolve()}" "{rel_src.resolve()}"')

    if undo_path is not None and (not dry_run or undo_path):
        undo_path.write_text("\n".join(undo_lines) + "\n", encoding="utf-8")
        actions.append(f"已写入回退脚本: {undo_path}")

    if log_path is not None and actions:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"# sortbox run @ {ts}\n")
            fh.write("\n".join(actions) + "\n\n")

    return actions


def _load_custom_map(path: Path) -> dict[str, str]:
    """从 JSON 文件加载自定义分类映射（{"ext": "Category"}）。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k.lower() if k.startswith(".") else f".{k.lower()}": v for k, v in raw.items()}


def run(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sortbox",
        description="零依赖的命令行文件整理工具：按扩展名或日期把文件归类到子目录。",
    )
    parser.add_argument("path", nargs="?", default=".", help="要整理的目录（默认当前目录）")
    parser.add_argument("-t", "--target", help="分类目标根目录（默认与源目录相同）")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归处理子目录中的文件")
    parser.add_argument(
        "-m", "--mode", choices=[MODE_EXT, MODE_DATE], default=MODE_EXT,
        help="归类模式：ext=按扩展名(默认)，date=按修改日期(YYYY-MM)",
    )
    parser.add_argument("--map", help="自定义分类映射 JSON 文件，如 {\".log\":\"Logs\"}")
    parser.add_argument("-n", "--dry-run", action="store_true", help="只预览，不真正移动文件")
    parser.add_argument("-u", "--undo", help="执行后写出回退脚本到该路径（建议用 .sh）")
    parser.add_argument("-l", "--log", help="把执行动作追加写入日志文件")
    parser.add_argument("-q", "--quiet", action="store_true", help="安静模式，仅输出汇总")
    parser.add_argument("--version", action="version", version=f"sortbox {__version__}")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(f"错误：路径不存在或不是目录：{root}", file=sys.stderr)
        return 2

    target = Path(args.target).expanduser().resolve() if args.target else None
    category_map = _load_custom_map(Path(args.map)) if args.map else None

    plan = build_plan(
        root, target=target, recursive=args.recursive, mode=args.mode, category_map=category_map
    )

    if not plan.moves:
        print("没有需要整理的文件。")
        return 0

    undo_path = Path(args.undo).expanduser().resolve() if args.undo else None
    log_path = Path(args.log).expanduser().resolve() if args.log else None

    actions = execute(plan, dry_run=args.dry_run, undo_path=undo_path, log_path=log_path)

    if not args.quiet:
        for line in actions:
            print(line)

    mode_label = "预览" if args.dry_run else "完成"
    collisions = sum(1 for m in plan.moves if m.collision)
    print(
        f"\n[{mode_label}] 计划移动 {plan.total} 个文件"
        f"（跳过 {plan.skipped} 项，其中 {collisions} 个因重名已重命名）。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
