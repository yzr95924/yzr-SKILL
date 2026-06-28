# Fixtures

CLI 实现 wiki 仓时落盘的 `wiki/index.md` / `wiki/log.md` / `wiki/MEMORY/README.md` / `.gitignore`
四个文件的**字面量金标准**。

## 用法

CLI 实现时，把 fixture 视为"必须 1:1 复现的目标"——CLI 用自己的 render 函数生成产物，写盘后做字节级比对（`cmp -s`）：

```bash
# 假设 CLI 把产物写到 $TMP/wiki/
# fixture 路径 = my_SKILL/llm-wiki-management/references/fixtures/

cmp -s $TMP/wiki/index.md       <fixture>/index.md.txt
cmp -s $TMP/wiki/log.md          <fixture>/log.md.txt
cmp -s $TMP/wiki/MEMORY/README.md <fixture>/memory-readme.txt
cmp -s $TMP/.gitignore           <fixture>/gitignore.txt
```

任何一个不一致 → CLI 实现有 bug，应 fail 退出。

## fixture 与 spec 的关系

| | spec | fixture |
|---|---|---|
| **形态** | 人类阅读的契约文档（`wiki-spec.md`） | 机器读取的字节模板（`*.txt`） |
| **作用** | 告诉 CLI "应该长什么样" | 给 CLI "字面量比对" 的金标准 |
| **变更** | spec 改 → fixture 改 | fixture 改 → spec 也要跟着改 |
| **权威性** | spec 是概念权威 | fixture 是字节权威 |

两者必须**同步**：spec §3 描述 index.md 的 frontmatter 字段时，fixture/index.md.txt 的实际 frontmatter 必须与之匹配。任一不一致 → review 时立即暴露。

## 四个 fixture 对应的"角色"

| fixture | CLI 何时生成 | 后续谁维护 |
|---|---|---|
| `index.md.txt` | init 时刻 | **LLM agent**（每次 ingest / 重写 / 归档同步） |
| `log.md.txt` | init 时刻（首条 setup 条目） | **LLM agent**（只 append ingest/query/lint 条目） |
| `memory-readme.txt` | init 时刻 | **LLM agent**（追加经验条目到 MEMORY/ 下） |
| `gitignore.txt` | init 时刻 | **不动**（除非用户手动调） |

详细归属见 `wiki-spec.md` 顶部声明。

## fixture 取值约定

- 主题名：`Test`
- 日期：`2026-06-28`
- 这两个值是**验证占位符替换正确性**的固定锚点；CLI 实现时按用户传入值替换即可，
  替换后字节级比对应继续成立

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

## 字节级一致性证据

本目录的 index.md.txt / log.md.txt / gitignore.txt 三个 fixture 与原 `scripts/setup_wiki.py`
（已删除，2026-06-28）的 `render_index_md()` / `render_log_md()` / `render_gitignore()` 函数的
落盘产物**字节级一致**。memory-readme.txt 是 0.2.0 新增的（spec §5），无历史对照，
但由 spec §5.1 的字段定义作为权威字面量来源。

验证脚本（已跑过）：

```python
from setup_wiki import render_index_md, render_log_md, render_gitignore
Path("wiki/index.md").write_text(render_index_md("Test", "2026-06-28"), encoding="utf-8")
Path("wiki/log.md").write_text(render_log_md("Test", "2026-06-28"), encoding="utf-8")
Path(".gitignore").write_text(render_gitignore(), encoding="utf-8")
# 三个产物与本目录下同名 .txt 文件 cmp -s 通过
```

（脚本里 `from setup_wiki import ...` 在 setup_wiki.py 删除后不可用；这条历史证据保留供 review。
memory-readme.txt 来自 spec §5.1 + 后续手动定稿，无需历史对照。）

## 清理时机

`scripts/setup_wiki.py` 已删除，本目录是 CLI 实现唯一能参照的字节标准。**不要删除本目录**——
这是"出生形态"的最后一道防线。