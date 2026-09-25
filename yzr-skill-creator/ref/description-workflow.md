# `description` 优化的完整流程

> 本文件承载[章节](../SKILL.md#description-优化)的完整流程、触发原理与写作指南

## 命令流程

前置：本机 `opencode run` 可用且已配置 provider（judge / improve 都走它）；模型、竞争池等参数的默认值与覆盖方式以 `--help` 为准

按[章节](#查询写作指南)写评估集 JSON（留存供轻量复用），与用户过一遍；
`python3 -m tools.optimize_description --skill-path <skill-dir> --eval-set <json>` 跑优化循环（stdout 即 results JSON，
留存供写回）；展示 before/after 分数，用户确认后写回：同命令加 `--apply <results.json> --dry-run` 看 diff，
确认后去掉 `--dry-run` 落盘

轻量修改（如顺一句措辞）复用上轮 `--eval-set` 只跑前后对比，不必跑完整优化循环，但无回归才写回（授权闸门见[章节](../SKILL.md#description-优化)）

## skill 触发的原理（写评估查询前先读）

skill 以 `name + description` 形式出现在 agent 的 `available_skills` 列表中，
agent 根据描述决定是否查阅该 skill。**经验观察：agent 倾向于只在它自己不容易处理的任务上才查阅 skill**：

- 简单、单步的请求（如"读这份 PDF"），即使描述完美匹配，agent 也可能不触发 skill，
  它能用基础工具直接处理，不必绕道查阅
- 复杂、多步、或专门的请求，只要描述对得上，通常会稳定触发 skill

因此评估查询要足够实质性，agent 才真正会想查阅 skill；"读文件 X" 式一句话查询，不管
描述写得多好都不会触发，是无效测试用例

## 查询写作指南

生成评估查询，should-trigger 与 should-not-trigger 各半（边界用例可微调），存为 JSON：

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

查询必须真实可信，看起来是用户实际会输入的内容：具体、细节丰富、有充分背景
（文件路径、个人上下文、列名和值、公司名、URL、一点背景故事；大小写混杂 / 缩写 /
口误 / 口语皆可）。不要抽象请求

不好的例子：`"Format this data"`、`"Extract text from PDF"`、`"Create a chart"`
好的例子：`"ok 我老板刚发了这个 xlsx 文件（在我的 downloads 里，大概叫 'Q4 sales final FINAL v2.xlsx'），她想让我加一列显示利润率百分比。营收在 C 列，成本好像在 D 列"`

**should-trigger 查询（8–10 条）**：考虑覆盖度：同一意图的不同说法（正式 / 口语），
用户没显式说出 skill 名字或文件类型但明显需要它的场景，不常见用例，以及本 skill 与
另一个 skill 竞争但应当胜出的场景

**should-not-trigger 查询（8–10 条）**：最有价值的是擦边但不该触发的：共享关键词或
概念、但需求不同的查询；相邻领域、措辞歧义大的场景（字面关键词匹配会触发但实际不该）；
触及 skill 能力某方面、但用别的工具更合适的场景。**关键要避免**明显无关的负样本
（"写个 fibonacci 函数"作为 PDF skill 的负样本太容易，什么都没测到），负样本要真正
有迷惑性

## description 优化原则

> 本节由 `tools/optimize_description.py` 按标题抽取，标题不得改；改名需同步改脚本
> 的标题匹配

写 / 改 skill 的 description（触发描述）时遵循：

- **固定格式（三组件硬性约定）**：description 只负责路由（agent 读它决定是否加载正文），三组件 +
  顺序 + 标记固定，槽内措辞自由：①**场景一句**（"当用户……时使用本 skill" + 干什么 + 关键能力）；
  ②**触发：** 用户原话 / 场景描述（主动句式；防触发不足的触发声明落此槽；保留英文原话，标记
  用中文）；③**不适用：** 负例
- **写法基线**：祈使语气（"Use this skill for…" 而非 "this skill does…"）；聚焦用户意图而非实现
  细节；有辨识度：和别的 skill 争夺 agent 注意力，写得独特、一眼能认出来
- **长度**：软目标约 100–200 词（写法基线，无机械校验）；硬上限是字符数，verify 拒收超限并要求重写，
  留足余量（数值口径归脚本，本文不抄）
- **别过拟合到具体查询**：从失败里归纳更宽泛的"用户意图类别 / 适用场景"，不逐条列失败用例。
  description 被注入到**所有**查询里且 skill 可能很多，别在单个 description 上占太多篇幅
- **agent 中立（默认不与具体 agent 强绑定）**：不点名具体 agent，用泛指（"AI coding agent"），
  点名缩窄触发面、降低寿命。**例外**：针对某 agent 的**特有机制**设计时（如 Qoder 的
  `.qoder/rules/` type 系统、Claude Code 的 hooks / `@import` 递归展开），点名是准确而非违规，
  但正文要讲清"为什么必须点名"
- **不写工作流摘要**：只列"用户意图类别 + 关键能力 + 触发场景"，不写"先做 X、再做 Y"式步骤序列。
  步骤属 SKILL.md 正文，写进 description 会让 agent 走捷径跳读正文、丢失"为什么"与例外处理。
  **界限**：列能力清单 / 入口列表允许；按顺序串讲成步骤禁止
- **防触发不足（写"主动"而非"被动"）**：agent 普遍有**少触发**倾向，写完"这 skill 干什么"后
  补一段**主动触发声明**：把相关表述、具体场景、甚至"用户没显式提 skill 名但明显需要它"的情形都
  列进去，用"只要用户提到 X / 想 Y / 需要 Z，即使没明说，也务必使用本 skill"句式收口。改写示例：
  被动句 "如何构建一个简单快速的面板来展示内部数据"，改写为 "如何构建简单快速的面板来展示内部数据。
  **只要用户提到 dashboard / 数据可视化 / 内部指标，或想展示任何公司数据，即使没明说'面板'，也
  务必使用本 skill**"
- **迭代策略**：同一思路连续失败就换句式 / 换措辞，别钻牛角尖；多轮迭代里换不同风格尝试，最终
  只取最高分那版
