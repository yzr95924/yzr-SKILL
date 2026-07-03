# 内容分层模型（L1 / L2 / L3）

> 本文件是「迁移时每段内容该落到哪里」的 SSOT。Step 1 给段落分类、Step 2 组织 AGENTS.md 时读它。
> SKILL.md 只给摘要 + 指针，不重抄。

所有内容按"加载频率"分三层，决定它放在哪个文件。

## 三层定义

| 层 | 文件 | 加载时机 | 内容特征 | 预算 |
|----|------|---------|---------|------|
| L1 常驻层 | `AGENTS.md` | 每次 session 必定加载（Claude Code 经薄壳、Qoder 原生） | 项目身份、核心规约、常用命令、高层结构 | ≤ 1500 词 |
| L2 按需层 | `.qoder/rules/*.md` | 按 rule type 加载（Specific Files / Model Decision / Always Apply） | 跨模块协作、特定路径下的规则 | 单文件 ≤ 2000 词 |
| L3 记忆层 | `MEMORY/` | `@MEMORY/MEMORY.md` 索引被 import 常驻，正文按需 Read | 跨会话"为什么"、设计决策、踩坑记录 | 索引 ≤ 200 行 |

> L2 是**可选**层——Qoder 原生读 `AGENTS.md` 已让项目兼容，L2 只为"按触发加载省常驻预算"而存在。
> 拆不拆的细则见 [`qoder-rules-format.md`](qoder-rules-format.md)。

## 段落分层决策树（Step 1 用）

对原 `CLAUDE.md` 的每个 `##` 段落执行：

```
Q1: 这段内容在 > 50% 的 session 中都需要吗？
  ├─ 是 → Q2: 能否用一两句话说清？
  │        ├─ 是 → L1（AGENTS.md 正文）
  │        └─ 否 → Q3: 是否只与特定文件 / 模块相关？
  │                 ├─ 是，有明确路径 → L2（.qoder/rules/，Specific Files）
  │                 ├─ 是，但跨多个不相关路径 → L2（.qoder/rules/，Model Decision）
  │                 └─ 否（通用但详细） → L1（AGENTS.md，注意压总词数）
  └─ 否 → Q4: 是"为什么"类的设计决策或踩坑记录？
           ├─ 是 → L3（MEMORY/<slug>.md）
           └─ 否 → 回到 Q3
```

## 段落类型 → 层级映射（快速参考）

| 段落类型 | 典型标题关键词 | 默认层级 |
|---------|--------------|---------|
| IDENTITY | 定位 / 是什么 / overview | L1 |
| CONVENTION | 规约 / 规范 / 必须 / 禁止 | L1 |
| COMMANDS | 常用命令 / lint / format | L1 |
| STRUCTURE | 目录结构 / 文件树 | L1 |
| COLLABORATION | 跨 skill 协作 / 数据流 / 管线 | L2 |
| TOOL_SPECIFIC | claude CLI / `.claude.json` | 改写后归 L1，或进 CLAUDE.md 薄壳逃生舱（R5） |
| CAUTION | 注意事项 / tip / warning | 就近合并（L1 或 L2） |

> `TOOL_SPECIFIC` 是唯一可能进逃生舱的类型——判定标准见 [`rewrite-rules.md`](rewrite-rules.md) R5：
> "去掉工具名后读者无法执行该操作"才进逃生舱；否则 R1 去品牌后归 L1。

## AGENTS.md 骨架（Step 2 用）

```markdown
# AGENTS.md

@MEMORY/MEMORY.md

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

## 注意事项                          ← CAUTION (L1 兜底)

<零散的 tip / warning>
```

**L1 词数控制**：总词数 ≤ 1500。如果超出，把详细内容下沉到 L2（`.qoder/rules/`），L1 只保留摘要 +
指向 rule 文件的说明。注意 Qoder rule 文件字符总和硬上限 100,000（见 [`qoder-rules-format.md`](qoder-rules-format.md)）。
