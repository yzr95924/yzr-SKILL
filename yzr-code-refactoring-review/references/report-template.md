<!-- markdownlint-disable MD025 -->

# 代码审查报告模板(SSOT)

主表 5 列固定,严重度 4 级,不允许 agent 自创新列。

---

# Code Refactoring Review Report

**输入**: <代码描述 / 文件路径 / diff 范围>
**语言**: <识别到的语言 / 未识别>
**静态工具**: <运行的工具清单 + 命中项数 / 未运行>
**Review 时间**: YYYY-MM-DD
**Reviewer**: <agent / 用户名>

## 发现项(主表)

| # | 位置(file:line) | 重构场景 | 严重度 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | src/parser.py:42 | Extract Method | Major | 抽 `parse_header()` 出来 |
| 2 | src/parser.py:55 | Replace Magic Literal | Minor | `0x0D` → `CR` 常量 |
| 3 | ... | ... | ... | ... |

每条规则:

- **位置**: 精确到 file:line(范围 review 写 file:line-line)
- **重构场景**: 映射到 `references/catalog.md` 卡片名(可加 lang 补充,如 "Extract Method (Python)")
- **严重度**: Blocker / Major / Minor / Nitpick — 判定查 `references/severity-rubric.md`
- **建议**: 一句话具体怎么做(不要泛泛"重构 X")

## 总结

- **总发现项**: N
- **按严重度分布**: Blocker X / Major Y / Minor Z / Nitpick W
- **优先 top-3**:
  1. <最优先项 + 原因>
  2. ...
  3. ...
- **风险点**: <如有 — 跨模块影响 / 公共 API / 测试覆盖不足等>

## 工具运行记录(脚注)

| 工具 | 状态 | 命中项数 | 备注 |
| --- | --- | --- | --- |
| ruff | 跑了 | N | - |
| mypy | 跑了 | N | - |
| bandit | 跳过 | 0 | 不在 PATH |

## 不报告项(透明)

为了让用户知道"我们看过但没报":

- <扫描覆盖范围,例如:扫描了 3 个文件,共 280 行>
- <明确忽略的类型,例如:不报告单行变量 typo>
