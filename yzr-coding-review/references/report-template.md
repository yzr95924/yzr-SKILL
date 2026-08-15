<!-- markdownlint-disable MD025 -->

# 代码审查报告模板(SSOT)

主表 5 列固定,严重度 4 级,不允许 agent 自创新列。

## 两档规则

- **轻量档**(默认): 头部 + 主表 + 一句话收尾。适用于日常单文件 / PR diff review(发现通常 ≤ 5 条)。
- **完整档**: 轻量档内容 + 总结段 + 不报告项。适用于大范围体检(多文件 / 遗留代码)或用户明确要存档。

---

# Code Review Report

**输入**: <代码描述 / 文件路径 / diff 范围>
**语言**: <识别到的语言 / 未识别>
**Review 时间**: YYYY-MM-DD
**Reviewer**: <agent / 用户名>

## 发现项(主表)

| # | 位置(file:line) | 场景 / 卡片 | 严重度 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | src/parser.py:42 | Extract Method | Major | 抽 `parse_header()` 出来 |
| 2 | src/parser.py:55 | Magic Literal | Minor | `0x0D` → `CR` 常量 |
| 3 | ... | ... | ... | ... |

每条规则:

- **位置**: 精确到 file:line(范围 review 写 file:line-line)
- **场景 / 卡片**: 映射到 `catalog.md` 卡片名
- **严重度**: Blocker / Major / Minor / Nitpick — 判定查 `severity-rubric.md`
- **建议**: 一句话具体怎么做(不要泛泛"重构 X")

**收尾**(轻量档必写,一句话): <一句结论,如 "共 3 条发现,2 Major 1 Minor,建议先处理 Extract Method。">

## 总结(仅完整档)

- **总发现项**: N
- **按严重度分布**: Blocker X / Major Y / Minor Z / Nitpick W
- **优先 top-3**:
  1. <最优先项 + 原因>
  2. ...
  3. ...
- **风险点**: <如有 — 跨模块影响 / 公共 API / 测试覆盖不足等>

## 不报告项(仅完整档)

为了让用户知道"我们看过但没报":

- <扫描覆盖范围,例如:扫描了 3 个文件,共 280 行>
- <明确忽略的类型,例如:不报告单行变量 typo>
