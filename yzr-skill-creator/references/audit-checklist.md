# 审计检查操作清单

> 入口 4（原则校验）的执行细节：按原则分节的 grep / 命令清单 / 判定步骤。
> 原则本体与"为什么"见 `references/skill-writing-principles.md`「正文写作原则」；
> 本文件由 SKILL.md 入口 4 直接挂载，只在审计时读，写作时不需要。

## 脚本入口（审计辅助）

| 脚本 | 用法与说明 |
| --- | --- |
| `quick_validate.py` | `python -m scripts.quick_validate <skill-dir> [--tier <default\|reference\|meta>]`——frontmatter 合法性（name 与目录一致 / description ≤ `DESCRIPTION_MAX_CHARS` / allowed-properties / **description 固定格式标记**（触发： / 不适用：））+ 正文结构（节名 / 顺序 / 豁免，WARN 不 fail）；节名 SSOT 在 `scripts/utils.py::CANONICAL_BODY_SECTIONS` |
| `check_skill_dependencies.py` | `python -m scripts.check_skill_dependencies <repo-root>`——列出互相提及的 skill 对 + 证据；"互提" ≠ "互依"，方向与是否成环靠 agent 读正文确认 |
| `check_anchor_health.py` | `python -m scripts.check_anchor_health <skill-dir>` 或 `--repo-root` 全扫；`--json` 机器可读；`--include-templates` 强制审 `*-template.md`（默认跳过——模板相对路径在 copy 进目标仓后才有效） |

## 跨文件重复检测

(1) 列出目标 skill 的所有 `.md` 文件（`SKILL.md` + `references/*.md`）；
(2) 对每条核心原则的**关键词**（概念性短语，按目标 skill 的领域自列——如 wiki 类 skill 的
    "tag 白名单" / "reviewed 戳" / "frontmatter 必填字段"），用 grep 在所有文件查；
(3) 按出现次数 + self-aware 注释存在性分类：

- 1 次 = 正常
- 2 次且一方是自包含模板（带 self-aware 注释指 SSOT）= 允许
- 2 次且都无注释 = 警告，读两段对比确认
- 3+ 次且都无 self-aware 注释 = 几乎必是 SSOT 违规

## 脚本常量作 SSOT 时的 prose 引用

`grep -nE "\b(<具体阈值/版本号裸数字>)\b" <skill>/**/*.md`——出现应改为常量名引用，除非该数字另有出处。

## 跨 skill 相对路径引用禁止

`grep -rEn '\]\(\.\./\.\./[a-z]' <skill>/**/*.md`——出现即报"跨 skill 相对路径引用"，按违规处理
（默认改成纯文本，不保留链接）。

## markdown 链接相对路径基准匹配

(1) 把 skill 内每条链接的 path 相对当前文件目录解析，target 文件不存在 = 死链嫌疑；
(2) 粗筛 `grep -rnE '\]\(\.\./[a-z_0-9-]+\.(md|py)' references/`，逐个确认 target 是 skill 根真文件
    （`../scripts/foo.py` 合法）还是同级误加 `../`（`../page-templates.md` 应为 `page-templates.md`）；
(3) fragment 漂移：`path#anchor` 的 anchor 若目标 heading 改名 / spec 演进后没跟着改 = 失效。
    **已自动化**：`scripts/check_anchor_health.py`（`--repo-root` 全扫 / `--json` 机器可读 /
    `--include-templates` 审模板）——跑脚本为准，本条只在脚本不可用时手工执行。

slug 规则（手工核对时用）：GitHub 风格 = 小写 + 去标点 + 空格转 `-`；全角标点 `：` / `、` / `（` / `）`
是**删除**而非转 `-`。

## Iron Law baseline 证据

`grep -nE "迭代|baseline|transcript|Rationalization|RED|GREEN|REFACTOR" <skill>/SKILL.md <skill>/references/*.md`
——命中其中 ≥ 1 项 = 有 baseline 证据；纪律型 / 模式型 skill（grep 命中禁令或步骤式措辞）若无 baseline
transcript 证据，按"未经验证"标注。

粗筛：`grep -rEn "(iteration-[0-9]+|without_skill|old_skill)" <workspace>/`——验证工作区是否真跑过 baseline。

## 纪律三件套（反合理化）

`grep -nE "NEVER|ALWAYS|必须|禁止|不能|不得" <skill>/SKILL.md <skill>/references/*.md` 命中 → 检查同一文件
是否同时含 Rationalization Table + Red Flags + "violating letter = violating spirit"（或
"违反字面 = 违反精神"）三段；缺任一 = 纪律型 skill 不合规。

反查：`grep -nE "Rationalization|合理化|借口|Red ?Flag|红旗" <skill>/**/*.md`——纪律型 skill 中应至少
命中 1 次（抓"用了禁令但忘了三件套"的常见漏）。

## 形式匹配失败

纯 judgment-based：读 RED transcript 判断失败类型归属（纪律 / 塑形 / 知识），再核对 skill 形式是否匹配；
混合使用多种形式时（如既有禁令又有配方），确认每段形式对应其要堵的具体失败，不要一刀切归类。

## 精简（长度）

`wc -w <skill>/SKILL.md` 应低于权威上限（SSOT 在 `skill-writing-principles.md`）；超 tier 软目标但低于
硬限标"WARN 偏臃肿"。**中文口径 caveat**：中文无空格分词，`wc -w` 对中文为主的 SKILL.md 严重低估
（实测约 1/3），改用 `wc -m` 按字符估算或按"1 词 ≈ 1.5–2 字"人工折算。

`grep -nE "(PDF (Portable|is a|are a)|files? (is|are) a common|is a common file format)" <skill>/**/*.md`
——找"通用背景铺垫"类冗余段。

## 版本演进史内联

`grep -cnE 'v?[0-9]+\.[0-9]+(\.[0-9]+)?' <skill>/SKILL.md <skill>/references/*.md`（排除 `CHANGELOG.md` /
`*changelog*.md`）——单文件命中密集（≥ 10 处）= 版本史内联嫌疑，再逐处人工区分"自身 / 所管 spec 的版本演进"
（违规：挪 changelog、原处留路标）还是"外部依赖版本约束"（合法）。
