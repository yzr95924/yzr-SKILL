# 鉴权与客户端配置

本附录集中描述 Outline Wiki MCP 服务的鉴权方式与常见客户端的接入命令。
SKILL.md 主体只规定"做什么"（搜索 / 读取 / 创建 / 编辑），不规定"怎么连"——
读完本附录后回到主文档继续工作流。

## MCP 端点

| 形态 | URL |
| --- | --- |
| 官方云 | `https://<your-subdomain>.getoutline.com/mcp` |
| 自托管 | `https://<your-domain>/mcp`（路径固定为 `/mcp`） |

> 官方文档原文："For self-hosted simply replace the URL with your own
> installation domain and append with `/mcp`."

## 鉴权方式

### 1. OAuth（默认）

- 在支持的客户端添加 MCP 端点后，**自动弹出浏览器登录窗口**完成授权
- 不需要手动管理 token，refresh 由 MCP server 处理
- 适合交互式场景（Claude Code / Claude Desktop）

### 2. API Key

- 在 Outline Wiki 设置中生成 API Key
- 通过 HTTP 头传递：`Authorization: Bearer <your-api-key>`
- 适合 CI / 自动化 / 无浏览器场景

## 客户端接入

### Claude Code（CLI）

```bash
claude mcp add --transport http outline https://<your-subdomain>.getoutline.com/mcp
```

完成后在 Claude Code 中输入 `/mcp` 触发 OAuth 登录。

### Claude Desktop

Settings → Connectors → Add Connector，粘贴 MCP URL：
`https://<your-subdomain>.getoutline.com/mcp`

### Cursor

Cursor Settings → MCP → Add new global MCP server，粘贴：

```json
{
  "mcpServers": {
    "outline": {
      "url": "https://<your-subdomain>.getoutline.com/mcp"
    }
  }
}
```

### 其他应用（通用 JSON）

Outline 只支持 **Streamable HTTP** 传输。对于只支持 STDIO 的客户端，
需要用 `mcp-remote` 做代理：

```json
{
  "mcpServers": {
    "outline": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://<your-subdomain>.getoutline.com/mcp"]
    }
  }
}
```

## 启用 MCP（前提）

在工作区 **Settings → AI** 中确认 MCP toggle 已开启。关闭后所有客户端
都会连接失败。
