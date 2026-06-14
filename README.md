# My SKILLs

这个仓库主要为个人常用的自定义 SKILL 合集，本身也是一个生成个人常用的 skills 的仓库

## 设计原则
- 主要参考
  - [Claude 官方指导](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
  - [Claude 官方生成 skill 的 skill](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
- 具体的实现原则，参考 `./yzr-skill-creator`

## SKILLs 分类

TODO：待后续不断补充；

## 代码仓规范

- 所有 SKILL 名字与起对应的文件夹名字保持一致，对应的文件夹下必须包含 `SKILL.md` 文件，其他目录结构可以先创建，后面再扩展；
- 所以 Markdown 文件需要进行格式化和 lint 操作，确保格式统一；
- 所有 Python 文件统一走 `ruff`（配置见根目录 `pyproject.toml`），`ruff format` + `ruff check` 双管齐下，target 锁在 `py37` 以保住 3.6 风格的类型注解；
- 一些经验可以持久化到 `MEMORY.md`

## 依赖的 MCP 和外部的 Skills
### 依赖的 MCP
- 需要依赖 Gemini 文档的 MCP 服务：Gemini Docs MCP

### 依赖的 Skills
- 有的 skills 涉及调用 Gemini 相关的 API，需要安装 Gemini API 的 skills
```shell
$> npx skills add google-gemini/gemini-skills --skill gemini-api-dev
$> npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev
$> npx skills add google-gemini/gemini-skills --skill gemini-interactions-api
```
