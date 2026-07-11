---
name: yzr-code-refactoring-review
description: |
  Use this skill when you need to 对一段现有代码做"可重构点巡检"——
  产出一份按严重度排序的代码审查报告(表格 + 总结),不主动改文件。
  内置 Fowler 60+ 经典重构场景 catalog(语言中立),按语言路由加载
  references/languages/{lang}.md 插件(Python / Golang / TypeScript / Java);
  静态分析工具(ruff / mypy / golangci-lint / eslint 等)能装就跑一轮机械
  检查,工具覆盖不到的设计层问题(职责 / 依赖 / 抽象 / 命名)由 LLM 走
  catalog 补充。触发: 用户显式说"重构 / review / 看看有什么可改进的";
  连续写完一批代码后由用户或 agent 主动询问是否需要巡检。
  不适用: 一次性 typo 修 / 加新功能 / 改 bug / 性能调优 / 重写。
metadata:
  author: Zuoru YANG
  category: code-quality
---

# yzr-code-refactoring-review

## 何时使用

**显式请求场景**:

- 用户说"重构 / review / 看看这段代码有什么可改进的 / 巡检一下"
- 接手遗留代码,需要一份系统化的问题清单
- 准备提交 PR 前,过一遍质量门

**总结时机**:

- 连续完成一批代码修改后,agent 主动询问"要不要用 yzr-code-refactoring-review 跑一遍"
- 主功能代码落地后,用户确认巡检

## 何时不使用

- 一次性 typo / 改一个变量名 → 单点改动,不是 review
- 加新功能 → 开发,不是重构
- 改 bug → debugging,不是 review
- 性能调优 → profile + benchmark,不是 catalog 覆盖范围
- 重写模块 → 跨越整个结构,不是 review
- 单步问询("这段代码干嘛的") → 直接答,不是 review

## 输入 / 输出

**输入**(任一形态):

- 完整代码段(直接粘贴)
- 文件路径(agent 自己读)
- git diff / patch(只 review 改动)
- 项目根目录 + 范围(文件 / 模块 / 类过滤)

**输出**: 代码审查报告(Markdown),结构见 `references/report-template.md`:

- 主表 5 列: # / 位置 / 重构场景 / 严重度 / 建议
- 总结段: 计数 + 按严重度分布 + 优先 top-3 + 风险点
- 工具运行记录脚注
- **不修改源文件**

## 执行原则 / 边界

1. **不主动改文件**: 产出是报告,用户点头后才走具体重构
2. **catalog SSOT**: `references/catalog.md` 是 60+ 场景卡片的唯一真源;SKILL.md 不重抄卡片
3. **严重度 SSOT**: `references/severity-rubric.md` 是 4 级严重度判定细则的 SSOT;SKILL.md 不重抄细则
4. **工具兜底**: 静态工具不在 PATH 时静默跳过,记录到报告脚注"工具不可用,纯 LLM 巡检"
5. **语言路由**: 拿到代码先判语言,加载对应 `references/languages/{lang}.md`;未识别语言时只走 catalog
6. **触发收敛**: 主路径是显式请求;总结时机是"询问"不是"自动跑"
7. **每条发现可追溯**: 每条报告项映射到至少 1 个 catalog 场景名

## 工作流 / 步骤

### Step 1: 收集代码

解析输入(代码段 / 路径 / diff / 范围),确定语言 + 行数;行数 > 500 时与用户确认分段粒度(按文件 / 按类 / 按函数)。

### Step 2: 加载参考

必读 `references/catalog.md`(场景表);条件读 `references/languages/{lang}.md`(已识别语言时);按需读 `references/severity-rubric.md`(判定严重度时)。

### Step 3: 跑静态工具(如可用)

按语言插件"工具映射表"逐个尝试;不在 PATH → 静默跳过;输出转主表行。

### Step 4: 走 catalog 补充

LLM 用 catalog 60+ 场景卡补设计层问题;与工具结果去重;每条映射到 ≥ 1 个场景名。

### Step 5: 生成报告 + 询问

按 `references/report-template.md` 输出;严重度查 `references/severity-rubric.md`;末尾问用户要不要细化 / 跳过 / 改判。

## 与相邻 skill 的关系

- **不调用** `outline-wiki-*`(报告默认输出到当前对话;若用户明确要入 wiki,转交 `outline-wiki-upload`)
- **不调用** `yzr-skill-creator`(本 skill 自身就是产物)
- **不调用** `gemini-paper-summary`(与论文无关)

## 参考样例

完整输入输出样例见 `references/examples.md`(Python 函数 / Go 文件 / TSX 组件)。

**简短示例** — 用户输入:

> 帮我 review 一下 src/parser.py(80 行 Python 解析器)

skill 产出主表(节选):

| # | 位置 | 重构场景 | 严重度 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | parser.py:1 | Extract Method | Major | 抽 `parse_lines()` / `calc_total()` |
| 2 | parser.py:14 | Replace Magic Literal | Minor | `0.9` / `100` / `0.95` / `1000` 改成具名常量 |
| 3 | parser.py:6 | Introduce Parameter Object | Major | `(qty, price)` 重复 4 处,改 dataclass |
