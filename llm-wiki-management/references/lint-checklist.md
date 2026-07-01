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
- **前提**：脚本**自动检测** wiki 根目录是否在 git 仓内（`.git/` 子目录存在与否）：
  - `.git/` 不存在 → 跳过 + 输出顶部 `[NOTES] raw-immutable-skipped: 未启用 git（无 .git/）`
  - `.git/` 存在但 `raw/` 未纳入 git 跟踪 → 跳过 + `[NOTES] raw-immutable-skipped: raw/ 未纳入 git 跟踪`
  - 真 git 仓 + raw 被改 → 报 `raw-modified` finding
- 强制跳过：传 `--no-git` 时完全静默跳过（不打 note）——给 CI / 裸仓场景
- **不要**在裸目录树 wiki 上"强假设 git"——`wiki-spec.md §7` 默认就是裸目录树

### 2. frontmatter 完整性

- 扫所有 `wiki/**/*.md`（排除 `index.md`、`log.md` 和 `MEMORY/MEMORY.md`——索引无 frontmatter）
- 每页**必须**含 `title` / `type` / `created` / `updated` / `tags` 字段
  （字段定义见 [page-templates.md §一](page-templates.md#一共有-frontmatter-段)）
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

- 每行匹配正则（见 [page-templates.md §7](page-templates.md#7-logmdlog)）
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

### 10. log.md 条目数（log-rotation）

- `wiki/log.md` 当前文件条目数 > 阈值（默认 500）→ 报告 `log-rotation-recommended`
- 阈值由 `scripts/lint_wiki.py` 顶部 `LOG_ROTATION_THRESHOLD` 常量控制
- **不**自动 rotate——lint 只建议；rotate 流程见 [wiki-spec §4.1](wiki-spec.md#41-log-rotation防-logmd-无限增长)
- 归档文件 `log-YYYY.md` 不计入（它们是只读归档，不需要再次 rotate）
- **严重性：warning**——超过阈值不是错误，但长期不 rotate 会让 `grep "^## ["` 噪声变大

### 11. Tag Taxonomy 校验

- 解析 `<wiki-root>/CLAUDE.md` 的 `### Tag Taxonomy` 段，提取允许的 tag 集合
- 段必须是**裸 bullet**（每行 `- ...`），不能包在 code block / HTML comment 里——
  包了就解析不出 0 个 tag，lint 静默跳过（视为未启用约束）
- 格式兼容：`- category：tag1 / tag2 / tag3`（中文 / 英文分隔符都支持；
  多 tag 用 `/` `，` `,` 任一字符分隔）
- 对每个内容页（5 类 + MEMORY 非 MEMORY.md）的 `frontmatter.tags` 元素做包含校验
- 找不到 CLAUDE.md / Tag Taxonomy 段 / 解析出 0 个 tag → 静默跳过（避免新 setup 的
  wiki 必报错）
- 严格匹配的 tag 名 = 严格小写 + kebab-case（`^[a-z0-9][a-z0-9-]*$`），与文件名命名一致
- **严重性：info**——tag 漂移不会立刻让 wiki 失能，但放任几个月后 index 噪音变大

### 12. 页面体量

- 5 类内容页（entities / concepts / sources / comparisons / syntheses）正文**非空行数** >
  阈值（SSOT = `scripts/lint_wiki.py` 的 `PAGE_SIZE_THRESHOLD`，默认 ~300 行）→ 报 `oversized-page`
- 阈值与 CLAUDE.md「Page Thresholds」段的「拆分页」行对齐（`claude-md-template.md` 也引用此 SSOT）
- `MEMORY/*` 豁免——按 wiki-spec §5.2「正文无长度上限」（agent 经验沉淀可长）
- 计**非空行**（纯空行不计），避免空行撑大计数
- **严重性：warning**——不是 error，但单页过长 = 主题过散，建议拆成子主题页 + cross-link

### 13. 认知质量信号（confidence / contested / contradictions）

- 把作者主动标注的"弱主张警示"拎出来供复审——防止单源弱断言无声固化成"wiki 事实"
  （字段语义见 [page-templates.md §一「可选：认知质量信号」](page-templates.md#可选认知质量信号防弱主张固化成事实)）
- 子检查（字段全部可选；省略 = 不评，不报）：
  - `contested-page`（warn）：`contested: true` 的页——含未解决矛盾，需裁定后移除标记
  - `low-confidence`（info）：`confidence: low` 的页——弱支撑主张
  - `invalid-confidence`（warn）：`confidence` 取值不在 `high` / `medium` / `low`
  - `contradiction-target-missing`（warn）：`contradictions` 指向不存在的页
  - `contradiction-asymmetric`（warn）：A 把 B 列入 `contradictions` 但 B 未反向标注 A
    （字段语义要求**双向标注**）
- **为什么是 deterministic 而非半定性**：这里只读作者**已写**的 frontmatter 信号并拎出来；
  判定"某主张到底该不该标 low / 是否真的矛盾"是 §三 14 的半定性工作，lint 不替作者决定
- **严重性**：见上各子项——`contested` / 断链类为 warn（需行动），`low-confidence` 为 info（提示）

### 14. MEMORY.md 索引一致性

- `wiki/MEMORY/MEMORY.md` 是被 `<wiki-root>/CLAUDE.md` 用 `@wiki/MEMORY/MEMORY.md` import 的轻量
  索引（无 frontmatter），让 agent 每次会话都能看到 MEMORY 里有哪些条目——避免 MEMORY 沦为
  只写不读的死库
- 扫 `wiki/MEMORY/*.md`（排除 `MEMORY.md` 本身）；任一经验条目 `<slug>.md` **未在 MEMORY.md 索引中
  列出** → 报 `memory-not-indexed`
- **反向**（索引列了某 `<slug>.md` 但文件不存在）由 §二.4 路径引用完整性的 `broken-link` 覆盖
  （MEMORY.md 的 markdown 链接会被扫）——本项不重复检查
- `MEMORY.md` 不存在 → **静默跳过**（老 wiki 迁移期 / spec <0.6.0 未补索引，不报错）
- **严重性：info**——MEMORY 是轻量索引非强制入口（区别于 §二.5 `index.md` 覆盖率是 error），
  漏列不阻断但提示 agent 补索引

## 三、半定性检查（agent 执行）

跑完 deterministic 检查后，agent 应当再做以下检查（**仅在 wiki 规模 < 200 页
时人工做**——更大规模需 LLM-based 自动检查）：

### 14. 矛盾主张

- 同一概念 / 实体在 ≥ 2 个页里被以**矛盾方式**描述（**内容层**矛盾，区别于 §二 13 的
  frontmatter `contested` 信号——后者是作者已标注、本项是 agent 主动发现未标注的）
- 例：`concepts/context-window.md` 说 "Llama 3 支持 200K tokens"，
  `sources/llama-2.md` 说 "128K tokens"（可能是不同版本，但未注明）
- 检查方法：grep 概念关键词 + 读周围上下文；发现后建议双方补 `contested: true` +
  `contradictions` 互指（让 §二 13 后续能持续追踪）
- **严重性：warning**——可能需要更深入调研

### 15. 缺失交叉引用

- 概念 X 出现在页面 A 的正文里，但 A 没有链接到 `concepts/x.md`
- 例：`sources/foo.md` 提到 "self-attention" 但没链到 `concepts/self-attention.md`
- 检查方法：grep 概念名 + 看是否生成了 link
- **严重性：info**——是 lint 的最高频 finding

### 16. 缺失 entity / concept 页

- 重要概念（出现在 ≥ 3 个 source 页）但没有独立 entity / concept 页
- 检查方法：grep 候选关键词 + 统计出现次数
- **严重性：info**

### 17. 调查方向建议

- 哪些主题"很热门"（多个 source 涉及）但 wiki 内的综合 / 对比页没有
- 例：5 篇 source 提到 RAG，但 `syntheses/rag-evolution.md` 不存在
- **严重性：info**——这是"建议新摄取 / 新合成"的机会

### 18. 资料投放口是否堆积

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
[INFO] memory-not-indexed: wiki/MEMORY/ocr-tips.md 未在 MEMORY.md 索引中列出
```

每条带：**严重性** + **类别** + **文件:行** + **描述**。

## 五、lint 之后

跑完 lint 后，agent 应当：

1. 整理报告（按严重性排序：error > warn > info）
2. **询问用户先修哪些**——不要一次全修（容易回退或引入新问题）
3. 修完后**重新跑 lint 验证**——不要带着 fix 没验过的状态前进
4. 若启用 git，重大修复 commit 时建议加 `lint: <summary>` 前缀；裸目录树 wiki 跳过 commit 步骤

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
