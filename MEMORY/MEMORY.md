# MEMORY/

跨会话"为什么 + 边界规则"的纯索引（L2 SSOT）；`AGENTS.md` 的“跨会话记忆（索引）”段用单行
`@MEMORY/MEMORY.md` 引入——自动展开 `@import` 的 agent 读入全文，不展开的由 AGENTS.md **顶部
强制 Read 指令**兜底（不再靠段内 HTML 注释）；正文按需 `Read`（`MEMORY/<slug>.md`，同级）。
新条目追加到本文件末尾即可，无需同步副本——只活这一份，AGENTS.md 单行引用负责把"指针"挂到 L1。

> 本文件是项目级规则的**唯一**真源；agent 会话级 memory 只放指向本文件的指针，不再持有内容副本，避免跟代码仓迁移时失同步。

## 规则

- [SKILL 的 md 不写代码实现细节](no-code-detail-in-skill-md.md)：分发面（SKILL.md/ref/assets/eval）标准只指
  md 产物或工具可见输出，禁 `*.py::符号` / 常量名；仓库维护文档（AGENTS.md / MEMORY）豁免

（2026-09 重建：旧条目已随重建清空，随新沉淀回补。）
