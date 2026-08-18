---
name: my-skill-name
description: |
  当用户<场景>时使用本 skill——<干什么 + 关键能力>（长度上限见
  scripts/utils.py::DESCRIPTION_MAX_CHARS）。
  触发：<"用户原话" / 场景描述，主动句式；把没显式提 skill 名但显然需要的
  情形也列进去，防 agent 少触发>
  不适用：<负例>
  完整原则见 references/skill-writing-principles.md「description 优化原则」。
metadata:
  author: 你的名字
  modify time: YYYY-MM-DD
---

# my-skill-name

一句话总述：这个 skill 让 agent 能干什么、产出什么。

## 何时不使用

<"何时使用"全部在 frontmatter description——正文不重抄（重抄 = 口径漂移 + description
优化后悄悄过期）。本节只列擦边负例（与本 skill 共享关键词 / 概念、但需求不同、
关键词匹配会误触发的场景）。跨 skill 去向不写——agent 扫 description 网络或问用户
自行路由>

## 输入 / 输出

| 方向 | 内容 |
| --- | --- |
| 输入 | <用户给什么 / agent 需要什么前置> |
| 输出 | <skill 交付什么：文件 / 结论 / 行为变化> |

## 执行原则 / 边界

<贯穿全程的判断基线：不单独属于某一步的规则、红线、以及"为什么"。视角 / 立场
一两句话能讲清 = 写成一条 bullet（立场 + 为什么）；需要成段展开（review / 评审类）
= 在本节后立一个领域节（如「评审立场」），判据见
references/skill-template-guide.md「变体」。参考资料型 skill 可省略本节>

## 工作流 / 步骤

<按顺序的操作步骤。多入口 skill 可在「何时不使用」之前加一个路由节（如
「四个入口」，判据见 references/skill-template-guide.md「变体」）。单步超过下放阈值
（见 references/skill-writing-principles.md「正文超长根因诊断」）= 下放到
references/xxx-workflow.md，正文留路标>

## 参考样例

<1–2 个真实用户输入 → 本 skill 介入路径的映射。与 description 的"常见触发"分工：
description 放触发短句（决定何时调），此处放介入路径 walkthrough（决定怎么干）。可省略>

## 参考文件

<有 references/ / scripts/ / assets/ 时列出并说明何时去读；没有则整节删除>
