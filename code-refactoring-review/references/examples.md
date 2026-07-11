<!-- markdownlint-disable MD024 MD025 MD060 -->

# 完整样例

## 样例 1:Python 函数 review

**输入**:

> 帮我 review 一下 src/parser.py(80 行 Python 解析器)

**输入文件**(节选):

```python
def parse_order(data):
    lines = data.split('\n')
    customer = lines[0]
    items = []
    total = 0
    for line in lines[1:]:
        if line == '':
            continue
        parts = line.split(',')
        qty = int(parts[1])
        price = float(parts[2])
        if qty > 100:
            price = price * 0.9  # bulk discount
        sub = qty * price
        total = total + sub
        items.append({'name': parts[0], 'qty': qty, 'price': price})
    if total > 1000:
        total = total * 0.95  # VIP discount
    print(f"Customer: {customer}")
    print(f"Total: {total}")
    return {'customer': customer, 'items': items, 'total': total}
```

**输出报告**:

# Code Refactoring Review Report

**输入**: src/parser.py(80 行)
**语言**: Python
**静态工具**: ruff 跑了(命中 1),mypy 跑了(命中 0)
**Review 时间**: 2026-07-11

## 发现项

| # | 位置 | 重构场景 | 严重度 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | parse_order:1 | Extract Method | Major | 抽 `parse_lines()`(按行解析);`calc_total()`(算总额) |
| 2 | parse_order:14 | Replace Magic Literal | Minor | `0.9` / `100` / `0.95` / `1000` 改成具名常量 `BULK_THRESHOLD` / `BULK_DISCOUNT` / `VIP_THRESHOLD` / `VIP_DISCOUNT` |
| 3 | parse_order:18 | Replace Magic Literal | Minor | 同上,VIP 相关常量 |
| 4 | parse_order:21 | Extract Function | Major | `print_summary()` 抽出来 |
| 5 | parse_order:6 | Introduce Parameter Object | Major | `(qty, price)` 重复 4 处,改 dataclass `LineItem` |

## 总结

- **总发现项**: 5
- **按严重度分布**: Blocker 0 / Major 3 / Minor 2 / Nitpick 0
- **优先 top-3**:
  1. Extract Method(parse_order 函数 28 行,职责过重: 解析 + 计算 + 打印)— Major
  2. Introduce Parameter Object(`(qty, price)` 重复 4 处,改 dataclass 后续扩展更稳)— Major
  3. Replace Magic Literal(4 个魔数散布,业务语义丢失)— Minor × 2 合并报
- **风险点**: 当前函数无单元测试覆盖;重构前建议补 parse / calc / print 三段独立测试

## 工具运行记录

| 工具 | 状态 | 命中项数 | 备注 |
| --- | --- | --- | --- |
| ruff | 跑了 | 1 | unused variable 警告 |
| mypy | 跑了 | 0 | 类型注解齐全 |

## 不报告项

- 扫描了 src/parser.py 单文件,共 28 行有效代码
- 命名整体清晰,无 rename 类发现
- 不报告 ruff 警告风格细节(已并入 ruff 命中)

---

## 样例 2:Go 文件 review(节选)

**输入**:

> review 一下 internal/handler/order.go

**输入文件**(节选):

```go
func (h *Handler) ProcessOrder(w http.ResponseWriter, r *http.Request) {
    var req OrderRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "bad request", 400)
        return
    }
    var total float64
    for _, item := range req.Items {
        if item.Qty <= 0 {
            continue
        }
        price := item.Price
        if item.Qty > 100 {
            price = price * 0.9
        }
        total = total + price*float64(item.Qty)
    }
    if total > 1000 {
        total = total * 0.95
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(OrderResponse{Customer: req.Customer, Total: total})
}
```

**输出报告**:

# Code Refactoring Review Report

**输入**: internal/handler/order.go(50 行,ProcessOrder 函数)
**语言**: Golang
**静态工具**: golangci-lint 跑了(命中 2),go vet 跑了(命中 0)
**Review 时间**: 2026-07-11

## 发现项

| # | 位置 | 重构场景 | 严重度 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | handler.go:ProcessOrder | Extract Method | Major | 抽 `decodeOrder()` / `calcTotal()` / `applyDiscount()` / `writeResponse()` |
| 2 | handler.go:14 | Replace Magic Literal | Minor | `100` / `0.9` / `1000` / `0.95` 改成 const + 业务命名 |
| 3 | handler.go:8 | Extract Function | Major | 错误处理 `http.Error(w, "bad request", 400)` 抽 `writeError()` |

## 总结

- **总发现项**: 3
- **按严重度分布**: Blocker 0 / Major 2 / Minor 1 / Nitpick 0
- **优先 top-3**:
  1. ProcessOrder 函数过长(> 20 行) + 多职责 → Major(必抽)
  2. 错误处理 inline → Major(抽出便于统一改格式 / 加 trace)
  3. 魔数 4 处散布 → Minor(改 const 集中)
- **风险点**: HTTP handler 是入口路径,重构需保留 status code 一致

## 工具运行记录

| 工具 | 状态 | 命中项数 | 备注 |
| --- | --- | --- | --- |
| golangci-lint | 跑了 | 2 | errcheck / ineffassign |
| go vet | 跑了 | 0 | - |

## 不报告项

- 不报告 errcheck / ineffassign 细节(已在工具记录中)
- handler.go 其余函数短小,无重大发现
