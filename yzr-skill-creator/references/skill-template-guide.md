# SKILL 写作骨架与模板

> 通用 SKILL 写作骨架（**目录布局 / 三级加载 / 输出格式模板**）——与具体
> skill 类型无关。agent 本应知道"skeleton 是什么"，但具体格式约定（目录 /
> progressive disclosure / 模板）放此处一次，SKILL.md 自身不再重抄以减少 token。

## 目录布局

```text
skill-name/
├── SKILL.md（必选，YAML frontmatter + Markdown 说明文档）
│   ├── YAML frontmatter（name、description 必需）
│   └── Markdown 说明正文
├── CHANGELOG.md（可选；skill 自身的版本演进史集中此处，SKILL.md / references 正文不内联版本史）
└── 捆绑资源（可选）
    ├── scripts/    - 用于确定性 / 重复性任务的可执行脚本（Python / Bash 等）
    ├── references/ - 按需加载到上下文的文档（heavy reference 必备）
    ├── assets/     - 用于输出的文件（模板 / 图标 / 字体）
    └── eval/       - 用于对当前 skill 的评估
```

需要考虑 `SKILL.md` 的大小：保持简短（正文长度权威上限见
`references/skill-writing-principles.md`「正文写作原则」），详细文档挪到 `references/`；
跨文件用链接引用，不内联。版本演进史不内联进 SKILL.md / references 正文——集中放
`CHANGELOG.md`（原则见 `references/skill-writing-principles.md`「正文不堆版本演进史」）。

## progressive disclosure（三级加载）

1. **元数据**（`name` + `description`）：始终在上下文中
2. **SKILL.md 正文**：skill 触发时进入上下文（尽量简短，触发即载入）
3. **捆绑资源**（`scripts/` / `references/` / `assets/` / `eval/`）：按需加载
   — scripts 可不读直接执行；references / assets 需 Read 才加载。

**关键模式**（以下条目的权威口径都在 `references/skill-writing-principles.md`「正文写作原则」，
此处只给结论、不重抄具体数字）：

- 长度上限 + 接近上限就抽一层到 `references/`，并给出清晰的"何时去读"指引
- SKILL.md 内引用其它文件时，说明何时去读
- one-level-deep：SKILL.md → references 合法；references → references 禁止（加载链）
- reference 文件超过 TOC 阈值要带目录（模板文件例外见原则文件）

**领域组织**：skill 支持多领域 / 框架时按变体组织——

```text
cloud-deploy/
├── SKILL.md（workflow + selection）
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

## 写作模式模板

### 定义输出格式

```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

### 示例模式

```markdown
## Commit message format
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat（auth）: implement JWT-based authentication
```

### 正文骨架（canonical 节）

SKILL.md 正文的规范 H2 节名、顺序、各类型的可省略规则——唯一真源在
`scripts/utils.py::CANONICAL_BODY_SECTIONS`（**prose 不重抄节名列表**，改常量一处生效；
快速审计用 `python -m scripts.quick_validate <skill-dir> --tier <type>`）。
可直接 `cp` 填充的骨架在 `assets/skill-template.md`。

### 变体（各类型的骨架适配）

- **参考资料型**（只聚合信息、不改变 agent 行为）：可省略「执行原则 / 边界」与
  「工作流 / 步骤」两节——把"行为约束 / 步骤"留给真正的配方型 skill
- **元 / 多入口 skill**：允许在第一个规范节前加**一个**路由节（如「四个入口」），
  规范节本身仍按 canonical 顺序完整保留
- **领域特有节**（评审立场 / 设计决策 / 前置条件等）：放「执行原则 / 边界」之后；
  超过下放阈值（见 `references/skill-writing-principles.md`「正文超长根因诊断路径」）
  下放到 `references/`，正文只留路标
- **视角 / 立场节的加与不加**：视角 / 立场（如「评审立场」）仅当 skill 的核心价值是
  **判断**且立场需要成段展开时才立节（review / 评审 / 审计类典型——立场本身决定产物：
  "以维护者立场而非作者立场看代码"）；一两句话能讲清的立场写成「执行原则 / 边界」的
  一条 bullet（"立场 + 为什么"）；机械型 skill（转换 / 提取 / 管线）**不加**——写不出
  有内容的视角节 = 该加的是别的东西或什么都不加

### 何时去读本文件

新 skill 起草 `/ audit 现有 skill` 时，需要通用骨架 / 模板就 `Read` 本文件；yzr-skill-creator 的 SKILL.md
不再重复"骨架 / 模板"内容（避免"通用背景铺垫"冗余段，省 token）。
