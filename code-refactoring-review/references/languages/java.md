# Java 语言插件

## 元信息

- 静态类型 + 编译期检查
- 主流 lint 工具: spotbugs / pmd / checkstyle / sonarqube / error-prone
- 风格基础: Google Java Style / Oracle Code Conventions
- 运行时: JVM(8+)

## 工具映射表

| 工具 | 检测项 | 安装 | 跑法 |
| --- | --- | --- | --- |
| spotbugs | 静态 bug 模式 | Maven/Gradle 插件 | `mvn spotbugs:check` |
| pmd | 代码质量(重复 / 复杂度 / 命名) | Maven/Gradle 插件 | `mvn pmd:check` |
| checkstyle | 风格检查 | Maven/Gradle 插件 | `mvn checkstyle:check` |
| sonarqube | 聚合(深度分析) | SonarQube 服务 | 通过 sonar-scanner 跑 |
| error-prone | 编译期 bug 模式 | Maven/Gradle 插件 | `mvn compile` |
| cpd | 复制粘贴检测(PMD 子工具) | Maven 插件 | `mvn pmd:cpd-check` |

不在 PATH → 静默跳过,记到报告脚注。

## Java 特定调优

- **Stream API vs for 循环**: 简单转换用 Stream;复杂分支用 for(可读性优先)
- **Optional 用法**: 返回值用 `Optional<T>` 表达可能为空;不要 Optional 作字段 / 参数
- **异常处理**: checked exception 仅在调用方必须恢复时使用;优先 unchecked
- **不可变对象**: 优先 `record` / 不可变类;减少共享状态
- **泛型通配符**: PECS 原则(生产者 `extends`,消费者 `super`);避免 raw type
- **equals / hashCode**: 一起重写;用 `Objects.equals` / `Objects.hash`

## 典型 Java 代码味补充

(catalog 之外)

- **原始类型 vs 包装类型**: 不要混用 `int` 和 `Integer`;默认包装类型(集合 / 泛型)
- **NPE 路径**: 多层 `getX().getY().getZ()`;改 Optional / 早判空
- **try-catch 吞异常**: `catch (Exception e) {}` 不留处理;至少打 log
- **魔法数字**: `1000` / `0.95` 等直接出现;改 `public static final double DISCOUNT = 0.95`
- **可变 static field**: static 字段被多处修改;改用 instance field + DI
- **深继承**: 继承链 > 3 层难维护;考虑组合
- **god service**: 一个 Service 几百行 + 几十方法;按职责拆
