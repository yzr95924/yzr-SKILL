"""安装本仓库开发所需的工具链：pyyaml + ruff（pip）+ markdownlint-cli（npm）。

跨平台：macOS / Debian / WSL 都走 ``pip install --user --break-system-packages``
（PEP 668 在 Homebrew Python 3.12+ 与 Debian/WSL 系统 Python 都启用）。
幂等：重复跑不重复安装。
自检：装完逐个 verify 并打印版本；若 PATH 缺失则用 ``python3 -m <tool>`` 回退。

用法::

    python3 scripts/install-dev-deps.py
    PYTHON=python3.11 python3 scripts/install-dev-deps.py
    SKIP_NPM=1 python3 scripts/install-dev-deps.py
    SKIP_PIP=1 python3 scripts/install-dev-deps.py

依赖：Python 3.7+ 标准库；如装 npm 包则需要系统装了 Node.js。
"""

import os
import shutil
import subprocess  # noqa: S404  # 使用 subprocess 是受控的（命令硬编码）
import sys
from typing import List, Optional, Tuple

# === 配置（环境变量驱动）===
PYTHON = os.environ.get("PYTHON", "python3")
SKIP_NPM = bool(os.environ.get("SKIP_NPM", ""))
SKIP_PIP = bool(os.environ.get("SKIP_PIP", ""))
PIP_TIMEOUT_SECONDS = 180
NPM_TIMEOUT_SECONDS = 180


def run(
    cmd: List[str], timeout: int = 60
) -> Tuple[int, str, str]:
    """调子进程并返回 (returncode, stdout, stderr)。

    显式传 stdout=PIPE / stderr=PIPE / universal_newlines=True（仓库既有
    风格；ruff UP021/UP022 已在 pyproject ignore，不会警告），见
    [[python-min-3-7]]。
    """
    proc = subprocess.run(  # noqa: S603,S607  # 命令硬编码，无 shell 注入风险
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def detect_pip_flags() -> List[str]:
    """按平台返回合适的 pip 标志。

    PEP 668 在 macOS Homebrew Python 3.12+ 与 Debian/WSL 系统 Python 都启用。
    ``--user --break-system-packages`` 在两类系统都能装到用户目录；老版本
    系统 Python（无 PEP 668）会忽略 ``--break-system-packages`` 或仅打印警告。
    """
    return ["--user", "--break-system-packages"]


def pip_install(packages: List[str], flags: List[str]) -> int:
    """通过 pip 装一组 Python 包，返回退出码。"""
    cmd = [PYTHON, "-m", "pip", "install"] + flags + ["--upgrade"] + packages
    print("==> Python 工具链 (" + ", ".join(packages) + ")")
    print("    命令: " + " ".join(cmd))
    rc, out, err = run(cmd, timeout=PIP_TIMEOUT_SECONDS)
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip(), file=sys.stderr)
    return rc


def npm_install(package: str) -> int:
    """全局装一个 npm 包，返回退出码。"""
    print("")
    print("==> " + package + " (npm)")
    rc, out, err = run(["npm", "install", "-g", package], timeout=NPM_TIMEOUT_SECONDS)
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip(), file=sys.stderr)
    return rc


def verify_pip_packages() -> None:
    """验证 pip 装的包，打印版本号。"""
    rc, out, _ = run([PYTHON, "-c", "import yaml; print(yaml.__version__)"])
    if rc == 0:
        print("  pyyaml         " + out.strip())
    else:
        print("  ! pyyaml 导入失败（" + PYTHON + " -m pip show pyyaml 检查）")

    if shutil.which("ruff") is not None:
        rc2, out2, _ = run(["ruff", "--version"])
        print("  ruff           " + out2.strip())
    else:
        rc2, out2, _ = run([PYTHON, "-m", "ruff", "--version"])
        if rc2 == 0:
            print(
                "  ruff           "
                + out2.strip()
                + "  (via "
                + PYTHON
                + " -m ruff)"
            )
            print(
                "  ! ruff 不在 PATH，建议加 "
                "export PATH=\"$HOME/Library/Python/3.14/bin:$PATH\""
            )
        else:
            print("  ! ruff 不可用（" + PYTHON + " -m pip show ruff 检查安装）")


def verify_npm_packages() -> None:
    """验证 npm 装的包，打印版本号。"""
    if shutil.which("markdownlint") is not None:
        rc, out, _ = run(["markdownlint", "--version"])
        print("  markdownlint   " + out.strip())
    else:
        print("  ! markdownlint 不在 PATH（npm root -g 查看全局安装目录）")


def preflight() -> int:
    """装前体检：检查 python3 + pip / npm 是否就位。"""
    if not SKIP_PIP:
        if shutil.which(PYTHON) is None:
            print("错误: 找不到 " + PYTHON, file=sys.stderr)
            return 1
        rc, _, _ = run([PYTHON, "-m", "pip", "--version"])
        if rc != 0:
            print("错误: " + PYTHON + " 没有 pip 模块", file=sys.stderr)
            return 1
    if not SKIP_NPM:
        if shutil.which("npm") is None:
            print(
                "错误: 找不到 npm；请先安装 Node.js"
                "（brew install node / nvm install --lts）",
                file=sys.stderr,
            )
            print("      或重跑并设置 SKIP_NPM=1 跳过 npm 包", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    """脚本主入口；返回进程退出码（0 = 成功）。"""
    rc = preflight()
    if rc != 0:
        return rc

    if SKIP_PIP:
        print("==> 跳过 pip (SKIP_PIP=1)")
    else:
        rc = pip_install(["pyyaml", "ruff"], detect_pip_flags())
        if rc != 0:
            return rc

    if SKIP_NPM:
        print("")
        print("==> 跳过 npm (SKIP_NPM=1)")
    else:
        rc = npm_install("markdownlint-cli")
        if rc != 0:
            return rc

    print("")
    print("==> 验证安装")
    if not SKIP_PIP:
        verify_pip_packages()
    if not SKIP_NPM:
        verify_npm_packages()

    print("")
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
