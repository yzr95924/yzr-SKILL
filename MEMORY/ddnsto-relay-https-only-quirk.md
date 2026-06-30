---
name: ddnsto-relay-https-only-quirk
description: ddnsto 内网穿透 relay 的 HTTP 80 端口对所有路径都回 "200 OK Content-Length: 0" 空 body（伪装成 Server: Caddy），实际转发只在 HTTPS 443；接入任何走 ddnsto 隧道的 MCP（含 outline）必须用 https://，否则 configure_mcp.py 的初始化握手会报 "响应非 JSON-RPC 格式"。
metadata:
  type: project
---

# ddnsto relay 仅 HTTPS 443 才透到上游

**Why：** 2026-06-30 给 self-hosted Outline 跑 outline-wiki-setup 时踩到——用户给的 endpoint 是 `http://myoutline.ddnsto.com/mcp`，脚本 `test_connection()` POST initialize 握手失败，报 "响应非 JSON-RPC 格式，无法解析"。手测 curl 发现：

- HTTP 80：`Server: Caddy` + `Content-Length: 0`，**所有路径**（含 `/`、`/api/health`、`/api/auth/limited`、随机不存在路径）都回 200/0 字节、无 401/404/502 差异化错误
- 和 ddnsto 主域栈（`ddnsto.com` → `Server: nginx/1.22.1`）的栈**不一致**——明显不是 ddnsto 自己
- HTTPS 443：握手正常，Outline MCP `serverInfo.name=outline version=1.8.1`，capabilities 含 `tools.listChanged`

说明 ddnsto relay **只**在 HTTPS 443 路径才把流量透到上游后端；HTTP 80 是一个返回占位空 200 的兜底响应（行为对所有 Host / 方法 / 头 / 路径完全相同）。用户原话："标记完的客户端主机,应该就可以访问了"——意思是需要在 ddnsto 控制台 / 客户端软件把 client host 标记为已激活，HTTPS 路径才会真正打通；HTTP 80 始终是空 200 占位，**与标记状态无关**。

**关键现象诊断要点**（先于任何"是不是鉴权问题 / 是不是 endpoint 错"的猜测）：

| 探测 | 期望差异化 | 实测 |
| --- | --- | --- |
| 错 API key vs 无 key vs 对 key | 鉴权失败 vs 成功 | 全部相同 ⇒ 不是鉴权问题 |
| 真实路径 vs 随机不存在路径 | 200/HTML vs 404 | 全部相同 ⇒ 不是 reverse_proxy 兜底（真 reverse proxy 至少在 Host 失配时回 502） |
| `Host: definitely-not-mine.example.com` | relay 路由不到，回错 | 行为相同 ⇒ relay 按 IP 而非 Host 路由 |
| **http → https** | 后端不一样 | **行为完全反转**（拿到真实 Outline MCP 响应）⇒ 协议层 middlebox 拦截，不是后端问题 |

唯一决定性证据是 "**换协议** vs **换其他变量**"：所有轴都同响应，唯独协议切换后透到真后端 ⇒ 协议层盒子。

**How to apply：**

- **接入任何走 ddnsto 隧道的 MCP 时，endpoint 必须用 `https://<sub>.ddnsto.com:443/mcp`**（或省略端口 `https://<sub>.ddnsto.com/mcp`），**不要**用 http://
- 用户第一次给的是 http://，**直接尝试 https://**——确认 HTTPS 通后即可正常接入
- 用户若说"标记完才能访问 / 它支持 HTTPS"——意思是 ddnsto 控制台要标记 client host；标记完 HTTPS 即生效
- **configure_mcp.py 失败时** 的快速排查探针：

  ```bash
  curl -i -sS --max-time 10 \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -X POST 'http://USER_HOST/mcp' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize",...}'

  curl -i -sS --max-time 10 -X POST 'https://USER_HOST:443/mcp' ...
  ```

  前者空 200 + Server: Caddy / 后者 SSE+JSON ⇒ 确诊 ddnsto HTTP 陷阱

**关联：**

- [[outline-mcp-permission-allowlist]] —— outline MCP 接入的另一类配置坑（settings.local.json 白名单）
- 同步建议：在 `outline-wiki-setup/SKILL.md` "故障排查" 段加 1 行症状清单 + 解决方案（指向本 memory）
