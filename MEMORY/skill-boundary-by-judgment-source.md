---
name: skill-boundary-by-judgment-source
description: skill 间分工按判据来源划：制品规约归 yzr-skill-creator，读者与语言归 yzr-writing-review；判据需查文本外证据（git blame / eval / 作者口述）才能定违反的，只报现象标存疑、不下删除判决。
metadata:
  type: project
  scope: 跨 skill 分工判据（yzr-writing-review/、yzr-skill-creator/）
---

# skill 分工按判据来源划，不按被审对象类型

不按"被审对象是不是 skill"划：两个集合必然相交，相交就得再写分工规则，重叠即由此而来。

| 判据来源 | 归属 | 能下的结论 |
| --- | --- | --- |
| 制品规约：模板节名 / frontmatter schema / 目录名 / 依赖 DAG / eval 痕迹 / 指标权威源 / git blame | yzr-skill-creator | 违反 + 权威源处置 |
| 读者与语言：读者先验 / 决策负担 / 论证成立性 / 信息线性 / 冗余损信息 / 语气文体 / AI 腔指纹 | yzr-writing-review | 现象 + 修法 |
| 要查文本之外的证据才能定违反：有没有真实失败、规则有没有据 | 谁都不下判决 | 只报现象、标存疑，交作者裁定 |

第三行不是新原则：writing-review 的 frontmatter description 已声明"不适用：事实核查（只指出
存疑不验证）"；skill-creator `ref/audit-workflow.md` 判定清单的"纪律内容须有据"（无 baseline /
eval 痕迹则标注"未经验证"，审计者不凭精读断言对错）与"保留门槛"（只标不删、用户裁定）是同一
原则的制品版。两边不是重抄，是同一原则的两个应用面。

## 判例

- writing-review `ref/catalog.md` 指令文档节的 `疤痕组织`（原写"删，没来自实际失败的补丁 =
  无依据"）与 `禁令无 why`（原写"补不出理由的禁令大概率本就该删"）都要查 git blame / eval
  才能定违反，却下了删除判决，改为标存疑交作者裁定。
- 更早同类：`description 常驻` 判定注与 skill-creator `ref/audit-workflow.md`"触发语不回正文"
  三点全等，且对方是 ERROR 级正本，已从 writing-review 删净。
- 查证后不算重叠的反例：writing-review `跨文档 SSOT` 的"审多文件目标时，文件集内部互为参照
  输入"与 skill-creator"指标单一来源"不撞。同一数字在两文件同值出现，不落在 内容重复（要逐字
  逐段）/ 口径漂移（要定义或术语不一致）/ 事实冲突（要值矛盾）/ 跨文档重述定义 任何一条上。

## 操作约束

- 改这类重叠只能改自己的措辞，不能写"见对方判定清单第 N 条"：skill-creator
  `ref/audit-workflow.md`"跨 skill 指称"禁止单向提及越过 skill 名指对方内部路径 / 节名 / 组名。
- 4 字级豁免语（如"外部依赖版本约束照写"）两边各留一份：跨 skill 各自自含比省这几个字重要。
