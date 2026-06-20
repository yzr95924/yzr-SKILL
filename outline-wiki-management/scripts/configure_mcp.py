"""配置 Outline Wiki MCP 服务到 Claude Code（默认项目级，一次配置仅当前项目生效）。

通过调用官方 `claude mcp add` CLI，把 server 注册到 Claude Code 的
项目级配置（`~/.claude.json#projects.<projectPath>.mcpServers`），仅在
当前项目下可见。首次进入项目时若弹出 trust prompt，按提示批准即可——
该提示每个项目只弹一次。

支持两种调用方式：
1. 交互模式（用户手动运行，逐项 prompt）
2. 非交互模式（由 outline-wiki-management skill 驱动）——通过环境变量
   传入 endpoint / 鉴权方式 / API key，跳过所有 prompt

执行流程：
1. 从环境变量（交互模式）或 prompt 收集 endpoint / 鉴权方式 / API key
2. 向 MCP 端点 POST initialize 握手，验证可达 + 鉴权可用
3. 探测同名 server 是否已注册（`claude mcp get outline`）
4. 调用 `claude mcp add --transport http --scope project --header ...` 完成注册
5. 再次 `claude mcp get outline` 确认 Connected
6. 提示用户重启 Claude Code 当前会话以加载新工具

调用方式：

    # 交互模式
    python3 outline-wiki-management/scripts/configure_mcp.py

    # 非交互模式（OUTLINE_MCP_ENDPOINT 一旦设置即启用）
    OUTLINE_MCP_ENDPOINT='https://acme.getoutline.com/mcp' \
    OUTLINE_MCP_AUTH_METHOD='apikey' \
    OUTLINE_MCP_API_KEY='<key>' \
    python3 outline-wiki-management/scripts/configure_mcp.py

    # 高级：自定义 scope（默认 project；可选 user / local）
    OUTLINE_MCP_ENDPOINT='...' OUTLINE_MCP_AUTH_METHOD='apikey' \
    OUTLINE_MCP_API_KEY='...' OUTLINE_MCP_SCOPE='project' \
    python3 outline-wiki-management/scripts/configure_mcp.py

依赖：Python 3.6+ 标准库 + 本机已安装并登录的 `claude` CLI。
"""

import json
import os
import subprocess
import sys
from typing import Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MCP_SERVER_NAME = "outline"
MCP_PROTOCOL_VERSION = "2024-11-05"
HTTP_TIMEOUT_SECONDS = 10
CLAUDE_CLI_TIMEOUT_SECONDS = 30
ALLOWED_SCOPES = ("user", "local", "project")
DEFAULT_SCOPE = "project"


def prompt(message: str, default: Optional[str] = None) -> str:
    """向用户请求输入；空输入时返回默认值。"""
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    return value if value else (default or "")


def confirm(message: str, default: bool = False) -> bool:
    """y/N 形式确认。"""
    suffix = " [y/N]" if not default else " [Y/n]"
    raw = input(f"{message}{suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def normalize_endpoint(endpoint: str) -> str:
    """保证 endpoint 以 /mcp 结尾。"""
    endpoint = endpoint.rstrip("/")
    if not endpoint.endswith("/mcp"):
        endpoint = endpoint + "/mcp"
    return endpoint


def choose_auth_method() -> str:
    """让用户在 OAuth / API key 之间二选一。"""
    print("")
    print("鉴权方式:")
    print("  1) OAuth  —— 浏览器登录（推荐，交互式）")
    print("  2) API key —— Bearer Token（CI / 自动化）")
    while True:
        choice = prompt("选择 [1/2]", "1").lower()
        if choice in ("1", "oauth"):
            return "oauth"
        if choice in ("2", "apikey", "api_key"):
            return "apikey"
        print("无效选择，请重试。")


def require_env(name: str) -> Optional[str]:
    """非交互模式下读取必需环境变量；缺失时打印错误并返回 None。"""
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"错误: 非交互模式下必须设置环境变量 {name}。",
            file=sys.stderr,
        )
        return None
    return value


def collect_noninteractive_inputs() -> Optional[Tuple[str, str, str, str]]:
    """从环境变量收集 endpoint / 鉴权方式 / API key / scope；任意必填项缺失返回 None。

    返回 (endpoint_raw, auth_method, api_key, scope)。auth_method / scope 已小写。
    """
    endpoint_raw = require_env("OUTLINE_MCP_ENDPOINT")
    if endpoint_raw is None:
        return None
    auth_method = require_env("OUTLINE_MCP_AUTH_METHOD")
    if auth_method is None:
        return None
    auth_method = auth_method.lower()
    if auth_method not in ("oauth", "apikey"):
        print(
            "错误: OUTLINE_MCP_AUTH_METHOD 必须是 'oauth' 或 'apikey'。",
            file=sys.stderr,
        )
        return None
    api_key = ""
    if auth_method == "apikey":
        api_key = os.environ.get("OUTLINE_MCP_API_KEY", "").strip()
        if not api_key:
            print(
                "错误: 鉴权方式为 apikey 时必须设置 OUTLINE_MCP_API_KEY。",
                file=sys.stderr,
            )
            return None
    scope = os.environ.get("OUTLINE_MCP_SCOPE", DEFAULT_SCOPE).strip().lower()
    if scope not in ALLOWED_SCOPES:
        print(
            f"错误: OUTLINE_MCP_SCOPE 必须是 {ALLOWED_SCOPES} 之一，当前 {scope!r}。",
            file=sys.stderr,
        )
        return None
    return endpoint_raw, auth_method, api_key, scope


def find_claude_cli() -> Optional[str]:
    """在 PATH 中查找 `claude` CLI；返回绝对路径或 None。"""
    for candidate in os.environ.get("PATH", "").split(os.pathsep):
        if not candidate:
            continue
        full = os.path.join(candidate, "claude")
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


def server_exists(name: str) -> Tuple[bool, str]:
    """通过 `claude mcp get <name>` 探测 server 是否已注册。

    返回 (exists, output)。`claude` CLI 不可用时返回 (False, 错误说明)。
    """
    cli = find_claude_cli()
    if cli is None:
        return False, "claude CLI 未找到（PATH 中无 `claude`）"
    try:
        proc = subprocess.run(  # noqa: S603,S607 — 已知固定参数
            [cli, "mcp", "get", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"执行 claude mcp get 失败: {exc}"
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, output


def register_via_claude_cli(name: str, url: str, api_key: str, scope: str = DEFAULT_SCOPE) -> Tuple[bool, str]:
    """调用 `claude mcp add` 把 HTTP MCP server 注册到指定 scope。

    等价命令（api_key 非空时）：
        claude mcp add --transport http --scope <scope> <name> <url> \\
            --header "Authorization: Bearer <api_key>"

    api_key 为空（OAuth 模式）时省略 --header，由 Claude Code 在首次调用时
    触发浏览器 OAuth 授权。

    返回 (ok, message)。失败时 message 包含 stderr 与退出码。
    """
    cli = find_claude_cli()
    if cli is None:
        return False, "claude CLI 未找到（PATH 中无 `claude`）"

    cmd = [
        cli,
        "mcp",
        "add",
        "--transport",
        "http",
        "--scope",
        scope,
        name,
        url,
    ]
    if api_key:
        cmd.extend(["--header", f"Authorization: Bearer {api_key}"])

    print(f"执行: claude mcp add --transport http --scope {scope} {name} {url}")
    if api_key:
        print("       --header 'Authorization: Bearer ***'  （密钥已遮蔽）")

    try:
        proc = subprocess.run(  # noqa: S603,S607
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"执行 claude mcp add 失败: {exc}"

    if proc.returncode == 0:
        return True, (proc.stdout or "").strip()

    err = (proc.stderr or proc.stdout or "").strip()
    return False, f"claude mcp add 退出码 {proc.returncode}: {err}"


def verify_registration(name: str) -> Tuple[bool, str]:
    """注册成功后再次 `claude mcp get <name>`，确认 Connected 状态。

    返回 (ok, message)。message 含 `claude mcp get` 完整输出，便于排错。
    """
    exists, output = server_exists(name)
    if not exists:
        return False, f"未在 Claude Code 中找到 '{name}':\n{output}"
    if "Connected" in output:
        return True, output
    return False, f"已注册但未连接（请检查鉴权 / endpoint 可达性）:\n{output}"


def test_connection(endpoint: str, auth_method: str, api_key: str) -> Tuple[bool, str]:
    """向 MCP 端点 POST initialize 握手，验证可达 + 鉴权可用。

    返回 (ok, message)。连接级 / 鉴权 / JSON-RPC 协议级失败都返回
    (False, reason)；只有握手成功才返回 (True, server_info)。
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if auth_method == "apikey" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "outline-wiki-management-setup",
                    "version": "1.0.0",
                },
            },
        }
    ).encode("utf-8")

    request = Request(endpoint, data=body, method="POST", headers=headers)
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if response.status != 200:
                return False, f"HTTP {response.status}: {raw[:200]}"
            try:
                payload = json.loads(raw)
            except ValueError:
                # 可能是 SSE（text/event-stream）
                data_line = next(
                    (
                        line[len("data:") :].strip()
                        for line in raw.splitlines()
                        if line.startswith("data:") and line.strip() != "data:"
                    ),
                    None,
                )
                if not data_line:
                    return False, "响应非 JSON-RPC 格式，无法解析。"
                try:
                    payload = json.loads(data_line)
                except ValueError:
                    return False, "响应 SSE data 字段非 JSON-RPC 格式。"
            if "error" in payload:
                err = payload["error"]
                return False, f"服务器返回错误: {err.get('code', '?')} {err.get('message', '?')}"
            if "result" in payload:
                server_info = payload["result"].get("serverInfo", {})
                name = server_info.get("name", "<unknown>")
                version = server_info.get("version", "<unknown>")
                return True, f"握手成功: {name} v{version}"
            return False, f"意外响应: {raw[:200]}"
    except HTTPError as exc:
        reason = exc.reason if hasattr(exc, "reason") else "?"
        return False, f"HTTP {exc.code} {reason}: {exc.read().decode('utf-8', errors='replace')[:200]}"
    except URLError as exc:
        return False, f"连接失败: {exc.reason}"
    except (TimeoutError, OSError) as exc:
        return False, f"网络错误: {type(exc).__name__}: {exc}"


def print_final_message(auth_method: str, scope: str) -> None:
    """打印收尾提示：强调"必须重启 Claude Code"，并附 4 步重启后验证清单。

    重启是硬约束 —— Claude Code CLI 在 session 启动时一次性读入
    `~/.claude.json#mcpServers`，mid-session 改文件不会被重读，
    也没有 `claude mcp reload` 子命令。完整论证与「为什么必须重启」
    见 references/onboarding.md 的「设计决策」小节。
    """
    auth_label = "API key" if auth_method == "apikey" else "OAuth"
    print("")
    print("=" * 60)
    print("配置完成（scope={}，{}）。".format(scope, auth_label))
    print("=" * 60)
    print("")
    print("=" * 60)
    print("!!  RESTART REQUIRED — 必须重启 Claude Code 当前会话  !!")
    print("=" * 60)
    print("  理由：Claude Code CLI 在 session 启动时一次性读入")
    print("        `~/.claude.json#mcpServers`；mid-session 改文件不会")
    print("        被重读，也没有 `claude mcp reload` 子命令。")
    print("  详见：outline-wiki-management/references/onboarding.md")
    print("        的「设计决策」小节。")
    print("")
    print("  续接当前 session 的推荐做法（保留对话历史）：")
    print("    Ctrl+D 退出当前 Claude Code")
    print("    claude --continue     # 或 claude -c，恢复最近一次会话")
    print("=" * 60)
    print("")
    print("重启后验证清单（4 步，逐条执行）：")
    print("")
    print("  [1] 续接 session")
    print("        claude --continue    # 恢复历史，避免任务进度丢失")
    print("")
    print("  [2] 检查 /mcp 状态")
    if auth_method == "oauth":
        print("        在 Claude Code 中输入 /mcp")
        print("        → 应触发浏览器 OAuth 登录窗口")
        print("        → 完成后 /mcp 列表里能看到 'outline ✓ Connected'")
    else:
        print("        在 Claude Code 中输入 /mcp")
        print("        → 应能看到 'outline ✓ Connected'")
    print("")
    print("  [3] 试调一次 outline 工具")
    print("        在对话里说：「调用 outline 搜索 测试」")
    print("        → 能拿到真实工具清单并成功调用 = OK")
    print("        → 报错：按 references/onboarding.md 的")
    print("          「常见问题」小节排查")
    print("")
    print("  [4] 失败退路")
    print("        终端跑：claude mcp get outline")
    print("          ✓ Connected  → 配置已生效，问题在调用方")
    print("          ⏸ Pending    → 需要 approve project-scoped server")
    print("          未找到       → 配置没写进去，重跑本脚本")
    print("")
    print("如需删除此 server：claude mcp remove outline -s", scope)


def run_noninteractive() -> int:
    """非交互模式：环境变量驱动，一次跑完。"""
    print("Outline Wiki MCP —— 非交互模式（由 skill 驱动）")
    print("=" * 60)

    cli = find_claude_cli()
    if cli is None:
        print("错误: PATH 中找不到 `claude` CLI，请先安装 Claude Code。", file=sys.stderr)
        return 1

    collected = collect_noninteractive_inputs()
    if collected is None:
        return 1
    endpoint_raw, auth_method, api_key, scope = collected

    endpoint = normalize_endpoint(endpoint_raw)
    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        print(f"错误: 协议必须是 http/https，当前为 {parsed.scheme!r}。", file=sys.stderr)
        return 1
    if not parsed.netloc:
        print("错误: Endpoint URL 缺少主机名。", file=sys.stderr)
        return 1

    print(f"Endpoint: {endpoint}")
    print(f"鉴权: {auth_method}    Scope: {scope}")
    print("")
    print("正在测试连接...")
    ok, message = test_connection(endpoint, auth_method, api_key)
    print(message)
    if not ok:
        print(
            "非交互模式: 连接测试失败，已中止（未注册）。",
            file=sys.stderr,
        )
        return 1

    # 检查是否已注册——幂等：已存在则跳过 add，直接进入验证
    exists, existing = server_exists(MCP_SERVER_NAME)
    if exists:
        print(f"检测到 '{MCP_SERVER_NAME}' 已注册，跳过 add，直接验证连接...")
    else:
        print("正在注册到 Claude Code...")
        ok, message = register_via_claude_cli(MCP_SERVER_NAME, endpoint, api_key, scope)
        print(message)
        if not ok:
            print("注册失败，已中止。", file=sys.stderr)
            return 1

    print("")
    print("正在验证注册状态...")
    ok, message = verify_registration(MCP_SERVER_NAME)
    print(message)
    if not ok:
        print("验证失败，请检查上方输出。", file=sys.stderr)
        return 1

    print_final_message(auth_method, scope)
    return 0


def run_interactive() -> int:
    """交互模式：逐项 prompt，适合手动跑。"""
    print("Outline Wiki MCP —— 客户端配置向导")
    print("=" * 60)

    cli = find_claude_cli()
    if cli is None:
        print("错误: PATH 中找不到 `claude` CLI，请先安装 Claude Code。", file=sys.stderr)
        return 1

    # 检查已注册情况
    exists, existing = server_exists(MCP_SERVER_NAME)
    if exists:
        print("")
        print(f"检测到 '{MCP_SERVER_NAME}' 已注册:")
        print(existing)
        if not confirm("覆盖已有配置？（会先 remove 再 add）", default=False):
            print("已取消。")
            return 0

    print("")
    print("Endpoint URL 示例:")
    print("  官方云: https://your-subdomain.getoutline.com/mcp")
    print("  自托管: https://your-domain/mcp")
    raw_endpoint = prompt("Endpoint URL")
    if not raw_endpoint:
        print("错误: Endpoint URL 必填。", file=sys.stderr)
        return 1

    endpoint = normalize_endpoint(raw_endpoint)
    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        print(f"错误: 协议必须是 http/https，当前为 {parsed.scheme!r}。", file=sys.stderr)
        return 1
    if not parsed.netloc:
        print("错误: Endpoint URL 缺少主机名。", file=sys.stderr)
        return 1

    auth_method = choose_auth_method()
    api_key = ""
    if auth_method == "apikey":
        api_key = prompt("API key")
        if not api_key:
            print("错误: API key 鉴权方式下 key 必填。", file=sys.stderr)
            return 1

    scope = prompt("Scope [user/local/project]", DEFAULT_SCOPE).lower()
    if scope not in ALLOWED_SCOPES:
        print(f"错误: Scope 必须是 {ALLOWED_SCOPES} 之一。", file=sys.stderr)
        return 1

    print("")
    print("正在测试连接...")
    ok, message = test_connection(endpoint, auth_method, api_key)
    print(message)
    if not ok:
        if not confirm("连接测试失败，仍要继续注册吗？", default=False):
            print("已取消。")
            return 1

    # 已注册情况：用户已确认覆盖，先 remove 再 add
    if exists:
        print(f"移除旧注册: claude mcp remove {MCP_SERVER_NAME} -s user/local/project")
        try:
            subprocess.run(  # noqa: S603,S607
                [cli, "mcp", "remove", MCP_SERVER_NAME, "-s", scope],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=CLAUDE_CLI_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"警告: 移除旧注册失败: {exc}（尝试直接 add）", file=sys.stderr)

    print("")
    print("正在注册到 Claude Code...")
    ok, message = register_via_claude_cli(MCP_SERVER_NAME, endpoint, api_key, scope)
    print(message)
    if not ok:
        print("注册失败，已中止。", file=sys.stderr)
        return 1

    print("")
    print("正在验证注册状态...")
    ok, message = verify_registration(MCP_SERVER_NAME)
    print(message)
    if not ok:
        print("验证失败，请检查上方输出。", file=sys.stderr)
        return 1

    print_final_message(auth_method, scope)
    return 0


def main() -> int:
    """脚本主入口；返回进程退出码（0 = 成功）。"""
    if os.environ.get("OUTLINE_MCP_ENDPOINT"):
        return run_noninteractive()
    return run_interactive()


if __name__ == "__main__":
    sys.exit(main())
