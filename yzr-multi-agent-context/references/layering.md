# 内容分层模型（L1 / L2）

> 本文件是「迁移时每段内容该落到哪里」的 SSOT。Step 1 给段落分类、Step 2 组织 AGENTS.md 时读它。
> SKILL.md 只给摘要 + 指针，不重抄。

所有内容按"加载频率"分两层，决定它放在哪个文件。

## 两层定义

| 层 | 文件 | 加载时机 | 内容特征 | 预算 |
|----|------|---------|---------|------|
| L1 常驻层 | `AGENTS.md` | 三家每次 session 必加载（Claude Code 经薄壳，Codex/Qoder 原生） | 项目身份 / 规约 / 命令 / 高层结构 / 协作摘要 | 正文 ≤1500 词 |
| L2 记忆层 | `MEMORY/MEMORY.md`（索引） + `MEMORY/<slug>.md`（正文） | 索引经 AGENTS.md 的 `@MEMORY/MEMORY.md` 一行引入 + Codex Read 指引；正文按需 `Read` | 跨会话”为什么”、设计决策、踩坑记录 | 索引行数不限（只存 `MEMORY.md`，AGENTS.md 单行引用不计入 L1） |

> 只有这两层。本 skill **不生成任何 agent 专属的触发式 rule 文件**（如 Qoder 的 `.qoder/rules/`）——
> 那类机制官方多未文档化，且 `AGENTS.md` 主路径已让读它的 agent 兼容；触发式拆分交给用户在目标
> agent 的 IDE 里自行配置。本 skill 只负责产出工具无关的 `AGENTS.md` + 薄壳 `CLAUDE.md` + `MEMORY/`。

## 段落分层决策树（Step 1 用）

对原 `CLAUDE.md` 的每个 `##` 段落执行：

```text
Q1: 这段内容在 > 50% 的 session 中都需要吗？
  ├─ 是 → Q2: 能否用一两句话说清？
  │        ├─ 是 → L1（AGENTS.md 正文）
  │        └─ 否（通用但详细） → 压成摘要归 L1，"为什么"部分下沉 L2（MEMORY/<slug>.md）
  └─ 否 → 是"为什么"类的设计决策或踩坑记录？
           ├─ 是 → L2（MEMORY/<slug>.md）
           └─ 否 → 多半不该留——与用户确认是否丢弃
```

## 段落类型 → 层级映射（快速参考）

| 段落类型 | 典型标题关键词 | 默认层级 |
|---------|--------------|---------|
| IDENTITY | 定位 / 是什么 / overview | L1 |
| CONVENTION | 规约 / 规范 / 必须 / 禁止 | L1 |
| COMMANDS | 常用命令 / lint / format | L1 |
| STRUCTURE | 目录结构 / 文件树 | L1 |
| COLLABORATION | 跨 skill 协作 / 数据流 / 管线 | L1（压成摘要；详细"为什么"归 L2） |
| TOOL_SPECIFIC | claude CLI / `.claude.json` | 改写后归 L1，或进 CLAUDE.md 薄壳逃生舱（R5） |
| CAUTION | 注意事项 / tip / warning | 就近合并到 L1 |

> `TOOL_SPECIFIC` 是唯一可能进逃生舱的类型——判定标准见 [`rewrite-rules.md`](rewrite-rules.md) R5：
> "去掉工具名后读者无法执行该操作"才进逃生舱；否则 R1 去品牌后归 L1。

## AGENTS.md 骨架（Step 2 用）

```markdown
# AGENTS.md

## 项目定位                          ← IDENTITY (L1)

<一两段描述仓库是什么、做什么>

## 仓库规约                          ← CONVENTION (L1)

<命名规范、文件格式、必须遵守的约束>

## 常用命令                          ← COMMANDS (L1)

### 校验 skill
### Markdown lint
### Python lint

## 高层结构                          ← STRUCTURE (L1)

<文件树 + 简要说明>

## 跨会话记忆（索引）                ← L2 索引 @import（R2；无 MEMORY/ 时省略本段）

@MEMORY/MEMORY.md

<!-- Codex Read 指引：完整注释模板见 rewrite-rules.md R2，逐字拷入本段 -->

## 注意事项                          ← CAUTION (L1 兜底)

<零散的 tip / warning>
```

**L1 词数控制**：正文总词数守 L1 预算（§两层定义），记忆索引段只占 2 行（`@MEMORY/MEMORY.md` + Codex Read 指引），
**不**计入 L1 词数预算——索引真实数据走 `MEMORY/MEMORY.md`，AGENTS.md 这段本质是引用 + fallback，不是内容。
如果 L1 内容超出 L1 预算，说明描述太详细——把”为什么”类设计决策下沉到 L2（`MEMORY/<slug>.md`），
L1 只保留摘要。索引本身无条数上限——索引只活在 `MEMORY/MEMORY.md`，AGENTS.md 只引用不计数。
