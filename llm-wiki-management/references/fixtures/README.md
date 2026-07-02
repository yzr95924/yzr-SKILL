# Fixtures

CLI 实现 wiki 仓时落盘的 `wiki/index.md` / `wiki/log.md` / `wiki/MEMORY/MEMORY.md`
/ `scripts/SCRIPTS.md` / `.gitignore` 五个文件的**字面量金标准**（`scripts/SCRIPTS.md`
于 0.9.0+ 引入）。

## 用法

CLI 实现时,把 fixtures 视为**带占位符的字节模板**,把 `references/canonical/` 视为
**字节金标准**——CLI 用自己的 render 函数生成产物,写盘后做字节级比对（`cmp -s`）：

```bash
# 假设 CLI 把产物写到 $TMP/wiki/
# canonical 路径 = my_SKILL/llm-wiki-management/references/canonical/
# fixture 路径  = my_SKILL/llm-wiki-management/references/fixtures/

cmp -s $TMP/wiki/index.md         canonical/index.md
cmp -s $TMP/wiki/log.md            canonical/log.md
cmp -s $TMP/wiki/MEMORY/MEMORY.md  canonical/memory-index.md
cmp -s $TMP/scripts/SCRIPTS.md     <fixture>/scripts.md.txt  # 0.9.0+；无占位符,直接 fixture 比对（与 gitignore 同款）
cmp -s $TMP/.gitignore             <fixture>/gitignore.txt   # .gitignore 无占位符,直接 fixture 比对
```

任何一个不一致 → CLI 实现有 bug,应 fail 退出。

> **术语**：fixtures 是**模板**(带 `{{TOPIC_NAME}}` / `{{SETUP_DATE}}` 占位符),
> canonical 是**渲染后字面量**(用锚点 mapping `{TOPIC_NAME: "Test", SETUP_DATE: "2026-06-28"}`
> 把 fixtures 跑一遍的产物,作为 SKILL 仓字节金标准)。CLI 升级 / fixture 变更时,SKILL 仓 owner
> 重新生成 canonical/。

## fixture 与 spec 的关系

| | spec | fixture |
|---|---|---|
| **形态** | 人类阅读的契约文档（`wiki-spec.md`） | 机器读取的字节模板（`*.txt`） |
| **作用** | 告诉 CLI "应该长什么样" | 给 CLI "字面量比对" 的金标准 |
| **变更** | spec 改 → fixture 改 | fixture 改 → spec 也要跟着改 |
| **权威性** | spec 是概念权威 | fixture 是字节权威 |

两者必须**同步**：spec §3 描述 index.md 的 frontmatter 字段时，fixture/index.md.txt 的实际 frontmatter 必须与之匹配。任一不一致 → review 时立即暴露。

## 五个 fixture 对应的"角色"

| fixture | CLI 何时生成 | 后续谁维护 |
|---|---|---|
| `index.md.txt` | init 时刻 | **LLM agent**（每次 ingest / 重写 / 归档同步） |
| `log.md.txt` | init 时刻（首条 setup 条目） | **LLM agent**（只 append ingest/query/lint 条目） |
| `memory-index.txt` | init 时刻 | **LLM agent**（追加经验条目到 MEMORY/ 下 + 同步 MEMORY.md 索引） |
| `scripts.md.txt`（0.9.0+） | init 时刻 | **用户 + LLM agent**（添加 / 修改脚本与同步 SCRIPTS.md 段是原子动作；与 MEMORY/tags.md 同形态——无 frontmatter） |
| `gitignore.txt` | init 时刻 | **不动**（除非用户手动调） |

详细归属见 `wiki-spec.md` 顶部声明。

## fixture 取值约定

fixtures 是**带占位符的字节模板**(而非渲染后的字面量)：
- 主题名占位符：`{{TOPIC_NAME}}`
- 日期占位符：`{{SETUP_DATE}}`
- `.gitignore` / `scripts.md.txt`（0.9.0+）无占位符,直接落盘

CLI 必须按 `mapping = {"TOPIC_NAME": <用户传入>, "SETUP_DATE": <today YYYY-MM-DD>}` 做替换，
**不**做替换的占位符会在落盘后被 lint 立即报错(spec §11)。

## CLAUDE.md 占位符（不在 fixture 范围）

`CLAUDE.md` 由 workspace CLI 拷贝 `references/claude-md-template.md` 生成，**不在** fixture 覆盖范围
（fixture 只覆盖 CLI init 时刻的"成品"，CLAUDE.md 是模板替换产物）。CLI 必须替换的占位符：

| 占位符 | 替换为 |
|---|---|
| `{{TOPIC_NAME}}` | 用户传入的主题名 |
| `{{SETUP_DATE}}` | 当天日期 `YYYY-MM-DD` |
| `{{WIKI_SPEC_VERSION}}` | CLI 当前兼容的 wiki spec 版本 |
| `{{CLI_VERSION}}` | CLI 自身版本号 |

CLI 替换后做内容级验证（不能用 fixture 字节比对）：

1. 4 个 `{{...}}` 占位符**全部被替换**——`grep -c '{{' CLAUDE.md` 应为 0
2. 生成的 CLAUDE.md §八 "Wiki Spec 版本" 与 SKILL 仓 `metadata.wiki_spec_version` 一致

## 字节级一致性证据(渲染后)

fixtures 是**模板**;CLI 渲染后产物与 `references/canonical/` 下的字面量文件**字节级一致**。
canonical/ 下的字面量文件是把 mapping 喂 `{TOPIC_NAME: "Test", SETUP_DATE: "2026-06-28"}` 后
渲染产物的副本,作为 SKILL 仓字节金标准。

CLI 升级 / fixture 变更时,跑附录 A 自检:用锚点 mapping render → cmp canonical → 不一致 = CLI / fixture 有 bug。

## 清理时机

`canonical/` 下的字面量文件是 SKILL 仓的**字节金标准**,`fixtures/` 是**带占位符的字节模板**。
**不要删除**任一目录——前者是字节防线的最后一道,后者是占位符替换的源材料。