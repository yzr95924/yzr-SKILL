# SKILL 文字优化原则

本文件是 yzr-skill-creator 管理"SKILL 文字怎么写好"的唯一真源（SSOT）。

**按任务选读**：改 / 优化 description → 只读 [章节](#description-优化原则)；写 / 改正文 → 读 [章节](#正文写作原则)
五组；审计（入口 4）→ 全组原则当 checklist + 末尾 [章节](#审计速查) 与 [章节](#审查深度标准入口-4-默认口径) 逐条执行；新增原则 →
先过下方“新增前三问”。不用每次全量加载。

- **description 优化原则**（下一节）由 description 优化器读取，在此新增 / 修改原则，下次跑优化器立即生效
  （抽取机制与改标题的注意事项见该节提示）。
- **正文写作原则**（再下一节）供创建 / 改进 skill 时参考，SKILL.md 的写作指南指向这里。

**怎么读**：每条 = 名称 + 规则句；例外 / 界限 / 准入等子结构以行内粗体标记折进，不单开子条目
（判断准则细节就是原则本身，不是装饰；长度随例外复杂度，不机械限句数）。审计检查（grep / 命令）
不内联在原则里：写作时不需要看，执行入口 4（原则校验）时查末尾 [章节](#审计速查)。

新增原则前先过三问，不要直接追加：

1. 是不是已有原则的特例？是 → 并入那条，不新增（同名内容两处 = 口径漂移，本文件曾有“修法优先级”
   两份的教训）。
2. 是不是在给单 case 打补丁 / 防御性回应假想读者？是 → 不写。删掉也不会让称职 agent 做错的
   提醒不需要规则承载（补丁没来自实际观察到的失败即无依据）。
3. 该进哪个分组？归位到对应 H3 组，不平铺堆叠、不用"子化 X / 与 Y 互补"交叉引用绕说。

改规则名时跑 `python -m scripts.check_anchor_health --repo-root` 核引用存活（覆盖范围见其
docstring）。改名 = 可检查的破坏性操作，不必手工 grep 全文件。

本文件自身同样受下述原则管辖。定期逐句问"删掉这句，称职 agent 会做错吗"；原则文件腐化的典型
长相：扁平堆叠、交叉引用绕说、同名多处、疤痕组织。

## description 优化原则

> 本节由 `optimize_description.py` 读取（按本 header 抽取到下一个 `##` 之前）；改标题会
> 破坏脚本抽取，改名需同步改 `optimize_description.py` 的 header 匹配。

写 / 改 skill 的 description（触发描述）时遵循：

- **固定格式（三组件硬性约定）**：description 只负责路由（agent 读它决定是否加载正文），三组件 +
  顺序 + 标记固定，槽内措辞自由：①**场景一句**（"当用户……时使用本 skill" + 干什么 + 关键能力）；
  ②**触发：** 用户原话 / 场景描述（主动句式；防 undertrigger 的触发声明落此槽；保留英文原话，标记
  用中文）；③**不适用：** 负例。
- **写法基线**：祈使语气（"Use this skill for…" 而非 "this skill does…"）；聚焦用户意图而非实现
  细节；有辨识度：和别的 skill 争夺 agent 注意力，写得独特、一眼能认出来。
- **长度**：约 100–200 词（中文按 1 词 ≈ 1.5–2 字折算）；硬上限 `DESCRIPTION_MAX_CHARS`（见
  `scripts/utils.py`，超出会被截断），保持在上限之内留有余量。
- **别过拟合到具体查询**：从失败里归纳更宽泛的"用户意图类别 / 适用场景"，不逐条列失败 case。
  description 被注入到**所有**查询里且 skill 可能很多，别在单个 description 上占太多篇幅。
- **agent 中立（默认不与具体 agent 强绑定）**：不点名 Claude Code / Qoder / Cursor 等，用泛指
  （"AI coding agent"），点名缩窄触发面、降低寿命。**例外**：skill 针对某 agent 的**特有机制**
  设计时（如 Qoder 的 `.qoder/rules/` type 系统、Claude Code 的 hooks / `@import` 递归展开），点名
  是准确而非违规，但正文要讲清"为什么必须点名"。
- **不写工作流摘要**：只列"用户意图类别 + 关键能力 + 触发场景"，不写"先做 X → 再做 Y"步骤序列。
  步骤属 SKILL.md 正文，写进 description 会让 agent 当 shortcut 跳读正文、丢失"为什么"与例外处理。
  **界限**：列能力清单 / 入口列表允许；按顺序串讲成步骤禁止。
- **防 undertrigger（写"主动"而非"被动"）**：agent 普遍有**少触发**倾向，写完"这 skill 干什么"后
  补一段**主动触发声明**：把相关表述、具体场景、甚至"用户没显式提 skill 名但明显需要它"的情形都
  列进去，用"只要用户提到 X / 想 Y / 需要 Z，即使没明说，也务必使用本 skill"句式收口。改写示例：
  被动句 "如何构建一个简单快速的面板来展示内部数据" → "如何构建简单快速的面板来展示内部数据。
  **只要用户提到 dashboard / 数据可视化 / 内部指标，或想展示任何公司数据，即使没明说'面板'，也
  务必使用本 skill**"。
- **迭代策略**：同一思路连续失败就换句式 / 换措辞，别钻牛角尖；多轮迭代里换不同风格尝试，最终
  只取最高分那版。

## 正文写作原则

> 审计检查操作见文件末尾 [章节](#审计速查)。写作时跳过，只在执行入口 4（原则校验）时查表执行。

写 / 改 SKILL.md 正文时遵循：

### 结构与加载

- **progressive disclosure 三级加载**（层级定义见
  [progressive disclosure](skill-template-guide.md#progressive-disclosure三级加载)，此处不重抄）：**正文长度权威上限 = `BODY_WORD_LIMIT` 词**（本仓库只在
  `scripts/utils.py` 给该指标，其它位置只引用不重抄；判定见[章节](#审计速查) BODY-LENGTH 行）；接近上限就抽一层到
  `ref/` 并写明"何时去读"；reference 一律不手写目录（TOC），agent 全量读入正文不看 TOC，目录只对浏览器 /
   编辑器有效（编辑器可按标题自动生成）。引用 `scripts/` / `ref/` / `assets/` 时一律说明何时去读。
- **长度软目标**：按 skill 类型分档的软目标在 `scripts/utils.py::SOFT_WORD_TARGETS`（default /
  reference / meta 三档，meta 不设上限），不取代 `BODY_WORD_LIMIT` 硬上限；判定见[章节](#审计速查)BODY-LENGTH
  行。高频触发的 skill 可由作者自愿再收紧一档，脚本不为其另设档位（避免为一次性偏好增加配置面）。
- **正文超长根因诊断**：超长时先查根因再删字：同一规则多处重抄 → 删重留指针；单步 /
  大样例未下放 → 挪 `ref/`。抽层直接拆 ref/ 文件，禁用 HTML `<details>` 折叠块；
  处置顺序见[修法优先级](#归属与下放)。
- **正文应覆盖（骨架 SSOT 在脚本常量）**：规范 H2 节名、顺序、各类型可省略规则见
  `scripts/utils.py::CANONICAL_BODY_SECTIONS`，此处与其它 prose 一律不重抄节名列表。可 `cp` 填充的
  骨架见 `assets/skill-template.md`；各类型适配见 [章节](skill-template-guide.md#变体各类型的骨架适配)。
- **selection 归 description，正文不设“何时不使用”节**：路由层负例（该不该用本 skill）全部
  进 frontmatter description 的“不适用”槽，正文是触发后才加载的，承载不了 selection 信息；
  反向同样成立：触发语 / 路由结论不写回正文（description 常驻上下文，正文复述 = 同文档双写；
  权限 / 纪律句在执行点的重述除外，归删除测试）。
  执行期边界（做本职工作时遇到毗邻情形怎么处理）归“执行原则 / 边界”，流程内分流归
  “工作流 / 步骤”（归位口径见 [章节](skill-template-guide.md#正文骨架canonical-节)末段）。
- **引用深度硬上限（one level deep）**：所有 reference 必须从 SKILL.md 直接挂；`ref/a.md →
  ref/b.md` 作**加载链**（"不读 b 就无法执行 a 的步骤"）**禁止**：agent 嵌套引用时用
  `head -100` 预览会丢信息。**例外**：CLI 字面拷贝模板；**SSOT 路标**：a.md 写"权威定义在 `b.md`
  §Y"式指路不算加载链，前提 b.md 也已从 SKILL.md 直接挂载。

### 单一真源（SSOT）

- **指标单一来源**：任何指标（字数、字符上限、阈值、轮数等）只在一处给权威值，其它位置只引用不
  重抄，数字散落多处 = 改一处要记得同步全部，极易漏改。脚本常量作 SSOT 时（Python 顶部
  `CONST = value`），prose **必须**用常量名引用（`` `PAGE_SIZE_THRESHOLD` ``），**禁止**写字面量
  （"300 行" / "500 条" / 裸版本号）。
- **自包含例外**：CLI 字面拷贝模板与字面量 fixture（字节级对比金标准）无法跨仓引用，允许
  自包含，但**必须**带注释指明"与哪份 SSOT 重复 + 自包含理由 + 改 SSOT 时同步改本段"，
  缺失 = 无意识重抄。

### 跨 skill 边界

- **依赖单向（避免双向依赖 / 成环）**：skill 间依赖（"转交 / 调用 / 产物交给 X 消费 / 风格对齐 X"
  等措辞）必须构成 DAG。A 依赖 B 时 B 不得反过来依赖 A，否则任务按错方向转交、演进互相锁死。
  `scripts/check_skill_dependencies.py` 只筛查"互相提及"候选对（互提 ≠ 互依，分工转交 / 风格对齐是
  良性的），方向是语义判断。确需双向协作时，把分工约定集中写在**一处**（根 `AGENTS.md`"跨 skill
  协作约定"）。
- **跨 skill 指称（单向提及一律模糊化）**：除真实功能依赖（A 离开 B 无法执行，显式保留）外，
  单向提及（路由指针 / 功能指称 / 题材点名 / 引文）一律模糊化为 `XX` 或删；基线期望零提及。
  逐条归因用 `scripts/check_skill_dependencies.py` 的 `one_way` 输出。
- **相对路径引用禁止**：markdown 链接只能指向本 skill 目录内文件；跨 skill 相对路径
  （`../../other-skill/...`）在独立分发（npx / vendored 副本）下会因对方目录重构**无声断裂**，需要
  时用纯文本"X 侧 spec §Y"描述，不带链接。

### 引用约定

仓内引用按"指什么"选语法。出处标 external（外部背书，优先于仓内先例）或 house（本仓自选）：

| 指什么 | 语法 | 出处 |
| --- | --- | --- |
| 节（同文件） | `[章节](#slug)` | external：GitHub section links；slug = 小写 + 去标点 + 每空格一个连字符 |
| 节（跨文件） | `[章节](ref/x.md#slug)` | external：同上；链接目标基准 = 所在文件目录 |
| 文件（操作指令） | 反引号相对路径，基准 = skill 根；cwd 不是 skill 根时文中明示（"从本文件目录运行"） | external：agentskills.io spec + Anthropic forms.md 实践 |
| 术语 / 规则名 / 强调 | “” | external：GB/T 15834 |
| 命令 / 文件名 / 代码 | 反引号 | markdown 惯例 |

- **文本不抄 slug**：agent 读 raw 不渲染，slug 已承载标题名，文本再抄一遍是双写噪音；文本默认用
  “章节”类泛指向词，仅在承载 slug 之外的增量时保留具名：区分一对锚点的短 handle（Step 4 / Step 6）、
  指向节内条目时写条目名（slug 是父节，如“跨 skill 指称”）。例外：assets/ 模板的交付文档面向
  渲染态人类读者（设计评审），文本用全名
- **链接是校验通道**：`scripts/check_anchor_health.py` 校验一切链接目标与锚点，指针漂移必报
  DEAD-LINK / ANCHOR-DRIFT；不被链接承载的文字引用在校验之外，少用。code fence 内示例路径豁免
  （target 本就不该存在）
- **直角引号退役**（house，2026-09）：corner bracket 的节名指针无外部背书、不被任何标准模板采用、
  无法靠校验兜底，仓内归零后不得再出现；节指针一律改链接
- **步骤引用**：跨节必须带名（`[Step 4](#step-4-形态路由)`），裸序号与序号区间
  （"Step 4–6"）禁止；同一工作流节内兄弟互指可裸序号（house：自含块惯例）
- **改节标题后**跑 `scripts/check_anchor_health.py`，按 ANCHOR-DRIFT 清零
- **行号引用**禁止（漂移最快、无任何校验通道）

### 方法论（写前 / 形式）

- **Iron Law（没观察到失败就别写 skill）**：写纪律型 / 模式型 / 参考型 skill 前必须先**不带 skill
  跑典型 prompt 观察失败**（条数权威值在 [章节](../SKILL.md#baseline-演练red-阶段)，此处不重抄），把
  agent 的违规与借口（"为简化" / "用户没说明" / "这样更快" / "应该等价"）
  **原样**抄进 Rationalization Table 输入池。没观察到失败就写 = 赌运气。按 **RED**（观察失败）→
  **GREEN**（写**最小** skill 堵刚看到的违规，不预堵假想漏洞）→ **REFACTOR**（重跑同一批 prompt
  确认每条违规被堵住，漏了回 GREEN）迭代。**适用于 EDITS，与新建同标准**（edit 未先跑当前版本记录
  失败 = 未经验证，丢弃回 RED）。纯参考资料型（只聚合信息、不改变行为决策）不强制 baseline。
- **形式匹配失败（prohibition vs recipe vs reference）**：从 RED transcript 判定失败类型再选形式：
  **纪律失败**（知道但懒 / 找借口绕开）→ **结构性禁令**（纪律型）+ 三件套（见下条）；**塑形失败**
  （想做但不会）→ **配方式步骤**（模式型：具体步骤 + 例子 + 何时用）；**知识失败**（不知道 / 引用错
  地方）→ **参考资料式**（参考型：聚合文档 + 链接 + 索引）。**禁止 nuance / 例外条款**：写禁令不要
  加 "if convenient" / "unless..." / "in most cases"，开口子就是给借口开口子；纪律禁令要么写、
  要么不写，没有"软版本"。
- **反合理化（仅限纪律型 skill）**：纪律型 skill 必须内嵌**三件套**堵借口漏洞：①**Rationalization
  Table**：RED transcript 里 agent **实际说过的**借口逐条配"为什么错 / 应改做什么"，不预写"可能存在
  的"借口；②**"违反字面 = 违反精神"**：明确写违反字面表述（含任何效果一致的绕法）= 违反精神，
  禁止"严格按字面 / 严格按精神"二选一措辞；③**Red Flags list**："出现这些念头 = 你正在找借口，
  停下重读"（红旗是**念头**而非行为：念头出现 = 警告，不是已违反）。模式型 / 参考型不需要；元 /
  多入口 skill（读者学方法论、不面对执行压力）可豁免。
- **无意外原则**：不建恶意 / 误导性 skill：description 声称做 A、实际诱导做 B（钓鱼 / 未授权访问 /
  数据外泄）直接拒绝，内容意图与描述一致；"扮演 X 角色"类 roleplay skill 允许（娱乐 / 教育正当）。
  创建流程第一步就审视用户请求是否符合此原则。

### 归属与下放

- **修法优先级**（正文超长 / 冗余处置顺序）：**(0) 机械操作 → 固化进脚本**（零判断字节
  操作过“机械操作脚本化”准入规则，直接消除 prose，优于一切挪位）→ (1) 挪 ref/
  → (2) 挪 tool help（`Run --help for
  details.` 替列所有 flag）→ (3) 交叉引用 → (4) 跨 skill 引用（**REQUIRED SUB-SKILL:** 替复述，
  **禁用 `@` 强制加载**）→ (5) 压示例 → (6) 删字（高风险，最后手段）。
- **机械操作脚本化（scripts 持有形式，md 持有判断）**：任何内容写进 skill 前先过**脚本化测试**：
  "能用脚本钉死吗？能 → 为什么没钉？"**归属默认是脚本，prose 留存要举证**，合法残留只有两类：
  **(1) 含不可枚举判断维度的任务引导**：判据是可枚举性而非复杂度（复杂但确定性的流程仍归
  脚本；简单但需判断的决策仍归 md）；**(2) 路由 / 胶水层**：description、"跑 X 命令"调用行、
  "何时去读"指针、"为什么"。账本：prose 每次触发全额占用 context，脚本实现细节永不进 context；
  prose 的正确性只能靠 eval 抽样（概率性、贵、低覆盖），脚本能靠测试（确定性、免费、全分支）：
  同一功能能用脚本表达，正确性保证就是跨维度地强。零判断的字节操作（严格格式行 / 字段增删 /
  从 frontmatter 派生条目）用 md 纪律文本维持 = 三层成本（"md 写规则 → agent 手工执行 → lint
  兜底"），且每层都在说话（正文"多且杂"的主因）。准入规则：**(1)
  输出字节是输入的纯函数**（不读正文内容、无权衡、无用户偏好）；**(2) lint 已有对应
  检查可验证产物**（round-trip 可测），两条都满足 → 固化进脚本（writer 子命令），md
  只留一句"跑 X 命令"；缺一 → 留 md 约束（摘要写作、语义合并、是否值得做这类判断永远属
  md）。**逃生舱**：手写始终合法、检查器守门，脚本是默认路径不是闸门。**格式流动期
  例外**：迁移 / 升级路径上的写操作一律 agent（脚本只认识当前形态，硬编码 = 探测器要
  同时理解新旧形态）。**推论**：md 大段重述脚本已实现的机制细节（算法 / 分支条件 /
  内部函数名）= 跨体裁重抄：机制归脚本 docstring，md 只留口径（是什么 / 严重性 / 怎么
  修）。**验收**：脚本改动不等于 ruff / lint 通过，静态检查只证明代码能跑、canary 只证明测量通道
  活着，都不证明判定逻辑对；新建或大改脚本必须配打桩冒烟（不依赖模型实跑、秒级），且**正反两向都钉**
  （脏 fixture 必须命中、干净 fixture 必须静默），只钉单向的检查器"永远报警"也算全绿。既有冒烟见
  `tests/smoke_test_*.py`。批量改写源码（按偏移 / 正则跨行替换）另有一条：**先留行为基线、改完对基线**，
  lint 绿不代表没吃掉内容（本仓一次批量改参数把两个脚本咬出语法洞，靠基线 diff 才发现）。
- **脚本化的代价核对（纯函数只是准入，不是理由）**：过两问之后还要算一笔账：
  **context 节省 × 频率** 是否高于新增代码的长期成本（脚本行数 + 抑误报的豁免清单 + 配套冒烟）。
  三类典型不值得，共同点都是 **context 节省 ≈ 0**：一条 `mkdir -p && cp -r` 就能做完的字节操作
  （md 本就一行命令，脚本比命令更长）；判定 100% 靠人、模式又是一行 alternation 的 grep
  （判断照样在 context 里发生，脚本只省一次复制粘贴）；为低频动作建的脚手架（一年跑两次，
  节省可忽略）。**启发式检查器另算**：
  它的真实成本不在规则而在**永远在长的豁免清单**，加规则前先估计本仓实跑的误报数，误报需人工
  复核的   只给 INFO 级，不升 ERROR。

## 审计速查

执行入口 4（原则校验）时逐条跑；判定为违规即报。

**机械项不必手打**：`python -m scripts.verify <skill-dir> --tier <type>` 一次跑完下表里能被程序化的
行（各行的检查列已写明由哪个脚本 / 哪个规则 ID 负责，输出统一 `LEVEL: 文件:行 证据 —— 修法`）。
**本表的价值在"判定"列**：脚本只出候选与证据，是否违规照该行判定口径由 agent 判；标着 grep 的行
= 脚本不做、逐条手工执行（原因见[脚本化的代价核对](#归属与下放)）。

**审查分工**：本表与 verify 只管**机制合规**；md 的散文质量审查归 yzr-writing-review（其
catalog“指令文档”组是为 agent 读者文档设计的场景卡），`scripts/*.py` 的审查归
yzr-coding-review。

### 审查深度标准（入口 4 默认口径）

> 用户要求"最严 / 仔细审查"时按此口径执行。散文层不在此审，转交 yzr-writing-review
> （见上 [审查分工](#审计速查)）。

- **全量范围**：`SKILL.md` + `ref/`（存量 `references/`）+ `scripts/` + `assets/` + `eval/` 每个文件逐行
  读，无抽样；`ref/canonical/` 与 `fixtures/*.txt` 是字节金标准，不碰内容，只审
  自包含注释（"与哪份 SSOT 重复 + 理由"）是否齐全
- **正确性以验证证据为准**：纪律型 / 模式型内容无 baseline / eval 证据时按"未经验证"报，
  审计者不凭精读断言其对错
- **报告只活在对话里**：用户没主动要 audit 文档时不建 `audit-*.md` 之类的归档文件、也不写
  MEMORY 历史，结论在回复里、修复在文件里，归档件只会变成无人维护的第二真源
- **修复流**：逐项等用户确认 → 修（只动仓库源，不手拷 vendored）→ `python -m scripts.verify
  <skill-dir>` 验证（改了脚本再手跑 `tests/smoke_test_*.py`）→ commit + push（用户经 npx
  同步 vendored）→ git 确认

| 原则 | 检查 | 判定 |
| --- | --- | --- |
| agent 中立 | `grep -ni "claude \?code\|qoder\|cursor\|windsurf\|codex"` | 命中逐处复核：特有机制点名 OK，可泛化却写死 → 改泛指 |
| 指标单一来源 | `python -m scripts.audit_prose <skill-dir>`（BARE-METRIC：同 skill 内同 `<数字><单位>` 跨 ≥ 2 文件） | INFO 候选 → 定权威源：脚本常量则 prose 改 `` `CONST` `` 引用，prose 则留一处其余改指针；跨 skill 的同名数字不算（各自独立演进） |
| 何时不使用节 | `python -m scripts.quick_validate <skill-dir>`（WHEN-NOT-SECTION） | 命中即报，selection 信息归 description“不适用”槽，按[章节](#结构与加载) selection 条迁移 |
| 触发语不回正文 | 人工：正文逐句问"管何时调还是怎么用"；比对须含 frontmatter description（常驻上下文） | 何时调内容（触发语 / 路由结论）出现在正文 = 违规，删或迁回 description；权限 / 纪律句在执行点的重述不算此条（口径在 yzr-writing-review 第八组判定注三） |
| reference 禁手写目录 | `python -m scripts.quick_validate <skill-dir>`（HAND-TOC WARN） | 命中即报，agent 全量读入不看 TOC，目录只对浏览器 / 编辑器有效 |
| 机械操作脚本化 | 语义检查：每段 prose 先过脚本化测试（"能用脚本钉死吗？能 → 为什么没钉？"），工作流步骤里"格式严格 / 必须按 X 格式写 / 手工同步"类纪律是高嫌疑起点；候选逐条过准入两问 + “脚本化的代价核对”那笔账 | 过准入 + 代价核对仍以 prose 承载、且无保留理由（判断引导 / 路由胶水 / context 节省 ≈ 0）→ 报"应脚本化"；md 重述脚本机制细节 → 报"机制挪 docstring"；纯函数但不值脚本成本的（低频 / 一行命令可代 / 判定全靠人）→ 报"过度固化"；脚本改动无打桩冒烟 → 报"验收缺失" |
| 依赖单向 | `python -m scripts.check_skill_dependencies <repo-root>` | 互提候选对 → 人工判方向，双向依赖 = 违规 |
| 跨 skill 指称 | `python -m scripts.check_skill_dependencies <repo-root>`（看 `one_way` 输出） | 判定口径见正文 [跨 skill 指称](#跨-skill-边界)原则，逐条归因，命中即报 |
| 相对路径禁止 | `python -m scripts.check_anchor_health <skill-dir>`（DEAD-LINK 覆盖 markdown 链接逃逸；CROSS-SKILL-PATH 覆盖反引号路径逃逸） | 出现即违规，改纯文本"X 侧 spec §Y"式描述 |
| 链接基准 | `python -m scripts.check_anchor_health --repo-root`（`--json` / `--include-templates`） | 有输出即修；code fence 教学示例豁免 |
| Iron Law 证据 | `grep -n "迭代\|baseline\|transcript\|RED\|GREEN\|REFACTOR"` | 纪律 / 模式型无命中 = 按"未经验证"标注 |
| Iron Law（粗筛） | `grep -rn "iteration-[0-9]\+\|without_skill\|old_skill" <workspace>/` | 命中 = 有 baseline 痕迹 |
| 反合理化三件套 | `grep -n "NEVER\|ALWAYS\|必须\|禁止\|不能\|不得"` + `grep -n "Rationalization\|合理化\|Red \?Flag\|红旗\|违反字面"` | 纪律型：前者命中而三件套缺任一 = 不合规（型态判定归人，见[反合理化](#方法论写前--形式)适用范围） |
| 长度软目标 | `python -m scripts.quick_validate <skill-dir> --tier <t>`（BODY-LENGTH，CJK / ASCII 分别折算） | 超软目标 = WARN 偏臃肿；超 `BODY_WORD_LIMIT` = 违规（估算值是代理指标，不据此自动 fail） |
| 时间性信息不内联 | `python -m scripts.audit_prose <skill-dir>`（VERSION-HISTORY-INLINE） | INFO 候选：自身演进史 = 违规（判定口径与版本约束例外见 yzr-writing-review `Instr.I4`，规则真源在该卡）；引语内示例豁免已由脚本处理，剩余命中人工判 |
