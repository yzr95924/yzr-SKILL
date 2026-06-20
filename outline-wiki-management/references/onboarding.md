# 客户端接入与首次配置

本附录集中描述 **Outline Wiki MCP 服务** 在 Claude Code 中的客户端接入流程，
包括：检测当前状态、引导收集配置信息、调用注册脚本、重启后验证清单、
设计决策（为什么必须重启）以及常见问题。

SKILL.md 主体只规定"做什么"（搜索 / 读取 / 创建 / 编辑），不规定"怎么连"。
读完本附录后回到主文档继续工作流。

## 目录

- [快速入口](#快速入口)
- [前置条件](#前置条件)
- [检测当前状态](#检测当前状态)
- [引导配置（agent 驱动）](#引导配置agent-驱动)
- [调用脚本](#调用脚本)
- [手动退路](#手动退路)
- [重启后验证清单](#重启后验证清单)
- [设计决策：为什么必须重启](#设计决策为什么必须重启)
- [常见问题](#常见问题)
- [旧版配置清理](#旧版配置清理)

## 快速入口

最常用路径（API Key 鉴权，agent 走非交互模式时）：

```bash
OUTLINE_MCP_ENDPOINT='https://<your-subdomain>.getoutline.com/mcp' \
OUTLINE_MCP_AUTH_METHOD='apikey' \
OUTLINE_MCP_API_KEY='<your-api-key>' \
python3 outline-wiki-management/scripts/configure_mcp.py
```

执行成功后，**必须重启 Claude Code 当前会话**（详见
[重启后验证清单](#重启后验证清单)），新工具才会出现在 `mcp__outline__*` 列表中。

OAuth 鉴权或希望手动跑的人：直接 `python3 outline-wiki-management/scripts/configure_mcp.py`
走交互模式，脚本会逐项提示。

## 前置条件

- 本机已安装并登录 `claude` CLI（`claude --version` 验证）
- 已拿到以下任一鉴权材料：
  - **API Key**：在 Outline Wiki 工作区 **Settings → API** 中生成
  - **OAuth**：在客户端添加 MCP 端点后会自动弹出登录窗口
- 已确认工作区 **Settings → AI** 中 MCP toggle 已开启（关闭后所有客户端
  都会连接失败）

## 检测当前状态

agent 在引导配置前必须依次检查：

1. **当前 session 是否已注册 `mcp__outline__*` 系列工具**
   - 若是 → 直接进入 SKILL.md 的"标准流程"，无需任何配置动作
2. **跑 `claude mcp get outline`**
   - 若返回 `Status: ✓ Connected` → 提示用户**重启当前会话**以加载 server，
     结束
   - 若返回 `Status: ⏸ Pending approval` 或未找到 → 走下面的引导流程

## 引导配置（agent 驱动）

全程用 `AskUserQuestion` 与用户对话，敏感字段单独处理：

- **Q1 endpoint 类型**：选项 `官方云` / `自托管` / `Other`
- **Q2 API key 传入方式**（仅 API key 鉴权时问；OAuth 走手动退路）：
  - `本机已 export OUTLINE_API_KEY`（推荐）—— agent 跑
    `bash -lc 'test -n "$OUTLINE_API_KEY" && echo present || echo missing'`
    探测，present 则直接走环境变量；missing 则退回 Other 让用户粘贴
  - `直接粘贴到对话` —— 用户在 Other 里贴一次，agent 立即使用、不会
    回写到任何 `.md` 报告

endpoint 的实际域名（子域名或自托管域名）单独用一句中文问
（`AskUserQuestion` 不适合放自由文本 URL），agent 自己拼成完整 URL
并交给脚本。

## 调用脚本

把上述值放到环境变量，非交互模式调用：

```bash
OUTLINE_MCP_ENDPOINT='<url>' \
OUTLINE_MCP_AUTH_METHOD='apikey' \
OUTLINE_MCP_API_KEY='<key>' \
python3 outline-wiki-management/scripts/configure_mcp.py
```

脚本会：

1. 归一化 endpoint、协议校验（http/https）
2. POST `initialize` 握手测试连接
3. 探测同名 server 是否已注册（`claude mcp get outline`）—— 幂等
4. 未注册则调 `claude mcp add --transport http --scope user outline <url>
   --header "Authorization: Bearer <key>"`
5. 已注册则跳过 add，直接进入验证
6. 最后再跑一次 `claude mcp get outline` 确认 `Status: ✓ Connected`

非交互模式下：跳过"覆盖已有配置？"与"连接测试失败仍要写入？"
两个确认；连接测试失败直接中止，让 agent 重新提示用户。

可选：`OUTLINE_MCP_SCOPE=local` 或 `project` 覆盖默认 `user`。

## 手动退路

用户在引导流程中选 `Other` / 中断 / 直接说"我自己跑"时，回退到手动命令：

```bash
python3 outline-wiki-management/scripts/configure_mcp.py
```

脚本的交互模式原样保留，可用于 OAuth 鉴权或重设配置。

如需更换 scope：脚本交互模式里直接选；或用环境变量
`OUTLINE_MCP_SCOPE=local`。

> 注意：`scripts/configure_mcp.py` 是**唯一**受控的客户端配置入口，agent
> **不**直接调 `claude mcp add`、也**不**直接编辑 `~/.claude.json` 或
> `.claude/settings.local.json`。agent 只负责收集信息 + 拼环境变量 +
> 调脚本，文件写入由脚本（透传 `claude mcp add`）完成。

## 重启后验证清单

> **重启是硬约束**：Claude Code CLI 在 session 启动时一次性读入
> `~/.claude.json#mcpServers`，mid-session 改文件不会重读。
> 没有 `claude mcp reload` / `claude mcp reconnect` 这类子命令。
> `/mcp` 斜杠命令支持对**已注册** server 做 reconnect / toggle，但
> **不会加载新 server**。详见
> [设计决策：为什么必须重启](#设计决策为什么必须重启)。

脚本配置完成后，按以下清单逐条验证：

1. **续接当前 session**：在终端按 `Ctrl+D` 退出当前 Claude Code，然后
   `claude --continue`（或 `claude -c`）重启并恢复对话历史。这能保留
   之前任务进度，避免丢失上下文。`--continue` 与 `--resume <id>` 行为
   类似，前者接"最近一次"会话，后者接指定 id。

2. **检查 `/mcp` 状态**：在 Claude Code 中输入 `/mcp`，应能看到
   `outline ✓ Connected` 列表项。OAuth 鉴权下首次 `/mcp` 会触发
   浏览器登录窗口。

3. **试调一次 outline 工具**：在对话里说"列出 outline 工具"或
   "调用 outline 搜索 '测试'"，看 agent 能否拿到真实工具清单并
   调用成功。如果报错，按 [常见问题](#常见问题) 排查。

4. **失败退路**：
   - `/mcp` 看不到 outline → 终端跑 `claude mcp get outline`，看返回是
     `✓ Connected`、`⏸ Pending approval` 还是"未找到"
   - Connected 但调用报错 → 99% 是鉴权问题（API Key 过期 / OAuth token
     失效），重新跑 `scripts/configure_mcp.py` 覆盖一次
   - 完全找不到 → 配置没写进去，看脚本输出最后的退出码与 stderr

> 一句话总结：**配置脚本只负责写入，重启是用户必须自己执行的步骤**。
> 不要试图让脚本"自己重启 Claude Code"——会破坏当前对话历史，
> 也拿不到用户的终端控制权。

## 设计决策：为什么必须重启

`claude mcp` CLI 的子命令集是固定的：

- `add` / `add-from-claude-desktop` / `add-json` —— 注册到
  `~/.claude.json#mcpServers`
- `get` / `list` —— 查询已注册项
- `remove` / `reset-project-choices` —— 移除
- `serve` —— 把 Claude Code 自身作为 MCP server 暴露给其它客户端

**没有** `reload` / `restart` / `reconnect` 子命令。MCP server 列表
在 session 启动时一次性从 `~/.claude.json` 读入，mid-session 改文件
不会被即时重读。`/mcp` 斜杠命令支持 reconnect / toggle 已注册的
server，但**不会**加载新 server。

可考虑的"绕路"以及为什么也不可行：

| 方案 | 问题 |
| --- | --- |
| 写项目级 `.mcp.json` | 同样在 session 启动时读，且多一层 trust prompt |
| 跑 `claude mcp serve` 转发 | 把 Claude Code 自己当 server 转发，与添加新 server 无关 |
| 用脚本 `kill` 当前进程并重启 | 脚本拿不到用户的终端控制权，也破坏 session 状态 |
| `mcp-remote` 代理 | 只是把 Streamable HTTP 转 STDIO，仍要 restart session |

结论：**重启是 Claude Code CLI 的硬约束**。skill 的工作是让用户
**只重启一次**、**重启即生效**、**重启后能立即验证**。这就是
[重启后验证清单](#重启后验证清单) 存在的原因。

未来如果 Claude Code 引入 hot-reload，本附录会同步更新并去掉重启
步骤；目前没有 ETA。

## 常见问题

### 1. 认证失败（401 / 403）

- **API Key**：检查是否过期或被撤销，让用户重新生成
- **OAuth**：让用户重新走一次授权流程（输入 `/mcp` 触发）

### 2. MCP 未启用（连接被拒）

- 提示用户到 Outline Wiki 工作区 **Settings → AI** 确认 MCP toggle 已开启
- 自托管实例需管理员在控制台开启

### 3. 工具名不匹配

- 重新调 `tools/list` 拿当前工具清单；不要凭记忆中的名字调用

### 4. 文档 ID 无效

- 用 search 重新定位目标文档，拿到新 ID
- 不要凭缓存的 ID 直接调用——文档可能已被归档 / 重命名

### 5. `claude mcp get outline` 返回 "未找到"

- 配置写入失败。常见原因：
  - 环境变量没传到子进程（脚本只读 `os.environ`，shell 没 export）
  - `claude` CLI 没登录（提示用户先 `claude login`）
  - 磁盘写入失败（检查 `~/.claude.json` 权限）

### 6. 重启后 `/mcp` 仍看不到 outline

- 终端跑 `claude mcp list` 看是否真的注册上了
- 确认启动 Claude Code 的用户与跑脚本的用户是同一个
  （`whoami` / `$HOME` 一致）
- 极端情况：删掉 `~/.claude.json` 中 `mcpServers.outline` 段，重新跑
  一次脚本

## 旧版配置清理

旧版本曾尝试写 `.claude/settings.local.json` 的项目级 `mcpServers`
段，但 Claude Code 静默忽略（项目级需 trust prompt 才生效），
已废弃。若该文件仍含 `mcpServers.outline` 段（已 gitignore），
可手动删除该段或整个文件。新流程不依赖也不再写入该文件。

## 相关参考

- SKILL.md —— 工作流主文档
- `references/auth.md` —— 鉴权方式与其它客户端（Claude Desktop / Cursor）
  的接入命令
- `scripts/configure_mcp.py` —— 唯一受控的客户端配置入口
