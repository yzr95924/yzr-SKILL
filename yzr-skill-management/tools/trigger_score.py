"""触发评估计分：verdicts 文件对照 eval/trigger_eval.json。

不收 LLM 原始输出解析，judge 的脏文本由编排 agent
转写（自由文本解析的维护税高）；按 query 逐字匹配，不按编号——编号会让指令
拼装与对账耦合出顺序依赖
"""

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"{path}: 读取失败：{e}", file=sys.stderr)
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="触发评估计分：verdicts 对照 eval/trigger_eval.json。"
        "全对退出 0；误判 / 缺判 / 多判 / 形状问题退出 1；用法或 JSON 损坏退出 2。"
        "对账按 query 逐字精确匹配"
    )
    parser.add_argument("skill_dir", help="目标 skill 目录（读其 eval/trigger_eval.json）")
    parser.add_argument(
        "verdicts",
        help='判定文件：[{"query": "...", "verdict": "触发" | "不触发"}]，query 与 trigger_eval.json 条目逐字一致',
    )
    args = parser.parse_args(argv)

    labels = load_json(Path(args.skill_dir) / "eval" / "trigger_eval.json")
    verdicts = load_json(Path(args.verdicts))
    if labels is None or verdicts is None:
        return 2
    if not isinstance(labels, list) or not isinstance(verdicts, list):
        print("两份文件都须是 JSON 数组", file=sys.stderr)
        return 2

    findings = []
    label_map = {}
    for i, row in enumerate(labels):
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("query"), str)
            or not isinstance(row.get("should_trigger"), bool)
        ):
            findings.append(f"trigger_eval.json 第 {i + 1} 条形状不对（须 query:str + should_trigger:bool）")
            continue
        label_map[row["query"]] = row["should_trigger"]

    verdict_map = {}
    for i, row in enumerate(verdicts):
        if not isinstance(row, dict) or not isinstance(row.get("query"), str):
            findings.append(f"verdicts 第 {i + 1} 条形状不对（须 query:str）")
            continue
        v = row.get("verdict")
        if v not in ("触发", "不触发"):
            findings.append(f"verdicts 第 {i + 1} 条 verdict 非法：{v!r}（只认 触发 / 不触发）")
            continue
        verdict_map[row["query"]] = v

    mismatches = []
    for query, should in label_map.items():
        if query not in verdict_map:
            findings.append(f"缺判：{query}")
            continue
        if (verdict_map[query] == "触发") != should:
            mismatches.append(query)
            findings.append(f"误判：{query}（应{'触发' if should else '不触发'}，判为 {verdict_map[query]}）")
    for query in verdict_map:
        if query not in label_map:
            findings.append(f"多判（标注里无此 query）：{query}")

    total = len(label_map)
    correct = total - len(mismatches)
    if total:
        print(f"标注 {total} 条，正确 {correct}，误判 {len(mismatches)}，正确率 {correct / total:.0%}")
    else:
        print("trigger_eval.json 没有可对账的条目")
    for f in findings:
        print(f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
