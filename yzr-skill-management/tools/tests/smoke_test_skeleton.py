"""skeleton.py 冒烟测试：new 出生即合规、check 抓到六类漂移。

契约点（破哪条挂哪条）：
  - new 生成的 SKILL.md 必须直接通过 check（形状派生自模板，出生即合规）；
  - new 拒绝非 kebab 名、超 64 字符名与已存在目录，且不留半成品；数字开头放行（对齐开放规范）；
  - check 必须抓到：frontmatter 多键、H2 缺 / 多 / 乱序、目录名与 name 值不一致、悬空引用名、
    死锚点、锚点链接文字非"章节"；
  - 指向本文件节 / 粗体条目 / 真实文件路径 / 合法锚点链接的引用不得误报；内联代码内的格式示例不查；
  - 围栏代码块内的 `## x` 不得计为节（现存 skill 的样例块是真实形状）。

Run: python3 tools/tests/smoke_test_skeleton.py  (from yzr-skill-management/)
Exit 0 = all green, 1 = regression.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SKELETON = Path(__file__).resolve().parent.parent / "skeleton.py"

GOOD = """---
name: demo-skill
description: |
  当用户X时使用本 skill，做Y。
  触发：做X
  不适用：Z
---

## 输入与输出

输入见上。

## 执行原则

原则内容。

## 工作流

步骤内容。
"""

FAILURES = []


def expect(cond: bool, label: str) -> None:
    if not cond:
        FAILURES.append(label)
        print(f"FAIL: {label}")


def make_skill(root: Path, dirname: str, content: str) -> Path:
    d = root / dirname
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")
    return d


def good(name: str) -> str:
    """GOOD 骨架换名，使目录名与 frontmatter name 一致（隔离各用例的唯一变量）。"""
    return GOOD.replace("name: demo-skill", f"name: {name}")


def run(args):
    return subprocess.run(
        [sys.executable, str(SKELETON), *[str(a) for a in args]],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="skeleton-smoke-"))

    # new：出生即合规
    r = run(["new", "fresh-skill", "--root", tmp])
    expect(r.returncode == 0, "new 合法名应成功")
    expect((tmp / "fresh-skill" / "SKILL.md").is_file(), "new 应生成 SKILL.md")
    r = run(["check", tmp / "fresh-skill"])
    expect(r.returncode == 0, f"new 产物应直接通过 check：{r.stdout}")

    # new：拒绝非法输入且不留半成品
    r = run(["new", "Bad_Name", "--root", tmp])
    expect(r.returncode != 0, "new 应拒绝非 kebab 名")
    expect(not (tmp / "Bad_Name").exists(), "非法名不应留下目录")
    r = run(["new", "a" * 65, "--root", tmp])
    expect(r.returncode != 0, "new 应拒绝超 64 字符名")
    r = run(["new", "2fa-helper", "--root", tmp])
    expect(r.returncode == 0, f"数字开头应放行（开放规范）：{r.stdout}")
    r = run(["new", "fresh-skill", "--root", tmp])
    expect(r.returncode != 0, "new 应拒绝已存在目录")

    # check：四类漂移逐一必抓（除标注外均名字对齐，finding 只来自被测缺陷）
    r = run(
        [
            "check",
            make_skill(
                tmp,
                "meta-skill",
                good("meta-skill").replace("name: meta-skill", "name: meta-skill\nmetadata:\n  author: x"),
            ),
        ]
    )
    expect(r.returncode != 0, "check 应抓到多余 frontmatter 键")
    r = run(["check", make_skill(tmp, "drop-skill", good("drop-skill").replace("## 工作流", "## 附录"))])
    expect(r.returncode != 0, "check 应抓到节缺失/多出（改名等价两者）")
    r = run(
        [
            "check",
            make_skill(
                tmp,
                "swap-skill",
                good("swap-skill")
                .replace("## 输入与输出", "## 临时")
                .replace("## 执行原则", "## 输入与输出")
                .replace("## 临时", "## 执行原则"),
            ),
        ]
    )
    expect(r.returncode != 0, "check 应抓到节乱序")
    r = run(["check", make_skill(tmp, "dir-mismatch", GOOD)])
    expect(r.returncode != 0, "check 应抓到目录名与 name 不一致")
    r = run(["check", make_skill(tmp, "ok-skill", good("ok-skill"))])
    expect(r.returncode == 0, f"形状正确的 skill 应过 check：{r.stdout}")

    # 围栏内的 ## 不计为节
    fenced = good("fence-skill").replace("步骤内容。", "步骤内容。\n\n```md\n## 假节\n```")
    r = run(["check", make_skill(tmp, "fence-skill", fenced)])
    expect(r.returncode == 0, f"围栏内 `## 假节` 不应计为节：{r.stdout}")

    # 引用名存活：指向本文件节的引用通过，悬空引用必抓
    ref_ok = good("ref-ok").replace("原则内容。", '原则内容。\n\n见"执行原则"。')
    r = run(["check", make_skill(tmp, "ref-ok", ref_ok)])
    expect(r.returncode == 0, f"指向本文件节的引用应过 check：{r.stdout}")
    ref_bad = good("ref-bad").replace("原则内容。", '原则内容。\n\n见"不存在的规则"。')
    r = run(["check", make_skill(tmp, "ref-bad", ref_bad)])
    expect(r.returncode != 0, "check 应抓到悬空引用名")
    # 假阳性钉死：引号内"过"不当触发词；单字标点捕获不算引用名；真实文件路径引用放行；
    # 内联代码内的格式示例（`[章节](#节名)`）不当真链接查
    fp = good("fp-skill").replace("原则内容。", '原则内容。\n\n推荐"逐条过"；"细化"适合发现少时。')
    fp = fp.replace("步骤内容。", "步骤内容。\n\n按 `known.md` 执行。\n\n跨节引用写 `[章节](#节名)`。")
    d = make_skill(tmp, "fp-skill", fp)
    (d / "known.md").write_text("# x\n", encoding="utf-8")
    r = run(["check", d])
    expect(r.returncode == 0, f"散文引号、真实文件路径、内联示例不应误报：{r.stdout}")

    # 锚点链接：合法通过；死锚点、链接文字非"章节"必抓
    link_ok = good("link-ok").replace("原则内容。", "原则内容。\n\n细则见[章节](#工作流)对应小节。")
    r = run(["check", make_skill(tmp, "link-ok", link_ok)])
    expect(r.returncode == 0, f"合法锚点链接应过 check：{r.stdout}")
    link_dead = good("link-dead").replace("原则内容。", "原则内容。\n\n见[章节](#不存在的节)。")
    r = run(["check", make_skill(tmp, "link-dead", link_dead)])
    expect(r.returncode != 0, "check 应抓到死锚点")
    link_label = good("link-label").replace("原则内容。", "原则内容。\n\n见[流程](#工作流)。")
    r = run(["check", make_skill(tmp, "link-label", link_label)])
    expect(r.returncode != 0, 'check 应抓到非"章节"的锚点链接文字')

    if FAILURES:
        print(f"\n{len(FAILURES)} case(s) FAILED")
        return 1
    print("all cases PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
