---
name: python-preferred-over-shell
description: 新脚本首选 Python 3 而非 bash / shell（统一脚本语言 + Python 生态管理）；仅一行管道 / awk / sed / grep 等 shell 天然更自然的场景用 shell。
metadata:
  type: project
---

# 后续脚本优先 Python 3 而非 shell

**Why：** 在 2026-06-20 反馈中明确——后续脚本优先用 Python 3 而非 bash / shell 实现。理由：脚本语言统一用 Python 3 便于在 Python 生态内统一管理（包管理、`subprocess`、`pathlib` 等），不被 bash 平台差异 / shell 解析边界问题分神。

**How to apply：**

- **首选 Python 3** 写新脚本，不再新写 bash / shell 脚本。唯一例外是 shell 天然更自然的场景：一行管道、纯文本流处理、`awk` / `sed` / `grep` 一句话即可
- **Python 3 内部**最低支持 3.7，版本边界与避开特性清单见 [[python-min-3-7]]
- **已有的 bash 脚本**不强制回溯改写，但新增脚本按本规则判断。`scripts/install-dev-deps.sh` 在 2026-06-20 已重写为 `install-dev-deps.py`，是这次转写的第一个落地例子
- **类型注解**完整写（`Optional[X]` / `List[X]` / `Tuple[X, ...]` / `Dict[X, Y]`），不省略

**关联：** [[python-min-3-7]]——本规则的版本下限与避开特性清单。
