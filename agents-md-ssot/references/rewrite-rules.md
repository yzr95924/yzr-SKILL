# 改写规则 R1–R5

> 本文件是「迁移时怎么改写每段内容」的 SSOT。Step 2 / 3 / 4 改写、Step 5 生成薄壳时读它。
> SKILL.md 只给摘要 + 指针，不重抄。

## R1 — 工具无关化（去品牌绑定）

**原则：不改事实，只去品牌。** 去掉对 Claude Code 的专有称呼，换成工具无关说法，让 AGENTS.md
对任何 agent 都成立。

| 原文 | 替换为 | 备注 |
|------|-------|------|
| `Claude Code (claude.ai/code)` | `AI coding agent` | 首次出现可用全称 |
| `CC`（指 Claude Code） | `agent` 或 `部分 agent` | 视上下文 |
| `claude -p` | `agent CLI` | 或在举例处写 `agent CLI（如 claude -p）` |
| `claude mcp add` | `MCP 注册命令` | |
| `.claude/settings.local.json` | `agent 配置文件` | 或直接删除引用 |
| "Claude 会话级 memory" | "agent 会话级 memory" | |
| "Claude Code 截断 MCP 多 block" | "部分 agent 截断 MCP 多 block" | 保留 bug 事实，只弱化归属 |

**判断是否需要保留工具名**：如果去掉工具名后，读者无法理解约束的来源（比如某个 workaround 是因为
特定 agent 的 bug），用 `部分 agent` / `某些 agent` 替代具体名字，保留可追溯性，而不是硬删。
一句话测试：**"另一个 agent 的用户读到这句，能不能照样执行？"** 能 → 去品牌；不能 → 考虑 R5 逃生舱。

> R1 不动的事实：命令名（`python3 -m scripts.run_eval`）、文件路径（`yzr-skill-creator/scripts/`）、
> 工具行为（"截断 MCP 多 block"）都保留，只换对工具的称呼。

## R2 — @import 位置

`@MEMORY/MEMORY.md` 必须写在 `AGENTS.md` 内（标题之后第一行），**不**写在 CLAUDE.md 内。
原因：`AGENTS.md` 是两边共同加载的真源，import 放这里才能保证 Claude Code（经 `@AGENTS.md` 展开）
和 Qoder（原生读 AGENTS.md）都拿到记忆索引。

## R3 — 行宽不变

原文遵守的行宽约束（本仓库是 ≤ 120 字符，见 `.markdownlint.jsonc` MD013）在改写后继续遵守。
改写时若加了文字，注意回行；最后 Step 6 跑 `markdownlint` 复核 0 error。

## R4 — MEMORY 改写

`MEMORY/` 下所有文件（`MEMORY.md` 索引 + 各 `<slug>.md` 正文）的品牌引用按 R1 改写。
**目录结构和文件数量不变**——只改措辞，不合并 / 拆分 / 删除条目。自检：
`grep -riE "claude code|Claude Code|\bCC\b" MEMORY/` 应无命中（`\bCC\b` 避免误伤"CC"作缩写）。

## R5 — 不可泛化内容的逃生舱

如果某段内容**确实无法泛化为工具无关表述**（比如 `run_eval.py` 调用 `claude -p` 子进程是硬编码依赖，
去掉 `claude` 读者就无法执行），处理方式：

1. 在 `AGENTS.md` 中写**泛化版本**：`评估脚本通过 agent CLI 子进程运行`。
2. 在 `CLAUDE.md` 薄壳尾部追加**具体实现**（见下方逃生舱格式）。

**逃生舱内容的判定标准**：去掉工具名后，读者无法执行该操作。典型场景：

- 脚本硬编码了 `claude` CLI 调用（如 `run_eval.py` / `improve_description.py` 调 `claude -p`）
- 特定的 `~/.claude.json` 配置路径
- Claude Code 特有 MCP 行为（如截断多 block）需要点名才能定位

**不要**把"只是提到 Claude Code 名字"的内容塞进逃生舱——那些 R1 去品牌后归 L1 即可。逃生舱只收
"点名才能执行"的硬依赖。

### CLAUDE.md 薄壳模板（Step 5 用）

```markdown
# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

> **薄壳声明**：项目上下文的**单一真源是 `AGENTS.md`**——本文件用 `@AGENTS.md` 引入全部共用内容。
> 改内容请改 `AGENTS.md`；本文件只承载 Claude 专属、无法泛化的逃生舱内容（见下方），勿在此编辑共用部分。

@AGENTS.md

<!-- Claude Code 专属（以下为无法泛化为工具无关的内容，AGENTS.md 不含此部分） -->
<!-- 如果没有专属内容，删除此注释块 -->
```

> 「薄壳声明」是**结构性指针**（指向 SSOT + 提醒勿编辑共用部分），不是被迁移的内容，不违反"薄壳不放大段正文"。
> 它让任何打开 CLAUDE.md 的人/agent 一眼知道：真源在 AGENTS.md、这里别动。Claude Code 加载时会把它和
> `@AGENTS.md` 展开内容一起读入，相当于一句"接下来这段是 AGENTS.md 的内容"的引导。

### 逃生舱内容格式

```markdown
- <具体说明>：`<claude 专属命令或路径>`，<约束或原因>。
```

每条一行，尽量简短。典型落地：

```markdown
<!-- Claude Code 专属 -->
- `yzr-skill-creator/scripts/run_eval.py` 调用 `claude -p` 子进程：需本机已安装并登录 Claude Code。
- Outline 大文档整篇重写走 REST 绕开 `update_document` 换行吞字 bug（Claude Code 特有 MCP 行为）。
```

### 薄壳验证（Step 5 自检）

- 总行数 ≤ 30（含注释标记）
- `@AGENTS.md` 存在
- 顶部有「薄壳声明」（指向 AGENTS.md 为单一真源、提醒勿编辑共用部分）——结构性指针，不计入"正文"
- 除「薄壳声明」、`@AGENTS.md` 和 HTML 注释标记外，不应有大段正文——有就说明该内容本该在 AGENTS.md（R1 去品牌后归 L1）或 MEMORY（R4），不该留在薄壳
