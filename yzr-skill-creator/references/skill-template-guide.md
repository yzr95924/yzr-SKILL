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
└── 捆绑资源（可选）
    ├── scripts/    - 用于确定性 / 重复性任务的可执行脚本（Python / Bash 等）
    ├── references/ - 按需加载到上下文的文档（heavy reference 必备）
    ├── assets/     - 用于输出的文件（模板 / 图标 / 字体）
    └── eval/       - 用于对当前 skill 的评估
```

需要考虑 `SKILL.md` 的大小：保持简短（正文长度权威上限见
`references/skill-writing-principles.md`「正文写作原则」），详细文档挪到 `references/`；
跨文件用链接引用，不内联。

## progressive disclosure（三级加载）

1. **元数据**（`name` + `description`）：始终在上下文中
2. **SKILL.md 正文**：skill 触发时进入上下文（尽量简短，触发即载入）
3. **捆绑资源**（`scripts/` / `references/` / `assets/` / `eval/`）：按需加载
   — scripts 可不读直接执行；references / assets 需 Read 才加载。

**关键模式**：

- SKILL.md 控制在长度上限以内（5000 词硬限；元 / 普通 skill tiered 软目标见
  `references/skill-writing-principles.md`）；接近上限就抽一层到 `references/`，
  并给出清晰的"何时去读"指引。
- SKILL.md 内清晰引用其它文件，并说明何时去读。
- `references/*.md` 与 SKILL.md 同级（**one-level-deep**：SKILL.md → references 合法；
  references → references 禁止——会丢信息，见原则文件「精简原则」）。
- 单个 reference 文件 > 300 行要带 TOC（模板文件 CLI 字面拷贝不受此约束）。

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

### 重点内容

1. **何时使用 / 不使用**：定义清楚 agent 调用的场景和不使用的场景
2. **输入 / 输出**：定义 skill 具体的输入输出形式
3. **执行原则 / 边界**：定义 skill 具体的执行原则和边界（贯穿全程的判断基线）
4. **工作流 / 步骤**：定义 skill 操作的步骤序列
5. **参考样例**：提供可指导 agent 的真实例子

### 何时去读本文件

新 skill 起草 `/ audit 现有 skill` 时，需要通用骨架 / 模板就 `Read` 本文件；yzr-skill-creator 的 SKILL.md
不再重复"骨架 / 模板"内容（避免"通用背景铺垫"冗余段，省 token）。
