#!/usr/bin/env python3
"""多模型代码评审编排：名单校验 → 建卷宗 → 并行 `opencode run` 逐票 spawn → reviews/ 落盘与逐票状态汇总。"""

import argparse
import concurrent.futures
import datetime
import difflib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, NamedTuple, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_review_packet import build_packet, expand_paths  # noqa: E402

# 默认名单 SSOT：改名单只改这里；tests/smoke_test_build_packet.py 钉它与 eval 期望同步
DEFAULT_ROSTER = [
    "opencode-go/deepseek-v4.1-flash",
    "opencode-go/glm-5.3",
    "opencode-go/qwen3.8-flash",
]

DEFAULT_TIMEOUT = 600
MODELS_TIMEOUT = 60
# 旧版 CLI 无 --file 时的内联降级上限；超出即中止（评审卷宗含全文，超限说明目标过大）
INLINE_LIMIT = 400_000

# 评审员走全 deny 纯文本 worker（机制同 skill-creator judge：专用 cwd 内 markdown agent，
# agent 级 permission 优先级最高）；卷宗经消息附件送达，附件属消息内容、不受工具 deny 影响
WORKER_AGENT = "yzr-review-worker"
WORKER_AGENT_MD = '---\ndescription: Text-only review worker\nmode: primary\npermission:\n  "*": deny\n---\n'
REVIEW_PROMPT = (
    "你是多模型代码评审的一名独立评审员（N 票之一）。你没有任何可用工具：不读盘、不跑命令，卷宗"
    "（附件或全文内联随本消息送达）是唯一输入，含被审内容清单、机械扫描候选、被审代码全文、"
    "文末契约附章。严格按附章 ref/reviewer.md 的角色、评审立场与产物顺序，在回复正文里直接产出最终评审，"
    "发现映射到附章 ref/catalog.md 的规则名；不与用户交互，最终回复即交付物。"
)

FINDING_RE = re.compile(r"^- (.+):\d+ \|", re.M)

_WORKER_DIR: Optional[Path] = None
_RUN_HELP: Optional[str] = None


class Vote(NamedTuple):
    """一票的结果：状态 / 产物路径 / 错误 / 格式机检告警。"""

    model: str
    status: str
    path: str
    error: str
    warnings: List[str]


def _worker_workdir() -> Path:
    """worker 调用的专用 cwd（惰性建一次）：内含 markdown 版 review worker agent。"""
    global _WORKER_DIR
    if _WORKER_DIR is None:
        _WORKER_DIR = Path(tempfile.mkdtemp(prefix="cr-worker-"))
        agent_dir = _WORKER_DIR / ".opencode" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / f"{WORKER_AGENT}.md").write_text(WORKER_AGENT_MD, encoding="utf-8")
    return _WORKER_DIR


def _run_help_text() -> str:
    """本机 `opencode run --help` 全文（惰性取一次）；flag 探测用子串匹配，help 行如 `--file, -f` 带逗号分词会失配。"""
    global _RUN_HELP
    if _RUN_HELP is None:
        try:
            result = subprocess.run(
                ["opencode", "run", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=30,
            )
            _RUN_HELP = result.stdout
        except (OSError, subprocess.TimeoutExpired):
            _RUN_HELP = ""
    return _RUN_HELP


def _opencode_env(workdir: Optional[Path] = None) -> dict:
    """opencode 子进程环境：清配置覆盖、停自动更新；专用 cwd 时同步 $PWD。"""
    env = dict(os.environ)
    env.pop("OPENCODE_CONFIG_CONTENT", None)
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    if workdir:
        # 坑：subprocess 的 cwd= 不更新 $PWD，opencode 按 $PWD 解析项目目录（agent 发现随之失效）
        env["PWD"] = str(workdir)
    return env


def _available_models() -> Set[str]:
    """`opencode models` 取本机可发现模型 ID 集合；通道不可用抛 RuntimeError。"""
    try:
        result = subprocess.run(
            ["opencode", "models"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=_opencode_env(),
            timeout=MODELS_TIMEOUT,
        )
    except FileNotFoundError:
        raise RuntimeError("opencode CLI not found on PATH; install opencode and configure a provider") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"opencode models timed out after {MODELS_TIMEOUT}s") from None
    if result.returncode != 0:
        raise RuntimeError(f"opencode models exited {result.returncode}: {result.stderr[:200]}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _model_present(model: str, available: Set[str]) -> bool:
    """名单校验口径：精确 ID 命中，或 `#variant` 后缀形态命中。"""
    return any(line == model or line.startswith(model + "#") for line in available)


def _call_review(model: str, packet: Path, timeout: int) -> str:
    """跑一票 `opencode run`（全 deny 纯文本 worker），返回 stdout；非零退出 / 空输出抛 RuntimeError。"""
    workdir = _worker_workdir()
    cmd = ["opencode", "run", "--agent", WORKER_AGENT, "--title", "coding-review-multi", "-m", model]
    prompt = REVIEW_PROMPT
    if "--file" in _run_help_text():
        cmd.extend(["--file", str(packet)])
    else:
        text = packet.read_text(encoding="utf-8")
        if len(text) > INLINE_LIMIT:
            raise RuntimeError(f"本机 opencode 不支持 --file 且卷宗 {len(text)} 字超内联上限；升级 opencode 后重试")
        prompt = f"{REVIEW_PROMPT}\n\n以下为卷宗全文：\n\n{text}"
    cmd.append(prompt)
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=_opencode_env(workdir),
            cwd=str(workdir),
            timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError("opencode CLI not found on PATH; install opencode and configure a provider") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"opencode run timed out after {timeout}s; retry with a larger --timeout") from None
    if result.returncode != 0:
        raise RuntimeError(f"opencode run exited {result.returncode}: {result.stderr[:200]}")
    if not result.stdout.strip():
        raise RuntimeError("opencode run returned empty output")
    return result.stdout


def _check_output(text: str, manifest_names: Set[str]) -> List[str]:
    """逐票输出契约机检（产物定义见 ref/reviewer.md）：复述段与发现行缺失只告警，不作废。"""
    warnings: List[str] = []
    if "复述" not in text:
        warnings.append("无理解复述段")
    files = FINDING_RE.findall(text)
    if not files:
        warnings.append("无契约格式发现行")
    seen: Set[str] = set()
    for raw in files:
        name = Path(raw.strip()).name
        if name not in manifest_names and name not in seen:
            seen.add(name)
            warnings.append(f"发现引用卷宗外文件 {name}")
    return warnings


def _slug(model: str) -> str:
    """模型 ID 的 reviews/<slug>.md 文件名安全形态。"""
    return re.sub(r"[^A-Za-z0-9._-]+", "__", model)


def _run_vote(model: str, packet: Path, reviews_dir: Path, timeout: int, manifest_names: Set[str]) -> Vote:
    """一票最多两次尝试（调用失败 / 空输出重试一次；格式告警不触发重试）。"""
    last_err = ""
    for _attempt in (1, 2):
        try:
            out = _call_review(model, packet, timeout)
        except RuntimeError as e:
            last_err = str(e)
            continue
        dest = reviews_dir / f"{_slug(model)}.md"
        dest.write_text(out, encoding="utf-8")
        return Vote(model, "ok", str(dest), "", _check_output(out, manifest_names))
    return Vote(model, "failed", "", last_err, [])


def _validate_roster(models: List[str]) -> int:
    """名单闸门：逐个校验可发现性并宣布名单与票数；返回 0 通过、2 停下交用户裁定。"""
    try:
        available = _available_models()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("ERROR: 名单校验通道不可用，停下报告；退回单模型现状", file=sys.stderr)
        return 2
    dead = [m for m in models if not _model_present(m, available)]
    for m in dead:
        hints = difflib.get_close_matches(m, sorted(available), n=3)
        print(f"ERROR: 名单模型本机不可发现: {m}；相近候选: {'、'.join(hints) if hints else '无'}", file=sys.stderr)
    if dead:
        print("ERROR: 不静默替换、不静默减票，交用户裁定", file=sys.stderr)
        return 2
    print(f"roster: {'、'.join(models)}（{len(models)} 票）")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：dry-run 只宣布与校验名单；实跑建卷宗并并行 spawn 全部票。"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", nargs="+", default=[], help="reviewed code file(s) or dir(s)")
    parser.add_argument("--models", default="", help="comma-separated exact model IDs (default: DEFAULT_ROSTER)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per opencode run call in seconds")
    parser.add_argument("--out", default="", help="packet dir (default: cr-<timestamp> under system temp)")
    parser.add_argument("--dry-run", action="store_true", help="仅宣布并校验名单，不建卷宗不 spawn")
    args = parser.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()] or list(DEFAULT_ROSTER)
    seen: Set[str] = set()
    models = [m for m in models if not (m in seen or seen.add(m))]

    rc = _validate_roster(models)
    if rc:
        return rc
    if args.dry_run:
        print("dry-run: 名单校验通过，未建卷宗未 spawn")
        return 0
    if not args.target:
        parser.error("--target is required unless --dry-run")

    targets = expand_paths(args.target, "被审")
    if args.out:
        out_dir = Path(args.out)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        out_dir = Path(tempfile.gettempdir()) / f"cr-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir = out_dir / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    packet = build_packet(out_dir, targets)
    print(f"packet: {packet}")

    names = {p.name for p in targets}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as pool:
        futures = [pool.submit(_run_vote, m, packet, reviews_dir, args.timeout, names) for m in models]
        votes = [f.result() for f in futures]

    failed = 0
    for v in votes:
        if v.status == "ok":
            line = f"vote: {v.model} ok -> {v.path}"
            for w in v.warnings:
                line += f"（WARN: {w}）"
        else:
            failed += 1
            line = f"vote: {v.model} FAILED after retry: {v.error}"
        print(line)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
