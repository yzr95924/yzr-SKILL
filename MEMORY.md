# MEMORY.md

跨会话需要持久化的"为什么"与边界规则。新条目追加在末尾。

> 本文件是项目级规则的**唯一**真源。Claude 会话级 memory（`~/.claude/projects/.../memory/`）只放指向本文件的指针，不再持有内容副本，避免跟代码仓迁移时失同步。

## 规则

### Python 3.6 兼容

**Why：** 部署目标含 CentOS 7 等老 OS（官方源最高只有 Python 3.6，通过 `python36` / SCL `rh-python36` 提供）。3.6 写出的代码在 3.6+ 全版本都能跑，向上兼容比向下兼容重要。

**How to apply：** 新写 Python 脚本时避开以下特性（按最低引入版本列）：

| 最低版本 | 特性 | 替代写法 |
| --- | --- | --- |
| 3.7+ | `subprocess.run(capture_output=True, text=True)` | `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True` |
| 3.7+ | `from __future__ import annotations` | 直接写完整注解（`Optional[X]` 而非 `X \| None`） |
| 3.7+ | `breakpoint()` | `import pdb; pdb.set_trace()` |
| 3.7+ | `asyncio.run` | `loop.run_until_complete(...)` |
| 3.8+ | walrus `:=` | 拆成两行 |
| 3.8+ | f-string `=`（`f"{x=}"`） | `f"x={x}"` |
| 3.9+ | PEP 585 内建泛型 `list[int]`、`dict[str, X]`、`tuple[X, Y]` | `from typing import List, Dict, Tuple` |
| 3.9+ | `zoneinfo`、`str.removeprefix/removesuffix` | 自行实现或 `s[:-len(x)] if s.endswith(x) else s` |
| 3.10+ | PEP 604 联合类型 `X \| Y`、`X \| None` | `from typing import Union, Optional`；用 `Optional[X]` |
| 3.10+ | `int.bit_count` | `bin(n).count("1")` |
| 3.10+ | `match` 语句 | if/elif 链 |

**静态扫描（写完自查）：**

```bash
grep -nE "(\| None|list\[|dict\[|tuple\[|capture_output|text=True|:=|breakpoint\(\))" path/to/script.py
```

空白命中即视为 3.6 不兼容。

**落地参考：** `yzr-skill-creator/scripts/` 下 8 个脚本（B1 修复时落地的合规示例）—— 含 `from typing import Optional, List, Dict, Tuple` 的导入，以及 `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 的标准调用形式。

### gemini-paper-summary 图片提取 fallback 设计

**Why：** Stage 1 让 Gemini 从 PDF 原内容估算 bbox 是基于语义而非像素的，精度差；caption 定位的旧启发式（"宽+多行正文段落"）在 figure 上方只有 annotation / label 时会退到 page 顶，造成大量上方留白（典型 case：ART-ICDE'13 第 5 页 Figure 6）。Stage 2 必须把页面渲染成 PNG 送给 Gemini 用视觉定位，caption 定位 fallback 也必须分多策略。

**How to apply：**

- Stage 2 坐标用 Gemini 官方归一化 0-1000 (`[ymin, xmin, ymax, xmax]`)；渲染图未做宽高变形时，`x_pt = x_norm * page.rect.width / 1000` 与 dpi_scale 无关
- Stage 2 Gemini 调用加重试（默认 3 次，指数退避 2s/4s）：临时错误 (`429/500/502/503/504`) 重试，永久错误 (`400/401/403/404`) 立即放弃
- caption 定位 fallback 三策略：①正文段落底部（图上方紧跟正文）→ ②annotation 顶部（用 caption 上方同栏所有"非正文"块的最上 y0，覆盖只有 annotation 的 case）→ ③page 顶兜底
- Stage 2 返回的 `is_key_figure=false` 直接过滤（让 Gemini 顺手判断"装饰图"）
- Stage 2 读出的完整 caption 覆盖 Markdown alt 文本中"图 N:"之后的部分，但**保留**"— <role 说明>"后段

**正文：** [`gemini-paper-summary-figure-extraction-edges.md`](gemini-paper-summary-figure-extraction-edges.md)
