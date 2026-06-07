# My SKILLs

这个仓库主要为个人常用的自定义 SKILL 合集

## 设计原理

- 主要参考 Claude 官方指导：<https://support.claude.com/en/articles/12512198-how-to-create-custom-skills>
- 可以参考模版 `SKILL_template.md`，但是不要求只有这些字段，可以扩展

## 字段含义

### Metadata 字段

1. `name`：A human-friendly name for your skill (64 characters maximum)
    - Example: Brand Guidelines
2. `description`: A clear description of what the skill does and when to use it.
    - this is critical—Claude uses this to determine when to invoke your skill (200 characters maximum).
3. `dependencies`: Software packages required by your skill.

### Body 字段

1. `何时使用 / 不使用`：定义清楚 agent 使用的场景和不使用的场景；
2. `输入 / 输出`：定义 skill 具体的输入输出形式；
3. `执行原则 / 边界`：定义 skill 具体的执行原则和边界；
4. `工作流 / 步骤`：定义这个 skill 要按照什么样的步骤执行；
5. `参考样例`：可以提供一些例子指导 agent；

## SKILLs 分类

TODO：待后续不断补充；

## 代码仓规范

- 所有 SKILL 名字与起对应的文件夹名字保持一致，对应的文件夹下必须包含 `SKILL.md` 文件；
- 所以 Markdown 文件需要进行格式化和 lint 操作，确保格式统一；
- 一些经验可以持久化到 `MEMORY.md`
