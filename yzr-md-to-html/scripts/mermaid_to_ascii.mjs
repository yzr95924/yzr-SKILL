#!/usr/bin/env node
// Mermaid 源码 → ASCII 图转换 wrapper（供 md_to_html.py subprocess 调用）。
//
// 用法：echo '<mermaid 源码>' | node scripts/mermaid_to_ascii.mjs
// 成功：ASCII 图写 stdout，退出码 0。
// 失败（不支持的图类型 / 语法错误 / 缺依赖）：原因写 stderr，退出码非 0。
//
// 依赖缺失时打印安装命令后退出（与 md_to_html.py 的 ensure_deps 同一模式，
// 不自动安装）。

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const SKILL_ROOT = fileURLToPath(new URL('..', import.meta.url));
// 版本号单一来源（SKILL.md 前置条件引用此常量）
const BEAUTIFUL_MERMAID_VERSION = '^1.1.3';

let renderMermaidASCII;
try {
  ({ renderMermaidASCII } = await import('beautiful-mermaid'));
} catch (err) {
  console.error(
    `缺少依赖 beautiful-mermaid（${err.code || err.message}），请先安装:\n    npm install beautiful-mermaid@${BEAUTIFUL_MERMAID_VERSION} --prefix ${SKILL_ROOT}`
  );
  process.exit(2);
}

const source = readFileSync(0, 'utf8');
if (!source.trim()) {
  console.error('输入为空（stdin 没有 mermaid 源码）');
  process.exit(3);
}

try {
  // colorMode none：HTML 里不需要 ANSI 颜色码
  const ascii = renderMermaidASCII(source, { colorMode: 'none' });
  process.stdout.write(ascii.endsWith('\n') ? ascii : ascii + '\n');
} catch (err) {
  console.error(`Mermaid 转 ASCII 失败: ${err.message}`);
  process.exit(1);
}
