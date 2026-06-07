# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库性质

个人 Claude Code 自定义 SKILL 合集（远程：`my_SKILL`）。
本仓库不构建、不运行、不测试——内容全部为 Markdown 文档，
最终被 Claude Code 解析为可在对话中调用的 skill。

每个 skill 是一段可被 Claude 自行调用的指令，由 frontmatter 中的
`name` + `description` 触发判定（`description` 写明"做什么 / 何时用"，
是 Claude 决定是否调用的唯一判据；务必说人话，不要堆关键词）。

## 目录结构

仓库是平铺的：每个 skill 一个独立文件夹，文件夹名 = skill 名 =
`SKILL.md` frontmatter 的 `name` 字段，三者必须一致。

```text
skills/
├── README.md            # 字段含义 / 代码仓规范的权威说明
├── SKILL_template.md    # 新建 skill 时的起手模板（cp 后填空即可）
├── MEMORY.md            # 跨会话的持久化经验
├── LICENSE              # MIT
└── <skill-name>/
    ├── SKILL.md         # skill 定义文件（必须）
    └── template.md      # 可选：skill 内部引用的辅助模板
```

## SKILL.md 必填项

新增 skill 的流程：先 `cp SKILL_template.md <name>/SKILL.md`，
再按 frontmatter + 6 段 body 填内容。

### Frontmatter（YAML，必填）

- `name`：与文件夹名一致，最长 64 字符
- `description`：最长 200 字符，**就是调用判据**——
  写清能力 + 触发场景 + 反例，让 Claude 在合适时自动选到
- `dependencies`（可选）：该 skill 依赖的软件包

**Body 章节骨架**（来自 `SKILL_template.md`，可按需扩展子章节，
但一级章节的顺序与必要性是约定，不轻易打乱）：

1. `# <skill 名>` —— 一句话讲清任务 / 能力 / 解决的问题
2. `## 何时使用 / 不使用` —— 触发场景 + 反例（与 `description` 互补）
3. `## 输入 / 输出` —— 输入输出形式
4. `## 执行原则 / 边界` —— 核心原则
5. `## 工作流 / 步骤` —— 具体执行步骤
6. `## 参考样例` —— 例子

字段详细定义见 [README.md](./README.md)；新章节写法不确定时
参考其他通用 SKILL（如 `outline-wiki-management/SKILL.md`）的样例。
注意：`design-doc-edit/SKILL.md` 是设计文档专用方法论，结构不同，
不作为通用 SKILL 模板参考。

## 维护约定

- 全部 `.md` 文件需格式化和 lint（仓库未提供 wrapper 脚本，
  按 README 要求用 `markdownlint-cli2` 处理；配置如有调整，
  优先复用根目录 `.markdownlint.jsonc`，不要散落多份）。
- 跨会话的"经验 / 决策"写入 `MEMORY.md`：用一两句话写
  "事实 + 为什么 + 何时套用"，避免变成文档搬家。
- 修改 `README.md` / `SKILL_template.md` 等顶层规范前先与用户确认——
  这些是给未来所有 session 看的共享上下文。

## 常用操作

- 新建 skill：`cp SKILL_template.md <name>/SKILL.md` 后填空
- 校验 skill 完整性：检查 `<name>/SKILL.md` 存在、frontmatter
  三字段齐备、文件夹名与 `name` 一致
- 仓库内无 build / test 命令——不要伪造 `pytest` / `make` 等
