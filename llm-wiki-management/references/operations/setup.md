# Setup 详细流程

本 skill 的 setup 是**一次性**的——把空目录变成符合 Karpathy 模式的 wiki 仓。
完成后用户只需把原始资料丢进 `raw/`，后续走 ingest / query / lint。

## 一、为什么分开 setup 和 ingest

- **setup** = 建脚手架（目录 + CLAUDE.md + index/log 空文件）
- **ingest** = 把第一份资料变成 wiki 内容

第一份 ingest 之前 wiki 是"空的"；setup 后到第一次 ingest 之间，用户可以自己往
raw/ 堆一批资料，再一次性 ingest 多个。

## 二、setup 前的环境准备

1. **确定 wiki 根目录**（`LLM_WIKI_ROOT`）
   - 推荐 `~/wiki/<topic-name>/`
   - `<topic-name>` 用 kebab-case（例 `llm-systems`、`distributed-systems`）
2. **确定主题名**（`<TOPIC_NAME>`）
   - 用于写入 CLAUDE.md frontmatter + 一些 log 条目
   - 例：`"LLM Systems"`、`"Distributed Systems"`
3. **确认 git 已装**
   - setup 脚本会 `git init`（如果目录还不是 git 仓）
4. **确认用户准备**：
   - 不要在 setup 之前让用户往 raw/ 放资料（首次 setup 后再放更清晰）

## 三、setup 脚本行为详解

调 `setup_wiki.py <topic-name> [<wiki-root>]`：

```bash
# 默认从 LLM_WIKI_ROOT 读
LLM_WIKI_ROOT=~/wiki/llm-systems \
  python3 llm-wiki-management/scripts/setup_wiki.py "LLM Systems"
```

脚本做的事（按顺序）：

1. **创建目录结构**（不存在则建）：
   ```
   <wiki-root>/
   ├── raw/
   │   ├── articles/      # 用户后续放资料
   │   └── assets/        # 图片 / PDF
   └── wiki/
       ├── index.md
       ├── log.md
       ├── comparisons/   # 字母序（与 page-templates.md §二 一致）
       ├── concepts/
       ├── entities/
       ├── sources/
       └── syntheses/
   ```

2. **生成 `<wiki-root>/CLAUDE.md`**
   - 从 skill 的 `references/claude-md-template.md` 读模板
   - 替换 `{{TOPIC_NAME}}` → 用户传的主题名
   - 替换 `{{SETUP_DATE}}` → 当天日期（`YYYY-MM-DD`）
   - 写到 `<wiki-root>/CLAUDE.md`

3. **生成 `wiki/index.md`**
   - frontmatter：`title="<topic-name> Index"`, `type="index"`, `created=updated=today`
   - 正文：5 个空类别段（Entities / Concepts / Sources / Comparisons / Syntheses），
     各带一句"暂无内容"的占位

4. **生成 `wiki/log.md`**
   - frontmatter：`title="<topic-name> Log"`, `type="log"`, `created=updated=today`
   - 正文：一条 setup 条目 `## [YYYY-MM-DD] setup | Initial scaffold by llm-wiki-management`

5. **生成 `.gitignore`**
   - 忽略 `.DS_Store`、Obsidian 配置等
   - **不忽略** `wiki/`、`raw/`、`CLAUDE.md`

6. **`git init`**（若尚未初始化）
   - `git add . && git commit -m "Initial wiki scaffold: <topic-name>"`

7. **打印后续指引**：
   - schema 读取说明：`CLAUDE.md` 在 wiki 根目录内会被 Claude Code 自动加载；别处由
     skill 经 `$LLM_WIKI_ROOT` 按需读取，**无需 symlink**
     — 关键：**让 LLM 启动时自动读到 schema**
   - 提示用户把 `LLM_WIKI_ROOT` 写入 shell 配置
   - 提示用户开始往 `raw/articles/` 丢资料

## 四、setup 后的验证清单

跑完 setup 后，agent 应当：

- [ ] 列出 `<wiki-root>/` 目录确认结构正确
- [ ] 读 `<wiki-root>/CLAUDE.md` 确认主题名 + 日期替换正确
- [ ] 读 `wiki/index.md` 确认 frontmatter 完整
- [ ] 读 `wiki/log.md` 确认 setup 条目格式正确
- [ ] `git log` 看到 1 个 commit
- [ ] 问用户：是否要现在做一次 ingest？如果是——把第一份资料路径给 agent

## 五、setup 失败的常见原因

- **目录已存在且非空**——脚本应拒绝（防误覆盖）；让用户选新目录或手动清空
- **`LLM_WIKI_ROOT` 未设**——脚本回退到 `~/wiki/` 下的 `<topic-name>/`，但需提示用户
- **git 未装**——脚本可以跳 git 步骤并 warn，但 lint 的 raw/ 不可变性检查会失效
- **模板找不到**——脚本路径相对 skill 自身；不要 `cd` 到别处再调

## 六、setup 的边界

- **不**接管已存在的 wiki 仓——若目标目录已有 `CLAUDE.md` 或 `wiki/index.md`，拒绝执行
- **不**写具体内容——只搭脚手架；写内容走 ingest
- **不**做 git push / 设置 remote——本地仓即可；用户自行决定 remote
