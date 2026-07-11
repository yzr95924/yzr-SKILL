# Python 语言插件

## 元信息

- 动态类型 + 运行时反射
- 主流 lint 工具: ruff / mypy / pyright / bandit / radon / vulture
- 风格基础: PEP 8 / PEP 484 (typing)
- 运行时: CPython / PyPy / uvloop 等

## 工具映射表

| 工具 | 检测项 | 安装 | 跑法 |
| --- | --- | --- | --- |
| ruff | 重复 / 复杂度 / unused / 风格 | `pip install ruff` | `ruff check <path>` |
| mypy | 类型错误 | `pip install mypy` | `mypy <path>` |
| pyright | 类型错误(更严) | `pip install pyright` | `pyright <path>` |
| bandit | 安全漏洞 | `pip install bandit` | `bandit -r <path>` |
| radon | 圈复杂度 / 维护性指数 | `pip install radon` | `radon cc -s <path>` |
| vulture | 死代码 | `pip install vulture` | `vulture <path>` |

不在 PATH → 静默跳过,记到报告脚注。

## Python 特定调优

- **typing.Protocol**: 用 Protocol 表达结构化类型;避免为类型继承而继承
- **dataclass 滥用**: 不要为"自动生成 `__init__`"而滥用 dataclass;字段需强约束时用 attrs / pydantic
- **mutable default args**: `def f(items=[]):` 是陷阱;改 `def f(items=None): items = items or []`
- **EAFP vs LBYL**: Python 偏 EAFP(try/except);LBYL 容易 TOCTOU
- **list comprehension vs map/filter**: 简单场景用 list comprehension,可读性更好
- **f-string vs format()**: f-string 是默认;复杂格式才用 format

## 典型 Python 代码味补充

(catalog 之外)

- **过度抽象**: 1-2 行包装成 5 层继承 / 装饰器栈
- **配置文件散落**: `os.environ.get("KEY")` 在函数里散落,难测试;改用 dataclass + 单一读取入口
- **async/await 滥用**: CPU bound 任务用 threading / multiprocessing,不是 asyncio
- **try/except 过宽**: `except Exception:` 把 KeyboardInterrupt 也吞了
- **is vs ==**: `is` 用于 None / True / False 单例,`==` 用于值比较
- **import \***: 不在生产代码用;改显式导入
- **类当命名空间**: 用 module 即可,不必造类
