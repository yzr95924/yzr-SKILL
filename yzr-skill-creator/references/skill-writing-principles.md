# SKILL 文字优化原则

本文件是 yzr-skill-creator 管理"SKILL 文字怎么写好"的唯一真源（SSOT）。

- **description 优化原则**（下一节）会被 `scripts/improve_description.py` 运行时读取并注入优化 prompt——在此新增 / 修改原则，下次跑优化器立即生效。
- **正文写作原则**（再下一节）供创建 / 改进 skill 时参考，SKILL.md 的写作指南指向这里。

新增原则直接追加到对应小节即可，无需改任何代码。

## description 优化原则

> 本节由 `improve_description.py` 读取（按本 header 抽取到下一个 `## ` 之前）。改本节标题会破坏脚本抽取——若要改名，同步改 `improve_description.py` 里的 header 匹配。

写 / 改 skill 的 description（触发描述）时遵循：

- **别过拟合到具体查询**：不要把当前看到的失败 case 逐条列进描述。从失败里归纳出更宽泛的"用户意图类别 / 适用场景"，而非不断追加"该 / 不该触发的具体查询"。原因有二：(1) 避免过拟合；(2) description 会被注入到**所有**查询里，且 skill 可能很多，不要在单个 description 上占太多篇幅。
- **agent 中立（默认不与具体 agent 强绑定）**：description 默认写成 agent 无关——不 presume 用户跑在某个 agent 上（Claude Code / Qoder / Cursor / Windsurf / Codex 等），也不用"为 X 设计"框死适用范围；需要提到 agent 概念时用泛指（"AI coding agent" / "某些 agent" / "读 AGENTS.md 的 agent"）。原因：(1) description 是触发信号且常驻所有查询上下文，绑死某个 agent 会让用其它 agent 的同类用户无法触发本该触发的 skill；(2) skill 常在多 agent 环境分发，中立描述覆盖面更广、寿命更长。**例外**：skill 本就是针对某 agent 的**特有机制**设计的（如 Qoder 的 `.qoder/rules/` type 系统、Claude Code 的 hooks / `@import` 递归展开），这时点名是准确而非违规——但正文要讲清"为什么必须点名这个 agent"（是它的特有行为，不是泛化措辞偷懒）。审计 grep：`grep -niE "claude ?code|qoder|cursor|windsurf|codex" <skill>/SKILL.md` 命中即**逐处**复核——确认每处是"特有机制必须点名"还是"可泛化却写死"，后者改泛指。
- **长度**：约 100–200 词；硬上限 `DESCRIPTION_MAX_CHARS`（见 `scripts/utils.py`，超出会被截断），保持在上限之内留有余量。
- **祈使语气**：用 "Use this skill for…" 这类主动说法，而非 "this skill does…"。
- **聚焦用户意图**：写用户想达成什么，而不是 skill 的实现细节。
- **有辨识度**：description 要和其它 skill 争夺 agent 的注意力——写得独特、一眼能认出来。
- **反复失败就换结构**：同一思路连续失败时，换句式 / 换措辞，别钻牛角尖。
- **鼓励创造性**：多轮迭代里换不同风格尝试，最终只取最高分那版。
- **不写工作流摘要（保留能力清单 / 入口列表，不写"先做 X 再做 Y"）**：description 只列"用户意图类别 + 关键能力 + 触发场景"，**不**写"先做 X → 再做 Y → ..."的步骤序列。步骤属于 SKILL.md 正文——description 写步骤会让 agent 把 description 当 shortcut 跳读 skill 正文、按 description 的步骤摘要执行（丢失正文里的"为什么"与例外处理），尤其在 `DESCRIPTION_MAX_CHARS` 硬截断时（见 `scripts/utils.py`，超限被截）会丢掉关键约束。**冲突说明**：superpowers 等其它方法论建议"description 永不写步骤"——yzr-skill-creator 保留"能力清单 + 入口列表"形式（这是**意图 + 触发场景**而非步骤），仅禁"step-by-step 流程摘要"——即"列出 4 个入口"是允许的，"入口 1 → 入口 2 → 入口 3 → 入口 4"按顺序串讲不允许。

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
- **跨 skill 依赖单向（避免双向依赖 / 成环）**：skill 之间通过正文措辞（“转交 / 调用 / 产物交给 X 消费 / 风格对齐 X / 前置条件依赖 X”等）表达的依赖关系必须构成**有向无环图（DAG）**——A 依赖 B 时，B 不得反过来依赖 A。双向依赖的典型长相是：A 正文写“这步走 B / 产物交给 B / 对齐 B 的风格”，同时 B 正文也写“输入来自 A / 调 A 的能力 / 转回 A 处理”。它会混淆模型对上下游的判断（跨 skill 任务按错方向转交），也让两个 skill 的演进互相锁死（动 A 就得同步动 B）。这是**仓库级原则**（其余原则都针对单个 skill）；判断依赖方向属语义判断，`scripts/check_skill_dependencies.py` 只筛查“互相提及”的候选对并给证据，但“互提”不等于“互依”（分工转交、风格对齐是良性的），是否成环仍需人工读正文确认。确需双向协作时，把分工约定集中写在**一处**（根 `CLAUDE.md` 的“跨 skill 协作约定”，或某个协调 skill 如 `yzr-llm-wiki-management` 统一编排论文管线），别让两个 skill 各写一半互相指。
- **跨 skill 相对路径引用禁止（链接 target 只限本 skill 目录）**：SKILL.md / `references/*.md` 中的 markdown 链接只能指向本 skill 目录（`<skill-name>/**`）下的文件——即相对路径必须以 `./` 开头（同一目录引用）或在本目录树内（如 `references/foo.md` / `../scripts/foo.py`）。跨 skill 目录（如 `../../other-skill/references/foo.md`）的相对路径**禁止**作为 markdown 链接使用。原因：跨 skill 路径在目标 skill 目录结构变化（重命名 / 移动文件 / 重构子目录）时**无声断裂**——渲染时是死链，但 markdownlint 等静态检查不一定能抓到（链接 fragment 不在目标 skill 的 SSOT 范围）。skill 是独立分发的（npx / vendored 副本），跨 skill 链接在不同机器 / 不同 commit hash / 副本路径下都可能漂移。若需指向其他 skill 的某个约定 / 章节，**用纯文本**（"X 侧 spec §Y" / "对齐 X 侧 §Z" / "X 仓的 <file> "）描述，不带链接。审计 grep：`grep -rEn '\]\(\.\./\.\./[a-z]' <skill>/**/*.md`——出现即报"跨 skill 相对路径引用"，按本条原则违规处理（默认改成纯文本，不保留链接）。
- **markdown 链接相对路径基准匹配（防漂移死链）**：markdown 链接的相对路径基准是**当前文件所在目录**——不是 skill 根、也不是任意约定。从 SKILL.md（在 skill 根）引用写 `references/foo.md`；从 `references/a.md`（在 references/）引用同目录 `b.md` 写 `b.md`，**不**写 `../b.md`（那会退到 skill 根的 `b.md`，不存在 = 死链）；引用 skill 根的 `scripts/foo.py` 写 `../scripts/foo.py`（合法，target 确实在 skill 根）。**最常见错误**：`references/` 内文档互相引用时误写 `../X.md`（多退一层）→ 解析到 `<skill>/X.md` 不存在。与"跨 skill 相对路径引用禁止"互补——那条禁 `../../` 跨 skill，本条管 skill 内基准。**例外**：code fence 内的"教学示例"路径（演示 wiki 内 / 目标产物内引用，如 `sources/foo.md` / `../concepts/x.md`）不受此约束——它们在围栏内、target 本就不该存在；agent 审计时需区分（看是否在 code fence 围栏内），别误报。**审计检查操作**：(1) 把 skill 内每条链接的 path 相对当前文件目录解析，target 文件不存在 = 死链嫌疑；(2) 粗筛 `grep -rnE '\]\(\.\./[a-z_0-9-]+\.(md|py)' references/` 找 `references/` 内指向 skill 根层级的引用，逐个确认 target 是 skill 根真文件（`../scripts/foo.py` 合法）还是同级误加 `../`（`../page-templates.md` 应为 `page-templates.md`）；(3) **fragment 漂移**：`path#anchor` 的 anchor 若目标 heading 改名 / spec 演进后没跟着改 = 失效（典型：heading 从 `wiki/MEMORY` 改 `MEMORY/`，slug 变、旧 anchor 失效），需对比目标 heading 实际 slug（GitHub 风格：小写 + 去标点 + 空格转 `-`；全角标点 `：` / `、` / `（` / `）` 是**删除**而非转 `-`）。
- **Iron Law（没观察到失败就别写 skill）**：任何"以改变 agent 行为"为目的的 skill——纪律型 / 塑形型 / 模式型（见下方"形式匹配失败"原则的 skill 类型区分）——写之前必须先**不带 skill 跑一遍典型任务**，记录 agent 怎么违反、用了什么借口（从 transcript 逐字摘），再起草 skill。三阶段：**RED**（不带 skill / 用旧版 skill 跑 2–3 个典型 prompt；agent 说的"为简化" / "用户没说明" / "这样更快" / "应该等价"等借口**原样**抄进 Rationalization Table 输入池）；**GREEN**（写**最小** skill 针对刚观察到的具体违规——不要预先堵"可能存在的"漏洞，过度泛化是反模式）；**REFACTOR**（用新 skill 重跑同一批 prompt，每条违规都被堵住即"过"；任何漏洞被发现就回 GREEN 重写，不要跳过 REFACTOR 直接发版）。**规则**：先观察到 agent 犯错 → 再写 skill 防止犯错。**没观察到失败就写 skill = 在赌运气**，大概率漏堵关键漏洞或过度泛化。**纯参考资料型 skill**（API 速查 / 文件路径 / 命令清单——只聚合信息、不改变 agent 行为决策）不强制 baseline（仍建议写测试 prompt 验证"agent 读后能正确引用"，但不需要 Rationalization Table）。
  - **适用于 EDITS，与新建同标准**：改进现有 skill 的 edit 也适用——若你**没有**先跑当前版本（带旧 skill）记录"哪些行为仍不对 / agent 又找出什么新借口"，那这个 edit 是**未经验证**的，立即丢弃并回到 RED。原则：edit 与新建同标准，不存在"小改免测"的灰色地带。
  - **审计检查操作**：`grep -nE "迭代|baseline|transcript|Rationalization|RED|GREEN|REFACTOR" <skill>/SKILL.md <skill>/references/*.md` 命中其中 ≥ 1 项 = 有 baseline 证据；纪律型 / 塑形型 skill（grep 命中禁令或步骤式措辞）若无 baseline transcript 证据，按"未经验证"标注。粗筛命令：`grep -rEn "(iteration-[0-9]+|without_skill|old_skill)" <workspace>/` 验证工作区是否真跑过 baseline。
- **形式匹配失败（prohibition vs recipe vs structural）**：skill 形式必须**匹配要堵的失败类型**——三类形式对应三类失败，错配会反效果。skill 类型判定（technique / pattern / reference / discipline-enforcing）见本原则后半段；下表为按失败类型选形式。
  - 三类失败 → 对应形式（从 RED transcript 判定 agent 是"知道但偷懒" / "想做但不会" / "根本不知道"哪个）：
    - **纪律失败**（agent 知道规则但懒 / 漏 / 找借口绕开）→ **结构性禁令** + Rationalization Table + Red Flags（见下方"反合理化"原则）。例："NEVER skip the test step before commit"。
    - **塑形失败**（agent 想做但不知道怎么做 / 做法不对）→ **配方式步骤**（具体步骤 + 例子 + 何时用）。例："Step 1: 读 X，Step 2: 解析 Y，Step 3: 写 Z"。
    - **知识失败**（agent 不知道某事实 / 引用错地方）→ **参考资料式**（聚合文档 + 链接 + 索引）。例：API 速查表 / 命令清单 / 文件路径表。
  - **反模式**：
    - 纪律失败用配方 → agent 配方做对了但**关键一步仍被跳**（因为跳那步最省事），配方无能为力。
    - 塑形失败用禁令 → agent 知道"不许做 X"但**不知道该做什么**，停下来等你手把手。
    - 知识失败用禁令 → 信息密度低、查不到东西。
  - **禁止 nuance / 例外条款**：写禁令时**不要**加 "if convenient" / "unless..." / "in most cases"——任何开口子都给借口开口子，agent 压力下都会"合理"地走例外。纪律禁令要么写、要么不写，没有"软版本"。**例外条款本身就是反模式**，发现应删除。**自包含说明**：本条自身举例的反例措辞（"if convenient" 等）为反例示意用引号框起，**不是**给本条开口子——本条无例外。
  - **审计提示**：纯 judgment-based——审计 agent 需读 RED transcript 判断失败类型归属，再核对 skill 形式是否匹配；混合使用多种形式时（如既有禁令又有配方），需确认每段形式对应其要堵的具体失败，不要一刀切归类。
- **反合理化（仅适用于纪律型 skill）**：纪律型 skill 的核心风险是 agent 压力下找借口绕开禁令——必须用**三件套**堵漏洞，缺任一都不合规。
  - **三件套**：
    1. **Rationalization Table**（合理化借口表）：从 RED transcript 摘出 agent **实际说过的**借口，逐条配"为什么这是错的 / 应改做什么"。例：agent 说"为节省时间跳过这步" → 反驳："这步是正确性前提，跳过 = 错误率↑，节省时间但交付物不可用"。**只收录 agent 实际说过的**，不预写"可能存在的"借口——预写 = 噪声 + 干扰信号；RED 没观察到 = 当前不需要。
    2. **"违反字面 = 违反精神"** 原则（violating the letter = violating the spirit）：skill 必须明确写"违反 X 字面表述 = 违反 X 精神——包括任何看起来不同但效果一致的绕法"。agent 倾向把禁令字面解读（"我没做 Y 所以没违反"——但实际做了 Z 实现 Y），需提前堵。**禁止**用"严格按字面 / 严格按精神"等二选一措辞给 agent 留"按字面就行"的退路。
    3. **Red Flags list**（红旗清单）：列出"出现以下念头 = 你正在找借口，停下来重读 skill"的征兆清单。例："觉得自己'理解精神了可以省一步'" / "觉得'这一步对当前 case 不必要'" / "觉得'用户没明确说要这步'"。**关键**：红旗是**念头**而非行为——念头出现 = 警告（要重读 skill），不是"已违反"——分清"念头"与"行动"两层。
  - **触发条件**：纪律型 skill（用禁令形式）**必须**带三件套；塑形 / 知识型 skill **不**需要（按形式匹配失败原则判定）。纪律型 skill 缺三件套 = 几乎必然被绕开。
  - **审计检查操作**：`grep -nE "NEVER|ALWAYS|必须|禁止|不能|不得" <skill>/SKILL.md <skill>/references/*.md` 命中 → 检查同一文件是否同时含 Rationalization Table + Red Flags + "violating letter = violating spirit"（或"违反字面 = 违反精神"）三段；缺任一 = 纪律型 skill 不合规。**反查**：`grep -nE "Rationalization|合理化|借口|Red ?Flag|红旗" <skill>/**/*.md` 在纪律型 skill 中应至少命中 1 次（用于抓出"用了禁令但忘了三件套"的常见漏）。
- **精简原则（每段先答 3 问再动笔）**：默认假设 agent 已够聪明——写每段 prose 前先答：(1) agent 真需要这解释吗？(2) 能假设 agent 自己知道吗？(3) 这段值它的 token 成本吗？任一答"否"→ 删或挪到 references/。Anthropic 教学对照：50 token 的"`Use pdfplumber for text extraction`+ 一段代码" vs 150 token 的"PDF (Portable Document Format) files are a common file format..."——3x 缩比（删 agent 已知的常识铺垫）。
  - **量化软目标**（不取代 5000 词硬上限）：参考资料型（API / 命令清单）< 300 词；高频触发 skill < 800 词；普通 skill < 2000 词；元 skill / 多入口 < 5000 词。**审计指标冲突说明**：本仓库无 `scripts/utils.py` 常量承托 tiered 阈值，prose 字面数字是软目标不是 SSOT；与"脚本常量作 SSOT 时的 prose 引用规范"子原则张力留作未来 TODO。
  - **修法优先级**（按收益与风险）：(1) 挪到 references/（-800 ~ -1500 词，低风险，正向加新文件不破坏结构）；(2) 挪到 tool help（`Run --help for details.` 替列所有 flag）；(3) 交叉引用（`See references/x.md` 替重写）；(4) 跨 skill 引用（`**REQUIRED SUB-SKILL:** Use <x>` 替复述，**禁用 `@` 强制加载**——会烧 200k+ context）；(5) 压示例（42 词 → 20 词）；(6) 删字（-100 ~ -300 词，高风险最后手段）。
  - **引用深度硬上限（one level deep）**：`SKILL.md → references/*.md` 合法；`references/a.md → references/b.md` 作**加载链**（"要执行 a 的流程必须串联读到 b.md"，agent 不到 b 就拿不全必需信息）**禁止**——agent 在嵌套引用时用 `head -100` 预览，丢信息。所有 reference 必须从 SKILL.md 直接挂。**例外**：(1) CLI 字面拷贝给目标仓的模板文件不适用此约束（同上"模板文件例外"原则）；(2) **SSOT 指引引用**——a.md 写"权威定义在 `b.md` §Y"式路标**不算**加载链，前提是 b.md 也已从 SKILL.md 直接挂载、且删掉路标就得在 a.md 重抄内容（重抄违反"正文描述一致性"，两害相权取路标）。审计区分：路标 = 指路去 SSOT 看定义（允许）；加载链 = 不读 b 就无法执行 a 的步骤（违规）。
  - **避免 time-sensitive 信息**：会过期事实（如 "v2 API 取代 v1"）写 `CHANGELOG.md` / `MEMORY/`，SKILL.md 引用而非内联——内联会随时间变成错信息。yzr-skill-creator 仓库不用 HTML `<details>` 折叠块，改用 markdown reference。
  - **避免太多选项**：每个决策点给"1 个推荐 + 1 个 escape hatch"，不列 N 个等价选项（"你可以用 A / B / C / D..."）——N 个等价选项逼 agent 自己判断，反而拖慢决策。
  - **executable scripts 优于生成代码**：可脚本化 + agent 多次需要时**写脚本**而非让 agent 现场生成——节省 token（脚本输出占 context、源码不占）、节省时间、保证一致性。论据来自 Anthropic skill 写作指南。
  - **one excellent example > 多个平庸样例**：一个完整可运行示例胜过 5 个模板填空 / 多语言实现（python + js + go + ...）——agent 自己会移植语言，选最相关的 1 个写好就够。
  - **审计检查操作**：`wc -w <skill>/SKILL.md` 应 < 5000 词（硬限）；超 tier 软目标但 < 5000 词标"WARN 偏臃肿"；跑 `grep -nE "(PDF (Portable|is a|are a)|files? (is|are) a common|is a common file format)" <skill>/**/*.md` 找"通用背景铺垫"类冗余段。
- **正文不堆版本演进史（版本史集中进独立 changelog 文件）**：SKILL.md 与主要 references 正文只写**当前状态**的规范 / 行为，不内联版本演进记录（"0.6.0 起删了 X" / "自 v1.2 起 Y 改为 Z" / "演进路线：A → B → C" 这类）。原因：(1) 版本史是考古信息——agent 执行任务只需当前口径，内联历史稀释信噪比，且 SKILL.md 每次触发都加载，历史段每次白占 token（违背"精简原则"）；(2) 内联历史随版本累积只增不减，终将盖过当前规范本身（典型反例：spec 每节挂"X 版新增 / Y 版废弃"脚注，正文退化成编年史）；(3) 旧行为描述留在正文里，agent 会误判"历史做法仍可选"而按过期口径执行。**确需追溯时**（spec 演进 / 破坏性变更 / 迁移依据）集中到一个独立 changelog 文件——skill 根 `CHANGELOG.md` 或 `references/<topic>-changelog.md`（本仓库先例：`yzr-llm-wiki-management/references/wiki-spec-changelog.md`）——正文最多留一句路标（"版本历史见 `CHANGELOG.md`"），演进细节一律不内联。**边界**：外部依赖的版本**约束**（"Python ≥ 3.7" / "需 v2 API"）是当前状态要求、不是版本史，照写正文不受本条限制；本条与「避免 time-sensitive 信息」互补——那条管"会过期的事实陈述"，本条管"skill 自身 / 所管对象的版本演进记录"。**审计检查操作**：`grep -cnE 'v?[0-9]+\.[0-9]+(\.[0-9]+)?' <skill>/SKILL.md <skill>/references/*.md`（排除 `CHANGELOG.md` / `*changelog*.md`）——单文件命中密集（≥ 10 处）= 版本史内联嫌疑，再逐处人工区分"自身 / 所管 spec 的版本演进"（违规：挪 changelog、原处留路标）还是"外部依赖版本约束"（合法）。
