# 初始化的执行细节

## 提议内容（一次给全，确认后创建）

1. `MEMORY/MEMORY.md`：从 `assets/memory-index-template.md` 的项目骨架节原样拷贝建索引；索引已存在则不动，已有记忆走清理流程
2. AGENTS.md 引用段：一个二级标题 + 单行引入，样例：

   ```markdown
   ## 跨会话记忆（索引）

   <!-- 下方 @引用若未被自动展开（看不到正文），用 Read 工具读取 -->
   @MEMORY/MEMORY.md
   ```

   **跳过条件**：若目标 AGENTS.md 已含 `@MEMORY/MEMORY.md` 行，则不提议改 AGENTS.md，只建
   MEMORY/ 骨架；llmw wiki 等实例的模板自带该行且文件禁手改，即属此情形

3. 首批条目：来源限于对话中用户已陈述的纠正 / 约定（项目现状只提供线索，对不上本轮具体事件就过不了证据这条），
   够格的过这些检查（按[章节](capture-workflow.md#自主写入的检查)执行）才提，没有就空着，不凑数

## 边界

MEMORY/ 位置规则见[章节](capture-workflow.md#memory-在哪)。项目已有别的记忆形态（内嵌记忆段 /
memory-bank/ 等）不动它、沿用既有机制；lint 只认标准格式，不为旧布局写第二套判据
