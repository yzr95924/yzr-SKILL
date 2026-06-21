---
name: prompt-length-unit-character
description: 论文总结字数限制用"字符"单单位，不用"词"或"中文字符"——避免单位和近似换算带来的歧义。
metadata:
  type: project
---

# 论文总结字数限制：单单位 = 字符

**Why：** "1000 词 ≈ 500 中文字符" 这种双单位 + 近似换算的写法有歧义——
- "词" 是英文单位（5-7 字符 / 词），中文没有"词"的概念
- "中文字符" 只算汉字，markdown 里的英文术语、标点、空格、emoji 不算
- "≈ 500" 是 heuristic，混排时（中文叙述 + ART / B+-tree / HyPer 等英文术语）无法精确换算

实测 2026-06-21：把"1000 词 ≈ 500 中文字符"换成"≤ 1000 字符（含中英文 / 空格 / 标点）"后，Gemini 输出从 2772 字符降到 1311 字符，明显更尊重约束——因为 "1000 字符" 在 token / char 层面是 Gemini 容易直接理解的目标，"1000 词" 模糊到 model 经常忽略。

**How to apply：**

- 论文总结的字数限制**只用**一个单位 = **字符**（character），含中文、英文、空格、标点
- 提示词（`assets/prompt-template.md`）声明：`总字符数 ≤ 1000`（或当前目标值）
- 不要再写"1000 词"、"500 中文字符"或换算近似——单一单位是用户和工具的**唯一公分母**：
  - Python `len(text)` = 字符数
  - Markdown linter 行宽限制 = 字符数
  - outline 编辑器字数统计 = 字符数
  - 用户直观感觉"页数 / 篇幅" ≈ 字符数
- SKILL.md / MEMORY.md / 故障排查表**都不要再写具体数值**——只指向 `assets/prompt-template.md` 单一来源；详见 [[memory-synced-to-skill-source]]
- 改字数目标时，**只改 `prompt-template.md` 的两处**（头部声明 + §基础要求 #4），SKILL.md 自动跟随
- **关联：** [[skill-source-vs-runtime-vendor]]（SSOT 思维延伸：每个"被多处引用的事实"应该有单一源）
