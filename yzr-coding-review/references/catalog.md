<!-- markdownlint-disable MD024 -->

# 重构 + 合理性审视场景 Catalog(SSOT)

本文件是 yzr-coding-review skill 的核心知识资产 — Fowler 经典重构场景卡片(语言中立)+ 合理性审视卡片(非 Fowler)。

## 怎么读本 catalog

每张卡片 3 项列表:

- **信号**: 看到什么模式应该想到这个场景
- **方案**: 一两句话怎么改
- **严重度**: 典型落点(不绑死,以 severity-rubric.md 为准);数值阈值**直取自 rubric** 的卡片
  标注"（对齐 rubric）"——改阈值只改 rubric 一处;其余为卡片演绎落点,判定仍以 rubric 为准。

语言中立,不绑 Python / Go / TS 特定语法。

## TOC

### 第一组:Naming

- [Rename Variable](#rename-variable)
- [Rename Function](#rename-function)
- [Change Function Declaration](#change-function-declaration)

### 第二组:Functions

- [Extract Function](#extract-function)
- [Inline Function](#inline-function)
- [Extract Variable](#extract-variable)
- [Inline Variable](#inline-variable)
- [Introduce Parameter Object](#introduce-parameter-object)
- [Remove Dead Code](#remove-dead-code)
- [Replace Algorithm](#replace-algorithm)

### 第三组:Classes & Modules

- [Extract Class](#extract-class)
- [Inline Class](#inline-class)
- [Move Function](#move-function)
- [Move Field](#move-field)
- [Hide Delegate](#hide-delegate)
- [Remove Middle Man](#remove-middle-man)

### 第四组:Data

- [Encapsulate Variable](#encapsulate-variable)
- [Replace Primitive with Object](#replace-primitive-with-object)
- [Encapsulate Record](#encapsulate-record)
- [Replace Derived Variable with Query](#replace-derived-variable-with-query)

### 第五组:Conditional Logic

- [Decompose Conditional](#decompose-conditional)
- [Consolidate Conditional Expression](#consolidate-conditional-expression)
- [Replace Nested Conditional with Guard Clauses](#replace-nested-conditional-with-guard-clauses)
- [Replace Conditional with Polymorphism](#replace-conditional-with-polymorphism)
- [Introduce Special Case](#introduce-special-case)

### 第六组:API

- [Parameterize Function](#parameterize-function)
- [Remove Flag Argument](#remove-flag-argument)
- [Preserve Whole Object](#preserve-whole-object)
- [Replace Parameter with Query](#replace-parameter-with-query)
- [Separate Query from Modifier](#separate-query-from-modifier)

### 第七组:Inheritance

- [Pull Up Method](#pull-up-method)
- [Push Down Method](#push-down-method)
- [Pull Up Constructor Body](#pull-up-constructor-body)

### 第八组:合理性审视(非 Fowler)

- [Missing Input Validation](#missing-input-validation)
- [Swallowed Error](#swallowed-error)
- [Inconsistent Error Handling](#inconsistent-error-handling)
- [Magic Literal](#magic-literal)
- [Inefficient Algorithmic Shape](#inefficient-algorithmic-shape)
- [Repeated Expensive Call](#repeated-expensive-call)
- [Duplicate Code](#duplicate-code)
- [Misleading Comment](#misleading-comment)

## 第一组:Naming

### Rename Variable

- **信号**: 变量名表意不清;同一个变量多处命名不一致(同一概念多种叫法);缩写 / 单字母滥用。
- **方案**: 改成业务概念名,替换全文引用;同名不同义的变量不要合并。
- **严重度**: 多数 Minor;若影响正确性(同名不同义)升 Major。

### Rename Function

- **信号**: 函数名不能表达"做什么";函数行为与名字不一致;调用处需要看实现才懂。
- **方案**: 改名 + 替换所有调用方。
- **严重度**: 多数 Minor;若调用 ≥ 5 处或被外部 API 引用升 Major。

### Change Function Declaration

- **信号**: 参数命名含混 / 顺序别扭;参数过多需拆;调用方普遍加注释解释参数。
- **方案**: 改名 + 调整参数顺序;参数过多时拆参数。
- **严重度**: 多数 Minor;调用广 / 跨模块升 Major;API 已发布升 Major + 留向后兼容。

## 第二组:Functions

### Extract Function

- **信号**: 函数体长(> 30 行);内嵌多个语义段(注释 / 空行分隔);一段代码被多处需要但有差异。
- **方案**: 抽出一段有名字的函数;参数 = 原代码用到的外部变量,返回值 = 原代码产出。
- **严重度**: 函数体超长(> 50 行)→ Major(对齐 rubric);局部提取 → Minor。

### Inline Function

- **信号**: 函数体与函数名一样清晰(几行 + 名字足够);函数被多层嵌套包装(过度抽象)。
- **方案**: 函数体替换到所有调用处;调用处保持可读;广泛调用但各调用处语境不同,内联
  可能引入混乱 → 不抽。
- **严重度**: 多数 Minor。

### Extract Variable

- **信号**: 表达式难读(嵌套三元 / 链式调用);同一表达式重复出现 ≥ 2 次。
- **方案**: 用有名字的局部变量承载表达式;表达式复杂考虑 Extract Function。
- **严重度**: 多数 Minor;表达式跨越 ≥ 3 个子表达式升 Major。

### Inline Variable

- **信号**: 变量名不提供新信息(与赋值表达式等价);变量仅用一次且无解释作用。
- **方案**: 用表达式直接替换变量引用;若变量名误导性比表达式更强 → 改名而非 Inline。
- **严重度**: 多数 Nitpick。

### Introduce Parameter Object

- **信号**: 多处函数签名带同一组参数(参数簇);参数列表 ≥ 4 个且常一起出现。
- **方案**: 把参数簇封装成结构 / 数据类;所有调用处改为传该对象。判别:参数簇来自同一
  既有对象(对象已存在) → 优先 Preserve Whole Object 复用对象;需要新建聚合概念才用本卡。
- **严重度**: 参数 ≥ 5 个 → Major;参数簇在 ≥ 3 个函数出现 → Major。

### Remove Dead Code

- **信号**: 变量 / 函数 / 类从未被调用;被注释掉的代码块;if 分支永远走不到。
- **方案**: 删;若怕后悔,git history 留着。
- **严重度**: 多数 Minor;死代码引发理解混乱升 Major;涉及公共 API 出口慎重。

### Replace Algorithm

- **信号**: 算法实现复杂 / 难懂易错;有更清晰的等价算法。
- **方案**: 替换函数体为新算法;逐步替换比一次性改安全(可对比测试)。复杂度降档
  (O(n²) → 线性)不属本卡,见 Inefficient Algorithmic Shape。
- **严重度**: 多数 Major;若有性能 / 正确性差异需要测试覆盖。

## 第三组:Classes & Modules

### Extract Class

- **信号**: 一个类承担多组不相关职责;字段 / 方法可拆成两个独立概念。
- **方案**: 抽出新类,把相关字段 + 方法搬过去;原类持新类的引用。
- **严重度**: 职责数量 ≥ 3 → Major(对齐 rubric);字段混搭无共同语义升 Major。

### Inline Class

- **信号**: 类不再独立承担职责(只剩 1-2 个方法);几乎不被外部引用。
- **方案**: 类内容搬回调用方;删除类。
- **严重度**: 多数 Minor;类被广泛引用时先考虑 Move Function 而非 Inline。

### Move Function

- **信号**: 函数多数行为依赖另一个类(被调用 ≥ 2 次来自另一类);所在类仅剩少量行为。
- **方案**: 函数搬去调用最多的类;调整调用方。
- **严重度**: 多数 Major;跨模块搬动需小心导入依赖。

### Move Field

- **信号**: 字段被另一个类的函数频繁使用;当前类几乎不用该字段。
- **方案**: 字段搬到使用最多的类;封装字段访问。
- **严重度**: 多数 Major;public 字段影响广,搬动要谨慎。

### Hide Delegate

- **信号**: 调用方代码穿透委托链(`a.b.c.field`);委托关系暴露给客户端。
- **方案**: 在委托起点类加委托方法,封装访问路径。
- **严重度**: 多数 Minor;委托链 ≥ 3 层升 Major。

### Remove Middle Man

- **信号**: 委托类一半方法都是简单委托;委托本身没增加价值。
- **方案**: 让调用方直接访问被委托类;删除中间方法。
- **严重度**: 多数 Minor;委托类几乎无自身逻辑 → Major。

## 第四组:Data

### Encapsulate Variable

- **信号**: 可变数据(模块级变量 / 类字段)被外部无约束读写;作用域过大,无访问控制。
- **方案**: 用 getter / setter(或属性访问器)封装;必要时加访问控制。
- **严重度**: 多数 Minor;被外部肆意修改 → Major。

### Replace Primitive with Object

- **信号**: 基本类型(字符串 / 数字)承载业务含义但无类型保护;同含义多形式(如 `"USD"` / `"usd"` / `"$"`)散落。
- **方案**: 引入值对象;在值对象里加格式校验 / 转换逻辑。
- **严重度**: 多数 Minor;跨模块 / 多源数据 → Major。

### Encapsulate Record

- **信号**: 记录(结构体 / dict)结构直接暴露,字段被外部读写;结构改动牵动所有调用方(演化耦合)。
- **方案**: 用类封装字段;对外暴露访问方法。
- **严重度**: 多数 Minor;广泛使用的配置记录升 Major。

### Replace Derived Variable with Query

- **信号**: 字段值可由其他字段算出;派生字段与源字段易失同步。
- **方案**: 删字段,改成 getter 算出;必要时缓存。
- **严重度**: 多数 Minor;同步维护多字段易出错 → Major。

## 第五组:Conditional Logic

### Decompose Conditional

- **信号**: 复杂条件(三元嵌套 / 多个 `&&` `||` / 长 if 链);同一条件多处重复。
- **方案**: 把每个条件 / 分支抽成具名函数。
- **严重度**: 多数 Major;if 嵌套 ≥ 3 层 → Major(对齐 rubric)。

### Consolidate Conditional Expression

- **信号**: 一连串条件都返回同一结果(检查同样的概念);或多个独立条件用同一处理。
- **方案**: 合并成单个条件 + 单一处理路径;提取检查为函数。
- **严重度**: 多数 Minor;≥ 3 个独立条件 → Major。

### Replace Nested Conditional with Guard Clauses

- **信号**: 嵌套 if 用于处理"异常 / 边界情况";正常路径在 else 深处。
- **方案**: 反转条件,用 early return 替代嵌套。
- **严重度**: 多数 Minor;嵌套 ≥ 3 层 → Major(对齐 rubric)。

### Replace Conditional with Polymorphism

- **信号**: switch / 多分支按类型走不同逻辑;新类型需改多处 switch。
- **方案**: 分支逻辑搬到子类 / 实现类;原 switch 删 / 改为多态调用。
- **严重度**: 多数 Major;switch ≥ 3 分支 + 跨模块升 Major。

### Introduce Special Case

- **信号**: 大量代码检查同一特殊值(null / undefined / 特定枚举);同一特殊处理逻辑重复出现。
- **方案**: 引入特殊值对象,把检查转为多态 / 默认值;消除重复 if。
- **严重度**: 多数 Major;null 检查散落 ≥ 3 处升 Major。

## 第六组:API

### Parameterize Function

- **信号**: 多个函数行为几乎相同,只在某个字面量 / 参数上有差异。
- **方案**: 把差异点提取成参数;合并函数。
- **严重度**: 多数 Minor;≥ 3 个近似函数 → Major。

### Remove Flag Argument

- **信号**: 函数有一个 bool / enum 参数控制分支;调用方普遍传字面量(`true` / `false`)。
- **方案**: 拆成两个具名函数;布尔语义明确化。
- **严重度**: 多数 Minor;调用 ≥ 3 处 → Major。

### Preserve Whole Object

- **信号**: 函数从对象取几个字段作参数;对象本身可整体传入。
- **方案**: 改参数为对象;函数内按需访问字段。判别:对象尚不存在、参数簇需封装成新
  聚合概念 → 优先 Introduce Parameter Object。
- **严重度**: 多数 Minor;参数 ≥ 3 个来自同一对象升 Major。

### Replace Parameter with Query

- **信号**: 参数值可由其他参数 / 上下文算出;调用方算好后传入。
- **方案**: 函数内自查;删参数。
- **严重度**: 多数 Minor;若参数有显式语义(测试桩 / API 兼容)保留。

### Separate Query from Modifier

- **信号**: 函数名是 query(名词 / 描述状态)但内部有副作用;副作用调用方不知情。
- **方案**: 拆 query + command 两个函数;query 纯查询,command 改状态。
- **严重度**: 多数 Major;涉及金融 / 通知等关键副作用升 Major / Blocker。

## 第七组:Inheritance

### Pull Up Method

- **信号**: 两个子类有相同方法体;父类可以承载该方法。
- **方案**: 移到父类;子类继承。
- **严重度**: 多数 Major。

### Push Down Method

- **信号**: 父类方法只被一个子类使用;其它子类不需要。
- **方案**: 移到对应子类;父类删。
- **严重度**: 多数 Minor。

### Pull Up Constructor Body

- **信号**: 子类构造函数有共同初始化逻辑;父类构造函数可承载。
- **方案**: 父类构造函数加公共部分;子类构造函数 `super()` 后做特化。
- **严重度**: 多数 Major。

## 第八组:合理性审视(非 Fowler)

> 本组覆盖"代码合不合理"维度:设计意图与职责 / 边界条件与错误处理 / 可读性;
> 计算逻辑经济性作为合理性的视角并入,不单列维度。
> 卡片 schema 与 Fowler 组一致;信号不来自重构经典,来自代码审查实践。

### Missing Input Validation

- **信号**: 对外部输入(用户输入 / API 参数 / 文件内容 / 环境变量)直接使用无校验;空值 / 越界 / 非法格式直接进核心逻辑;信任边界处没有快速失败。
- **方案**: 在信任边界入口校验(类型 / 范围 / 非空 / 格式);非法输入快速失败(fail fast);内部调用处已有校验的不重复。
- **严重度**: 信任边界处缺失 → Major;数据破坏 / 注入类后果 → Major;内部调用已有校验但重复 → Minor。

### Swallowed Error

- **信号**: 空 except / 忽略错误返回值 / `// ignore` 注释;错误只 log 后继续;catch-all 裸捕获。
- **方案**: 至少记录错误上下文;无法处理时向上传播或显式降级(有兜底路径);避免裸 catch-all。
- **严重度**: 静默吞错导致数据丢失 / 状态不一致 → Major;错误完全无痕(无日志) → Major;仅吞无副作用异常 → Minor。

### Inconsistent Error Handling

- **信号**: 同一模块混用返回值 + 异常 + 全局错误码;部分函数抛异常、部分返回 None / 0 表示失败;调用方无法统一判断失败。
- **方案**: 统一错误传递机制;跨边界转换处集中管理。
- **严重度**: 调用方易漏判失败 → Major;模块内统一但跨模块不一致 → Minor。

### Magic Literal

- **信号**: 代码中出现裸字面量(数字 / 字符串)承载业务含义;同一值多处重复出现;字面量含义靠上下文猜。
- **方案**: 提取为具名常量 / 枚举;业务配置项走配置。
- **严重度**: 重复 ≥ 3 处或含义隐晦 → Major;单处且语境清晰 → Minor。

### Inefficient Algorithmic Shape

- **信号**: 无界 / 大数据集上的嵌套循环(O(n²) 以上);可提前退出却全量扫描;线性可解却用平方实现;列表反复 `in` 查找(应换 set / 索引)。
- **方案**: 换数据结构或算法把复杂度降档;先确认数据规模与热路径再决定是否值得改;
  等价但更清晰的实现重写见 Replace Algorithm。
- **严重度**: 无界数据 + 热路径 → Major;数据有界且小 → Minor;仅理论更优 → 不报(洁癖但克制)。

### Repeated Expensive Call

- **信号**: 循环内重复调用外部资源(DB / 网络 / 文件 IO)——N+1 模式;循环不变量在循环内重复计算;同一昂贵结果多处重算未缓存。
- **方案**: 批量取数 / 提升循环不变量 / 缓存重复结果。
- **严重度**: 循环内外部调用 → Major;循环不变量重复计算 → Minor;冷路径 → Minor 或不报。

### Duplicate Code

- **信号**: 相同 / 近似代码块在 ≥ 3 处出现或单块 > 5 行;同一修改需在多处同步。
- **方案**: 抽公共函数 / 方法,差异点参数化;仅 1–2 处且短小的重复不值得抽,维持现状。
- **严重度**: 重复 ≥ 3 处或 > 5 行 → Major(对齐 rubric);单处短重复 → Minor / 不报。

### Misleading Comment

- **信号**: 注释说 A 但代码做 B;注释描述的行为与实现不一致;注释描述已删除的旧行为。
- **方案**: 以代码为准——改注释对齐代码,或代码确实是 bug 则改代码;陈旧注释直接删 / 更新。
- **严重度**: 注释与代码矛盾 → Major(对齐 rubric);纯陈旧但无害注释 → Minor。

## 维护说明

**新增场景**: 在对应分组末尾追加卡片,保持 3 项列表 schema 完整;TOC 加链接;不改 SSOT 措辞(改卡片不改 SKILL.md)。

**TOC 维护**: TOC 锚点按卡片标题生成(GitHub 风格:小写 + 去标点 + 空格转 `-`),全角标点 `:` / `、` / `(` / `)` 删除。

**边界**: 本 catalog 是"语言中立骨架";具体语言细节(typing Protocol / Go error wrapping / TS strict null 等)
不写进卡片,由 LLM 自身语言知识判断。第八组只收"合理性"维度卡片,bug 修复 / 性能调优执行 / 安全审计专项不进本 catalog。

**与 lint 的分工**: 能写成确定性规则的机械检查(具体风格规则 / 格式 / TODO 残留 / 文档字符串缺失)
归项目 CI,不进 catalog、不占发现项;对 lint 有信号但无结论的主题(死代码 / 魔数 / 空 catch / 函数过长),
卡片聚焦"信号之后怎么判"。例外:"是否偏离本仓自身惯例"属判断层(仓内惯例往往未写入配置),可进发现项。
