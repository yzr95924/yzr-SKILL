---
name: yzr-multi-agent-context
description: 在用户想把一个工程的上下文变成「AGENTS.md 作单一真源（SSOT）、对多个 agent 兼容」时使用
  本 skill——两条路径归约到同一份工具无关的 AGENTS.md：① 有 CLAUDE.md（+可选 MEMORY/）→ 去品牌迁移、
  CLAUDE.md 收敛成薄壳；② 已有 AGENTS.md（可能 +CLAUDE.md 并存）→ 规范化 / 合并去重。AGENTS.md 是跨
  agent 标准，Claude Code 经薄壳 @AGENTS.md 引入，Codex / Qoder 原生直读；L2 记忆索引内联进正文（不靠
  @MEMORY import——Claude 专属，Codex / Qoder 不展开），三家读正文即见全部记忆。结果一套真源、Claude
  Code / Codex / Qoder 三家共存。适用：用户说「把 CLAUDE.md 转 AGENTS.md / CLAUDE.md 和 AGENTS.md 共存
  / 让项目在 Codex / Qoder 里也能跑 / 已有 AGENTS.md 想规范化 / 多工具共存」。不适用：迁移权限
  settings.local.json、改 MCP 配置、改 scripts/references/eval/、删掉 CLAUDE.md（保留薄壳共存）、迁向
  不读 AGENTS.md 的 agent、生成 agent 专属触发式 rule 文件（如 .qoder/rules/）、解析 Cursor .cursor/rules
  或 Gemini GEMINI.md 等专属格式（先手动转成 AGENTS.md / CLAUDE.md 再来）、裸项目从零生成（既无 CLAUDE.md
  又无 AGENTS.md——先用 agent 的 /init 生成初始上下文再来）。
metadata:
  author: Zuoru YANG
  category: project-config
  last_modified: 2026-07-11
---

# AGENTS.md 作单一真源（CLAUDE.md 薄壳共存）

把一个工程的项目上下文归约成「**AGENTS.md 作单一真源（SSOT）、对多个 agent 兼容**」——不管源是
`CLAUDE.md` 还是已有的 `AGENTS.md`，两条路径收敛到同一份工具无关的 `AGENTS.md`，Claude Code /
Codex / Qoder 各用各的入口加载它，不必维护两份。

## 为什么这样设计

核心是让 **`AGENTS.md` 成为单一真源**：所有项目上下文只在这里维护一份，`CLAUDE.md` 退化成引入它的
薄壳（加少量 Claude 专属逃生舱）。`AGENTS.md` 是跨 agent 的事实标准——任何读它的 agent（Codex / Qoder）
都**原生识别**，无需额外配置（例见 [Qoder 官方 Rules 文档](https://docs.qoder.com/user-guide/rules)
原文：“copy your `AGENTS.md` file to your project directory.
The Agent will automatically recognize and utilize the rules defined in the file”）；Claude Code 则经薄壳
`CLAUDE.md → @AGENTS.md` 引入同一份内容。所以去品牌化的 `AGENTS.md` 单独一步就让 L1 正文对三家可用。

**L2 记忆层是关键陷阱**：`@path` 递归 import 是 **Claude Code 专属**（CLAUDE.md 支持递归展开）；Codex 的
AGENTS.md **不展开** import（openai/codex#17401 未实现），Qoder 也无 import 语法。若把记忆挂在
`@MEMORY/MEMORY.md` 上，Codex / Qoder 只看到一个裸字符串，**整个 `MEMORY/` 对它们不可见**——“真源”
只在 L1 兑现，L2 成了 Claude 独享。故本 skill 把 `MEMORY.md` 索引**内联**进 AGENTS.md 正文（R2）+
自然语言 Read 指引：三家读正文即见全部记忆条目摘要，质变（知道记忆存在）交给机制，量变（读正文）
由 Read 指引引导 agent 按需 `Read`。

三家兼容性矩阵：

| 层 | Claude Code | Codex | Qoder |
|---|---|---|---|
| L1 AGENTS.md 正文 | 经薄壳 `@AGENTS.md` | 原生读 | 原生读 |
| L2 记忆索引（内联） | 读正文即见 | 读正文即见 | 读正文即见 |
| L2 记忆正文 | 按需 Read | 按需 Read | 按需 Read |
| 触发式 rule | 不涉及（全读） | 层级 AGENTS.md | `.qoder/rules/`（本 skill 不生成） |

## 何时使用 / 不使用

### 使用

- 用户说「把 CLAUDE.md 迁移成 AGENTS.md / 让项目在 Qoder / Codex 里也能用 / 多工具共存 / agent 上下文迁移」
- 用户从 Claude Code 切到读 AGENTS.md 的 agent（如 Qoder / Codex），或想让多个 IDE 同时用同一个项目
- 项目已有 `AGENTS.md`（手写 / 别的工具生成 / 之前部分迁移），想规范化成多 agent 通用标准——去品牌、
  补 L2 记忆内联、合并并存的 `CLAUDE.md`
- 项目根有 `CLAUDE.md`（带或不带 `MEMORY/`），想生成跨 agent 通用的 `AGENTS.md`

### 不使用

- **迁移权限**（`.claude/settings.local.json`）或 **MCP 配置**——本 skill 不碰，两者工具专属且敏感
- **改 `scripts/` / `references/` / `eval/`**——只动上下文文件（CLAUDE.md / AGENTS.md / MEMORY）
- **删掉 `CLAUDE.md`**——本 skill 保留薄壳共存；若用户想只用读 AGENTS.md 的 agent、彻底删 CLAUDE.md，需显式确认
- **迁向不读 `AGENTS.md` 的 agent**——本 skill 主路径（生成通用 `AGENTS.md`）对任何读 `AGENTS.md`
  的 agent（Qoder / Codex 等）都成立；只有目标 agent 完全不读 `AGENTS.md`（只认自家专属上下文格式）
  时才不适用
- **生成 agent 专属触发式 rule 文件**（如 Qoder 的 `.qoder/rules/`）——那类机制官方多未文档化，交给
  用户在目标 agent IDE 里自行配置；本 skill 只产 `AGENTS.md` + 薄壳 `CLAUDE.md` + `MEMORY/`
- **解析 agent 专属触发式 / 格式**（Cursor 的 `.cursor/rules/*.mdc`、Gemini 的 `GEMINI.md`、
  Windsurf 的 `.windsurfrules` 等）——格式各异且多带触发条件，本 skill 不解析；先手动转成
  `AGENTS.md` 或 `CLAUDE.md` 再走对应路径
- **裸项目从零生成**（既无 `CLAUDE.md` 又无 `AGENTS.md`）——本 skill 只归约**已有**的 agent 上下文；
  裸项目请先用 agent 自带的 `/init` 生成初始 `CLAUDE.md` / `AGENTS.md`，再来归约成多 agent 通用

## 输入 / 输出

### 输入

| 输入 | 必需 | 说明 |
| --- | --- | --- |
| 项目根目录 | 是 | 默认 cwd；两条路径之一：含 `CLAUDE.md` / 含 `AGENTS.md`（都没有→先用 `/init`） |
| `MEMORY/` | 否 | 存在则一并去品牌化（Step 3）；不存在跳过 |
| 源文件快照 | 自动 | Step 1 自动快照源（CLAUDE.md / AGENTS.md）到 `.migration-backup/`，供 Step 5 覆盖率比对 |

### 输出

```text
<project-root>/
├── AGENTS.md                 新/改：工具无关真源（agent 原生读 + Claude Code 经薄壳引入）
├── CLAUDE.md                 薄壳（@AGENTS.md + <!-- Claude Code 专属 --> 逃生舱）——让 Claude Code 也
│                             加载同一份 AGENTS.md；有现有 CLAUDE.md 则改写，纯 AGENTS.md 项目则新建最小薄壳
├── MEMORY/                   改：去品牌化（R4，结构与文件数不变）
└── .migration-backup/        自动：源文件快照 + 迁移 / 覆盖率报告
```

## 两条路径（前置检测路由）

`precheck.py` 检测项目状态，路由到两条归约路径之一——两条**共享后半段**（去品牌 R1–R5 + L2 内联 R2 +
覆盖率验证），只前半段（源提取）不同：

| 项目状态 | 路径 | 前半段（源提取） |
|---|---|---|
| 有 `CLAUDE.md`，无 `AGENTS.md` | **1 迁移** | 扫描 CLAUDE.md 段落分类 → 去品牌（现有流程） |
| 有 `AGENTS.md`（可能 +`CLAUDE.md`） | **2 规范化** | 诊断现有 AGENTS.md（品牌残留？L2 内联？）+ 合并存 CLAUDE.md，冲突让用户裁定；清单见 [`references/rewrite-rules.md`](references/rewrite-rules.md) |
| 都没有（裸项目） | 硬阻塞 | 不在本 skill 范围——先用 agent 的 `/init` 生成初始 `CLAUDE.md` / `AGENTS.md` 再来 |

两条都收敛到同一份工具无关 `AGENTS.md` SSOT，并产出 `CLAUDE.md` 薄壳让 Claude Code 也加载同一份内容。

## 核心设计：薄壳共存

```text
AGENTS.md                    唯一真源（工具无关，人工维护的唯一目标）
  └── ## 跨会话记忆（索引）  MEMORY.md 索引内联进正文（R2）+ Read 指引

CLAUDE.md                    薄壳（自动生成，不需要人工维护）
  ├── @AGENTS.md             引入全部共用内容
  └── <!-- Claude Code 专属 -->  几行无法泛化的工具绑定内容（如有）
```

**信息流**（三家统一）：任一 agent 启动 → 读 `AGENTS.md` 正文（含内联记忆索引）→ 按需 `Read`
`MEMORY/<slug>.md` 正文。Claude Code 的入口多一层薄壳：`CLAUDE.md → @AGENTS.md` 展开；Codex / Qoder
原生读 `AGENTS.md`。三家都不依赖 `@MEMORY` import（那是 Claude 专属，另两家不展开）。

完整分层模型（L1 常驻 / L2 记忆）与**段落分层决策树**见
[`references/layering.md`](references/layering.md)——Step 1 给段落分类时读它。

## 执行原则 / 边界

### 改写规则 R1–R5（摘要）

- **R1 工具无关化**：去品牌、不改事实。完整替换表（`Claude Code` → `AI coding agent`、
  `claude -p` → `agent CLI` 等，含"何时保留工具名"判定）见
  [`references/rewrite-rules.md`](references/rewrite-rules.md)——Step 2 / 3 改写时对照。
- **R2 记忆索引内联**：`MEMORY.md` 全部索引行 inline 进 `AGENTS.md` 的 `## 跨会话记忆` 段落 + Read 指引，
  **不**写 `@MEMORY/MEMORY.md`。理由：`@import` 是 Claude Code 专属，Codex / Qoder 不展开 → 靠 import
  挂 L2 会让 `MEMORY/` 对后两家不可见。内联后三家读正文即见全部记忆条目（详见
  [`references/rewrite-rules.md`](references/rewrite-rules.md) R2）。
- **R3 行宽不变**：原文遵守的行宽约束（≤ 120 字符）改写后继续遵守。
- **R4 MEMORY 改写**：MEMORY 正文按 R1 去品牌；目录结构和文件数量不变。
- **R5 逃生舱**：无法泛化的工具专属内容（如脚本硬编码 `claude -p` 子进程），在 AGENTS.md 写泛化版、
  在 CLAUDE.md 薄壳尾部追加具体实现。**判定标准**：去掉工具名后读者无法执行该操作 → 进逃生舱。

### 边界

- 不碰权限 / MCP / `scripts` / `references` / `eval`
- 不删 `CLAUDE.md`（薄壳共存）；彻底删需用户显式确认
- 不生成 agent 专属触发式 rule 文件（`.qoder/rules/` 等）——交给用户在目标 agent IDE 配置
- **幂等**：重复运行覆盖已有 `AGENTS.md`，不产生重复文件

## 工作流 / 步骤

> 贯穿全程：分类表（Step 1）、逃生舱内容（Step 4）两处**交互确认点**，不要静默决断。

### Step 0：前置检查 + 路径判定（跑 `scripts/precheck.py`）

```bash
python3 scripts/precheck.py <project-root>
```

报告项目状态并判定路径：① 有 `CLAUDE.md` 无 `AGENTS.md` → 路径 1（迁移）；② 有 `AGENTS.md`（可能
+`CLAUDE.md`）→ 路径 2（规范化）；都没有 → 硬阻塞，提示先用 `/init`。同时报告 `MEMORY/` 是否存在。
**路径 2 修改现有 `AGENTS.md`（规范化 / 合并并存 `CLAUDE.md`）时停下来让用户确认合并策略**，绝不静默覆盖。

### Step 1：快照 + 源提取（按路径分支）

1. 快照源文件到 `.migration-backup/`（路径 1 快照 `CLAUDE.md`；路径 2 快照原 `AGENTS.md`，并存
   `CLAUDE.md` 时一并快照）——Step 5 覆盖率比对要用，这是**唯一机会**。
2. 按路径提取源内容：
   - **路径 1**：解析 `CLAUDE.md` 所有 `##` 段落，跑 [`references/layering.md`](references/layering.md) 分层决策树。
   - **路径 2**：对现有 `AGENTS.md` 跑 [`references/rewrite-rules.md`](references/rewrite-rules.md) 的**规范化诊断清单**
     （品牌残留？有无 L2 记忆内联？有无 MEMORY 支持？）；若 `CLAUDE.md` 并存，一并解析按层决策树合并。
3. 输出分类 / 诊断表，**展示给用户确认 / 调整**再继续。

### Step 2：生成 AGENTS.md（LLM，核心步）

1. 按 [`references/layering.md`](references/layering.md) 的 AGENTS.md 骨架组织 L1 内容
   （项目定位 / 仓库规约 / 常用命令 / 高层结构 / 注意事项）。
   - **路径 1**：CLAUDE.md 段落去品牌改写入骨架。
   - **路径 2**：在现有 AGENTS.md 基础上规范化（补 L2 内联、去品牌残留、合并 CLAUDE.md 内容去重），
     冲突口径让用户裁定。
2. 加 `## 跨会话记忆（索引）` 段落：把 `MEMORY.md` 全部索引行 inline 进正文 + 段末 Read 指引（R2）。
   **不**写 `@MEMORY/MEMORY.md`（Claude 专属，Codex / Qoder 不展开）。无 `MEMORY/` 时省略本段。
3. 应用 R1（去品牌）+ R3（行宽）。
4. 控制正文词数 ≤ 1500 词（L1 预算，记忆索引段不计入）；超出把详细内容下沉到 L2（`MEMORY/`）。
5. 自检：`grep -iE "claude code|\.claude/" AGENTS.md` 应无命中；`grep -n '@MEMORY' AGENTS.md` 应无命中。

### Step 3：改写 MEMORY（LLM，如存在）

应用 R4：MEMORY 正文按 R1 去品牌，目录结构 / 文件数量不变。
自检：`grep -riE "claude code|Claude Code|\bCC\b" MEMORY/` 应无命中（`\bCC\b` 避免误伤缩写）。

### Step 4：生成 CLAUDE.md 薄壳

让 Claude Code 也能加载同一份 `AGENTS.md`：有现有 `CLAUDE.md`（路径 1；路径 2 并存场景）则改写成薄壳；
纯 `AGENTS.md` 项目（路径 2 无 CLAUDE.md）则新建最小薄壳。按 [`references/rewrite-rules.md`](references/rewrite-rules.md)
的薄壳模板：顶部「薄壳声明」（点明 AGENTS.md 是单一真源、勿在此编辑共用部分）+ `@AGENTS.md` +
`<!-- Claude Code 专属 -->` 逃生舱（Step 2 识别出的 TOOL_SPECIFIC 内容，按 R5 处理）。没有逃生舱内容就省略注释块。
**逃生舱内容展示给用户确认。** 自检：总行数 ≤ 30、`@AGENTS.md` 存在、顶部含薄壳声明、除声明 / @import / HTML 注释外无大段正文。

### Step 5：覆盖率验证（跑 `scripts/coverage.py`）

```bash
python3 scripts/coverage.py <project-root>
```

拿 Step 1 快照的原 `CLAUDE.md`，逐行 token 比对 `AGENTS.md` + 薄壳 `CLAUDE.md`
（内置去品牌归一化，让 `Claude Code`→`agent` 后仍能匹配），输出未匹配行清单 + 覆盖率 %。
**未匹配行 ≠ 一定丢失**——可能是去品牌改写或合理下沉；逐条与用户确认是丢失还是改写。
覆盖率 100% 是目标。最后跑 `markdownlint` 检查所有新 / 改文件 0 error。

## 参考样例

两条路径各有 fixture（见 `eval/evals.json`）：路径 1 用本仓库自身的 `CLAUDE.md` + `MEMORY/`（真实复杂）；
路径 2 用 `eval/fixtures/` 下的合成项目。骨架模板（AGENTS.md 骨架、CLAUDE.md 薄壳模板、路径 2 规范化
诊断清单）分别在 [`references/layering.md`](references/layering.md) /
[`references/rewrite-rules.md`](references/rewrite-rules.md)，按需 Read。
