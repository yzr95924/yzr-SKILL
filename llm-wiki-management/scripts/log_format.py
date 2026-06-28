#!/usr/bin/env python3
"""log.md 行格式正则 SSOT。

权威定义与 [`references/page-templates.md` §7](../references/page-templates.md#7-logmdlog) 同步。
若要改格式，必须**同时**改这里 + page-templates.md §7 + references/claude-md-template.md §一
中的格式说明。

两类正则：
- `LOG_LINE_RE`：全 op（ingest/query/lint/setup）——用于 lint 验证 log.md 每行格式合法
- `LOG_INGEST_RE`：仅 ingest op + 抓标题——用于 ingest_diff 从 log.md 提取"被 ingest 过"的标题集合
"""

import re

# 文档 SSOT: references/page-templates.md §7
LOG_LINE_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|setup) \| .+$")

# 仅 ingest 分支（用于从 log.md 反查 ingest 过的标题；不是 lint 全格式校验）
LOG_INGEST_RE = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] ingest \| (.+)$")
