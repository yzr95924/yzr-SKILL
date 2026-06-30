# MEMORY/

跨会话需要持久化的"为什么"与边界规则。新条目追加在末尾。`MEMORY.md`（本文件）只做索引，正文与本文件同级。

> 本文件是项目级规则的**唯一**真源。Claude 会话级 memory（`~/.claude/projects/.../memory/`）只放指向本文件的指针，不再持有内容副本，避免跟代码仓迁移时失同步。

## 规则

### Python 3.6 兼容

**Why：** 部署目标含 CentOS 7 等老 OS（官方源最高只有 Python 3.6，通过 `python36` / SCL `rh-python36` 提供）。3.6 写出的代码在 3.6+ 全版本都能跑，向上兼容比向下兼容重要。

**How to apply：** 新写 Python 脚本时避开以下特性（按最低引入版本列）：

| 最低版本 | 特性 | 替代写法 |
| --- | --- | --- |
| 3.7+ | `subprocess.run(capture_output=True, text=True)` | `stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True` |
| 3.7+ | `from __future__ import annotations` | 直接写完整注解（`Optional[X]` 而非 `X \| None`） |
| 3.7+ | `breakpoint()` | `import pdb; pdb.set_trace()` |
| 3.7+ | `asyncio.run` | `loop.run_until_complete(...)` |
| 3.8+ | walrus `:=` | 拆成两行 |
| 3.8+ | f-string `=`（`f"{x=}"`） | `f"x={x}"` |
| 3.9+ | PEP 585 内建泛型 `list[int]`、`dict[str, X]`、`tuple[X, Y]` | `from typing import List, Dict, Tuple` |
| 3.9+ | `zoneinfo`、`str.removeprefix/removesuffix` | 自行实现或 `s[:-len(x)] if s.endswith(x) else s` |
| 3.10+ | PEP 604 联合类型 `X \| Y`、`X \| None` | `from typing import Union, Optional`；用 `Optional[X]` |
| 3.10+ | `int.bit_count` | `bin(n).count("1")` |
| 3.10+ | `match` 语句 | if/elif 链 |

**静态扫描（写完自查）：**

```bash
grep -nE "(\| None|list\[|dict\[|tuple\[|capture_output|text=True|:=|breakpoint\(\))" path/to/script.py
```

空白命中即视为 3.6 不兼容。

**落地参考：** `yzr-skill-creator/scripts/` 下 8 个脚本（B1 修复时落地的合规示例）—— 含 `from typing import Optional, List, Dict, Tuple` 的导入，以及 `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 的标准调用形式。

### 后续脚本优先 Python 3

**Why：** 在 2026-06-20 反馈中明确——后续脚本优先用 Python 3 而非 bash / shell 实现，**同时**在 Python 3 内部严格走 3.6 语法以保老 OS 兼容。理由是：(1) 部署目标含 CentOS 7（`python36` / SCL `rh-python36`）等只到 Python 3.6 的环境，参见上方的 "Python 3.6 兼容" 小节；(2) 脚本语言统一用 Python 3 便于在 Python 生态内统一管理（包管理、`subprocess`、`pathlib` 等），不被 bash 平台差异 / shell 解析边界问题分神。

**How to apply：**

- **首选 Python 3** 写新脚本，不再新写 bash / shell 脚本。唯一例外是 shell 天然更自然的场景：一行管道、纯文本流处理、`awk` / `sed` / `grep` 一句话即可
- **Python 3 内部** 严格遵守上方 "Python 3.6 兼容" 小节的所有规则
  - `Optional[X]` 而非 `X | None`；`List[X]` / `Dict[X, Y]` / `Tuple[X, ...]` 而非 PEP 585 内建泛型
  - `subprocess.run(stdout=PIPE, stderr=PIPE, universal_newlines=True)` 而非 `capture_output + text`
  - 不使用 walrus `:=`、`match` 语句、`int.bit_count`、`f"{x=}"`、`from __future__ import annotations`、`breakpoint()`、`asyncio.run` 等 3.7+ 特性
- **已有的 bash 脚本** 不强制回溯改写，但新增脚本按本规则判断。`scripts/install-dev-deps.sh` 在 2026-06-20 已重写为 `install-dev-deps.py`，是这次转写的第一个落地例子
- **类型注解** 完整写（`Optional[X]` / `List[X]` / `Tuple[X, ...]` / `Dict[X, Y]`），不省略



### SKILL 描述类修改：默认同步仓库源

**Why：** 本仓库是 SKILL 的"源 / 描述"载体（`outline-wiki-setup/` / `outline-wiki-search/` / `outline-wiki-upload/` / `gemini-paper-summary/` / `yzr-skill-creator/` / `design-doc-edit/` 等顶层子目录即各 skill 源），而 Claude Code 加载的是 `.claude/skills/<name> -> ../../.agents/skills/<name>` 的软链（vendored 副本，被 `.gitignore` 排除）。两套文件**不同 inode**——`Edit` 默认改的是 vendored 副本，不在 git 跟踪范围内，会随下次 `npx skills` 同步被覆盖。

**How to apply：**

- 修改任何 skill 的 `SKILL.md` / `references/*.md` / `scripts/*.py` 等"描述类"文件前，**先**问自己："这次修改是要进仓库源（`.gitignore` 之外），还是只调 vendored 副本做本地实验？"
- 默认是前者（持续维护的代码），改完后**必须**同步到仓库源——通常用 `cp` 把 vendored 副本拷回源（`cp .claude/skills/<name>/SKILL.md <name>/SKILL.md`），用 `git status` / `git diff --stat` 确认
- 一次只改一个 skill，不要顺手把 vendored 里其他无关改动一起带回去——`cp` 之前先 `diff` 一遍
- 涉及仓库源里 `Edit` 不到的字符（如大段重写、含特殊符号的）也可以走 `cp`，但**只覆盖源里未改的部分**；源已被别处修改时必须 `Edit` 走精准 patch，否则会丢别人的改动
- 反例：上次的 SKILL 修改我只在 `.claude/skills/outline-wiki-management/` 改了，没主动同步到源仓库，被用户提醒才补；这就是这条规则要堵的洞（2026-06-29 拆 3 skill 后该路径已不存在，仅作历史反例保留）





### SKILL 源 vs 运行时 vendor：两套独立文件，改源才有效

**Why：** 复盘 2026-06-21 改 v3.2 caption 规则时栽的坑——`Skill` 命令从 `~/.claude/skills/<name>/SKILL.md` 加载（运行时 vendor），而代码仓源是仓库根的 `<name>/SKILL.md`。两者**不是软链，是两份独立文件**（vendor 是 `npx skills add` install 出来的真目录）。`Edit` 默认改的是 vendor，源没动——下次 npx 重装就丢改、或 `git status` 看不到这次改。

```text
/home/zryang/my_SKILL/gemini-paper-summary/                  # ← 代码仓源（SSOT）
/home/zryang/my_SKILL/.agents/skills/gemini-paper-summary/   # ← vendored 真目录
/home/zryang/my_SKILL/.claude/skills/gemini-paper-summary    # ← 软链 → 上面那个
```

`ls -la .claude/skills/gemini-paper-summary` → `lrwxrwxrwx ... -> ../../.agents/skills/gemini-paper-summary`，`file .agents/skills/gemini-paper-summary` → `directory`。

**How to apply：**

- **改 SKILL 必须改源**（仓库根 `<name>/`），改完**手动同步**到 `.agents/skills/<name>/`（vendor）才能让当前 Claude 会话看到新内容
- 同步命令（dry-run 先过一遍再实跑）：
  ```bash
  diff -q gemini-paper-summary/SKILL.md .claude/skills/gemini-paper-summary/SKILL.md
  rsync -a --delete --dry-run gemini-paper-summary/ .claude/skills/gemini-paper-summary/
  rsync -a --delete gemini-paper-summary/ .claude/skills/gemini-paper-summary/
  ```
- `cp` 风险：源被别处修改过（被别人改过）时 `cp` 会丢对方改动，**优先 Edit 精准 patch**；大段重写 / 含特殊字符时走 `cp` 但 `cp` 之前必须 `diff` 一次
- vendor 副本在 `.gitignore` 内，git 跟踪不到——只改 vendor 等于"本地实验"，**不算**给仓库做了贡献
- 现状：本次会话发现 prompt-template.md 在源（仓库根）和 vendor 不一致，已把 vendor 改回成源的旧版（revert），下一步在**源**重新做 v3.2 同步

**正文：** [`skill-source-vs-runtime-vendor.md`](./skill-source-vs-runtime-vendor.md)

### 影响 SKILL 输出的"为什么"记忆必须同步到 SKILL 源

**Why：** 本仓库是 SKILL 的代码仓。MEMORY 记的是"为什么 + 边界规则"，但**光放 MEMORY 不够**——SKILL.md / assets / scripts 才是 Claude Code 触发 SKILL 时实际加载的上下文。如果设计决策**没有**在 SKILL 文件里**显式落地**，下次触发 SKILL 时这个决策就丢了（典型 case：MEMORY §8 v3.2 写了"alt = 中文、不写独立 caption 行"，但 SKILL.md §核心原则 #5 + prompt-template.md 仍停留在 v3.1——脚本实际跑出来还是 v3.1 格式）。

**How to apply：**

- 写任何影响 SKILL **最终输出 / 行为** 的 MEMORY 时，**同步**做两件事：
  1. **改 SKILL.md 对应小节**（让 Skill 加载时看到新规则）
  2. **改 assets / scripts / references**（让脚本实际跑出新行为）
- 判定：影响输出格式 / 行为 / 边界 → 必须同步；纯工作日志 / 任务状态 → 留 MEMORY
- 冲突处理：MEMORY 和 SKILL 冲突时，**以更新日期晚的为准**；改 SKILL 的要把"为什么"补到 MEMORY；改 MEMORY 的要同步 SKILL
- 本条与上方 "SKILL 源 vs 运行时 vendor" 配套——同步时记得**两边都改**（源 + vendor）

**正文：** [`memory-synced-to-skill-source.md`](./memory-synced-to-skill-source.md)

### outline MCP 工具必须在 settings.local.json 加白名单

**Why：** 2026-06-21 实测——多次 `mcp__outline__update_document` 写入大文档（≥ 3000 字符）被 auto mode classifier 拦下（false positive），需要回退到 curl REST API。根因：`/home/zryang/my_SKILL/.claude/settings.local.json#permissions.allow` 之前只显式允许 `mcp__gemini-api-docs-mcp__*`，没有 `mcp__outline__*`。classifier 启发式判断下，大内容 / 多次连续调用容易踩雷。

**How to apply：**

- 新装 / 维护 outline MCP 时**同步**加 15 条 `mcp__outline__*` 白名单（覆盖 attachment / document / comment / collection / list_* 五组工具）
- 白名单是 mid-session 即时生效，不用重启 Claude Code
- **退路**：被拦时改用 outline REST API 走 curl + API key，POST `/api/documents.update`
- 不要只把白名单写用户级 `~/.claude/settings.json`——项目级 `settings.local.json` 没继承的话，agent 在本项目里还是被拦

**正文：** [`outline-mcp-permission-allowlist.md`](./outline-mcp-permission-allowlist.md)



### SKILL 代码仓优先级：SKILL 源 > MEMORY > vendor

**Why：** 2026-06-21 用户明确——

1. "本代码仓是一个管理 SKILL 的代码仓，MEMORY 和 vendor 目录下的内容，原没有实际对应 SKILL 目录的内容重要，优先保证对 SKILL 效果影响的内容都同步到了对应文件夹"
2. **"这些 SKILL 的目录后面用户会通过 npx skills 安装，安装时不会携带 MEMORY 的记录信息，所以需要确保 MEMORY 中影响 SKILL 效果的内容，都已经同步到了对应文件夹"**

**根因**：用户最终通过 `npx skills add` 把 `gemini-paper-summary/` / `outline-wiki-setup/` / `outline-wiki-search/` / `outline-wiki-upload/` 等子目录分发出去，**分发包只含 SKILL 目录内容**（`SKILL.md` + `assets/` + `scripts/` + `references/`），**不含** `MEMORY/` 也不含仓库的"为什么"记录。**所以 MEMORY 里的"影响 SKILL 效果"的内容如果不显式落到 SKILL 目录，npx 装出去的版本就会丢这些规则。**

**优先级排序**（从高到低）：

1. **SKILL 源**（仓库根 `gemini-paper-summary/` / `outline-wiki-setup/` / `outline-wiki-search/` / `outline-wiki-upload/` / `design-doc-edit/` / `yzr-skill-creator/`）—— SSOT，Claude Code 触发 skill 时实际加载的上下文；**也是 npx 分发包的内容**，安装到其他机器上的就是这些文件。影响 SKILL 行为的**所有**修改必须先改这里
2. **MEMORY**（`MEMORY/MEMORY.md` + 正文同级）—— 索引 + "为什么 + 边界规则"，**没有**实际运行效果，**也不会被 npx 分发**；只承载"为什么"注解，正文必须落到 SKILL 源
3. **vendor**（`.agents/skills/<name>/` + `.claude/skills/<name>` 软链）—— 当前 session 加载副本，**派生**于 SKILL 源；同样**不被 npx 分发**（仅本机 session 用）

**How to apply：**

- 改任何 SKILL 相关规则 / 输出格式 / 边界 → **必须**先改 SKILL 源（`SKILL.md` / `assets/` / `scripts/` / `references/`）
- **MEMORY 同步检查清单**（每次写 MEMORY 条目前 + 写入后自检）：
  1. MEMORY 条目引用的规则 / 边界 / 输出格式 / 行为，**有对应文件** 在 SKILL 源里？（`SKILL.md` / `assets/prompt-template.md` / `scripts/*.py` / `references/*.md`）
  2. **npx skills add 装出去的版本也能拿到这些规则**？如果只在本仓库的 `MEMORY/` 里就等于没装出去
  3. 跨机器场景：用户**新装**本 skill（不含本仓库任何历史），能否仅凭 `SKILL.md` + `assets/` + `scripts/` 复现所有行为？如果不能 → 缺东西
- vendor 同步是**派生操作**——SKILL 源改完后 `cp -r` 同步到 `.agents/skills/<name>/` 让当前 session 生效
- 冲突处理：MEMORY / vendor / SKILL 源三者矛盾时，**以 SKILL 源为准**；MEMORY 是过时的"为什么"提示，vendor 是过时的"加载副本"
- **反模式**：
  - 只改 MEMORY 不改 SKILL 源（规则在仓库外，**npx 装出去就丢**）
  - 只改 vendor 不改 SKILL 源（vendor 不在分发包内，**npx 装出去一样丢**；且本机 clean 重建也丢）
  - 只改 SKILL 源不 vendor 同步（当前 session 看不到新内容，**仅影响本地调试**）
  - **MEMORY 写规则但 SKILL 源已完整吸收**（MEMORY 不随 npx 分发，重复记录 = 死代码；维护时容易跟 SKILL 源漂移；按"SKILL 源是 SSOT"原则**应直接删除**，而不是"留 MEMORY 提醒"——SKILL.md 自己的描述才是 npx 装出去能看到的地方）

**关联**：

- [[memory-synced-to-skill-source]]——本规则的"前情提要"版（旧版只说"同步"，没强调优先级 + 没解释 npx 分发根因）
- [[skill-source-vs-runtime-vendor]]——vendor 副本的物理结构



### paper-wiki 整合：llm-wiki-management 只管本地，远端发布独立成 skill（2026-06-29 decoupling refactor 后重写）

**Why：** 2026-06-29 分析"llm-wiki-management 管理 paper-wiki（参考 gemini-paper-summary）"得出。llm-wiki-management 的 description 自己声明"不用于云端 wiki，走 outline-wiki-upload / outline-wiki-search"——把发布塞进它会违反自己的触发边界，糊掉"本地复利"身份。发布是跨 skill 编排胶水（读本地 + 驱动 outline MCP + 跟 outline_id + 图上传），通用性也超出 paper-wiki，该独立。**2026-06-29 decoupling refactor 后**：耦合方向归零——`llm-wiki-management → gemini-paper-summary`，producer 不假设有 consumer。

**How to apply：**

- **llm-wiki-management 永远不碰远端**——加 paper 支持时只做本地：raw 沿用 Karpathy LLM Wiki 约定（`raw/papers/<slug>.{quick,full}.md` + `raw/assets/<slug>/`，非 PDF、非压缩 summary）、source 页是多轮对话蒸馏出的成熟总结、两阶段（处理 PDF → 多轮蒸馏）
- **paper-wiki profile §7 是上游抽 PDF 工具的权威集成契约**（gemini-paper-summary 是**推荐实现**，**不**是硬依赖）——任意满足 raw 端约定的工具都可被消费
- **gemini-paper-summary 扩 `--full` 模式**（复用图片抽取机制、去字数压缩）产出全量抽取当 raw 底座；layout 沿用 Karpathy 模式，不硬绑定任何 consumer
- **远端发布 / outline 同步 / outline_id 跟踪 / 图上传 → 独立 publish skill**，别塞进 llm-wiki-management；**别现在建**，先在 paper-wiki profile 里跑稳再抽
- 落地时必须写进对应 SKILL 源（npx 分发不带 MEMORY）

**正文：** [`paper-wiki-integration-design.md`](./paper-wiki-integration-design.md)

### gemini-paper-summary --full 模式 4 个设计决策（2026-06-29，decoupling refactor 后重写）

**Why：** 为 gemini-paper-summary 补 `--full` 模式（产出"全量结构化转储"用于 Karpathy LLM Wiki raw 端约定）。决策点：(D1) 与 default 关系 = 单次调用两份产物 / (D2) layout = 沿用 Karpathy LLM Wiki raw 端约定（`raw/papers/<slug>.{quick,full}.md` + `raw/assets/<slug>/`）/ (D3) 骨架 = 沿用同 H2 + 解除 ≤2500 字符 + 按 `Section X.Y` 全文级展开 / (D4) Stage 2 视觉定位必须带；冲突检测默认拒绝覆盖（`--force-full`）。**重要**：layout 选择基于 Karpathy 模式的**可识别性**，不是为满足特定 consumer——producer 描述 layout，consumer 在自家 SKILL.md 里点名 producer。

**How to apply：** 本文为 producer 侧的设计 SSOT；`gemini-paper-summary-full-mode-design.md` 已按新单向口径重写。consumer 侧的集成契约见 [`llm-wiki-management/references/paper-wiki-profile.md` §7](../llm-wiki-management/references/paper-wiki-profile.md#7-与上游抽-pdf-工具的边界与集成gemini-paper-summary-是推荐实现)。`prompt-template.md` / `gemini_paper_summary.py` / `SKILL.md` 改动都指回 producer 侧 SSOT，consumer 侧改动指回 profile §7——避免口径漂移。

**正文：** [`gemini-paper-summary-full-mode-design.md`](./gemini-paper-summary-full-mode-design.md)

### H1 transform 决策：publish 时注入，local 保持无 H1（parked, 2026-06-29）

**Why：** 2026-06-29 用户提出——Gemini 产物（local `.md`）当前无 H1，标题在 outline `title` 字段（即 document ID）里、不在 markdown body。推送到 outline-wiki 后 outline doc 缺 H1，**浪费一级标题**且正文读者看不到标题。H1 注入是 **publish 时的 transform**——不属于 `gemini-paper-summary` 的职责（它要维持"无 H1"的 local 约定，与项目其他 4 个 SKILL.md 一致）。

**How to apply：**

- **`gemini-paper-summary` 不变**：保持产物无 H1（已通过 `prompt-template.md` 风格约定 #9 + 基础要求 #5 固化，2026-06-29 audit 后统一）
- **publish transform 注入 H1**：源 = `outline` `documents.create` 传入的 `title` 参数（无需额外 API 调用）；在调 outline API 前对 content 做 `f"# {title}\n\n{content}"` 拼接
- **不回写 local**：H1 只活在 outline doc body，local `.md` 文件保持无 H1——避免"local 有 H1、publish 又覆盖"的双写漂移
- **复活点**：建 publish skill 时重提，先实现 transform；同时在 `paper-wiki-profile.md` §7 加"H1 由 publish transform 注入（源 = outline `title`）"作为契约
- **park 原因**：publish skill 还没建（参考 [[paper-wiki-integration-design]] "别现在建"决策）；避免在 publish skill 落地前造临时小工具（with_h1.py 之类的预制件）
- **不撤回的边界**：本决策不破坏 audit 已立的"4 个 SKILL.md 无 H1"约定——它明确划出 **local 文件无 H1 / outline doc 有 H1** 两条规则的边界

**关联：**

- [[paper-wiki-integration-design]]——本决策的父决策（publish skill 独立、远端不归 llm-wiki-management）
- [[gemini-paper-summary-full-mode-design]]——producer 侧 SSOT；本决策不与 D1-D4 冲突（layout 不变，仅 H1 由 publish 端补）

### ddnsto relay 仅 HTTPS 443 才透到上游（2026-06-30 outline-wiki-setup 接入时新发现）

**Why：** 2026-06-30 给 self-hosted Outline 跑 outline-wiki-setup 时收到用户给的 `http://myoutline.ddnsto.com/mcp`，configure_mcp.py 的 test_connection 失败。curl 探测后确诊：**ddnsto relay 的 HTTP 80 端口对所有路径都回 "200 OK Content-Length: 0 + Server: Caddy"，HTTPS 443 才真正转发到上游后端**。用户原话"标记完的客户端主机,应该就可以访问了"是指 ddnsto 控制台要标记 client host——但**与 HTTP 80 占位无关**，标记仅让 HTTPS 路径生效。

**诊断关键**（先于任何"鉴权 / endpoint 错"的猜测）：换 API key / 换 Host 头 / 换路径 / 换方法**全部同响应**，唯独**换协议 http→https 后行为完全反转**拿到真实 Outline MCP 响应——决定性证据是协议层 middlebox。

**How to apply：**

- **接入任何走 ddnsto 隧道的 MCP 时，endpoint 必须用 `https://<sub>.ddnsto.com:443/mcp`**（或省略端口），不要用 http://
- 用户第一次给 http:// 时**直接尝试 https://**，不用先排查鉴权
- 已在 `outline-wiki-setup/SKILL.md` 故障排查段同步加症状+解药一行（指向 MEMORY 正文）

**正文：** [`ddnsto-relay-https-only-quirk.md`](./ddnsto-relay-https-only-quirk.md)

### 影响分发后行为的经验必须进 SKILL，不能只留 MEMORY（2026-06-30 实战感悟）

**Why：** 2026-06-30 修 ddnsto 陷阱 + outline MCP 白名单时发现——两份关键经验最初都只写在仓库 `MEMORY/`，**SKILL 没接收**。而 `MEMORY/` 是仓库 SSOT，**不进 npx、不进 vendor 副本、不会出现在新安装用户的 Claude Code 上下文中**——等于踩过的坑在新环境会重演。本轮把两条同步进了 SKILL.md / onboarding.md 才补上。

**判定核心问题**：「另一个用户在另一台机器上 `npx install <skill>`，能指望他们自己撞见并解决吗？」——不能则必须进 SKILL；能则可留 MEMORY；边界模糊倾向 SKILL（错放 SKILL 多一句废话；错放 MEMORY 会让人重蹈覆辙）。

**How to apply：**

- **新发现的"坑 / 经验"先进 SKILL，后 MEMORY**——MEMORY 是补充不是替代
- 进 SKILL 按"症状→指引 / 详方案放 references/"分层，保 SKILL.md 不顶 5000 词
- 同主题的另一篇 MEMORY（[[memory-synced-to-skill-source]]）从**作者改动流程**视角，本条从**用户分发端**视角，互补

**反模式**："先写 MEMORY 下次补 SKILL" = 窗口期给未来用户挖坑；"description 加触发就够" = description 只决定**是否触发**，不决定**怎么跑**。

**正文：** [`experience-affecting-skill-distribution-goes-to-skill-not-memory.md`](./experience-affecting-skill-distribution-goes-to-skill-not-memory.md)
