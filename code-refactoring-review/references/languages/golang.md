# Golang 语言插件

## 元信息

- 静态类型 + 编译期检查
- 主流 lint 工具: golangci-lint / go vet / staticcheck / gosec / deadcode
- 风格基础: gofmt / Effective Go
- 运行时: 标准库 + goroutine 调度

## 工具映射表

| 工具 | 检测项 | 安装 | 跑法 |
| --- | --- | --- | --- |
| golangci-lint | 聚合(多种 linter) | `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest` | `golangci-lint run <path>` |
| go vet | 标准静态检查 | (内置) | `go vet <path>` |
| staticcheck | 高级静态检查 | `go install honnef.co/go/tools/cmd/staticcheck@latest` | `staticcheck <path>` |
| gosec | 安全漏洞 | `go install github.com/securego/gosec/v2/cmd/gosec@latest` | `gosec <path>` |
| deadcode | 死代码 | `go install github.com/tsenart/deadcode@latest` | `deadcode <path>` |
| gocyclo | 圈复杂度 | `go install github.com/fzipp/gocyclo/cmd/gocyclo@latest` | `gocyclo -top 10 <path>` |

不在 PATH → 静默跳过,记到报告脚注。

## Golang 特定调优

- **error wrapping**: 错误传递用 `fmt.Errorf("...: %w", err)`,不要丢上下文
- **panic vs error**: 库代码不要 panic;只在 main / 初始化阶段用
- **goroutine 泄漏**: goroutine 启动要确保有退出路径;用 context 取消
- **channel 用法**: send-only / receive-only channel 显式标注方向
- **interface 隔离**: 接受 interface,返回 struct;避免无意义接口抽象
- **pointer vs value receiver**: 内部一致性,不要混用

## 典型 Golang 代码味补充

(catalog 之外)

- **不必要的 nil 检查**: `if x != nil { x.Foo() }` 通常是过度防御
- **interface{} 滥用**: 能用具体类型就不用 `any`;json 序列化场景除外
- **init() 函数滥用**: init 副作用难追踪;改用显式初始化函数
- **defer 滥用**: defer 在循环里累积;长循环里手动释放
- **裸 return**: 多返回值函数里 `return` 不带命名,降低可读性
- **package 命名过长**: 包名短而清晰;URL / util / helper 都不是好名字
- **god struct**: 一个 struct 承担多种角色(类似 god object);按职责拆
