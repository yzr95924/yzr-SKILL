# 定性测试循环协议

## 工作区

- `<skill-name>-workspace/test-<N>/case-<K>/{sandbox,outputs}`，与 skill 目录同级；逐用例独立沙箱，互不可见
- 目录靠 `*-workspace/` 的 gitignore 覆盖，不入仓；再跑一轮即重建

## 裸跑（起草前）

- 对照基线的记录项：产物体积、通知行为、退出码；顺带验证素材本身有效，无效先修素材再跑
- 每用例指令前缀：工作目录给沙箱；产物只写沙箱与其 outputs；除这两处不读工作区外内容；
  需要用户确认处，把本应展示的内容写进 outputs 后按最合理默认继续；最终回复必含三节：
  产物路径 / 做了什么 / 没做到什么及原因
- harness 会注入全局配置且无法屏蔽，注入内容如与任务相关须在记录中注明

## 行为测试（起草后）

- **正文必须内联**：把新正文与其引用的 ref 文件全文贴进指令，并加一行"忽略你技能清单里的同名 skill"。
  harness 加载的是安装快照（vendored 副本），不是仓库新文；不内联测到的是旧文
- 用例要操作的固定输入（skill 目录、样例文件）存 `eval/fixtures/<用例 id>/`，跑前整个拷进沙箱再用；
  内容跟着 expectations 走，改一方同步另一方
- 判定：对照 `eval/evals.json` 中该用例的 expectations 逐条过；发现弱断言（错误输出也会过的）
  同步收紧该用例的 expectations

## 触发测试（description 草案后）

- judge subagent 只拿 name + description 与不带标注的 query 列表，判定回显 query 原文；
  编排 agent 把判定转写成 verdicts 文件（形状见 `trigger_score.py --help`），跑
  `python3 yzr-skill-management/tools/trigger_score.py <skill-dir> <verdicts-file>` 对账
- 正例负例都要有，负例取相邻请求类型
- 单 judge 属同模型自判，存在偏置；边缘误判升给人工复核，不加机械 A/B

## evals 格式

- `eval/evals.json`：`{"skill_name", "evals": [{"id", "prompt", "expectations": [...]}]}`
  expectations 写成能堵死"自建等效路径"的硬判据（如"跑 tools/x.py，不手拼产物"），
  不写叙述式 expected_output、不留空转 files 字段；未实跑的用例加 `"status": "未实跑"` 标注，实跑后转正或删除
- `eval/trigger_eval.json`：`[{"query", "should_trigger"}]`，形状由 trigger_score.py 读取时校验；
  未实跑的条目同 evals.json 加 `"status": "未实跑"` 标注
