---
name: outline-wiki-setup
description: 用户要把 Outline Wiki 接入 Claude Code 时使用——outline MCP 工具未
  注册 / 工具列里看不到、首次配置 outline MCP、或已拿到 endpoint + API key /
  OAuth 想连上。配置写完后用户必须重启一次会话才会生效（Claude Code 的硬约束，
  无法 mid-session 重载）。也覆盖配置阶段排查：MCP 未启用、401 / 403、重启后
  仍看不到 server。**不**用于搜 / 读 / 写 / 编辑 outline 文档（走
  outline-wiki-search / outline-wiki-upload）；**不**用于 Notion / Confluence /
  Obsidian / GitHub Wiki。
metadata:
  author: Zuoru YANG
  category: knowledge-base
  last_modified: 2026-06-29
---

# Outline Wiki Setup

把 Outline Wiki 内置 MCP 服务接入 Claude Code 的**一次性配置** skill。
本 skill 解决"工具列里看不到 `mcp__outline__*`"这一类**配置阶段**问题——
搜 / 读 / 写 / 编辑的具体文档操作，分别由 [`outline-wiki-search`](../outline-wiki-search/SKILL.md)
和 [`outline-wiki-upload`](../outline-wiki-upload/SKILL.md) 负责。

完成本 skill 的工作后，配置信息按所选 scope 落盘（`project` 默认 → 仓库根
`.mcp.json`；`user` / `local` → `~/.claude.json`），agent 在当前项目内就能调
outline MCP 工具；之后所有 outline 文档操作都由另外两个 skill 接管。

## 何时使用 / 不使用

### 使用

- 用户首次提到"接入 outline / 配置 outline MCP / outline 怎么连"
- 用户的 endpoint 形态是 `https://<your-subdomain>.getoutline.com/mcp` 或
  `https://<your-domain>/mcp`（自托管）
- 当前 session 调 `mcp__outline__*` 工具失败，提示未注册 / 连接被拒
- 用户已拿到 **API Key**（Settings → API）或走 **OAuth** 浏览器登录
- 需要排查"配置写入失败 / 重启后 /mcp 看不到 outline / 401 / 403"等
  配置阶段问题
- 客户端是 Claude Code / Claude Desktop / Cursor / 其他支持 Streamable HTTP
  传输的 MCP 客户端

### 不使用

- **搜 / 读 outline 文档**——走 [`outline-wiki-search`](../outline-wiki-search/SKILL.md)
- **写 / 编辑 outline 文档**（含图片附件 / @mention / 评论 / Collection 管理
  / 移动 / 删除）——走 [`outline-wiki-upload`](../outline-wiki-upload/SKILL.md)
- **非 Outline Wiki 的知识库**（Notion / Confluence / Obsidian / GitHub Wiki）
- **配置已成功、只是个别调用报错**——按 outline-wiki-search / outline-wiki-upload
  的"故障排查"小节定位

## 输入 / 输出

### 输入

启动时需具备以下任一鉴权材料：

- **API Key**：在 Outline Wiki 工作区 **Settings → API** 中生成，通过 HTTP 头
  `Authorization: Bearer <key>` 传递——适合 CI / 自动化 / agent 走非交互模式
- **OAuth**：在客户端添加 MCP 端点后**自动弹出浏览器登录窗口**——适合交互式
  场景（Claude Code / Claude Desktop）

外加 **MCP endpoint URL**（二选一）：

- 官方云：`https://<your-subdomain>.getoutline.com/mcp`
- 自托管：`https://<your-domain>/mcp`（路径固定为 `/mcp`）

### 输出

- **配置写入**（按 scope 落盘）：
  - `project`（默认）→ 仓库根 `.mcp.json`（可随 git 共享给团队）
  - `user` → `~/.claude.json#mcpServers`（本机所有项目）
  - `local` → `~/.claude.json#projects.<projectPath>.mcpServers`（仅本机本项目）
- **首次进入项目**：Claude Code 弹一次 trust prompt，按提示批准即可——每个
  项目只弹一次
- **重启 Claude Code 当前会话**（硬约束）后，`/mcp` 列表里能看到
  `outline ✓ Connected`，agent 可调 `mcp__outline__*` 系列工具

## 设计决策（重启硬约束）

> **重启 Claude Code 是硬约束**。Outline Wiki MCP server 必须在
> `~/.claude.json#mcpServers` 中注册，且 Claude Code CLI 在 session 启动时
> 一次性读入；mid-session 改文件不会被重读，也没有 `claude mcp reload` /
> `claude mcp restart` / `claude mcp reconnect` 这类子命令。
> `/mcp` 斜杠命令能 reconnect **已注册**的 server，但**不会**加载新 server。
>
> 因此：使用本 skill 前，**如果 outline 相关 MCP 工具尚未在当前 session 注册**，
> 必须先跑配置脚本，**然后重启当前会话**（推荐 `claude --continue` 续接历史）。
> 完整流程、"为什么必须重启"以及重启后验证清单见
> [`references/onboarding.md`](references/onboarding.md)。

### 已考虑过的"绕路"以及为什么也不可行

| 方案 | 问题 |
| --- | --- |
| 写项目级 `.mcp.json` | 同样在 session 启动时读；项目级多一层 trust prompt——本 skill 默认就是项目级，已接受这个成本换取"配置不外溢到其他项目" |
| 跑 `claude mcp serve` 转发 | 把 Claude Code 自己当 server 转发，与添加新 server 无关 |
| 用脚本 `kill` 当前进程并重启 | 脚本拿不到用户的终端控制权，也破坏 session 状态 |
| `mcp-remote` 代理 | 只是把 Streamable HTTP 转 STDIO，仍要 restart session |

结论：**重启是 Claude Code CLI 的硬约束**。本 skill 的工作是让用户**只重启
一次**、**重启即生效**、**重启后能立即验证**。

## 工作流 / 步骤

### 标准流程

1. **检测当前状态**：先检查 `mcp__outline__*` 工具是否已在 session 注册
   - 若是 → 已配置完成，提示用户直接走 outline-wiki-search / outline-wiki-upload
   - 若否 → 进入引导配置流程
2. **收集信息**：用 `AskUserQuestion` 引导用户提供
   - endpoint 类型（官方云 / 自托管）
   - endpoint 实际域名（子域名或自托管域名）
   - 鉴权材料（API key 或 OAuth）
   - 配置范围 scope（`project` 默认 / `user` / `local`；详见
     [`references/onboarding.md`](references/onboarding.md) 的 Q3）
3. **调用配置脚本**：把收集到的值放到环境变量，调 `scripts/configure_mcp.py`
4. **验证注册**：脚本内部跑 `claude mcp get outline` 确认 `Status: ✓ Connected`
5. **提示用户重启**：打印重启后验证清单，**不要**让脚本自己重启（会破坏 session）
6. **重启后验证**（用户执行）：
   - `Ctrl+D` 退出当前 session → `claude --continue` 续接
   - `/mcp` 看 `outline ✓ Connected`
   - 试调一次 `mcp__outline__search_documents`（任意 query）确认可用
   - 失败按 [`references/onboarding.md`](references/onboarding.md) "常见问题"排查

### 最常用路径（API Key 鉴权，非交互模式）

```bash
OUTLINE_MCP_ENDPOINT='https://<your-subdomain>.getoutline.com/mcp' \
OUTLINE_MCP_AUTH_METHOD='apikey' \
OUTLINE_MCP_API_KEY='<key>' \
python3 outline-wiki-setup/scripts/configure_mcp.py
```

执行成功后，**必须重启 Claude Code 当前会话**，新工具才会出现在
`mcp__outline__*` 列表中。

OAuth 鉴权或希望手动跑：直接 `python3 outline-wiki-setup/scripts/configure_mcp.py`
走交互模式，脚本会逐项提示。

### Scope 选择

配置范围（scope）决定配置写到哪里、对谁可见。交互模式用脚本的
`choose_scope()` 三选一；agent 驱动通过 Q3（见
[`references/onboarding.md`](references/onboarding.md)）收集后用
`OUTLINE_MCP_SCOPE` 传入；非交互模式直接设 `OUTLINE_MCP_SCOPE`：

- `project`（默认）：仅当前项目，落仓库根 `.mcp.json`，可随 git 共享给团队
- `user`：本机所有项目共享，落 `~/.claude.json#mcpServers`
- `local`：仅本机 + 当前项目，落 `~/.claude.json#projects.<projectPath>.mcpServers`，不进 git

### 受控入口约束

**`scripts/configure_mcp.py` 是唯一受控的客户端配置入口**。agent **不**直接
调 `claude mcp add`、也**不**直接编辑 `~/.claude.json` 或
`.claude/settings.local.json`。agent 只负责：

1. 收集信息（endpoint + 鉴权材料）
2. 拼环境变量
3. 调 `scripts/configure_mcp.py`

文件写入由脚本（透传 `claude mcp add`）完成。

### 故障排查

按以下顺序定位：

1. **认证失败（401 / 403）**
   - API Key：检查是否过期或被撤销，让用户重新生成
   - OAuth：让用户重新走一次授权流程（输入 `/mcp` 触发）
2. **MCP 未启用（连接被拒）**
   - 提示用户到 Outline Wiki 工作区 **Settings → AI** 确认 MCP toggle 已开启
   - 自托管实例需管理员在控制台开启
3. **`claude mcp get outline` 返回 "未找到"**
   - 配置写入失败。常见原因：
     - 环境变量没传到子进程（脚本只读 `os.environ`，shell 没 export）
     - `claude` CLI 没登录（提示用户先 `claude login`）
     - 磁盘写入失败（检查 `~/.claude.json` 权限）
4. **重启后 `/mcp` 仍看不到 outline**
   - 终端跑 `claude mcp list` 看是否真的注册上了
   - 确认启动 Claude Code 的用户与跑脚本的用户是同一个
     （`whoami` / `$HOME` 一致）
   - 极端情况：删掉 `~/.claude.json` 中
     `projects.<projectPath>.mcpServers.outline` 段，重新跑一次脚本

## 参考样例

### 样例一：首次接入（API Key 模式）

**用户指令**："帮我接入我们公司的 outline，endpoint 是 `https://acme.getoutline.com/mcp`，
API key 在我环境变量 `OUTLINE_API_KEY` 里"

**执行**：

```text
1. 探测环境变量：bash -lc 'test -n "$OUTLINE_API_KEY" && echo present || echo missing'
   → present
2. 直接调脚本（非交互）：
   OUTLINE_MCP_ENDPOINT='https://acme.getoutline.com/mcp' \
   OUTLINE_MCP_AUTH_METHOD='apikey' \
   OUTLINE_API_KEY=$OUTLINE_API_KEY \
   python3 outline-wiki-setup/scripts/configure_mcp.py
3. 脚本内部：握手测试 + claude mcp get outline 验证 + 打印 4 步重启清单
4. 让用户 Ctrl+D → claude --continue
5. 用户重启后说"试调 outline 搜索 '测试'"，验证生效
```

### 样例二：重连（已注册但 Connected 失败）

**用户指令**："之前配过 outline，但今天 /mcp 看到 outline ⏸ Pending approval，
点一下 trust 也没用"

**执行**：

```text
1. 跑 claude mcp get outline 看具体状态
2. 若 Status: ⏸ Pending → 项目级 trust prompt 没批准；让用户到 Claude Code 里
   看信任弹窗
3. 若 Status 已 Connected 但调用报错 → 99% 是鉴权问题，重新跑脚本覆盖 key
4. 都不行 → 删掉 projects.<projectPath>.mcpServers.outline 段，重跑配置
```

## 相关参考

- [`references/onboarding.md`](references/onboarding.md) — 完整 onboarding 流程
  （快速入口 / 前置条件 / 引导配置 / 重启后验证清单 / 设计决策 / 常见问题）
- [`references/auth.md`](references/auth.md) — 鉴权方式 + 多客户端接入命令
  （Claude Code / Claude Desktop / Cursor）
- [`scripts/configure_mcp.py`](scripts/configure_mcp.py) — 唯一受控的客户端配置入口
- [`outline-wiki-search`](../outline-wiki-search/SKILL.md) — 配套：搜 / 读 outline 文档
- [`outline-wiki-upload`](../outline-wiki-upload/SKILL.md) — 配套：写 / 编辑 outline 文档
