---
name: entry-slug
description: 一句话事实摘要，脱离索引也成立（长度与字段约束见本文件底部"字段约定"）
metadata:
  type: feedback
  scope: 约束对象（目录 / 文件 / 决策点）
  modified: 2026-09-24
---

# 条目标题

- 结论 / 规则一句话起笔；展开"为什么 / 边界"再成段，不复述代码能给出的细节
- 正文超 120 行（lint 报 ENTRY-LONG）几乎总是路由错误："为什么"的展开该吸收进 docs /
  AGENTS.md，条目降级成一行结论 + 指针

## 关键证据

<!-- 可选节：证据绑定（哪次纠正、哪个坑、用户原话）落这里；没证据的条目不该存在 -->

## 字段约定

<!-- 本节是格式说明；把本文件拷成真实条目时删除本节与上面注释占位 -->

- `name`：= 文件名 slug（kebab-case），两者不一致 lint 报 ERROR
- `description`：≤ 200 字符的事实摘要；写不出具体内容的摘要说明条目本身空泛
- `metadata.type`：四选一，即 `user`（用户角色与偏好）/ `feedback`（用户纠正与确认过的做法）/
  `project`（代码与 git 推不出的项目事实）/ `reference`（项目外的信息指针）
- `metadata.scope`：条目约束的目录 / 文件 / 决策点；事件驱动复核靠它匹配 git 变更，缺失
  lint 报 WARN
- `metadata.modified`：YYYY-MM-DD；并入更新时刷新，仅供新鲜度参考（不作为陈旧的判决依据）
