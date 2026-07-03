---
name: claude-to-agents-ssot
description: 在用户想让一个 Claude Code 项目的上下文变成「AGENTS.md 作单一真源（SSOT）、
  CLAUDE.md 收敛成只含 Claude 强绑定内容的薄壳」时使用本 skill——生成工具无关的 AGENTS.md
  （Claude Code 经薄壳 CLAUDE.md 的 @AGENTS.md 引入；读 AGENTS.md 的 agent 如 Qoder 可原生直读），
  把 CLAUDE.md 改成只留 @import + 少量无法泛化的 Claude 专属内容（逃生舱），对正文与 MEMORY 去品牌化。
  结果一套真源、Claude Code 与读 AGENTS.md 的 agent 双工具共存,
  不必维护两份。适用：用户说「把 CLAUDE.md 转 AGENTS.md / CLAUDE.md 和 AGENTS.md 共存 /
  AGENTS.md 当单一真源 / 让这个 Claude 项目在 Qoder 里也能跑 / 双工具共存」。不适用：迁移权限
  settings.local.json、改 MCP 配置、改 scripts/references/eval/、删掉 CLAUDE.md（本 skill 保留薄壳
  共存）、迁向不读 AGENTS.md 的 agent（只认自家专属上下文格式）、生成 agent 专属触发式 rule 文件
  （如 Qoder 的 .qoder/rules/，交给目标 agent IDE 自行配置）、从零建项目上下文（没有 CLAUDE.md 可迁）。
metadata:
  author: Zuoru YANG
  category: project-config
  last_modified: 2026-07-04
---

# AGENTS.md 作单一真源（CLAUDE.md 薄壳共存）

把一个 Claude Code 项目的项目级上下文（`CLAUDE.md` + 可选 `MEMORY/`）重构成「**AGENTS.md 作单一
真源（SSOT）、CLAUDE.md 收敛成只含 Claude 强绑定内容的薄壳**」——一套真源，Claude Code 与读
`AGENTS.md` 的 agent（如 Qoder）各用各的入口加载它，不必维护两份。

## 为什么这样设计

核心是让 **`AGENTS.md` 成为单一真源**：所有项目上下文只在这里维护一份，`CLAUDE.md` 退化成引入它的
薄壳（加少量 Claude 专属逃生舱）。这样 Claude Code（经 `CLAUDE.md → @AGENTS.md`）和任何读
`AGENTS.md` 的 agent 共享同一份内容，改一处即生效。`AGENTS.md` 是跨 agent 的事实标准——
任何读它的 agent（Qoder / Codex 等）都**原生识别**，无需额外配置（例见 [Qoder 官方 Rules 文档](https://docs.qoder.com/user-guide/rules)
原文："copy your `AGENTS.md` file to your project directory.
The Agent will automatically recognize and utilize the rules defined in the file"）。所以去品牌化的
`AGENTS.md` 单独一步就让项目对这些 agent 可用。`@MEMORY/MEMORY.md` 写在
`AGENTS.md` 内（R2），Claude Code 侧经递归 `@` 展开一定加载记忆索引。

## 何时使用 / 不使用

### 使用

- 用户说「把 CLAUDE.md 迁移成 AGENTS.md / 让项目在 Qoder 里也能用 / 双工具共存 / agent 上下文迁移」
- 用户从 Claude Code 切到读 AGENTS.md 的 agent（如 Qoder / Codex），或想让两个 IDE 同时用同一个项目
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
- **从零建项目上下文**（没有现成 CLAUDE.md）——没有源可迁，直接写 `AGENTS.md` 即可，用不上改写流程

## 输入 / 输出

### 输入

| 输入 | 必需 | 说明 |
| --- | --- | --- |
| 项目根目录 | 是 | 默认 cwd；必须含 `CLAUDE.md` |
| `MEMORY/` | 否 | 存在则一并去品牌化（Step 3）；不存在跳过 |
| 原 CLAUDE.md 快照 | 自动 | Step 1 自动快照到 `.migration-backup/CLAUDE.md.original`，供 Step 5 覆盖率比对 |

### 输出

```text
<project-root>/
├── AGENTS.md                 新：工具无关真源（agent 原生读 + Claude Code 经薄壳引入）
├── CLAUDE.md                 改：薄壳（@AGENTS.md + <!-- Claude Code 专属 --> 逃生舱）
├── MEMORY/                   改：去品牌化（R4，结构与文件数不变）
└── .migration-backup/        自动：原 CLAUDE.md + 迁移 / 覆盖率报告
```

## 核心设计：薄壳共存

```text
AGENTS.md                    唯一真源（工具无关，人工维护的唯一目标）
  └── @MEMORY/MEMORY.md      记忆引入（写在 AGENTS.md 内，两边都能加载）

CLAUDE.md                    薄壳（自动生成，不需要人工维护）
  ├── @AGENTS.md             引入全部共用内容
  └── <!-- Claude Code 专属 -->  几行无法泛化的工具绑定内容（如有）
```

**信息流**：Claude Code 启动 → 读 `CLAUDE.md` → `@AGENTS.md` 展开 → `@MEMORY/MEMORY.md` 展开；
读 `AGENTS.md` 的 agent 启动 → 读 `AGENTS.md`（原生）→ `@MEMORY/MEMORY.md` 展开。

完整分层模型（L1 常驻 / L2 记忆）与**段落分层决策树**见
[`references/layering.md`](references/layering.md)——Step 1 给段落分类时读它。

## 执行原则 / 边界

### 改写规则 R1–R5（摘要）

- **R1 工具无关化**：去品牌、不改事实。完整替换表（`Claude Code` → `AI coding agent`、
  `claude -p` → `agent CLI` 等，含"何时保留工具名"判定）见
  [`references/rewrite-rules.md`](references/rewrite-rules.md)——Step 2 / 3 改写时对照。
- **R2 @import 位置**：`@MEMORY/MEMORY.md` 写在 `AGENTS.md` 内（不在 CLAUDE.md）。Claude Code 经
  `@AGENTS.md` 递归展开一定加载；读 `AGENTS.md` 的其它 agent 能否展开内部 `@import` 不确定，但该行
  至少作为显式指针存在（详见 [`references/rewrite-rules.md`](references/rewrite-rules.md) R2）。
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

### Step 0：前置检查（跑 `scripts/precheck.py`）

```bash
python3 scripts/precheck.py <project-root>
```

报告 `CLAUDE.md` 是否就绪、`MEMORY/` 是否存在、是否已有 `AGENTS.md`。
**已有 `AGENTS.md` 时停下来让用户确认覆盖**，绝不静默覆盖。

### Step 1：快照 + 扫描分类

1. 快照原 `CLAUDE.md` 到 `.migration-backup/CLAUDE.md.original`——Step 5 覆盖率比对要用，
   这是**唯一机会**（Step 2 / 4 会改写 / 覆盖 CLAUDE.md）。
2. 解析 `CLAUDE.md` 所有 `##` 段落，对每段跑 [`references/layering.md`](references/layering.md) 的分层决策树。
3. 输出分类表（段落 → 类型 → 层级 → 目标文件），**展示给用户确认 / 调整**再继续。

### Step 2：生成 AGENTS.md（LLM 改写，核心步）

1. 按 [`references/layering.md`](references/layering.md) 的 AGENTS.md 骨架组织 L1 内容
   （项目定位 / 仓库规约 / 常用命令 / 高层结构 / 注意事项）。
2. 标题之后第一行加 `@MEMORY/MEMORY.md`（R2）。
3. 应用 R1（去品牌）+ R3（行宽）。
4. 控制总词数 ≤ 1500 词（L1 预算）；超出把详细内容下沉到 L2（`MEMORY/`）。
5. 自检：`grep -iE "claude code|\.claude/" AGENTS.md` 应无命中。

### Step 3：改写 MEMORY（LLM，如存在）

应用 R4：MEMORY 正文按 R1 去品牌，目录结构 / 文件数量不变。
自检：`grep -riE "claude code|Claude Code|\bCC\b" MEMORY/` 应无命中（`\bCC\b` 避免误伤缩写）。

### Step 4：生成 CLAUDE.md 薄壳

按 [`references/rewrite-rules.md`](references/rewrite-rules.md) 的薄壳模板：顶部「薄壳声明」（点明
AGENTS.md 是单一真源、勿在此编辑共用部分）+ `@AGENTS.md` + `<!-- Claude Code 专属 -->` 逃生舱
（Step 2 识别出的 TOOL_SPECIFIC 内容，按 R5 处理）。没有逃生舱内容就省略注释块。
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

本仓库自身的 `CLAUDE.md` + `MEMORY/` 是一个真实、足够复杂的 fixture——eval 时用它端到端跑一遍
（见 `eval/evals.json`）。骨架模板（AGENTS.md 骨架、CLAUDE.md 薄壳模板）分别在
[`references/layering.md`](references/layering.md) / [`references/rewrite-rules.md`](references/rewrite-rules.md)，按需 Read。
