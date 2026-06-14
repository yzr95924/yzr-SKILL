---
name: yzr-yzr-skill-creator
description: |
  what it does:
    主要用于从头创建新的 skill，修改优化当前已存在的 skills，评估 skill 的性能
  when to use:
    创建 skill、编辑或优化现有 skills、运行评估来测试 skill
    对 skill 能进行基准测试，优化 skill 描述以获得更好的触发准确率
  key capabilities：生成 skill，优化 skill 描述
metadata:
  author: Zuoru YANG
  modify time: 2026-06-14
---

# yzr skill creator

这是一个用于创建新 skill，并对其进行迭代改进的 skill

从整体的角度，创建一个 skill 的主要流程如下：
1. 明确你希望这个 skill 做什么,以及大致如何实现
2. 起草一份 skill
3. 设计几个测试 prompt，让能访问该 skill 的 agent 在这些 prompt 上跑一遍
4. 协助用户对结果进行定性和定量两方面的评估
  - 在后台运行评估的同时，如果没有现成的定量评估，就先起草一份（如果已有，可以直接使用，在觉得需要调整时可以进行修改）
  - 然后向用户解释这些评估（如果已经存在，就直接解释现有的）
  - 使用 `scripts/generate_review.py` 脚本向用户展示结果，供其查看，同时让用户查看定量指标
5. 根据用户对结果的反馈（以及定量基准中暴露出的明显缺陷）改写 skill
6. 重复上述过程，直到满意为止

当你使用本 skill 时，你的任务是判断用户当前处于上述流程的哪个阶段，然后介入，帮助他们推进
比如，用户可能会说“我想做一个关于 X 的 skill”，这时你可以帮助其澄清需求、起草初稿、编写测试用例、设计评估方式、运行所有 prompt，然后反复迭代
另一方面，如果用户已经有了一份 skill 草稿，你就可以直接进入评估/迭代
保持灵活，如果用户表示 “我不需要跑一堆评估，直接跟我一起头脑风暴就行”，你完全可以照做

待 skill 完成之后，你还可以运行 skill 描述优化器，一个专门用于优化 skill 的触发准确性脚本

## 与用户沟通
skill 创建器的使用者编程背景差异很大，所以请注意根据上下文线索来调整措辞
如果你拿不准，简短解释一下术语是 OK 的
不确定用户是否能理解时，可以用一句简短定义来澄清


## 创建一个 skill

### 意图识别
先理解用户的意图
当前的对话中可能已经包含用户希望捕获的工作流（比如用户说把这段流程沉淀成一个 skill）
如果是这样，先从对话历史中抽取答案：用到了哪些工具、步骤顺序、用户做了哪些修正、观察到的输入/输出格式

用户可能需要补全缺口，在进入下一步之前应当先确认：
1. 这个 skill 应该让 agent 能做什么？
2. 应该在什么时机触发？（什么样的用户表述/上下文）
3. 期望的输出格式是什么？
4. 是否需要设置测试用例来验证 skill 是否可用？
5. 对于可以客观验证输出的 skill（文件转换、数据抽取、代码生成、固定工作流步骤），测试用例是有益的

### 访谈与调研
主动询问边界情况、输入/输出格式、示例文件、成功标准、依赖项等问题；在这些问题没有梳理清楚之前，先不要写测试 prompt
检查可用的 MCP，如果对调研有帮助（搜索文档、查找类似 skill、查阅最佳实践），且支持子 agent，就并行调研，否则直接内联进行
带着充分的上下文来,减少用户的负担

### Write the SKILL.md
基于用户访谈的结果,填充以下组件
YAML frontmatter 的字段描述：要求精简，明确，不要过于冗长，也不要过于模糊，总长度控制 250 词以内
1. `name`：skill 的名字
2. `description`: skill 简介的功能说明，主要解释
  - 一句话说清楚这个 skill 是干什么的？
  - 什么场景下使用这个 skill？要写明在哪些具体场景下使用，所有“何时使用”的信息都放在这里，而不是正文里；请把 skill 描述写得"主动一些"
  - 关键的能力
3. `allowed-tools`：限制使用的工具，可选字段，如果没有，则置空
4. `metadata`：用户自定义字段，当前主要是作者（Zuoru YANG）、最后修改时间、skill 分类标签等信息

后面为 skill 的正文

### skill writing guide

#### skill 的主要目录框架
```
skill-name/
├── SKILL.md（必选，YAML frontmatter + Markdown 的文档）
│   ├── YAML frontmatter (name、description 必需)
│   └── Markdown 说明正文
└── 捆绑资源（可选）
    ├── scripts/    - 用于确定性/重复性任务的可执行的脚本（Python, Bash, etc）
    ├── references/ - 按需加载到上下文中的文档
    └── assets/     - 用于输出的文件（模板、图标、字体）
    └── eval/       - 用于对当前 skill 的评估
```
需要考虑优化 `SKILL.md` 的大小：保持 `SKILL.md` 在 5,000 词以内，将详细文档移至 `references` 目录；通过链接引用外部文档，而非内联


#### progressive disclosure

skill 使用三级加载体系:
1. 元数据（name + description）：始终在上下文中
2. SKILL.md 正文：skill 触发时进入上下文（理想情况下 < 5000 词）
3. 捆绑资源：按需加载（无限制,脚本可以不加载直接执行）
以上词数为大致参考,必要时可以超长

**关键模式**:
- SKILL.md 控制在 5000 词以内；如果接近这个上限，就增加一层引用，并给出清晰的指引，告诉使用本 skill 的模型下一步应该去哪里
- 从 SKILL.md 中清晰引用其他文件，并说明何时去读
- 对于大型 reference 文件(> 300 行)，需要包含目录

**领域组织**：当一个 skill 支持多个领域/框架时,按变体组织：
```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

#### 写作模式
SKILL 描述大多以中文为主，关键名词流程可以用英文辅助；说明性文字优先使用祈使语气

**定义输出格式**：
```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

**示例模式**：加入示例很有用，可以这样排版（但如果示例中要标注Input和Output,你可能想稍作变体）
```markdown
## Commit message format
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

**重点内容**：
1. `何时使用 / 不使用`：定义清楚 agent 使用的场景和不使用的场景
2. `输入 / 输出`：定义 skill 具体的输入输出形式
3. `执行原则 / 边界`：定义 skill 具体的执行原则和边界
4. `工作流 / 步骤`：定义这个 skill 要按照什么样的步骤执行
5. `参考样例`：可以提供一些例子指导 agent

### writing style
尽量向模型解释“为什么这件事重要”，而不是堆砌生硬的 MUST
运用心理揣摩，让 skill 尽量通用，而不是过度绑定到具体例子；先写一份草稿，再用新的眼光审视并改进

### test case
写完 skill 草稿后，设计 2–3 个真实的测试 prompt，也就是真实用户实际会说的话
跟用户确认：这是我准备跑的几个测试用例，你看这样 OK 吗？要不要再补几个？然后跑起来

测试用例存到 `evals/evals.json`。先不写断言,只写 prompt,等下一步再起草断言。

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

## 运行与评估测试用例
TODO: 当前优先级较低，后面再考虑

## 改进 skill

这是整个循环的核心
跑过测试用例、用户评审过结果，现在需要根据反馈让 skill 变得更好

### 改进的思考方式

1. **从反馈中归纳泛化**：
我们试图创建可以被调用一百万次的 skill，在各种不同 prompt 上都能工作
这里你和用户反反复复迭代的只是少数例子,用户对这些例子烂熟于心，评估新输出对他们来说很快
但你和用户共同开发的 skill 如果只能在这几个例子上工作，那就毫无价值
与其做细碎的、过拟合的修改，或者堆砌压迫性的 MUST，面对一个顽固的问题，你不妨尝试换一种隐喻，或者推荐不同的工作模式
试试看成本相对较低，也许会有惊喜

2. **保持 prompt 精简**：
把那些不发挥作用的内容删掉
一定要读 transcript,而不只是看最终输出
如果发现 skill 让模型浪费了大量时间做无效工作
你可以尝试去掉导致这种行为的内容，然后观察结果

3. **解释为什么**：
尽全力解释你让模型做的每件事背后的**原因**
现在的 LLM 都很聪明，它们有不错的心理揣摩能力，如果给它们一个好的脚手架，它们能超越死板指令，真正把事情做成
即使用户的反馈很短或带情绪，也要真的去理解任务、用户为什么写这段话、他们实际写了什么，然后把这些理解传递到指令里
如果你发现自己写了全大写的 ALWAYS 或 NEVER，或者用了非常僵化的结构，那就是黄灯
如果可能，重新组织措辞并解释原因，让模型理解为什么这件事重要，这是一种更人性化、更有力、更有效的方式

4. **寻找跨测试用例的重复工作**：
阅读测试运行的 transcript，注意子 agent 是否各自独立地写了类似的辅助脚本，或者用了相同的多步方法
如果 3 个测试用例都让子 agent 写了 `create_docx.py` 或 `build_chart.py`，那就是一个很强的信号：这个 skill 应该捆绑那个脚本
写一次,放进 `scripts/`，让 skill 去用，这样以后每次调用就都不用重复造轮子

### 迭代循环

完成改进后:
1. 把改进应用到 skill
2. 重新跑所有测试用例，输出到新的 `iteration-<N+1>/` 目录
**包括** 使用 baseline 的结果；如果是创建新 skill，baseline 始终是 `without_skill`，这在迭代间保持不变
如果是改进现有 skill，baseline 取舍靠你判断：用用户最初拿来的版本，还是上一轮迭代？
3. 用 `--previous-workspace` 指向上一轮来启动 reviewer
4. 等用户评审完，告诉你他们完成了
5. 读新反馈，继续改进，循环

满足以下任一条件即可停止:
- 用户表示满意
- 反馈全部为空（一切都没问题）
- 已经看不到有意义的进展

## 描述优化

SKILL.md frontmatter 中的 `description` 字段是决定 agent 是否调用该 skill 的主要机制
创建或改进完 skill 之后,可以提供优化描述以提升触发准确率的服务

### 第 1 步:生成触发评估查询

生成 20 条评估查询：should-trigger 与 should-not-trigger 混合
存为 JSON:
```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

查询必须真实可信，看起来是用户实际会输入的内容，不要抽象的请求，而要具体、细节丰富、有充分背景的请求
不好的例子:`"Format this data"`、`"Extract text from PDF"`、`"Create a chart"`
好的例子:`"ok 我老板刚发了这个 xlsx 文件(在我的 downloads 里,大概叫 'Q4 sales final FINAL v2.xlsx'),她想让我加一列显示利润率百分比。营收在 C 列,成本好像在 D 列"`

**should-trigger 查询(8–10 条)**：
考虑覆盖度
你需要同一意图的不同说法，有些正式，有些口语化
要包含那些用户没有显式说出 skill 名字或文件类型、但明显需要它的场景
再加一些不常见用例,以及那些本 skill 与另一个 skill 竞争但应当胜出的场景

**should-not-trigger 查询(8–10 条)**：
最有价值的是擦边但不该触发的跟 skill 共享关键词或概念、但其实需要别的东西的查询
考虑相邻领域、措辞歧义大的场景（naive 的关键词匹配会触发但实际不该）
以及触及 skill 能力的某些方面、但用别的工具更合适的场景

关键要避免：不要让 should-not-trigger 查询明显无关
比如用写个 fibonacci 函数作为 PDF skill 的负样本太容易了；它什么也没测到，负样本应该是真正有迷惑性的

### 第 2 步:与用户过一遍

用 HTML 模板把评估集呈现给用户审阅:
1. 读取 `assets/eval_review.html` 模板
2. 替换占位符:
   - `__EVAL_DATA_PLACEHOLDER__` → 评估项的 JSON 数组（**不要**加引号包起来,这是 JS 变量赋值）
   - `__SKILL_NAME_PLACEHOLDER__` → skill 的名字
   - `__SKILL_DESCRIPTION_PLACEHOLDER__` → skill 当前的描述
3. 写入一个临时文件（例如 `/tmp/eval_review_<skill-name>.html`）并打开:`open /tmp/eval_review_<skill-name>.html`
4. 用户可以编辑查询、切换 should-trigger、增删条目，然后点"Export Eval Set"
5. 文件会下载到 `~/Downloads/eval_set.json`；由于可能存在多个版本（例如 `eval_set (1).json`），下载文件夹里检查最新的那一份
这一步很重要，评估查询质量差，描述优化效果就差

### 第 3 步:运行优化循环

告诉用户：这一步会花一些时间，我会在后台跑优化循环，并定期检查进度
把评估集存到 workspace，然后后台运行:
```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

使用你系统 prompt 中的模型 ID，保证触发测试与用户实际体验一致
跑的过程中，定期 tail 输出，告知用户当前在第几轮、分数长什么样
这个脚本会自动跑完整个优化循环：把评估集拆成 60% 训练 / 40% 保留测试

### skill 触发的原理

理解触发机制有助于设计更好的评估查询
skill 以 `name + description` 形式出现在 agent 的 `available_skills` 列表中
agent 根据描述决定是否查阅该 skill，需要知道的一点是：agent 只在它自己不容易处理的任务上才去查阅 skill
像读这份 PDF 这种简单、单步的请求，即使描述完美匹配，agent 也可能不会触发 skill，因为它能用基础工具直接处理
复杂的、多步的、或者专门的请求，只要描述对得上，会稳定地触发 skill

这意味着评估查询要足够实质性，agent 才真正会想去查阅 skill
像读文件 X 这样的简单查询，不管描述写得多好，都是糟糕的测试用例，怎么写都不会触发。

### 第 4 步:应用结果

从 JSON 输出中取 `best_description`，更新到 skill 的 SKILL.md frontmatter
向用户展示 before/after，并汇报分数

## 参考文件

`references/agents/` 目录包含专用子 agent 的指令。需要启动相关子 agent 时读取。
- `references/agents/grader.md` —— 如何对照输出评估断言
- `references/agents/comparator.md` —— 如何对两份输出做盲测 A/B
- `references/agents/analyzer.md` —— 如何分析为什么某个版本胜出

`references/` 补充文档:
- `references/schemas.md` —— evals.json、grading.json 等的 JSON 结构


最后再强调一遍核心循环,务必记住:
- 明确这个 skill 是关于什么的
- 起草或编辑 skill
- 让能访问该 skill 的 agent 在测试 prompt 上跑一遍
- 与用户一起评估输出:
  - 创建 benchmark.json，并跑 `eval-viewer/generate_review.py` 让人类评审测试用例
  - 跑定量评估
- 反复迭代，直到你和用户都满意
- 打包最终 skill 并交付给用户