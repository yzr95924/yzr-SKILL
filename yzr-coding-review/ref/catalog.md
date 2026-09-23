# 重构 + 合理性审视规则清单(SSOT)

## 怎么读本 catalog

每条规则: 信号与判定点跟在规则名后,修法保留 Fowler 术语作关键词,数值阈值与报 / 不报豁免内联;
引用一律用规则名。语言中立,不绑 Python / Go / TS 特定语法

## 重构规则

- **命名与签名**(Rename Variable / Rename Function / Change Function Declaration): 变量名表意不清、
  同一概念多处叫法、缩写 / 单字母滥用;函数名不能表达"做什么"或与行为不一致,调用处需看实现才懂;
  参数命名含混 / 顺序别扭,调用方普遍加注释解释参数。改成业务概念名并替换全文引用,同名不同义不合并;
  改名 + 调参数顺序;API 已发布时留向后兼容
- **函数粒度**(Extract / Inline Function、Extract / Inline Variable): 函数体 > 30 行或内嵌多个语义段
  (注释 / 空行分隔) → 抽具名函数,一段代码多处需要但有差异 → 抽出 + 差异参数化;函数体与名字一样清晰
  或过度包装 → 内联,广泛调用但各调用处语境不同的不内联;表达式难读(嵌套三元 / 链式调用 / 跨越
  ≥ 3 个子表达式)或同表达式 ≥ 2 处 → 具名局部变量,复杂到带逻辑时抽函数;变量名不提供新信息 / 仅用
  一次且无解释作用 → 直接用表达式,名字误导时改名而非内联
- **参数与接口**(Introduce Parameter Object / Preserve Whole Object / Remove Flag Argument /
  Parameterize Function / Replace Parameter with Query / Separate Query from Modifier): 参数簇在 ≥ 3 个
  函数出现,或参数列表 > 5 个 / ≥ 4 个常同现 → 封装成结构 / 数据类;参数簇来自既有对象 → Preserve
  Whole Object 复用,需新建聚合概念才封装新对象;bool / enum 参数控制分支 → 拆具名函数;多个近似函数
  只在字面量有差异 → 合并 + 差异提参数;参数可由其他参数 / 上下文算出 → 删,测试桩 / API 兼容语义保留;
  函数名是 query 但内部有副作用 → 拆 query + command
- **职责与归属**(Extract / Inline Class、Move Function / Field、Pull Up / Push Down Method、
  Pull Up Constructor Body、Hide Delegate / Remove Middle Man): 一个类承担 ≥ 3 个独立职责或字段 / 方法
  可拆成两个独立概念 → 拆类;类只剩 1-2 个方法且几乎不被外部引用 → 并回,被广泛引用时先考虑 Move;
  函数 / 字段多数行为依赖另一个类 → 搬过去,跨模块注意导入方向,public 字段先封装再搬;继承:两个子类
  同方法体 Pull Up,父类方法只被一个子类用 Push Down,构造公共段上提父类;委托链穿透(`a.b.c.field`)
  → 加委托方法封装;一半方法都是简单委托且无增值 → 删中间层
- **数据封装**(Encapsulate Variable / Record、Replace Primitive with Object、Replace Derived Variable
  with Query): 可变数据被外部无约束读写 / 记录结构直接暴露 → 用访问器 / 类封装,必要时加访问控制;
  基本类型承载业务含义且同含义多形式散落(`"USD"` / `"usd"` / `"$"`) → 值对象 + 格式校验;字段可由
  其他字段算出 → 删字段改 getter,注意派生字段与源字段的同步失配
- **条件逻辑**(Decompose / Consolidate Conditional Expression、Replace Nested Conditional with Guard
  Clauses、Replace Conditional with Polymorphism、Introduce Special Case): 复杂条件(三元嵌套 / 长 if
  链 / 同一条件多处重复),条件嵌套 ≥ 3 层 / 循环嵌套 ≥ 2 层 → 抽具名函数;一连串条件返回同一结果
  (检查同一概念)或 ≥ 3 个独立条件用同一处理 → 合并单路径;嵌套处理异常 / 边界、正常路径在 else 深处
  → 反转 early return;类型 switch ≥ 3 分支 → 搬子类多态;同一特殊值(null / undefined / 特定枚举)
  检查散落 → 特殊值对象
- **死代码**(Remove Dead Code): 从未被调用的变量 / 函数 / 类、被注释掉的代码块、走不到的分支 → 删,
  git history 留着;涉及公共 API 出口先确认无外部调用

## 合理性审视

> 覆盖"代码合不合理"维度:设计意图与职责 / 边界条件与错误处理 / 可读性;计算经济性作为合理性的
> 视角并入,不单列维度。信号不来自重构经典,来自代码审查实践

- **边界与校验**: 外部输入(用户输入 / API 参数 / 文件内容 / 环境变量)直接进核心逻辑,信任边界无校验
  → 入口校验(类型 / 范围 / 非空 / 格式)+ 非法输入快速失败(fail fast);内部调用已有校验的不重复
- **错误处理**: 空 except / 忽略错误返回值 / 错误只 log 后继续 / 裸 catch-all → 至少记录错误上下文,
  无法处理时向上传播或显式降级(有兜底路径);同模块混用返回值 + 异常 + 错误码,调用方无法统一判断
  失败 → 统一传递机制,跨边界转换集中管理
- **魔法值**: 裸字面量(数字 / 字符串)承载业务含义、同一值多处重复、含义靠上下文猜 → 具名常量 / 枚举;
  业务配置项走配置
- **计算经济性**: 无界 / 大数据集上的嵌套循环(O(n²) 以上)、可提前退出却全量扫描、列表反复 `in` 查找
  (应换 set / 索引) → 换数据结构或算法把复杂度降档;循环内重复调外部资源(N+1)、循环不变量重复计算、
  同一昂贵结果多处重算未缓存 → 批量取数 / 提循环不变量 / 缓存。先确认数据规模与热路径:仅理论更优的
  不报,冷路径可不报;复杂度不变、只是有更清晰等价实现的 → Replace Algorithm,逐步替换 + 测试覆盖
- **重复代码**: 相同 / 近似代码块 ≥ 3 处出现或单块 > 5 行、同一修改需多处同步 → 抽公共函数 / 方法,
  差异点参数化;仅 1-2 处且短小的重复不抽,维持现状
- **注释**: 注释说 A 但代码做 B / 描述已删除的旧行为 → 以代码为准改注释对齐(代码确实是 bug 则改代码);
  逐行复述 what、段头横幅、docstring 复读签名 → 删。解释 why / 非显然约束 / 外部契约的保留;删前确认
  没藏非显然信息(魔数来源 / 坑的成因),有则改写成一句 why;矛盾注释归前一条,不双报

## 维护说明

**新增规则**: 归入最贴近的规则条目;修法关键词与阈值内联,不改 SSOT 措辞(改 catalog 不改 `SKILL.md`)

**边界**: 本 catalog 是"语言中立骨架";具体语言细节(typing Protocol / Go error wrapping / TS strict null 等)
不写进规则,由 LLM 自身语言知识判断。只收"合理性"维度规则,bug 修复 / 性能调优执行 / 安全审计专项不进本 catalog

**与 lint 的分工**: 机械检查不进 catalog(归项目 CI 的口径见 [章节](../SKILL.md#执行原则) 第 3 条);
对 lint 有信号但无结论的主题(死代码 / 魔数 / 空 catch / 函数过长),规则聚焦"信号之后怎么判"。
例外:"是否偏离本仓自身惯例"属判断层(仓内惯例往往未写入配置),可进发现项
