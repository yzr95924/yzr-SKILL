<!-- markdownlint-disable MD024 -->

# Fowler 重构场景 Catalog(SSOT)

本文件是 code-refactoring-review skill 的核心知识资产 — Fowler 经典重构场景卡片(语言中立)。

## 怎么读本 catalog

每张卡片 5 段:

- **代码味信号**: 看到什么模式应该想到这个场景
- **解决方案**: 伪代码 / 英文意图描述
- **Before / After**: 占位符伪代码(占位符统一 `<expr>` / `<method>` / `<field>` / `<class>` / `<param>`)
- **严重度提示**: 典型落点(不绑死,以 severity-rubric.md 为准)
- **语言无关**: 不绑 Python / Go / TS 特定语法

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

---

## 第一组:Naming

### Rename Variable

**代码味信号**: 变量名表意不清;同一个变量在多处使用但命名不一致(同一概念多种叫法);缩写 / 单字母滥用。

**解决方案**: 改成业务概念名;替换全文引用;注意同名不同义的变量不要合并。

**Before / After**:

- Before: `let d = ...; // d 是 days 还是 data 还是 distance?`
- After: `let elapsed_days = ...;`

**严重度提示**: 多数 Minor;若影响正确性(同名不同义)升 Major。

---

### Rename Function

**代码味信号**: 函数名不能表达"做什么";函数行为与名字不一致;阅读调用处需要看实现才知道干什么。

**解决方案**: 改名 + 替换所有调用方;IDE 重构工具辅助。

**Before / After**:

- Before: `fn proc(d) // proc 是什么?process?procedure?`
- After: `fn parse_config(d)`

**严重度提示**: 多数 Minor;若调用 ≥ 5 处或被外部 API 引用升 Major。

---

### Change Function Declaration

**代码味信号**: 函数名表达模糊,或参数命名 / 顺序不合理;调用方普遍加注释解释参数含义。

**解决方案**: 改名 + 调整参数顺序;可选拆参数(参数过多时);IDE 重命名支持跨文件。

**Before / After**:

- Before: `fn circ(d, t) // d 直径还是半径? t 啥?`
- After: `fn circ(radius, fill)`

**严重度提示**: 多数 Minor;若调用广 / 跨模块升 Major;若 API 已发布升 Major + 留向后兼容。

---

## 第二组:Functions

### Extract Function

**代码味信号**: 函数体长(> 30 行);内嵌多个语义段(用注释 / 空行分隔);一段代码被多处需要但有差异。

**解决方案**: 抽出一段有名字的函数;参数 = 原代码用到的外部变量;返回值 = 原代码产出。

**Before / After**:

- Before:

  ```text
  fn process(<order>):
    // 计算总价
    <base> = <order>.<qty> * <order>.<price>
    <discount> = ...
    <total> = <base> - <discount>
    // 打印账单
    print(...)
    print(...)
  ```

- After:

  ```text
  fn process(<order>):
    <total> = calc_total(<order>)
    print_bill(<order>, <total>)
  ```

**严重度提示**: 函数 > 50 行 → Major;函数 > 100 行 → Major 必报;局部提取 → Minor。

---

### Inline Function

**代码味信号**: 函数体与函数名一样清晰(几行 + 名字足够说明);函数被多层嵌套包装(过度抽象)。

**解决方案**: 把函数体替换到所有调用处;调用处保留可读。

**Before / After**:

- Before: `fn get_rating(): return more_than_five_late_deliveries() ? 2 : 1`
- After: 删除函数;调用处替换为原表达式。

**严重度提示**: 多数 Minor;若被广泛调用但调用处语境不同可能引入混乱 → 不抽。

---

### Extract Variable

**代码味信号**: 表达式难读(嵌套三元 / 链式调用);同一表达式重复出现 ≥ 2 次。

**解决方案**: 用有名字的局部变量承载表达式;若表达式复杂考虑 Extract Function。

**Before / After**:

- Before:

  ```text
  return <order>.<qty> * <order>.<price> -
         Math.min(0, <order>.<qty> - 500) * <order>.<price> * 0.05 +
         Math.min(<order>.<qty> * <order>.<price> * 0.1, 100)
  ```

- After:

  ```text
  let base_price = <order>.<qty> * <order>.<price>
  let shipping = Math.min(<base_price> * 0.1, 100)
  return <base_price> - <discount> + <shipping>
  ```

**严重度提示**: 多数 Minor;若表达式跨越 ≥ 3 个子表达式升 Major。

---

### Inline Variable

**代码味信号**: 变量名不提供新信息(与赋值表达式等价);变量仅用一次且无解释作用。

**解决方案**: 用表达式直接替换变量引用。

**Before / After**:

- Before: `let base_price = <order>.<qty> * <order>.<price>; return <base_price>;`
- After: `return <order>.<qty> * <order>.<price>;`

**严重度提示**: 多数 Nitpick;若变量名误导性更强 → 改名而非 Inline。

---

### Introduce Parameter Object

**代码味信号**: 多处函数签名带同一组参数(参数簇);参数列表 ≥ 4 个且常一起出现。

**解决方案**: 把参数簇封装成结构 / 数据类;所有调用处改为传该对象。

**Before / After**:

- Before: `fn amount_invoiced(<start>, <end>); fn amount_received(<start>, <end>); fn amount_overdue(<start>, <end>);`
- After: `fn amount_invoiced(<a_date_range>); fn amount_received(<a_date_range>); fn amount_overdue(<a_date_range>);`

**严重度提示**: 参数 ≥ 5 个 → Major;参数簇在 ≥ 3 个函数出现 → Major。

---

### Remove Dead Code

**代码味信号**: 变量 / 函数 / 类从未被调用;被注释掉的代码块(历史遗留);if 分支永远走不到。

**解决方案**: 删;若怕后悔,git history 留着。

**Before / After**:

- Before: 存在未被调用的函数 / 注释掉的代码块 / 永远走不到的 if 分支
- After: 直接删除

**严重度提示**: 多数 Minor;死代码引发理解混乱升 Major;涉及公共 API 出口慎重。

---

### Replace Algorithm

**代码味信号**: 算法实现复杂 / 难懂 / 有 bug;有更清晰的等价算法。

**解决方案**: 替换函数体为新算法;逐步替换比一次性改安全(可对比测试)。

**Before / After**:

- Before:

  ```text
  fn find_person(<people>):
    for <p> in <people>:
      if <p> == "Don" or <p> == "John" or <p> == "Kent":
        return <p>
    return ""
  ```

- After:

  ```text
  let candidates = {"Don", "John", "Kent"}
  fn find_person(<people>):
    for <p> in <people>:
      if <p> in <candidates>:
        return <p>
    return ""
  ```

**严重度提示**: 多数 Major;若有性能 / 正确性差异需要测试覆盖。

---

## 第三组:Classes & Modules

### Extract Class

**代码味信号**: 一个类承担多组不相关职责;类的字段 / 方法可拆成两个独立概念。

**解决方案**: 抽出新类,把相关字段 + 方法搬过去;原类持新类的引用。

**Before / After**:

- Before:

  ```text
  class Employee {
    name, department, manager     // 员工属性
    office_area_code, office_number  // 办公电话
  }
  ```

- After:

  ```text
  class Employee {
    name, department, manager
    office: TelephoneNumber
  }
  class TelephoneNumber {
    area_code, number
  }
  ```

**严重度提示**: 职责数量 ≥ 3 → Major;字段混搭无共同语义升 Major。

---

### Inline Class

**代码味信号**: 类不再独立承担职责(只剩 1-2 个方法);几乎不被外部引用。

**解决方案**: 把类内容搬回调用方;删除类。

**Before / After**:

- Before: `class TelephoneNumber { area_code, number }; class Employee { name, office: TelephoneNumber }`
- After: `class Employee { name, office_area_code, office_number }`(电话字段并回 Employee)

**严重度提示**: 多数 Minor;若类被广泛引用,先考虑 Move Function 而非 Inline。

---

### Move Function

**代码味信号**: 函数多数行为依赖另一个类(被调用 ≥ 2 次来自另一类);函数所在类仅剩少量行为。

**解决方案**: 把函数搬去调用最多的类;调整调用方。

**Before / After**:

- Before:

  ```text
  class Account {
    overdraft_charge(): ...  // 大量逻辑依赖 AccountType
  }
  ```

- After:

  ```text
  class AccountType {
    overdraft_charge(<days>): ...
  }
  class Account {
    overdraft_charge():
      self.type.overdraft_charge(self.days_overdrawn)
  }
  ```

**严重度提示**: 多数 Major;若跨模块搬动需小心导入依赖。

---

### Move Field

**代码味信号**: 字段被另一个类的函数频繁使用;当前类几乎不用该字段。

**解决方案**: 把字段搬到使用最多的类;封装字段访问。

**Before / After**:

- Before: `class Customer { name, discount_rate }`(discount_rate 主要被 Order 用)
- After: `class Customer { name; contract: Contract }; class Contract { discount_rate }`

**严重度提示**: 多数 Major;public 字段影响广,搬动要谨慎。

---

### Hide Delegate

**代码味信号**: 调用方代码穿透委托链(`a.b.c.field`);委托关系暴露给客户端。

**解决方案**: 在委托起点类加委托方法;封装访问路径。

**Before / After**:

- Before: 客户端 `manager = <john>.department.manager`
- After: `class Person { manager: return self.department.manager }; 客户端 manager = <john>.manager`

**严重度提示**: 多数 Minor;委托链 ≥ 3 层升 Major。

---

### Remove Middle Man

**代码味信号**: 委托类一半方法都是简单委托;委托本身没增加价值。

**解决方案**: 让调用方直接访问被委托类;删除中间方法。

**Before / After**:

- Before: `class Person { manager: return self.department.manager; department: return self._department }`
- After: `class Person { department: return self._department }`(客户端改用 `john.department.manager`)

**严重度提示**: 多数 Minor;委托类几乎无自身逻辑 → Major。

---

## 第四组:Data

### Encapsulate Variable

**代码味信号**: 模块 / 类的 public 字段被外部直接修改;变量作用域过大。

**解决方案**: 用 getter / setter(或属性访问器)封装;必要时加访问控制。

**Before / After**:

- Before:

  ```text
  let default_owner = { firstName: "Martin", lastName: "Fowler" }
  // 调用方直接 default_owner.firstName = ...
  ```

- After:

  ```text
  let default_owner_data = { firstName: "Martin", lastName: "Fowler" }
  export fn default_owner(): return { ...default_owner_data }
  export fn set_default_owner(<arg>): default_owner_data = <arg>
  ```

**严重度提示**: 多数 Minor;被外部肆意修改 → Major。

---

### Replace Primitive with Object

**代码味信号**: 基本类型(字符串 / 数字)承载业务含义但无类型保护;同含义多形式(如 `"USD"` / `"usd"` / `"$"`)散落。

**解决方案**: 引入值对象;在值对象里加格式校验 / 转换逻辑。

**Before / After**:

- Before: `orders.filter(<o> => <o>.currency == "USD")`(偶尔有 `"usd"` / `"$"` 漏过)
- After: `class Currency { code: string; equals(<other>): return this.code == <other>.code }; orders.filter(<o> => <o>.currency.equals(Currency.USD))`

**严重度提示**: 多数 Minor;跨模块 / 多源数据 → Major。

---

### Encapsulate Record

**代码味信号**: 记录(结构体 / dict)字段直接被外部读写;记录结构改动牵动所有调用方。

**解决方案**: 用类封装字段;对外暴露访问方法。

**Before / After**:

- Before:

  ```text
  let org = { name: "Acme", country: "GB" }
  // 直接读写 org.name,改 org 结构牵动所有调用方
  ```

- After:

  ```text
  class Organization {
    data = { name: "Acme", country: "GB" }
    get name(): return this.data.name
    set name(<arg>): this.data.name = <arg>
  }
  ```

**严重度提示**: 多数 Minor;广泛使用的配置记录升 Major。

---

### Replace Derived Variable with Query

**代码味信号**: 字段值可由其他字段算出;派生字段与源字段易失同步。

**解决方案**: 删字段;改成 getter 算出;必要时缓存。

**Before / After**:

- Before:

  ```text
  class Production:
    primary_production: number
    secondary_production: number
    total: number  // 派生字段,需手动同步

    apply_adjustment(<adj>):
      this.primary_production += <adj>.amount
      this.secondary_production += <adj>.amount
      this.total += <adj>.amount  // 必须同步更新
  ```

- After:

  ```text
  class Production:
    get total(): return this.primary_production + this.secondary_production

    apply_adjustment(<adj>):
      this.primary_production += <adj>.amount
      this.secondary_production += <adj>.amount
  ```

**严重度提示**: 多数 Minor;同步维护多字段易出错 → Major。

---

## 第五组:Conditional Logic

### Decompose Conditional

**代码味信号**: 复杂条件(三元嵌套 / 多个 `&&` `||` / 长 if 链);同一条件多处重复。

**解决方案**: 把每个条件 / 分支抽成具名函数。

**Before / After**:

- Before:

  ```text
  if (<date> < SUMMER_START || <date> > SUMMER_END):
    <charge> = <quantity> * winter_rate + winter_service_charge
  else:
    <charge> = <quantity> * summer_rate
  ```

- After:

  ```text
  if is_winter(<date>):
    <charge> = winter_charge(<quantity>)
  else:
    <charge> = summer_charge(<quantity>)
  ```

**严重度提示**: 多数 Major;if 嵌套 ≥ 3 层 → Major。

---

### Consolidate Conditional Expression

**代码味信号**: 一连串条件都返回同一结果(检查同样的概念);或多个独立条件用同一处理。

**解决方案**: 合并成单个条件 + 单一处理路径;提取检查为函数。

**Before / After**:

- Before: `if (<seniority> < 2): return 0; if (<months_disabled> > 12): return 0; if (is_part_time): return 0`
- After: `if is_not_eligible_for_full_benefits(): return 0`

**严重度提示**: 多数 Minor;≥ 3 个独立条件 → Major。

---

### Replace Nested Conditional with Guard Clauses

**代码味信号**: 嵌套 if 用于处理"异常 / 边界情况";正常路径在 else 深处。

**解决方案**: 反转条件,用 early return 替代嵌套。

**Before / After**:

- Before:

  ```text
  fn pay_amount(<employee>):
    if <employee>.is_separated:
      <result> = separated_amount()
    else:
      if <employee>.is_retired:
        <result> = retired_amount()
      else:
        <result> = normal_pay_amount()
    return <result>
  ```

- After:

  ```text
  fn pay_amount(<employee>):
    if <employee>.is_separated: return separated_amount()
    if <employee>.is_retired: return retired_amount()
    return normal_pay_amount()
  ```

**严重度提示**: 多数 Minor;嵌套 ≥ 3 层 → Major。

---

### Replace Conditional with Polymorphism

**代码味信号**: switch / 多分支按类型走不同逻辑;新类型需改多处 switch。

**解决方案**: 把分支逻辑搬到子类 / 实现类;原 switch 删 / 改为多态调用。

**Before / After**:

- Before: `switch <bird>.type: "European": return "Sparrow"; "African": return ...; "NorwegianBlue": return ...`
- After: 多态调用,各 bird 子类实现 `plumage()` 方法。

**严重度提示**: 多数 Major;switch ≥ 3 分支 + 跨模块升 Major。

---

### Introduce Special Case

**代码味信号**: 大量代码检查同一特殊值(null / undefined / 特定枚举);同一特殊处理逻辑重复出现。

**解决方案**: 引入特殊值对象,把检查转为多态 / 默认值;消除重复 if。

**Before / After**:

- Before: `if <customer> == "unknown": <name> = "occupant"; else: <name> = <customer>.name`
- After: `class UnknownCustomer { name = "occupant" }`(调用方不再判断)

**严重度提示**: 多数 Major;null 检查散落 ≥ 3 处升 Major。

---

## 第六组:API

### Parameterize Function

**代码味信号**: 多个函数行为几乎相同,只在某个字面量 / 参数上有差异。

**解决方案**: 把差异点提取成参数;合并函数。

**Before / After**:

- Before:

  ```text
  fn ten_percent_raise(<person>):
    <person>.salary = <person>.salary * 1.1
  fn five_percent_raise(<person>):
    <person>.salary = <person>.salary * 1.05
  ```

- After:

  ```text
  fn raise(<person>, <factor>):
    <person>.salary = <person>.salary * (1 + <factor>)
  ```

**严重度提示**: 多数 Minor;≥ 3 个近似函数 → Major。

---

### Remove Flag Argument

**代码味信号**: 函数有一个 bool / enum 参数控制分支;调用方普遍传字面量(`true` / `false`)。

**解决方案**: 拆成两个具名函数;布尔语义明确化。

**Before / After**:

- Before: `fn book_conference(<customer>, is_premium): ...`(调用方 `book_conference(c, true)` 含义不明)
- After: `fn book_conference(<customer>): ...; fn premium_book_conference(<customer>): ...`

**严重度提示**: 多数 Minor;调用 ≥ 3 处 → Major。

---

### Preserve Whole Object

**代码味信号**: 函数从对象取几个字段作参数;对象本身可整体传入。

**解决方案**: 改参数为对象;函数内按需访问字段。

**Before / After**:

- Before: `fn within_plan_temp_range(<low>, <high>): ...; // 调用方 within_plan_temp_range(<plan>.daily_temp_low, <plan>.daily_temp_high)`
- After: `fn within_plan_temp_range(<plan>): return <plan>.within_range(<plan>.daily_temp_low, <plan>.daily_temp_high)`

**严重度提示**: 多数 Minor;参数 ≥ 3 个来自同一对象升 Major。

---

### Replace Parameter with Query

**代码味信号**: 参数值可由其他参数 / 上下文算出;调用方算好后传入。

**解决方案**: 函数内自查;删参数。

**Before / After**:

- Before:

  ```text
  fn available_vacation(<an_employee>, <an_employee>.grade):
    return <an_employee>.seniority < 1 ? 0 : <an_employee>.grade * 4
  // 调用方 available_vacation(emp, emp.grade)
  ```

- After:

  ```text
  fn available_vacation(<an_employee>):
    return <an_employee>.seniority < 1 ? 0 : <an_employee>.grade * 4
  ```

**严重度提示**: 多数 Minor;若参数有显式语义(测试桩 / API 兼容)保留。

---

### Separate Query from Modifier

**代码味信号**: 函数名是 query(名词 / 描述状态)但内部有副作用(改状态);副作用调用方不知情。

**解决方案**: 拆 query + command 两个函数;query 纯查询,command 改状态。

**Before / After**:

- Before: `fn get_total_outstanding_and_send_bill(): // 算总额 // 发账单 — 副作用`
- After: `fn total_outstanding(): ... // 纯查询; fn send_bill(): ... // 副作用`

**严重度提示**: 多数 Major;涉及金融 / 通知等关键副作用升 Major / Blocker。

---

## 第七组:Inheritance

### Pull Up Method

**代码味信号**: 两个子类有相同方法体;父类可以承载该方法。

**解决方案**: 移到父类;子类继承。

**Before / After**:

- Before:

  ```text
  class Salesman(Employee):
    get name(): return self._name
  class Engineer(Employee):
    get name(): return self._name
  ```

- After:

  ```text
  class Employee:
    get name(): return self._name
  // Salesman / Engineer 继承即可
  ```

**严重度提示**: 多数 Major;≥ 3 个子类重复 → Major。

---

### Push Down Method

**代码味信号**: 父类方法只被一个子类使用;其它子类不需要。

**解决方案**: 移到对应子类;父类删。

**Before / After**:

- Before: `class Employee { quota(): ... }; class Salesman(Employee); class Engineer(Employee) // 不需要 quota`
- After: `class Salesman(Employee) { quota(): ... }`(quota 移下来)

**严重度提示**: 多数 Minor。

---

### Pull Up Constructor Body

**代码味信号**: 子类构造函数有共同初始化逻辑;父类构造函数可承载。

**解决方案**: 父类构造函数加公共部分;子类构造函数 `super()` 后做特化。

**Before / After**:

- Before:

  ```text
  class Party:
    name
  class Employee(Party):
    constructor(<name>, <id>):
      super()
      self._id = <id>
      self._name = <name>
  class Department(Party):
    constructor(<name>, <staff>):
      super()
      self._name = <name>
      self._staff = <staff>
  ```

- After:

  ```text
  class Party:
    constructor(<name>): self._name = <name>
  // 子类:
  //   constructor(<name>, <spec>): super(<name>); self._<spec> = <spec>
  ```

**严重度提示**: 多数 Major;≥ 2 个子类有共同初始化 → Major。

---

## 维护说明

**新增场景**: 在对应分组末尾追加卡片,保持 5 段 schema 完整;TOC 加链接;不改 SSOT 措辞(改卡片不改 SKILL.md)。

**TOC 维护**: TOC 锚点按卡片标题生成(GitHub 风格:小写 + 去标点 + 空格转 `-`),全角标点 `:` / `、` / `(` / `)` 删除。

**边界**: 本 catalog 是"语言中立骨架";具体语言(typing Protocol / Go error wrapping / TS strict null 等)
放到 `references/languages/{lang}.md`,不混进 catalog。
