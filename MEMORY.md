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
