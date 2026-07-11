# Semantic-merge 规则（0.18.0+）

> 本文件原为 `lint-checklist.md` §五（0.18.0+ 拆出）。`lint_checkiki.py --check-version --apply`
> 落盘的 `.migration-plan.json`（含 `actions[]` 修内容页 frontmatter + `fixtures_actions[]`
> 修约定文件）走 agent 执行时，**结构性字节合规**由 `scripts/check_wiki_fixtures.py` 扫并产出
> `fixtures-fix-*` action；**跨 entry 的语义合并**（老字段升级、index 重复条目、多 MEMORY
> 条目归并、0.16.0 → 0.17.0 anchor 多 entry 合并）由 agent 按本文件规则走——脚本不替代语义判断。

## 五、Semantic-merge 规则（0.18.0+ agent 走 `.migration-plan.json` 时的合并依据）

本节是 0.18.0+ 加进来的——把 `lint_wiki.py --check-version --apply` 落盘的
`.migration-plan.json`（含 `actions[]` 修内容页 frontmatter + `fixtures_actions[]`
修约定文件）做成 agent 可独立执行的标准化 step。**结构性字节合规** 由
[`scripts/check_wiki_fixtures.py`](../scripts/check_wiki_fixtures.py) 扫并产出对应
`fixtures-fix-*` action（含 `expected` / `actual`）；**跨 entry 的语义合并**（老字段升
级、index 重复条目、多 MEMORY 条目归并、0.16.0 → 0.17.0 anchor 多 entry 合并）
由 agent 按本节规则走。本 skill **不**在脚本里硬塞语义理解——`scripts/` 只产 plan，
LLM 用本节规则人工合并。

### 5.1 frontmatter 字段合并

- `confidence: <v>` 单独存在 → 删 `confidence`；若 `v == high` 则加 `reviewed: true`
  + `reviewed_at: <migrate-day YYYY-MM-DD>`。`<migrate-day>` 取 `.migration-plan.json`
  `generated_at` 字段（plan 落盘当日，由 lint_wiki.py 在 `--apply` 时自动写入）
- 同时含 `confidence` + `reviewed` → **`legacy-confidence-conflict`**，转人工裁定，
  永远不进 plan（已在 plan["skipped_conflicts"] 里标红）
- `type: memory` / `type: memory-entry`（MEMORY 扩展类型）→ **保留原样**——
  0.19.0 起 MEMORY 桶的 `type` 字段经 `VALID_TYPES` 扩展后两类均合法（spec §5.2）；
  无需迁到 `memory-entry` 也无需删除 `type`
- `subpath:` 字段（0.17.0 退役的 anchor 字段）→ 走 §5.3 anchor 合并处理，不在本节管

### 5.2 wiki/index.md 条目合并

- **同 `<relative-path>` link 但多条目出现** → 留信息最完整的那一条（按以下优先级）：
  1. 含 `✓ reviewed <date>` badge（最新 reviewed_at）
  2. 含 `description` 摘要字段
  3. `updated` 最新者
  余删
- **同 `<title>` 词但不同 `<relative-path>`** → 标红（`✗ duplicate-title`），转人工裁定——
  是 entity 重命名（保留新路径、合并到老路径）还是概念拆页（重命名其中之一）由人决定
- **新分类（如 0.X 引入第六类 `Comparisons`）→ 老 wiki 无该类时**，在 wiki/index.md 末尾
  按 wiki-spec §3 模板加新类别 H2 + 一行 `<!-- agent: TODO 归类旧页 -->` 占位，提醒人工归类
- **`raw/external/<symlink>` 形式的源条目**——0.17.0+ 改用 symlink 名（kebab-case）而非
  老 `<source-name>/` 子目录；index.md 里所有 `raw/external/<source-name>/...`
  形式条目同步改为 `raw/external/<symlink>/...`

### 5.3 raw/external anchor 合并（0.16.0 → 0.17.0 TOML 迁移）

anchor 从「每仓一份 `<source-name>/.symlink-anchor.json`（JSON object）」改为「单文件
`external/.symlink-anchor.toml`（TOML `[[entry]]` 数组）」。迁移走 5 步：

1. `find raw/external -name .symlink-anchor.json` 找全部老 anchor
2. 对每个 `<source-name>/.symlink-anchor.json`：
   - 读 JSON 拿 `{target, captured_at, kind, ...git-扩展字段}`
   - 扫 `<source-name>/` 下所有 symlink（每个 symlink = 一条 entry）
3. 对每个 symlink `<name>`：
   - 检查 `raw/external/<name>` 是否被占用（symlink 或目录）；占用 → 标 `✗ conflict` 转
     人工决定改名 / 合并 / 跳过
   - 不冲突 → `mv <source-name>/<name> <name>`（移 symlink 到 `external/` 顶层）
4. 构造 `[[entry]]` 块（含 `symlink` + `target` + `captured_at` + `kind='external-repo'`
   + git 仓时 `remote_url`/`commit`/`branch` 三扩展字段），追加写到
   `raw/external/.symlink-anchor.toml` 末尾（按 symlink 名字典序排版，便于 git diff）
5. `rm -rf raw/external/<source-name>/` 删整个子目录

**subpath 字段退役**：老 anchor 含 `subpath` 时，先创建两个 symlink——
`<name>` → `target` + `<name>-sub` → `target/<subpath>`，再写两条 entry（subpath 信息
落到 entry 的 `notes` 字段，可选）。

**多仓合并**：若老 wiki 有 N 个 `<source-name>/` 子目录同时迁移，按 symlink 字典序排版
新 anchor 文件——每仓一个 `{symlink, target, captured_at, kind, ...}` 块。

**反模式**：

- **不要**用脚本（`Python json.dumps`）整文件 `tomllib.dump` 整文件重写——会丢注释、丢
  字段顺序、跨机器 diff 噪音
- **不要**保留任何 `<source-name>/` 子目录——`symlink-anchor-flat-not-legacy` check
  看到会报 error
- **不要**在保留老 anchor JSON 的同时新建 TOML（两份并存会让 lint 报
  `external-anchor-orphan`）——必须删 JSON 才能写到 TOML 同一份 manifest

### 5.4 MEMORY 经验条目合并

- **两条 MEMORY entries 描述同一 case**（`grep` / 关键词检索可判定）→ 留更新日期晚者，
  旧 entry 文末追加一行 `# superseded by <new-slug>`，**不**删除（踩坑记录沉淀价值大）
- **或合并为一条多 bullet 形式**（`- 原因: ... \n - 解法: ... \n - 验证: ...`）——LLM
  按上下文长度 / 复用价值选；短经验优先合并，长经验（> 30 行）优先 supersede
- **索引同步**——无论是 supersede 还是合并，**必须**同步更新 `MEMORY/MEMORY.md` 索引
  一行（合并后删旧 slug 行，加合并后的新行；supersede 后旧 slug 行保留但加 supersede 提示）

### 5.5 wiki/log.md 严格保留（不合并）

- 历史 log **永远不**允许删除 / 合并 / 修改
- 唯一例外：0.16.0- 老 wiki 在 CLI 红线贯彻时 log 含 legacy `git init` 之类无效行——
  保留不修，lint 不报（log-rotation / log-format 都不查 legacy git 行）
- `fixtures-fix-log-format` action 仅当 **新增** 行不合规时落，迁移期**不变更 history**

### 5.6 决策树（脚本 vs LLM 合并）

| 场景 | 工具 |
|---|---|
| 结构性字节缺失（`.gitignore` 旧规则 / `MEMORY.md` 含 frontmatter） | 脚本 → `fixtures-fix-*` action；LLM 用 Edit 落 |
| 跨多 entry 语义归并（`subpath` 拆多 symlink / 重复 MEMORY 合并） | 脚本只 plan；LLM 走 §5.3 / §5.4 规则用 Edit/Write 落 |
| 冲突页（老 + 新字段共存，如 `confidence` + `reviewed`） | 转人工裁定 — 不进 plan；plan["skipped_conflicts"] 标红 |
| log 类（历史 log 修订） | **不**动 — lint 永远不报 log 字段 |
| 子目录 → 扁平（0.17.0 anchor 翻新） | 脚本只报 `symlink-anchor-flat-not-legacy`；LLM 走 §5.3 五步迁移 |

**判定经验**：看完 plan["actions"] + plan["fixtures_actions"] 之后——
若 actions 数量 > 50 或含 ≥ 3 条 `fixtures-fix-anchor-*`，agent 必须先 Read
[`references/migrate-workflow.md`](migrate-workflow.md) 走"多步迁移"流程；反之直接顺序 Edit。