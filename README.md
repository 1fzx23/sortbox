# sortbox

> 零依赖的命令行文件整理工具 —— 把散落一地的文件，按扩展名或日期自动归类到子目录。

[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org)

每次下载文件夹被图片、文档、压缩包、代码搅成一团？`sortbox` 一个命令帮你收拾干净。
**只使用 Python 标准库**，无第三方依赖，跨 Windows / macOS / Linux。

- 🗂️ **按扩展名分类**：图片 / 文档 / 代码 / 压缩包 / 音频 / 视频 / 其他
- 📅 **按修改日期分类**：归入 `YYYY-MM` 月目录
- 👀 **dry-run 预览**：先看看会动哪些文件，再决定是否执行
- ↩️ **undo 回退脚本**：一键生成反向 `mv` 脚本，手滑也能救
- 🔒 **安全重名处理**：目标已存在时自动加 `_1` 序号，绝不静默覆盖
- 🔁 **递归处理**：连子目录里的文件一起收拾

---

## 安装

只需要 Python 3.8+，无需安装任何依赖。

```bash
# 方式一：直接下载单文件使用
curl -O https://raw.githubusercontent.com/1fzx23/sortbox/main/sortbox.py
python sortbox.py --help

# 方式二：克隆仓库后作为模块运行
git clone https://github.com/1fzx23/sortbox.git
cd sortbox
python sortbox.py --help
```

> 提示：把 `sortbox.py` 所在目录加入 `PATH`，即可在任何地方用 `python sortbox.py ...`。

---

## 使用方法

### 1. 预览（不改动任何文件）

```bash
python sortbox.py ~/Downloads --dry-run
```

### 2. 真正整理到原目录下的分类子文件夹

```bash
python sortbox.py ~/Downloads
```

执行后 `~/Downloads` 下会生成 `Images/`、`Documents/`、`Archives/` 等子目录。

### 3. 整理到指定目标目录（保持源目录干净）

```bash
python sortbox.py ~/Downloads --target ~/Sorted
```

### 4. 生成回退脚本（推荐第一次用）

```bash
python sortbox.py ~/Downloads --undo undo.sh
# 后悔了就执行：
bash undo.sh
```

### 5. 按修改日期归类

```bash
python sortbox.py ~/Photos --mode date
# 生成 2026-01/、2026-02/ ... 这样的月目录
```

### 6. 递归处理子目录

```bash
python sortbox.py ./mess --recursive
```

### 7. 自定义分类规则

写个 `my-map.json`：

```json
{
  ".log": "Logs",
  ".tmp": "Temp",
  ".pdf": "MyDocs"
}
```

然后：

```bash
python sortbox.py ./data --map my-map.json
```

---

## 命令参数一览

| 参数 | 说明 |
| --- | --- |
| `path` | 要整理的目录，默认当前目录 `.` |
| `-t, --target` | 分类目标根目录（默认与源目录相同） |
| `-r, --recursive` | 递归处理子目录中的文件 |
| `-m, --mode` | `ext`（按扩展名，默认）或 `date`（按修改日期） |
| `--map` | 自定义分类映射 JSON 文件 |
| `-n, --dry-run` | 只预览，不真正移动文件 |
| `-u, --undo` | 执行后写出回退脚本到该路径（建议 `.sh`） |
| `-l, --log` | 把执行动作追加写入日志文件 |
| `-q, --quiet` | 安静模式，仅输出汇总 |

---

## 示例输出

```
移动: /Users/me/Downloads/cat.png  ->  /Users/me/Downloads/Images/cat.png
移动: /Users/me/Downloads/report.pdf  ->  /Users/me/Downloads/Documents/report.pdf
已写入回退脚本: undo.sh

[完成] 计划移动 2 个文件（跳过 0 项，其中 0 个因重名已重命名）。
```

---

## 工作原理

1. **扫描**：列出目标目录（或递归）下的所有文件，跳过目录与隐藏文件。
2. **分类**：根据扩展名查映射表 → 分类目录名；或读取文件 mtime → `YYYY-MM`。
3. **规划**：为每份文件计算目标路径，若目标已存在则自动追加 `_1` 序号避免覆盖。
4. **执行**：创建分类目录并移动文件；可同时写出反向 `mv` 脚本以便回退。

整个流程**只读文件元数据 + 移动文件**，不会读取/上传文件内容，可放心用于隐私目录。

---

## 测试

```bash
python tests/test_sortbox.py
```

覆盖：扩展名/日期分类、dry-run 不移动、实际移动与 undo、重名重命名。

---

## License

[MIT](LICENSE) © 1fzx23
