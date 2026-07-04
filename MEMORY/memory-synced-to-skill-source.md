---
name: memory-synced-to-skill-source
description: 本代码仓是 SKILL 的代码仓；影响 SKILL 最终输出的"为什么 / 边界"记忆必须同步到对应 SKILL 文件（SKILL.md / scripts / assets / references），不只放 MEMORY。
metadata:
  type: project
---

# 影响 SKILL 输出的记忆必须同步到 SKILL 源

**Why:** 本仓库是 SKILL 的代码仓（AGENTS.md / CLAUDE.md 顶层定义）。MEMORY/ 里记的是"为什么 +
边界规则"，但**光放 MEMORY 不够**——SKILL.md 是 agent 触发 SKILL 时实际加载的
上下文（description + 正文），如果 MEMORY 里的设计决策**没有**在 SKILL.md / scripts /
assets / references 里**显式落地**，下次触发 SKILL 时这个决策就丢了。

典型反面例子：MEMORY/gemini-paper-summary-figure-extraction-edges.md §8 v3.2 写了
"image alt = 中文翻译+总结、不要独立 caption 行"的设计决策，但 SKILL.md §核心原则 #5
和 `assets/prompt-template.md` 都还停留在 v3.1（独立 `**图 N**: <caption>` 行）——结果
脚本实际跑出来是 v3.1 格式，v3.2 决策等于没生效。

**How to apply:**

- 写任何影响 SKILL **最终输出 / 行为** 的 MEMORY 时，**同步**做两件事：
  1. **改 SKILL.md 对应小节**（让 Skill 加载时看到新规则）
  2. **改 assets / scripts / references**（让脚本实际跑出新行为）
- 只放 MEMORY 不动 SKILL 文件 = 设计决策停留在文档层，下次触发不会被采纳
- 反过来：只改 SKILL 文件不留 MEMORY = 后续开发者 / agent 不知道为什么这么改，容易
  误改回旧版

**判定标准**（记忆是否要同步到 SKILL）：

- 影响 SKILL **输出格式 / 行为 / 边界**（如 v3.2 caption 规则）→ 必须同步
- 记录 SKILL 内部的 `为什么` + 维护决策 → 必须同步到 SKILL.md 注释或 references/
- 只是工作日志 / 当前任务状态 / 与 SKILL 无关的事实 → 留 MEMORY 即可

**反模式**：

- "我先把想法记到 MEMORY，下次有空再改 SKILL"——中间窗口期 SKILL 行为已与决策不一致
- 以为"description 触发就够了"——description 只决定**是否触发**，正文才决定**怎么跑**
- MEMORY 和 SKILL 内容冲突时**以 SKILL 为准**还是以 MEMORY 为准？→ **以更新日期晚的为准**；
  改的一方必须主动通知对方（改 SKILL 的要把"为什么"补到 MEMORY；改 MEMORY 的要同步 SKILL）

**关联：** [[skill-source-vs-runtime-vendor]]——SKILL 文件本身有两份（源 vs vendor），
两边都要保持一致。
