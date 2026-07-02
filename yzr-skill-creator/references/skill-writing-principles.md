# SKILL 文字优化原则

本文件是 yzr-skill-creator 管理"SKILL 文字怎么写好"的唯一真源（SSOT）。

- **description 优化原则**（下一节）会被 `scripts/improve_description.py` 运行时读取并注入优化 prompt——在此新增 / 修改原则，下次跑优化器立即生效。
- **正文写作原则**（再下一节）供创建 / 改进 skill 时参考，SKILL.md 的写作指南指向这里。

新增原则直接追加到对应小节即可，无需改任何代码。

## description 优化原则

> 本节由 `improve_description.py` 读取（按本 header 抽取到下一个 `## ` 之前）。改本节标题会破坏脚本抽取——若要改名，同步改 `improve_description.py` 里的 header 匹配。

写 / 改 skill 的 description（触发描述）时遵循：

- **别过拟合到具体查询**：不要把当前看到的失败 case 逐条列进描述。从失败里归纳出更宽泛的"用户意图类别 / 适用场景"，而非不断追加"该 / 不该触发的具体查询"。原因有二：(1) 避免过拟合；(2) description 会被注入到**所有**查询里，且 skill 可能很多，不要在单个 description 上占太多篇幅。
- **长度**：约 100–200 词；硬上限 `DESCRIPTION_MAX_CHARS`（见 `scripts/utils.py`，超出会被截断），保持在上限之内留有余量。
- **祈使语气**：用 "Use this skill for…" 这类主动说法，而非 "this skill does…"。
- **聚焦用户意图**：写用户想达成什么，而不是 skill 的实现细节。
- **有辨识度**：description 要和其它 skill 争夺 agent 的注意力——写得独特、一眼能认出来。
- **反复失败就换结构**：同一思路连续失败时，换句式 / 换措辞，别钻牛角尖。
- **鼓励创造性**：多轮迭代里换不同风格尝试，最终只取最高分那版。

## 正文写作原则

写 / 改 SKILL.md 正文时遵循：

- **progressive disclosure 三级加载**：元数据（name + description）始终在上下文；SKILL.md 正文触发时加载；捆绑资源按需加载。**正文长度权威上限 = 5000 词**（本仓库只在此处给出该指标，其它位置只引用不重抄，参见下方”指标单一来源”原则）；接近上限就抽一层到 `references/`，并给出清晰的”何时去读”指引；> 300 行的 reference 文件要带目录。
  - **模板文件例外**：CLI 字面拷贝给目标仓的模板文件（如 `references/claude-md-template.md`
    经 `cp` 拷到 `<wiki-root>/CLAUDE.md` 这类）**不**适用 "> 300 行要带目录" 规则。
    **两个原因**：(1) 模板读者是**顺序消费**——agent 读 CLAUDE.md 是一次性顺序读,不是按 TOC 跳读,
    TOC 在小文档里反而占 token 无收益;(2) **产物形态固定**——CLI 按字面拷贝 + 占位符替换,
    加 TOC 会把目录段带进目标仓 CLAUDE.md,破坏"按模板字面拷贝"语义。
    **审计识别方法**：文件名带 `-template.md` / `-template.txt` 后缀,或路径在 `references/` 下
    但被 spec 标为"CLI init 拷贝"。
- **正文超长根因诊断路径**（接 progressive disclosure 上限）：触到或超过 5000 词时，常见反应用 Edit 在 SKILL.md 直接删字——但根因常是”references 内容被复制到 SKILL.md” + “次级 workflow 步骤没下放”，删字只治标。**诊断三步**：(1) **全节重抄检测**——grep 同一规则关键词在 SKILL.md + references/ 出现 ≥ 2 次且内容相似 = 重抄信号（详见正文描述一致性 + 跨文件重复检测子原则）；(2) **次级 workflow 步骤未下放**——“### 1. <Op>” / “### 2. <Op>” 等多步操作单步超过 30 行 = 应下放到 `references/<op>-workflow.md`；(3) **冗长参考样例**——“## 参考样例” / “## Examples” 段超过 80 行 = 应下放到 `references/examples.md`。**修法优先级**：先”加新 references 文件”（正向，不破坏现有结构）而非”在 SKILL.md 删字”（负向，易丢上下文）。预期收益：加新 references 文件 -800 ~ -1500 词（低风险）；压 §核心原则段为”title + 1 句话 + reference” -200 ~ -500 词（中风险）；直接删字 -100 ~ -300 词（高风险）。
- **语言**：正文以中文为主，关键名词 / 流程可用英文辅助；说明性文字优先祈使语气。
- **解释"为什么"而非堆砌 MUST**：尽量讲清楚每条要求背后的原因；全大写的 ALWAYS / NEVER 或僵化结构是黄灯，能用"为什么"替代就替代。运用心理揣摩让 skill 通用，不过度绑定到具体例子；先写草稿，再用新眼光复审。
- **正文应覆盖**：何时使用 / 不使用、输入 / 输出、执行原则 / 边界、工作流 / 步骤、参考样例。
- **清晰引用外部文件**：从 SKILL.md 引用 `scripts/` / `references/` / `assets/` 时，说明何时去读。
- **指标单一来源（避免散弹式修改）**：SKILL 涉及的任何指标（字数、字符上限、阈值、轮数等）只在**一个**地方给出权威值并加以控制，其它位置只引用、不重抄。同一个数字散落多处 = 改一处要记得同步改全部，极易漏改；保持单一来源才能"改一次即生效"。
- **脚本常量作 SSOT 时的 prose 引用规范**（子化指标单一来源）：当 SSOT 落在脚本常量（Python 顶部 `CONST = value`）时，prose **必须**用**代码风格常量名引用**（`` `PAGE_SIZE_THRESHOLD` `` / `` `LOG_ROTATION_THRESHOLD` `` / `` `metadata.wiki_spec_version` ``），**禁止**写字面量（"300 行" / "500 条" / 版本号裸字面量）。原因：常量改了 prose 不跟 = docs 与 code 脱节，SSOT 形同虚设。**审计检查操作**：`grep -nE "\b(<具体阈值/版本号裸数字>)\b" <skill>/**/*.md`——出现应改为常量名引用，除非该数字另有出处。
- **正文描述一致性（避免散落）**：同一件事（概念、规则、术语、事实、流程等）尽量只在**一个**地方完整描述，其它位置需要时引用、不重抄——避免一件事散落在 SKILL 文档各处、口径漂移甚至互相打架。若某内容确实必须在多处出现，各处措辞要完全对齐；冲突的描述会让模型无所适从、按错的那份执行。上条”指标单一来源”是本原则在数字指标上的特例。
- **自包含例外规范**（子化正文描述一致性）：同一规则在多处出现是 SSOT 违反，但**部分文件物理上无法跨仓引用 SKILL.md**——必须自包含。区分”必要自包含”与”无意识重抄”：**允许自包含**的场景——(a) 会被 CLI 拷贝到目标仓的模板（如 wiki 的 CLAUDE.md 模板；分发目的地是目标仓，跨仓无法引回 SKILL.md）；(b) 字面量 fixture（CLI 字节级对比金标准，注释会破坏对比）。**禁止重抄**的场景——SKILL.md 自身 §核心原则段、`references/<other>.md`（普通 reference）；这两类都在同一仓内，引用即可。**关键纪律**：自包含时**必须**带 self-aware 注释——明确写”本段与 SKILL.md §X 重复——本文件是 <自包含理由>，必须自包含；SSOT 在 <path/to/ssot.md> §Y。本文件与 SSOT 措辞故意保持一致，改 SSOT 时同步改本段”。缺失 self-aware 注释 = 无意识重抄嫌疑，agent 跑审计时必报。
- **跨文件重复检测操作步骤**（子化正文描述一致性）：”同一规则尽量只在一个地方完整描述”是抽象目标，agent 跑审计时需要**具体操作**才能稳定识别违规。**操作步骤**：(1) 列出目标 skill 的所有 `.md` 文件（`SKILL.md` + `references/*.md`）；(2) 对每条核心原则的**关键词**（如”tag 白名单” / “scripts/SCRIPTS.md” / “reviewed 戳” / “frontmatter 必填字段”等概念性短语），用 grep 在所有文件查；(3) 按出现次数 + self-aware 注释存在性分类：1 次 = 正常；2 次且一方是自包含模板（带 self-aware 注释指 SSOT）= 允许；2 次且都无注释 = 警告，agent 读两段对比确认；3+ 次且都无 self-aware 注释 = 几乎必是 SSOT 违规。**典型高频违规概念**（agent 重点 grep 这些短语）：”tag 白名单” / “tag 字典” / “tag taxonomy”、”scripts/SCRIPTS.md” / “scripts/ 索引”、”MEMORY/MEMORY.md” 索引、”frontmatter 必填字段” / “5 必填” / “5 类内容页”、”reviewed 戳” / “reviewed: true” 生命周期、log 格式正则 / “log.md 条目”。
- **跨 skill 依赖单向（避免双向依赖 / 成环）**：skill 之间通过正文措辞（“转交 / 调用 / 产物交给 X 消费 / 风格对齐 X / 前置条件依赖 X”等）表达的依赖关系必须构成**有向无环图（DAG）**——A 依赖 B 时，B 不得反过来依赖 A。双向依赖的典型长相是：A 正文写“这步走 B / 产物交给 B / 对齐 B 的风格”，同时 B 正文也写“输入来自 A / 调 A 的能力 / 转回 A 处理”。它会混淆模型对上下游的判断（跨 skill 任务按错方向转交），也让两个 skill 的演进互相锁死（动 A 就得同步动 B）。这是**仓库级原则**（其余原则都针对单个 skill）；判断依赖方向属语义判断，`scripts/check_skill_dependencies.py` 只筛查“互相提及”的候选对并给证据，但“互提”不等于“互依”（分工转交、风格对齐是良性的），是否成环仍需人工读正文确认。确需双向协作时，把分工约定集中写在**一处**（根 `CLAUDE.md` 的“跨 skill 协作约定”，或某个协调 skill 如 `llm-wiki-management` 统一编排论文管线），别让两个 skill 各写一半互相指。
- **跨 skill 相对路径引用禁止（链接 target 只限本 skill 目录）**：SKILL.md / `references/*.md` 中的 markdown 链接只能指向本 skill 目录（`<skill-name>/**`）下的文件——即相对路径必须以 `./` 开头（同一目录引用）或在本目录树内（如 `references/foo.md` / `../scripts/foo.py`）。跨 skill 目录（如 `../../other-skill/references/foo.md`）的相对路径**禁止**作为 markdown 链接使用。原因：跨 skill 路径在目标 skill 目录结构变化（重命名 / 移动文件 / 重构子目录）时**无声断裂**——渲染时是死链，但 markdownlint 等静态检查不一定能抓到（链接 fragment 不在目标 skill 的 SSOT 范围）。skill 是独立分发的（npx / vendored 副本），跨 skill 链接在不同机器 / 不同 commit hash / 副本路径下都可能漂移。若需指向其他 skill 的某个约定 / 章节，**用纯文本**（"X 侧 spec §Y" / "对齐 X 侧 §Z" / "X 仓的 <file> "）描述，不带链接。审计 grep：`grep -rEn '\]\(\.\./\.\./[a-z]' <skill>/**/*.md`——出现即报"跨 skill 相对路径引用"，按本条原则违规处理（默认改成纯文本，不保留链接）。
