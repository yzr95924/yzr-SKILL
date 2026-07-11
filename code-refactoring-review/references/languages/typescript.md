# TypeScript 语言插件

## 元信息

- 静态类型(可选)+ 编译期检查
- 主流 lint 工具: eslint / tsc / biome / depcheck / madge
- 风格基础: prettier + Airbnb / Standard / Google 任选
- 运行时: Node.js / Browser / Deno / Bun

## 工具映射表

| 工具 | 检测项 | 安装 | 跑法 |
| --- | --- | --- | --- |
| eslint | 风格 / 潜在 bug / 复杂度 | `npm install -D eslint` | `eslint <path>` |
| tsc | 类型检查 | `npm install -D typescript` | `tsc --noEmit` |
| biome | 聚合(fast rust-based) | `npm install -D @biomejs/biome` | `biome check <path>` |
| depcheck | 未使用的依赖 | `npm install -g depcheck` | `depcheck <path>` |
| madge | 循环依赖 | `npm install -g madge` | `madge --circular <path>` |
| ts-prune | 未使用的导出 | `npm install -g ts-prune` | `ts-prune` |

不在 PATH → 静默跳过,记到报告脚注。

## TypeScript 特定调优

- **strict mode**: tsconfig 开 `strict: true`,从源头减少 null/undefined 错误
- **any vs unknown**: 输入边界用 `unknown` + 校验;`any` 仅在迁移期用
- **type vs interface**: 对象形状用 `interface`(可扩展);联合 / 计算类型用 `type`
- **null vs undefined**: 默认用 `undefined`(API 边界除外);`strictNullChecks` 开启
- **Promise 链**: 简单链用 `.then()`;复杂并行 / 取消用 `Promise.all` / `AbortController`
- **enum 慎用**: 优先 `as const` 对象;`enum` 有运行时开销和兼容问题

## 典型 TypeScript 代码味补充

(catalog 之外)

- **type assertion 滥用**: `as` 强制转换绕过类型检查;能改类型就别 `as`
- **可选链滥用**: `?.` 层层穿透掩盖真实 null 路径;根因可能在数据契约
- **any leak**: 函数返回 `any`,整个调用链失去类型保护
- **default export 滥用**: 命名 export 更利于 IDE 跳转和重命名
- **JSX 中过度内联**: 长 JSX 直接写在 component body;抽出子组件
- **useEffect 滥用**: 不必要的 useEffect(派生状态 / 事件订阅);用 useMemo / 直接计算
- **类型导入未独立**: `import { Foo }` 与 `import type { Foo }` 混用;统一 type-only import
