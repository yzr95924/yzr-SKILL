# Migration Test Fixtures

`scripts/lint_wiki.py --check-version` 的 6 套 mini-wiki 测试数据。
与 `references/fixtures/`（CLI init 时刻的字节模板 + `references/canonical/` 字节金标准）
**概念不同**——这里是测试脚本的输入样例，不是 CLI 的生成模板。

## 6 套场景

| 场景 | 目录 | 期望 |
|---|---|---|
| 等版本 | `equal-version/` | `current_spec == skill_spec`, `needs_migration: false`, 无 legacy |
| 老版本 + 老 confidence 字段 | `older-confidence/` | `comparison: older`, plan 含 `frontmatter-rename` actions |
| 老版本 + 冲突页 | `older-conflict/` | plan 把冲突页归入 `skipped_conflicts` |
| wiki 比 SKILL 新 | `newer-than-skill/` | 告警但**不**写 plan |
| 老版本（0.7.0） + CLAUDE.md 仍含 `### Tag Taxonomy` 段（0.8.0+ 迁移目标） | `tag-section-legacy/` | `claudemd-tag-section` pattern 触发；plan 含 `tag-taxonomy-migrate` action（写 wiki/tags.md + 删 CLAUDE.md 段） |
| 老版本（0.10.0） + CLAUDE.md 仍是完整 SSOT 形态（0.11.0+ 迁移目标） | `older-claudemd-ssot/` | `claudemd-not-thinshell` pattern 触发；plan 含 `claudemd-to-agents-md-split` action（老 CLAUDE.md 正文搬到 AGENTS.md + CLAUDE.md 重写为薄壳） |

## 用法

每个目录都是一个**完整的 wiki 仓骨架**（CLAUDE.md + wiki/{index,log,...}.md），可以直接
当 `--check-version` 的入参：

```bash
SCRIPT=llm-wiki-management/scripts/lint_wiki.py

# 跑 dry-run
python3 $SCRIPT llm-wiki-management/scripts/test_fixtures/migration/equal-version --check-version

# 跑 JSON 输出
python3 $SCRIPT llm-wiki-management/scripts/test_fixtures/migration/equal-version --check-version --json

# 跑 apply (落盘 .migration-plan.json)
python3 $SCRIPT llm-wiki-management/scripts/test_fixtures/migration/older-confidence --check-version --apply

# 验证 apply 后的 wiki 重跑 --check-version 是干净的
# (需要先按 plan 走 Edit/Write 修复；本 fixtures 不带修复运行)
```

## 为什么不放 references/fixtures/

`references/fixtures/README.md` 第 31-37 行明确写"fixtures 是机器读取的字节模板、
spec 是概念权威"，由 CLI 在 init 时按 mapping 替换占位符渲染。迁移 fixtures 是
**测试脚本的输入**，与 CLI init 无关；混在一起会污染字节金标准的语义。
