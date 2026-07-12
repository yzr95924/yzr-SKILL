---
name: python-min-3-7
description: 仓库脚本最低支持 Python 3.7（2026-07-01 起放弃 CentOS 7 / 3.6 兼容）；附 3.8+ / 3.9+ / 3.10+ 必须避开特性清单与静态扫描自检方法。
metadata:
  type: project
---

# Python 最低 3.7

**Why：** 2026-07-01 起放弃 CentOS 7 / Python 3.6 兼容，最低支持版本提到 3.7，与 `pyproject.toml` 的 `target-version = "py37"` 对齐。历史：曾因部署目标含 CentOS 7（官方源最高只到 Python 3.6，通过 `python36` / SCL `rh-python36` 提供）而保 3.6；现该约束已撤销。

**How to apply：** 新写 Python 脚本最低支持 3.7，避开以下 3.8+ 特性（3.7 不支持）：

| 最低版本 | 特性 | 替代写法 |
| --- | --- | --- |
| 3.8+ | walrus `:=` | 拆成两行 |
| 3.8+ | f-string `=`（`f"{x=}"`） | `f"x={x}"` |
| 3.9+ | PEP 585 内建泛型 `list[int]`、`dict[str, X]`、`tuple[X, Y]` | `from typing import List, Dict, Tuple` |
| 3.9+ | `zoneinfo`、`str.removeprefix/removesuffix` | 自行实现或 `s[:-len(x)] if s.endswith(x) else s` |
| 3.10+ | PEP 604 联合类型 `X \| Y`、`X \| None` | `from typing import Union, Optional`；用 `Optional[X]` |
| 3.10+ | `int.bit_count` | `bin(n).count("1")` |
| 3.10+ | `match` 语句 | if/elif 链 |

3.7 特性（`subprocess.run(capture_output=True, text=True)`、`breakpoint()`、`asyncio.run`、`from __future__ import annotations`）现已可用。但仓库既有脚本沿用 `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 写法（`pyproject.toml` 保留 UP021/UP022 ignore 维持风格一致），新脚本跟随既有风格。

**静态扫描（写完自查）：**

```bash
grep -nE "(\| None|list\[|dict\[|tuple\[|:=)" path/to/script.py
```

命中即视为可能引入 3.8+ 特性，需判断是否回退。

**落地参考：** `yzr-skill-creator/scripts/` 下 8 个脚本——含 `from typing import Optional, List, Dict, Tuple` 的导入，以及 `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 的标准调用形式。

**关联：** [[python-preferred-over-shell]]——本规则是"优先 Python 3"的版本下限。
