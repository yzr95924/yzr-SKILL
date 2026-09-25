---
name: no-code-detail-in-skill-md
description: skill 分发面（SKILL.md/ref/assets/eval）的 md 禁止出现代码实现细节指针（常量名/函数名/*.py::符号）；标准指 md 产物，数值以工具输出为准；仓库维护文档（AGENTS.md/MEMORY）豁免。
metadata:
  type: feedback
  scope: 分发面 md（yzr-*/SKILL.md、yzr-*/ref/、yzr-*/assets/、yzr-*/eval/）
---

# SKILL 的 md 不写代码实现细节

- 规则：凡随 skill 分发的文本（`SKILL.md`、`ref/`、`assets/`、`eval/`），标准与判据只能指向 **md 产物或工具可见
  输出**，不得写 `*.py::符号`、常量名（如 `CANONICAL_BODY_SECTIONS`、`DESCRIPTION_MAX_CHARS`）、函数名。
  节名 / 顺序标准 → `assets/skill-template.md`；数值阈值 → 不抄，写"以 verify 输出为准"（verify 的状态词如
  `TEMPLATE-SECTION-DRIFT` 是 agent 可观察行为，可引用）；脚本消息文本也算分发面，同样别指挥 agent 去读
  Python 常量。
- 为什么：双读者分离——md 给执行 agent 读，代码清单只给 checker 用。把代码符号当标准写进散文 = "agent 要执行先读代码"的耦合，且代码改名 / 挪动时无声断裂。
- 豁免：仓库维护文档（`AGENTS.md`、`MEMORY/`、`README`）可指代码符号——它们不随 skill 分发，受众是本仓维护 agent，指针正是其价值（"改哪、别重复造解析器"）。
- 检查器与模板的一致性由 verify 自动查漂移，散文无需宣告"机器清单在哪"。

## 关键证据

2026-09 对 yzr-skill-creator 的全量审计 + 修复中，我两次把代码符号写回 md（节名 SSOT 括号注、折算口径
指针），均被用户纠正后清除；清除后 `rg '\.py::' yzr-*/ -g '*.md' -g '*.json'` 除豁免面外归零。
