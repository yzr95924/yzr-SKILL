# 初始化 init 的执行细节

> 本文件承载[章节](../SKILL.md#初始化-init)的全部执行细节

## 提议内容（一次给全，确认后创建）

1. `MEMORY/MEMORY.md`：从 `assets/memory-index-template.md` 拷贝（含索引行格式与预算约定）
2. AGENTS.md 引用段：一个二级标题 + 单行引入，样例：

   ```markdown
   ## 跨会话记忆（索引）

   <!-- 下方 @引用若未被自动展开（看不到正文），用 Read 工具读取 -->
   @MEMORY/MEMORY.md
   ```

3. 首批条目：从对话 / 项目现状提取真正够格的（过五道闸，按[章节](capture-workflow.md#五道闸agent-自主写入的准入)执行），没有就空着，不凑数

## 边界

单仓一份：寻址规则见[章节](capture-workflow.md#寻址)。项目已有别的记忆形态（内嵌记忆段 /
memory-bank/ 等）不动它、沿用既有机制；lint 只认 canonical 格式，不为旧布局写第二套判据
