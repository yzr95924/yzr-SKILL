# Lint 详细 Checklist

Lint 让 wiki **不腐烂**。Karpathy 原话："The tedious part of maintaining a knowledge
base is not the reading or the thinking — it's the bookkeeping." Lint 把 bookkeeping
的一部分自动化。

Lint 分**两层**：

1. **Deterministic**（脚本检查，可程序化）——`scripts/lint_wiki.py`
2. **Semi-qualitative**（agent 检查，需理解语义）——本文件"半定性检查"段

## 一、调用方式

```bash
python3 llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT"
# 或带严重性过滤
python3 llm-wiki-management/scripts/lint_wiki.py "$LLM_WIKI_ROOT" --severity error
```

退出码：0 = 干净；1 = 有问题（看输出）。

## 二、Deterministic 检查清单（脚本执行）

### 1. `raw/` 不可变性

- 在 `<wiki-root>/` 跑 `git status raw/`；有改动 → 报告
- **严重性：error**——任何 raw/ 改动都是违反 skill 纪律

### 2. frontmatter 完整性

- 扫所有 `wiki/**/*.md`（排除 `index.md` 和 `log.md`）
- 每页**必须**含 `title` / `type` / `created` / `updated` / `tags` 字段（与 `lint_wiki.py` 一致）
- `type` 必须是 `entity` / `concept` / `source` / `comparison` / `synthesis` 之一
- **严重性：error**——缺字段或 type 非法

### 3. frontmatter 来源（source / synthesis 页）

- `type: source` 的页面，`sources` 字段必须非空，且每个值是 `raw/` 下的现存路径
- `type: synthesis` 的页面，`sources` 字段必须非空（可以指 wiki 内其它页）
- **严重性：error**——断链

### 4. 路径引用完整性

- 扫所有 `wiki/**/*.md` 的 Markdown 链接 `[text](path)` 和图片 `![alt](path)`
- 相对路径解析后必须指向现存文件（在 wiki 范围内）
- 外部 URL（http/https）跳过
- **严重性：error**——断链影响阅读

### 5. index.md 覆盖

- 读 `wiki/index.md`
- 提取所有相对路径引用
- `wiki/**/*.md` 减去 `index.md` / `log.md` 后，每个文件**必须**被 index 引用
- **严重性：error**——孤儿页失去单一入口的意义

### 6. log.md 格式

- 每行匹配 `^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|setup) \| .+$`
- **严重性：warning**——格式错乱会破坏 `grep "^## \[" log.md` 的可用性

### 7. 过期摘要

- `type: source` 且 `updated` 距今 > 90 天 → 报告
- **严重性：warning**——不是 error，但建议复查

### 8. 文件名规范

- 所有 `wiki/**/*.md` 文件名必须是 kebab-case（小写 + `-`）
- 避免空格、大写、下划线
- **严重性：warning**

### 9. 重复标题

- 同一 `title` 出现在多个 wiki 页 → 报告
- **严重性：warning**——可能是合并候选

## 三、半定性检查（agent 执行）

跑完 deterministic 检查后，agent 应当再做以下检查（**仅在 wiki 规模 < 200 页
时人工做**——更大规模需 LLM-based 自动检查）：

### 10. 矛盾主张

- 同一概念 / 实体在 ≥ 2 个页里被以**矛盾方式**描述
- 例：`concepts/context-window.md` 说 "Llama 3 支持 200K tokens"，
  `sources/llama-2.md` 说 "128K tokens"（可能是不同版本，但未注明）
- 检查方法：grep 概念关键词 + 读周围上下文
- **严重性：warning**——可能需要更深入调研

### 11. 缺失交叉引用

- 概念 X 出现在页面 A 的正文里，但 A 没有链接到 `concepts/x.md`
- 例：`sources/foo.md` 提到 "self-attention" 但没链到 `concepts/self-attention.md`
- 检查方法：grep 概念名 + 看是否生成了 link
- **严重性：info**——是 lint 的最高频 finding

### 12. 缺失 entity / concept 页

- 重要概念（出现在 ≥ 3 个 source 页）但没有独立 entity / concept 页
- 检查方法：grep 候选关键词 + 统计出现次数
- **严重性：info**

### 13. 调查方向建议

- 哪些主题"很热门"（多个 source 涉及）但 wiki 内的综合 / 对比页没有
- 例：5 篇 source 提到 RAG，但 `syntheses/rag-evolution.md` 不存在
- **严重性：info**——这是"建议新摄取 / 新合成"的机会

### 14. 资料投放口是否堆积

- `raw/articles/` 是否有大量未摄取文件（跑 `ingest_diff.py` 即可知）
- **严重性：info**——堆积太久会让 ingest 时信息过载

## 四、报告格式

脚本 + agent 一起输出统一格式：

```text
[ERROR] raw-modified: raw/articles/foo.md has uncommitted changes
[ERROR] missing-frontmatter: wiki/concepts/bar.md missing 'sources' field
[ERROR] broken-link: wiki/sources/baz.md links to 'concepts/missing.md' which doesn't exist
[ERROR] orphan-page: wiki/concepts/qux.md is not listed in wiki/index.md
[WARN] stale-summary: wiki/sources/quux.md type=source updated=2024-01-01 (>90 days)
[WARN] log-format: wiki/log.md line 23: '## [bad] ingest | foo' doesn't match expected format
[INFO] missing-xref: wiki/sources/abc.md mentions 'self-attention' but doesn't link to concepts/self-attention.md
[INFO] missing-entity: 'rotary-position-embedding' appears in 4 source pages but has no entity page
```

每条带：**严重性** + **类别** + **文件:行** + **描述**。

## 五、lint 之后

跑完 lint 后，agent 应当：

1. 整理报告（按严重性排序：error > warn > info）
2. **询问用户先修哪些**——不要一次全修（容易回退或引入新问题）
3. 修完后**重新跑 lint 验证**——不要带着 fix 没验过的状态前进
4. 重大修复 commit 时建议加 `lint: <summary>` 前缀

## 六、lint 频率

- **小 wiki（< 50 页）**——每月 1 次足够
- **中 wiki（50-200 页）**——每 2 周 1 次
- **大 wiki（> 200 页）**——每周 1 次；可考虑写 cron
- **重大 ingest 后**——建议跑一次（可能引入新 entity / 断链）

## 七、lint 的边界

- **不**自动修——只报告；修由用户 / agent 决定
- **不**评估内容质量（不是 fact-checker）——只看结构和纪律
- **不**评估 frontmatter 的语义是否合理（只检查字段存在性 + 类型合法）
- **不**取代 schema（`CLAUDE.md`）——schema 是源头，lint 是脚本化检查
