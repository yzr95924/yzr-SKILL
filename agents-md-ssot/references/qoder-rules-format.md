# Qoder 的上下文机制（事实与诚实边界）

> 本 skill 的模式（AGENTS.md 作单一真源 + CLAUDE.md 薄壳）对任何读 `AGENTS.md` 的 agent 都成立；
> Qoder 是**当前主要落地目标**，故单独成文档化它的具体机制。换别的 AGENTS.md-reading agent 时，
> 这里的 `.qoder/rules/` 细节需按那个 agent 的实际行为重核对，SSOT 共存的骨架不变。
>
> 本文件是「Qoder 实际怎么加载项目上下文」的 SSOT，基于
> [官方 Rules 文档](https://docs.qoder.com/user-guide/rules)（2026-07 核对）。Step 3 判断要不要拆
> `.qoder/rules/`、怎么拆时读它。SKILL.md 只给摘要 + 指针，不重抄。
>
> **关键诚实点**：Qoder 的 `.qoder/rules/*.md` 磁盘 frontmatter 格式**官方未文档化**。本 skill 因此
> 不杜撰 `trigger:` 字段——见文末「为什么我们不写 trigger frontmatter」。

## 1. Qoder 原生读 AGENTS.md（这是主路径的根基）

官方原文：

> "Qoder rules are now compatible with AGENTS.MD. ... Simply copy your `AGENTS.md` file to your project
> directory. The Agent will automatically recognize and utilize the rules defined in the file.
> No additional configuration is required."

含义：**只要项目根有一份去品牌化的 `AGENTS.md`，Qoder 就能直接用**。这是本 skill 主路径
（AGENTS.md + 薄壳 CLAUDE.md）成立的依据——L2（`.qoder/rules/`）拆分是锦上添花，不是必需。

> 冲突时 **rule 优先级高于 AGENTS.md**（官方："In case of conflicts between AGENTS.md content and
> rules content, rules content takes precedence."）。所以同一规则别在两处写不同口径。

**一个未文档化的边界（影响 R2 / MEMORY 加载）**：Qoder 官方只说"识别并使用 AGENTS.md 里的规则"，
**没有**明确说会展开 AGENTS.md 内部的 `@import`（如 `@MEMORY/MEMORY.md`）。Claude Code 会递归展开
`@` import，所以薄壳 `CLAUDE.md → @AGENTS.md → @MEMORY/MEMORY.md` 在 Claude Code 侧没问题；
Qoder 侧能否展开 `@MEMORY/MEMORY.md` 不确定。即便 Qoder 不展开，`@MEMORY/MEMORY.md` 这行留在
AGENTS.md 里也只是一行指针文本，不会出错——最坏情况是 Qoder 用户需手动 `Read` MEMORY 正文。
R2 仍把 import 写在 AGENTS.md（Claude Code 侧一定生效，Qoder 侧尽力）。若实测发现 Qoder 不展开
`@` import，再把 `@MEMORY/MEMORY.md` 在薄壳 CLAUDE.md 里也直写一份。

## 2. 四种 rule type（通过 IDE UI 设置）

| Type | 行为 | 适用场景 |
|------|------|---------|
| Always Apply | 所有 Chat + Inline Chat 都加载 | 项目级强制标准（编码风格、文档格式） |
| Model Decision | Agent 模式下 AI 评估 description 决定是否应用 | 场景化任务（生成单测 / 注释） |
| Specific Files | 匹配通配符的文件才加载（`*.js`、`src/**/.ts`） | 语言 / 目录特定规则 |
| Apply Manually | 用 `@rule` 手动引用 | 按需工作流、自定义 prompt |

**配置入口**：IDE 右上角用户图标 → Qoder Settings → Rules → Add。rule type 在 UI 里选，不是写进文件。

## 3. 存储与共享

- rule 文件存于项目 `.qoder/rules/`，随 git 与团队共享。
- 想**本地不共享**：把 `.qoder/rules/` 加进 `.gitignore`。

## 4. 硬限制（写 rule 时必须遵守）

- **所有活跃 rule 文件字符总和 ≤ 100,000**——超出会被截断（L2 预算的真正天花板，比单文件 2000 词更硬）。
- **纯自然语言——不放图片、不放 markdown 链接**。Qoder 不解析 rule 里的链接；需要引用其它文件时
  用纯文本路径（如 "见 yzr-skill-creator/SKILL.md 的评估章节"），不要写 `[链接](path)`。

## 5. `.qoder/rules/` 拆分细则（Step 3 用）

### 5.1 先判断要不要拆

只有当某段内容**确实需要"按文件 / 场景触发加载"**（而非每个 session 常驻）才值得拆进 L2。
判断不准就**不拆**——AGENTS.md 已让项目兼容，L2 是纯增益。

适合拆的信号：

- 内容只与**特定路径**相关（如"在 `outline-wiki-*/` 下工作时…"）→ Specific Files
- 内容只在**特定场景**触发（如"评估 skill 时…"）→ Model Decision
- AGENTS.md 总词数超 1500，需要把详细部分下沉省常驻预算

不适合拆的信号：

- 每个 session 都需要的核心规约 → 留 L1
- "为什么"类设计决策 → 留 L3（MEMORY）

### 5.2 文件格式（最稳公共子集）

```markdown
---
description: <一句话，说清这条规则管什么、何时需要它>
---

# <规则主题>

<内容，已按 R1 去品牌；纯自然语言；不放图片、不放 markdown 链接>
```

frontmatter **只写 `description`**——这是各类 rule 系统（Qoder / Cursor 等）最稳的公共子集。
`description` 也是 Model Decision type 下 AI 判断"要不要应用"的依据，要写得具体（见 §5.4）。

### 5.3 rule type 选择决策

```
此规则只与特定文件 / 目录相关？
  ├─ 是 → Specific Files（通配符在 IDE UI 里填，如 outline-wiki-*/**）
  └─ 否 → 此规则与某个概念 / 操作相关？
           ├─ 是 → Model Decision（description 写清"何时需要"）
           └─ 否（所有 session 都需要）
                  → 不该拆进 rules，放回 AGENTS.md（L1），或用 Always Apply（慎用，占常驻预算）
```

`Specific Files` 的通配符（如 `*.md`、`src/*.java`）在 IDE UI 里填，**不**写进文件——本 skill 在
迁移报告里标注"建议 type + 建议通配符"，让用户去 UI 设。

### 5.4 命名与约束

- 文件名：`collaboration-<scope>.md`，scope 取协作涉及的主要模块名，kebab-case。
  例：`collaboration-outline-wiki.md`（outline-wiki-{setup,search,upload} 三者协作）、
  `collaboration-paper-wiki-pipeline.md`（gemini-paper-summary → outline-wiki-upload）。
- `description` 写**具体**：写"outline-wiki 三件套的 MCP 读写与 REST 退化策略"，
  而不是"跨 skill 协作规则"——Model Decision 靠它判断是否加载。
- 单文件 ≤ 2000 词；同时记住所有 rule 文件字符总和 ≤ 100,000（§4）。

## 6. 为什么我们不写 `trigger:` frontmatter

来源 spec 用了 `trigger: model_decision` / `trigger: glob` 这样的 frontmatter 字段。但 Qoder 官方
文档**从未**记载 `.qoder/rules/*.md` 文件用 frontmatter 声明 type——它只说 type 在 IDE UI 里选。
spec 的 `trigger:` 字段是**未经验证的杜撰**：写进文件 Qoder 可能根本不按它解析，反而误导。

因此本 skill 的立场：

1. 主路径不依赖 rule frontmatter（AGENTS.md 本身让项目兼容）。
2. Step 3 拆 rule 时，frontmatter 只写 `description`（公共子集，最稳）。
3. rule type 让用户在 IDE UI 里设；本 skill 在迁移报告里给"建议 type + 建议通配符"，不落进文件。

> 若未来 Qoder 公开文档化了 rule 文件的 frontmatter 字段，再据此更新本节 + Step 3。
