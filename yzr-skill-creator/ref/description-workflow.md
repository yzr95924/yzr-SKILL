# `description` 优化的完整流程

> 本文件承载[章节](../SKILL.md#description-优化)的完整流程、触发原理与写作指南

## 命令流程

前置：harness 可发起 subagent（judge 由编排 agent 在会话内并行发起，脚本零 LLM、零子进程）。
harness 无此能力时如实报告"触发评估不可用"，不跑评估，`description` 改动直接交用户裁定，不静默改走 CLI

一段评估（prep → spawn judge → score）：

1. 按[章节](#查询写作指南)写评估集 JSON（留存供轻量复用），与用户过一遍
2. `python3 -m tools.desc_eval prep --skill-path <skill-dir> --eval-set <json> --out-dir <D> [--description-file <候选描述文件>]`
   产出 `D/manifest.json` 与 `D/prompts/run-<k>.txt`（默认 3 run；竞争技能池默认读 `~/.agents/skills`，`--skills-dir` 可覆盖）
3. 一条消息并行 spawn：每 run 一个 judge subagent，prompt 逐字交付对应 prompt 文件内容；
   judge 自行把判定 JSON 数组写进 `D/results/run-<k>.json`
4. `python3 -m tools.desc_eval score --out-dir <D>`：汇总四象限；stdout 即 results JSON（before/after 各自留存供展示）

优化循环（编排 agent 驱动，默认 ≤ 5 轮，全过或无可改进即停）：score 有失败，编排者按失败清单与[章节](#description-优化原则)
起草新 description 存成文件（用户点名要无偏版本时才 spawn 一个 fresh subagent 起草），带 `--description-file` 进下一轮 prep，取最高分那版。
写回：用户确认后 `python3 -m tools.desc_eval apply --skill-path <dir> --description-file <f> --dry-run` 看 diff，
确认后去掉 `--dry-run` 落盘

两条口径：before/after 必须同协议比较（整批 judge 与历史"每查询独立判"的分数不可直接对照，擦边查询在整批下会被判通）；
金丝雀失败 = 判官通道坏了，score 拒绝出数，重跑该 run 而非改描述

## 触发原理

skill 以 `name + description` 出现在 agent 的 available_skills 列表，agent 据描述决定是否查阅。
经验观察：**agent 倾向于只在它自己不容易处理的任务上才查阅 skill**——简单单步请求即使描述完美
匹配也可能不触发（它能用基础工具直接处理）；复杂、多步、专门的请求只要描述对得上就稳定触发。
评估查询因此必须足够实质，让"查阅 skill"成为 agent 眼中的划算选择

## 查询写作指南

生成评估查询，should-trigger 与 should-not-trigger 各半（边界用例可微调），存为 JSON：

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

查询必须真实可信、足够实质性：具体、细节丰富、有背景（文件路径、个人上下文、列名和值、公司名、
URL、一点背景故事；大小写混杂 / 缩写 / 口误 / 口语皆可）。"读文件 X"式一句话查询不会让 agent 想
查阅 skill，是无效测试用例

不好的例子：`"Format this data"`、`"Extract text from PDF"`
好的例子：`"ok 我老板刚发了这个 xlsx 文件（在我的 downloads 里，大概叫 'Q4 sales final FINAL v2.xlsx'），她想让我加一列显示利润率百分比。营收在 C 列，成本好像在 D 列"`

- **should-trigger（8–10 条）**：同一意图的不同说法（正式 / 口语），用户没显式说出 skill 名字或
  文件类型但明显需要它的场景，不常见用例，以及本 skill 与另一个 skill 竞争但应当胜出的场景
- **should-not-trigger（8–10 条）**：最有价值的是擦边但不该触发的：共享关键词或概念但需求不同的
  查询；相邻领域、措辞歧义大的场景；触及 skill 能力某方面但用别的工具更合适的场景。避免明显无关
  的负样本（"写个 fibonacci 函数"作为 PDF skill 的负样本什么都没测到）

## description 优化原则

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
- **不写工作流摘要**：只列"用户意图类别 + 关键能力 + 触发场景"，不写"先做 X、再做 Y"式步骤序列。
  步骤属 SKILL.md 正文，写进 description 会让 agent 走捷径跳读正文、丢失"为什么"与例外处理。
  **界限**：列能力清单 / 入口列表允许；按顺序串讲成步骤禁止
- **防触发不足（写"主动"而非"被动"）**：agent 普遍有**少触发**倾向，写完"这 skill 干什么"后
  补一段**主动触发声明**：把相关表述、具体场景、甚至"用户没显式提 skill 名但明显需要它"的情形都
  列进去，用"只要用户提到 X / 想 Y / 需要 Z，即使没明说，也务必使用本 skill"句式收口。改写示例：
  被动句 "如何构建一个简单快速的面板来展示内部数据"，改写为 "如何构建简单快速的面板来展示内部数据。
  **只要用户提到 dashboard / 数据可视化 / 内部指标，或想展示任何公司数据，即使没明说'面板'，也
  务必使用本 skill**"
- **迭代策略**：同一思路连续失败就换句式 / 换措辞，别钻牛角尖
