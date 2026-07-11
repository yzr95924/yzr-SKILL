---
name: yzr-skill-creator
description: |
  Use this skill when the user wants to 把流程沉淀成 skill、改进 / 评估现有 skill
  （with-skill vs baseline 迭代）、独立优化某 skill 的触发 description、或独立
  审计某 skill 是否符合写作原则。触发信号："帮我做一个关于 X 的 skill" /
  "改进 / 评估 XX skill" / "帮我优化 XX 的描述，让它该触发时触发" /
  "帮我检查 XX skill 写得规不规范"。
metadata:
  author: Zuoru YANG
  modify time: 2026-07-12
---
# yzr skill creator

这是一个用于创建、改进 skill、独立优化 skill 触发描述，并能校验 skill 写作原则符合度的 skill

## 四个入口

用户进入本 skill 通常属于以下四种之一。先判断用户属于哪一种，再介入：

1. **创建新 skill** —— 从零做一个 skill（“帮我做一个关于 X 的 skill” / “把这段流程沉淀成 skill”）
2. **改进现有 skill** —— 已有一个 skill，想评估 + 迭代优化它（“改进 yzr-outline-wiki-upload 这个 skill”）
3. **优化某个 skill 的描述（独立入口）** —— 只想优化某个已有 skill 的 description / 触发准确率，不动 skill 正文（“帮我优化 XX 的描述，让它该触发时触发”）。**这是独立入口，不需要先创建或改进那个 skill**；脚本 `run_loop.py` / `improve_description.py` 原生支持指向任意 skill 目录，详见文末「描述优化（独立入口）」一节
4. **校验某个 skill 的写作原则（独立入口）** —— 不动手改，拿写作原则当 checklist 审计某个已有 skill 符合多少、违反哪些（“帮我检查 XX skill 写得规不规范 / 有没有散弹式散落、口径冲突”）。**只报告、不改写**；要修让用户点头。详见文末「原则校验（独立入口）」一节

入口 1 和 2 共享一个核心循环；入口 3、4 独立，见文末。

## 何时不使用

本 skill 不适用的场景——agent 看到这些时**不应**触发本 skill，应直接用基础工具回答：

- **单步问询**（"X 是什么意思？"、"这段代码哪里报错？"）—— 一句话就能答，不必拉一整个 skill
- **写代码 / 改代码**（"帮我写个 Python 函数"、"重构这段"）—— 直接写
- **读 / 改既有文档**（"读完这份 PDF"、"改这篇 markdown 的措辞"）—— 走对应专用 skill（如 `yzr-outline-wiki-search` / `yzr-outline-wiki-upload` / `yzr-llm-wiki-management`），本 skill 不擅长
- **不涉及 skill 生命周期的杂事**（解释概念、调试输出、临时性 ETL）—— 本 skill 的输出是 SKILL.md / 评估产物 / 审计报告，跟这些场景对不上
- **目标产物不是 skill**：用户最终要的是一个**已存在的脚本**、一个 docx、一段 prose——这些都不属于本 skill 范畴

### 核心循环（入口 1 / 2）

从整体的角度，创建/改进一个 skill 的主要流程如下：
1. 明确你希望这个 skill 做什么，以及大致如何实现
2. **不带 skill 跑 2–3 个典型 prompt 观察失败（RED 阶段）**——记录 agent 怎么违反、用了什么借口（逐字摘 transcript），这些 transcript 是后续起草 + Rationalization Table 的输入。原则见 `references/skill-writing-principles.md`「Iron Law」。**纯参考资料型 skill 可跳过**（仍建议写测试 prompt 验证可引用性）。
3. 起草一份 skill（改进场景下是编辑现有 skill）——**针对 RED transcript 观察到的具体违规做最小封堵**，不预堵"可能存在的"漏洞
4. 设计几个测试 prompt，让能访问该 skill 的 agent 在这些 prompt 上跑一遍
5. 协助用户对结果进行定性和定量两方面的评估
  - 在后台运行评估的同时，如果没有现成的定量评估，就先起草一份（如果已有，可以直接使用，在觉得需要调整时可以进行修改）
  - 然后向用户解释这些评估（如果已经存在，就直接解释现有的）
  - 使用 `scripts/generate_review.py` 脚本向用户展示结果，供其查看，同时让用户查看定量指标
6. 根据用户对结果的反馈（以及定量基准中暴露出的明显缺陷）改写 skill
7. 重复上述过程，直到满意为止

当你使用本 skill 时，你的任务是判断用户当前处于上述流程的哪个阶段，然后介入，帮助他们推进
比如，用户可能会说“我想做一个关于 X 的 skill”，这时你可以帮助其澄清需求、起草初稿、编写测试用例、设计评估方式、运行所有 prompt，然后反复迭代
另一方面，如果用户已经有了一份 skill 草稿，你就可以直接进入评估/迭代
保持灵活，如果用户表示 “我不需要跑一堆评估，直接跟我一起头脑风暴就行”，你完全可以照做

## 与用户沟通
skill 创建器的使用者编程背景差异很大，所以请注意根据上下文线索来调整措辞
如果你拿不准，简短解释一下术语是 OK 的
不确定用户是否能理解时，可以用一句简短定义来澄清

## 执行原则 / 边界

无论走哪个入口，下面这些原则贯穿全程——不是单独某一步的规则，而是 agent 在用本 skill 时应保持的判断基线：

- **元 skill 的"元"特征**：本 skill 的产物不是用户最终要的文件，而是"让 agent 在某类任务上更靠谱"的载体；写每段 prose 前先问"下游 agent 读到这里会怎么想"
- **过拟合红线**：用户给的反馈只覆盖少数 prompt；要让 skill 在一百万次调用里都成立，必须从反馈归纳"意图类别"而非把 case 逐条抄进 SKILL.md
- **必须跑评估，不要只凭脑改 skill**：写完草稿不跑 eval = 在赌运气；哪怕只跑 1 个 case 也能暴露"skill 让模型做了无效工作"这类肉眼难发现的问题
- **保留旧版本做 baseline**：改进现有 skill 时，先 `cp -r` 旧版到 workspace，否则改进"是否真的更好"无法量化
- **描述（trigger）与正文（body）是两件事**：description 只决定"何时调"，正文才决定"怎么用"；入口 3 只动 description，入口 1/2 才动正文——别混淆
- **用户说的"描述"是泛指**：中文里"优化 XX 的描述"默认包含整个文件的描述性内容
  （frontmatter `description` 字段 + 标题 + 正文 / 章节 + when-to-use 措辞 + 操作步骤说明），
  不要默认专指 frontmatter `description` 字段；用户如要细分会用更精确的措辞
  （"只改 frontmatter" / "只动 description 字段" / "标题层调整"等）
- **不要混用 `/skill-test` 之类的其它评估框架**：它们有自己一套目录约定，混用会让本 skill 的 `iteration-N/eval-N/with_skill|baseline` benchmark 数据无法跨迭代对比
- **writer 与 grader 分离**：跑评估的子 agent 跟打分的子 agent 不要合并，否则 grader 会偏向自己刚写的版本
  ——见 `references/agents/{grader,comparator}.md` 的盲测约定
- **阈值与版本号等指标必须单一来源**：脚本里有 `CONST = value` 的，prose 用 `` `CONST` `` 引用，禁止写字面量
  ——本 skill 自身在 `scripts/utils.py::DESCRIPTION_MAX_CHARS`、`scripts/run_loop.py::DEFAULT_HOLDOUT_RATIO` 带头遵守

## 输入 / 输出

四个入口的输入 / 输出对照——用来快速判断当前用户意图该走哪条路：

| 入口 | 用户输入 | skill 交付 |
| --- | --- | --- |
| 1. 创建新 skill | 一句中文意图（"帮我做一个关于 X 的 skill"）+ 必要的边界 / 样例澄清 | 起草好的 `<skill-name>/SKILL.md`（含 frontmatter）+ `references/` / `scripts/` 骨架，可选的 `eval/evals.json` |
| 2. 改进现有 skill | 现有 skill 路径 + 改进诉求（"评估 + 迭代" / "按反馈改写"） | 改写后的 SKILL.md、本地 `<skill-name>-workspace/iteration-N/` 下的 with-skill / baseline 评估产物、`benchmark.json` + viewer 反馈 |
| 3. 描述优化（独立） | 任意 skill 路径 + 一组 20 条 trigger 评估查询 | 新 `description` 候选 + before/after 触发准确率（按 `DEFAULT_HOLDOUT_RATIO` 拆训练 / 保留测试，见 `scripts/run_loop.py`） |
| 4. 原则校验（独立） | 任意 skill 路径 | 一份审计报告（每条原则 pass/fail + 证据 + 建议修法），不动手改 |


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
带着充分的上下文来，减少用户的负担

### baseline 演练（RED 阶段）

> 原则见 `references/skill-writing-principles.md`「Iron Law」。

不写 skill，先用旧版 skill（改进场景）或完全不带 skill（创建场景）跑 2–3 个典型 prompt——

- **创建场景**：完全不带 skill 跑 prompt，让 agent 用基础能力自由发挥，记录它**怎么违反**（哪些规则被跳 / 哪些步骤被漏 / 用了什么借口逐字摘抄）。
- **改进场景**：用当前版本的 skill 跑 prompt，记录**还错在哪**（旧 skill 没堵住的口子 / agent 找出的新借口）。

这些 transcript 作为起草 skill 的**输入**——skill 不是凭空设计，是**针对观察到的违规做最小封堵**。后续 Rationalization Table + Red Flags 的素材都来自这里。**纯参考资料型 skill 跳过**。

### Write the SKILL.md
基于用户访谈的结果，填充以下组件
YAML frontmatter 的字段描述：要求精简，明确，不要过于冗长，也不要过于模糊（词数指引见 `references/skill-writing-principles.md#description-优化原则`）
1. `name`：skill 的名字
2. `description`: skill 简介的功能说明，主要解释
  - 一句话说清楚这个 skill 是干什么的？
  - 什么场景下使用这个 skill？要写明在哪些具体场景下使用，所有“何时使用”的信息都放在这里，而不是正文里；请把 skill 描述写得"主动一些"
  - 关键的能力
3. `allowed-tools`：限制使用的工具，可选字段，如果没有，则置空
4. `metadata`：用户自定义字段，当前主要是作者（Zuoru YANG）、最后修改时间、skill 分类标签等信息

后面为 skill 的正文

### skill writing guide

通用骨架（目录布局 / progressive disclosure / 写作模式模板）见 `references/skill-template-guide.md`——
yzr-skill-creator 自身不在此重抄"什么是 SKILL.md 目录 / 什么是 progressive disclosure"这类
agent 通识，避免"通用背景铺垫"占 token。写作风格 / 语言原则见
`references/skill-writing-principles.md`「正文写作原则」。

### writing style

写作风格原则（解释"为什么"而非堆砌 MUST、心理揣摩、通用不绑定例子、草稿→复审）见
`references/skill-writing-principles.md#正文写作原则`。

### test case
写完 skill 草稿后，设计 2–3 个真实的测试 prompt，也就是真实用户实际会说的话
跟用户确认：这是我准备跑的几个测试用例，你看这样 OK 吗？要不要再补几个？然后跑起来

测试用例存到 `eval/evals.json`。先不写断言，只写 prompt，等下一步再起草断言。

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

本节是连续流程，不要中途停下来。

- workspace 在 `<skill-name>-workspace/`（与 skill 目录同级），按 `iteration-N/eval-<N>/{with_skill|baseline|without_skill|old_skill}/outputs/` 嵌套；目录边做边建
- **不要**使用 `/skill-test` 或任何其它评估框架——目录约定不对齐会让 benchmark
  数据无法跨迭代对比
- with-skill 与 baseline 在**同一轮**并行启动（不要串行）；baseline 类型：
  - 入口 1（创建）→ `without_skill/`
  - 入口 2（改进）→ `old_skill/`（编辑前先 `cp -r` 快照旧版到 `skill-snapshot/`）

5 步细节（启动 + 起草断言 + 采时序 + 评分聚合 + 读反馈、viewer 口径、
`eval_metadata.json` / `timing.json` / `grading.json` schema、`aggregate_benchmark.py` /
`generate_review.py` 用法）见 `references/eval-pipeline.md`。

## 改进 skill

跑过测试用例、用户评审过结果后，根据反馈迭代。

### 改进的思考方式（4 条核心原则）

1. **从反馈归纳泛化**：用户给的反馈只覆盖少数 prompt——要做一个能跑一百万次的 skill，
   必须从反馈归纳"意图类别"，不把 case 逐条抄进 SKILL.md（过拟合红线）。
2. **保持精简**：删掉不发挥作用的段；**读 transcript**，不只看最终输出——agent 浪费
   token 做无效工作常肉眼难发现。
3. **解释"为什么"而非堆砌 MUST**：全大写 ALWAYS / NEVER 或僵化结构是黄灯，重组措辞
   让模型理解 why——更人性、有力、有效（见 principles「精简原则」+「解释为什么」）。
4. **找跨用例重复工作**：3 个 eval 都让子 agent 写了 `create_docx.py` = 这个脚本
   该进 `scripts/`，下次不重复造轮子。

### 迭代循环

完成改进后：(1) 应用改动 → (2) 跑新 `iteration-<N+1>/`（**含** baseline，baseline
取值：创建场景始终 `without_skill`；改进场景：用户最初版本 or 上一轮迭代，由你判）→
(3) `--previous-workspace` 启动 reviewer → (4) 等用户评审完 → (5) 读 `feedback.json`
继续循环。

### 堵 loophole（REFACTOR 阶段）

> 原则见 `references/skill-writing-principles.md`「Iron Law」+「反合理化」。

每次迭代结束 + 读 transcript 后：(1) 识别新合理化（agent 又用什么借口绕禁令）；
(2) 加进 Rationalization Table（**只**补 agent 实际说过的——预写"可能存在"借口是反模式）；
(3) 对应红旗征兆若有缺则补 Red Flags；(4) agent 是否用看似不同但效果一致的手法绕禁令
→ 在"违反字面 = 违反精神"里加新案例；(5) 重测同批 prompt，新借口应不再出现；
仍出现 = 回 GREEN 重写。

### Concision review（每轮迭代必做）

下轮改动前先答 3 问：(1) 哪段 agent 实际用过且必需？(2) 哪段是 agent 已知的常识
（冗余）？(3) 哪段是 1-2 次 case 抄进去的（过拟合）？处理顺序按"修法优先级"6 步
（挪 references/ → tool help → 交叉引用 → 跨 skill 引用 → 压示例 → 删字）——完整规则
见 `references/skill-writing-principles.md`「精简原则」。

停止条件：用户满意 / 反馈全空 / 看不到有意义的进展。

## 参考样例

下面是用户输入 → 本 skill 介入路径的几个典型映射——用来快速判断当前对话该走哪个入口：

### 样例一：从零搭 skill

> 用户："帮我做一个处理 Excel 表格的 skill，能按列名做条件过滤并导出成 CSV"

→ 入口 1（创建）：先访谈边界（"哪些 Excel 库？" / "支持 xls 还是 xlsx？" / "导出的 CSV 编码？"），
  再起草 SKILL.md + `scripts/filter.py`，跑 2–3 个 eval case 验证，最后用 viewer 让用户评审

### 样例二：迭代改进

> 用户："这个 yzr-outline-wiki-upload skill 在上传大文档时总吞换行，你帮我改进一下"

→ 入口 2（改进）：先快照旧版 → 跑 with-skill vs baseline（同一 prompt，对照行为差异）→
  看 transcript 找"模型在哪里挣扎"→ 改 SKILL.md / 加 REST fallback 脚本 → 再跑同一轮 eval 看是否真的变好

### 样例三：只优化触发

> 用户："我那个 pdf skill 写得不错但该触发时总不触发，帮我只调 description"

→ 入口 3（描述优化）：先让用户跑 `scripts/generate_review.py` 出一份 20 条 trigger 评估查询
  （8–10 should-trigger / 8–10 should-not-trigger）→ 后台跑 `scripts/run_loop.py`
  （自动按 `DEFAULT_HOLDOUT_RATIO` 拆训练 / 保留）→ 取 `best_description` 替换 frontmatter，正文不动

### 样例四：只审计不改

> 用户："帮我看看 yzr-skill-creator 自己写得规不规范、有没有散弹式散落"

→ 入口 4（原则校验）：跑 `quick_validate.py`（frontmatter）+ `check_skill_dependencies.py`（互依）
  + grep 阈值 / 重复概念，按 `references/skill-writing-principles.md` 逐条 pass/fail；
  产报告**不改写**，等用户决定

## 描述优化（独立入口）

> 优化原则见 `references/skill-writing-principles.md#description-优化原则`（`improve_description.py` 运行时也读这一节）。

这一节是本 skill 的**独立入口之一**（四个入口中的第 3 个）：不经过”创建/改进”流程，直接优化某个已有 skill 的 description，提升其触发准确率——该触发时触发、不该触发时不触发。

适用场景：你有一个已经能用的 skill，但它的 description 触发不准（该用时没被调用，或不该用时乱触发）。脚本 `run_loop.py` / `improve_description.py` 原生支持指向任意 skill 目录，**不要求**该 skill 是本会话刚创建的——`--skill-path` 传到任意 skill 即可。

如果你是刚创建/改进完一个 skill、想顺手优化它的描述，同样走这套流程，只是 `--skill-path` 指向刚做好的那个。

SKILL.md frontmatter 中的 `description` 字段是决定 agent 是否调用该 skill 的主要机制。

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
好的例子:`"ok 我老板刚发了这个 xlsx 文件（在我的 downloads 里，大概叫 'Q4 sales final FINAL v2.xlsx'），她想让我加一列显示利润率百分比。营收在 C 列，成本好像在 D 列"`

**should-trigger 查询（8–10 条）**：
考虑覆盖度
你需要同一意图的不同说法，有些正式，有些口语化
要包含那些用户没有显式说出 skill 名字或文件类型、但明显需要它的场景
再加一些不常见用例，以及那些本 skill 与另一个 skill 竞争但应当胜出的场景

**should-not-trigger 查询（8–10 条）**：
最有价值的是擦边但不该触发的跟 skill 共享关键词或概念、但其实需要别的东西的查询
考虑相邻领域、措辞歧义大的场景（naive 的关键词匹配会触发但实际不该）
以及触及 skill 能力的某些方面、但用别的工具更合适的场景

关键要避免：不要让 should-not-trigger 查询明显无关
比如用写个 fibonacci 函数作为 PDF skill 的负样本太容易了；它什么也没测到，负样本应该是真正有迷惑性的

### 第 2 步:与用户过一遍

用 HTML 模板把评估集呈现给用户审阅:
1. 读取 `assets/eval_review.html` 模板
2. 替换占位符:
   - `__EVAL_DATA_PLACEHOLDER__` → 评估项的 JSON 数组（**不要**加引号包起来，这是 JS 变量赋值）
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
  --max-iterations 5 \
  --verbose
```

`--model` 可选：省略时 `claude -p` 用本机 claude CLI 的默认模型（不强绑定具体模型）；要指定时传 `--model <id>`。
跑的过程中，定期 tail 输出，告知用户当前在第几轮、分数长什么样
这个脚本会自动跑完整个优化循环：把评估集按 `DEFAULT_HOLDOUT_RATIO` 拆训练 / 保留测试（SSOT 在 `scripts/run_loop.py`）

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

## 原则校验（独立入口）

第 4 个独立入口：不动手改 skill，只拿写作原则当 checklist，审计某个已有 skill 符合多少、
违反哪些——产出报告，**只审计、不改写**，要修让用户点头再动（或转入口 2）。
适用场景：frontmatter 合不合法、指标是否散弹式散落、同一件事是否多处口径冲突、
正文是否覆盖该有章节、description 触发措辞如何等。

### 怎么校验

1. 把 `references/skill-writing-principles.md` 当 checklist（description 优化原则 + 正文
   写作原则，逐条——每条原则的"审计检查操作"小段已给出 grep / 命令清单）。
2. 读目标 skill 的 `SKILL.md`（必要时连带 `references/` / `scripts/`）。
3. 逐条核对 → 通过 / 违反（附证据：文件:行 + 具体内容）。能程序化的查：

   | 类别 | 操作 |
   | --- | --- |
   | frontmatter 合法性 | `python -m scripts.quick_validate <skill-dir>` |
   | 跨 skill 双向依赖 | `python -m scripts.check_skill_dependencies <repo-root>`（"互提" ≠ "互依"，是否成环靠 agent 读正文确认） |
   | 正文长度 / 跨文件重复 / scripts 常量与 prose / 自包含例外 / 链接路径基准 / Iron Law baseline / 纪律三件套 / 形式匹配 / `wc -w` 量化精简 | 见 `references/skill-writing-principles.md` 各原则的"审计检查操作"小段（不在 SKILL.md 重抄） |

4. 产出报告（**只审计、不改写**）——每条 pass / fail + 证据 + 建议修法。

## 参考文件

`references/agents/` 目录包含专用子 agent 的指令。需要启动相关子 agent 时读取。
- `references/agents/grader.md` —— 如何对照输出评估断言
- `references/agents/comparator.md` —— 如何对两份输出做盲测 A/B
- `references/agents/analyzer.md` —— 如何分析为什么某个版本胜出

`references/` 补充文档:
- `references/schemas.md` —— evals.json、grading.json 等的 JSON 结构


最后再强调一遍核心循环，务必记住:
- 明确这个 skill 是关于什么的
- 起草或编辑 skill
- 让能访问该 skill 的 agent 在测试 prompt 上跑一遍
- 与用户一起评估输出:
  - 创建 benchmark.json，并跑 `scripts/generate_review.py` 让人类评审测试用例
  - 跑定量评估
- 反复迭代，直到你和用户都满意
- 把改动提交到 git（`git add` + `git commit`）