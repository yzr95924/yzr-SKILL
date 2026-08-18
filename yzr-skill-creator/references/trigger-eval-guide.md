# 描述优化的评估查询指南

> 本文件承载「描述优化」独立入口第 1–2 步的机械细节与写作指南：触发原理、查询写作、
> 审阅流程。SKILL.md 主文件只留指针，避免把写作指南抬进正文。

## skill 触发的原理（写评估查询前先读）

skill 以 `name + description` 形式出现在 agent 的 `available_skills` 列表中，
agent 根据描述决定是否查阅该 skill。**agent 只在它自己不容易处理的任务上才查阅 skill**：

- 简单、单步的请求（如"读这份 PDF"），即使描述完美匹配，agent 也可能不触发 skill——
  它能用基础工具直接处理，不必绕道查阅
- 复杂、多步、或专门的请求，只要描述对得上，会稳定触发 skill

→ 评估查询要足够实质性（"老板刚发了这个 xlsx..."式、有文件名 / 列名 / 背景细节），
agent 才真正会想查阅 skill。"读文件 X" 这种一句话查询，不管描述写得多好，都是糟糕的
测试用例——怎么写都不会触发。

## 查询写作指南

生成约 20 条评估查询，should-trigger 与 should-not-trigger 各半（边界用例可微调），存为 JSON：

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

查询必须真实可信，看起来是用户实际会输入的内容：具体、细节丰富、有充分背景
（文件路径、个人上下文、列名和值、公司名、URL、一点背景故事；大小写混杂 / 缩写 /
口误 / 口语皆可）。不要抽象请求。

不好的例子：`"Format this data"`、`"Extract text from PDF"`、`"Create a chart"`
好的例子：`"ok 我老板刚发了这个 xlsx 文件（在我的 downloads 里，大概叫 'Q4 sales final FINAL v2.xlsx'），她想让我加一列显示利润率百分比。营收在 C 列，成本好像在 D 列"`

**should-trigger 查询（8–10 条）**：考虑覆盖度——同一意图的不同说法（正式 / 口语），
用户没显式说出 skill 名字或文件类型但明显需要它的场景，不常见用例，以及本 skill 与
另一个 skill 竞争但应当胜出的场景。

**should-not-trigger 查询（8–10 条）**：最有价值的是擦边但不该触发的——共享关键词或
概念、但需求不同的查询；相邻领域、措辞歧义大的场景（naive 关键词匹配会触发但实际不该）；
触及 skill 能力某方面、但用别的工具更合适的场景。**关键要避免**明显无关的负样本
（"写个 fibonacci 函数"作为 PDF skill 的负样本太容易，什么都没测到）——负样本要真正
有迷惑性。

## 第 2 步：与用户过一遍

把评估集呈现给用户审阅：在对话里列出全部查询（should-trigger / should-not-trigger
分组），请用户确认或提出增删改。用户确认后把评估集存为 JSON（结构见上节），进入
第 3 步。

## 何时去读本文件

执行「描述优化」独立入口第 1–2 步时 `Read`。
