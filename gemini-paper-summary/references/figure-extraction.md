# 把关键架构图导出为图片

> 本文件是 `SKILL.md` 核心原则 #5 的延伸。默认总结里的图引用是
> `![图 1：xxx](PDF p.3)` 这种 page reference 形式——它能让读者回到原 PDF 对应页看图，
> 但不会真的把图嵌到 Markdown 里。本文件说明三种把"真实图片"嵌回去的方案。

## 方案对比

| 方案 | 依赖 | 输出质量 | 自动化程度 | 适用场景 |
| --- | --- | --- | --- | --- |
| 整页截图 | 无（系统 PDF 阅读器） | 包含页边距、页眉页脚 | 半自动（手动） | 偶尔几张图 |
| `pymupdf` 抽嵌入图片 | `pymupdf`（pip 安装） | 仅嵌入图片（不含坐标轴） | 全自动 | 矢量图、嵌入位图 |
| `pymupdf` 渲染指定页/区域 | `pymupdf` | 整页或裁剪区域的高质量位图 | 全自动 | 任意 PDF（兜底） |

> 推荐顺序：先试"嵌入图片"（图 1），再不行就"渲染指定页区域"（图 2）。

## 方案 1：整页截图（最简单）

用任何 PDF 阅读器（macOS Preview、Adobe Reader、浏览器）打开 PDF，
翻到目标页，`Cmd+Shift+4`（macOS）或截图工具截屏，保存为 PNG。

适合"一两张图就行"的轻量场景。缺点是分辨率受显示器限制，
且带页眉页脚、页码、左右边距。

## 方案 2：抽取嵌入图片（高质量）

`pymupdf` 可以枚举 PDF 中所有嵌入的位图 / 矢量图，单独导出：

```bash
pip install --user --break-system-packages pymupdf
```

最小脚本（`extract_figures.py`）：

```python
import sys
from pathlib import Path

import fitz  # pymupdf


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 extract_figures.py <pdf>", file=sys.stderr)
        sys.exit(2)
    pdf_path = Path(sys.argv[1])
    out_dir = pdf_path.with_suffix("")  # paper.pdf -> paper/
    out_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)
    for page_idx, page in enumerate(doc, start=1):
        images = page.get_images(full=True)
        for img_idx, img in enumerate(images, start=1):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            # 透明图转白底，避免部分 Markdown 渲染器显示成黑块
            if pix.n - pix.alpha >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            out_path = out_dir / f"page{page_idx:02d}-img{img_idx}.png"
            pix.save(out_path)
            print(f"saved {out_path}")
    print(f"all done -> {out_dir}")


if __name__ == "__main__":
    main()
```

跑完后在 Markdown 总结里把

```markdown
![图 1：整体架构](PDF p.3)
```

替换成

```markdown
![图 1：整体架构](paper/page03-img1.png)
```

`paper/` 与 `paper.pdf` 同目录，Markdown 相对路径引用即可。

> 局限：如果论文的图是用矢量指令画出来的（很多会议论文都是这样），
> `get_images()` 找不到 entry，会得到空结果——这时改用方案 3。

## 方案 3：渲染指定页 / 指定矩形（兜底）

直接用 `pymupdf` 把整页（或其中一块矩形区域）按 2-3 倍 DPI 渲染成 PNG：

```python
import sys
from pathlib import Path

import fitz


def main():
    pdf_path = Path(sys.argv[1])
    page_num = int(sys.argv[2])  # 1-based
    out_path = Path(sys.argv[3])  # 输出 PNG 路径

    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    # 2x DPI
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix)
    pix.save(out_path)
    print(f"saved {out_path} ({pix.width}x{pix.height})")


if __name__ == "__main__":
    main()
```

调用：

```bash
python3 extract_page.py paper.pdf 3 paper-figure-1.png   # 第 3 页整页
```

如果只想截图中某个区域，传入 clip：

```python
clip = fitz.Rect(x0, y0, x1, y1)  # 单位是 PDF point（1 point = 1/72 inch）
pix = page.get_pixmap(matrix=matrix, clip=clip)
```

> 单位换算：A4 是 595×842 points，Letter 是 612×792 points。
> PDF 阅读器显示坐标时也是用 point，但通常原点是左上角（与 `fitz.Rect` 一致）。

## 方案 4（批处理）：根据总结里"关键架构图"段批量导出

如果你已经跑过 `gemini_paper_summary.py`，得到了带 `PDF p.X` 引用的 Markdown，
可以用正则批量抓出页码，再循环调方案 3：

```python
import re
import subprocess
import sys
from pathlib import Path

import fitz


def main():
    md_path = Path(sys.argv[1])  # paper.summary.md
    pdf_path = Path(sys.argv[2])  # paper.pdf
    out_dir = pdf_path.with_suffix("") / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    text = md_path.read_text()
    pages = sorted({int(m) for m in re.findall(r"PDF p\.(\d+)", text)})
    print(f"found page references: {pages}")

    doc = fitz.open(pdf_path)
    for i, page_num in enumerate(pages, start=1):
        page = doc[page_num - 1]
        out_path = out_dir / f"figure-{i}-p{page_num}.png"
        page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0)).save(out_path)
        print(f"saved {out_path}")

    # 把 Markdown 里的 (PDF p.X) 替换为 (paper/figures/figure-N-pX.png)
    # N 是 pages 列表中的索引
    def repl(match):
        page_num = int(match.group(1))
        idx = pages.index(page_num) + 1
        return f"({pdf_path.stem}/figures/figure-{idx}-p{page_num}.png)"

    new_md = re.sub(r"\(PDF p\.(\d+)\)", repl, text)
    md_path.write_text(new_md)
    print(f"updated {md_path}")


if __name__ == "__main__":
    main()
```

调用：

```bash
python3 embed_figures.py paper.summary.md paper.pdf
```

跑完之后，Markdown 里的所有 `PDF p.X` 都会被替换成对应 PNG 的相对路径，
可以直接被任何 Markdown 渲染器（VS Code、Obsidian、GitHub）正常显示。

## 注意事项

1. **版权 / 公开性**：把论文里的图直接嵌到二次创作的总结里，注意目标受众与发布渠道，
   学术笔记自用一般没问题；公开发布（如博客、知乎）请确认目标出版方的图复用政策。
2. **文件大小**：高 DPI 渲染单页可能 1-3 MB，10+ 张图会让 Markdown 文件臃肿。
   本 skill 的脚本提供内置体积控制（无需手动 convert）：
   - `--figure-format webp` / `jpeg`：直接把图存为压缩格式，体积比 PNG 小 30-70%
   - `--figure-quality 1-100`：控制 WebP/JPEG 压缩质量（默认 85）
   - `--max-width N`：等比缩放到 ≤ N px 宽
   - `--max-size-kb N`：超 N KB 自动降级（quality → format → scale）
   - `--thumbnail` + `--thumbnail-width 400`：导出缩略图，Markdown 只引缩略图，
     点击跳原图——适合长博客 / README 列表等"小图预览 + 大图查看"场景
3. **pymupdf 不是默认依赖**：本 skill 的 `google-genai` 流水线不依赖 `pymupdf`，
   需要导出图时按上面 `pip install pymupdf` 自行安装。
