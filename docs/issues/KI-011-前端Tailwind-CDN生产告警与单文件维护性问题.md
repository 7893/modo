# KI-011 · 前端Tailwind CDN生产告警与单文件维护性问题

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-23
- 适用范围：`edge-app/src/index.html`
- 关联：[已知问题看板](../KNOWN-ISSUES.md)

---

## 结论

在 [`edge-app/src/index.html`](../../edge-app/src/index.html) 中，前端曾直接使用 `<script src="https://cdn.tailwindcss.com"></script>` 运行时解析引擎，导致浏览器控制台每次加载均弹出生产禁用警告，并带来首屏渲染阻塞与样式闪烁风险（FOUC）。此外，原单文件接近 2000 行，HTML 结构、ECharts 配置、Supabase Realtime 监听和 CSS 动画紧密耦合，缺乏现代前端工程化拆分与重绘防抖机制。

---

## 只读证据（2026-09-23）

### 1. 生产环境引入开发模式 JIT 脚本
在 [`edge-app/src/index.html#L10`](../../edge-app/src/index.html#L10) 中：
```html
<script src="https://cdn.tailwindcss.com"></script>
```
Tailwind CSS 官方文档明确指出：
`cdn.tailwindcss.com should not be used in production`。每次访问该页面，控制台均会输出黄色警告日志。

### 2. 2000 行单文件无组件拆分与 Resize 节流
在 [`edge-app/src/index.html`](../../edge-app/src/index.html) 中，整套单页应用全部挤在单一 HTML 文件中：
- 缺乏编译打包流程（如 Vite / Tailwind CLI），无法提取最小化 CSS，增大了首屏体积；
- 包含多个 ECharts 实例的图表渲染，但在窗口尺寸变化时直接响应 `resize`，未配置 `debounce` 节流，在用户缩放浏览器或移动端旋转时容易发生严重掉帧。

---

## 影响分析

1. **工程专业性与开源观感**：控制台明显的官方警告削弱了项目的成熟度形象。
2. **性能与弱网体验**：浏览器必须在运行时下载并执行数十 KB 的 Tailwind 编译器来即时生成 CSS，延迟了首屏内容渲染（LCP 指标劣化）。
3. **协作困难**：单文件超过 2000 行使得多人协作时容易出现复杂的 Git 冲突。

---

## 治理目标与方案

1. **样式静态化构建**：
   - 引入静态构建工具链（如配置 `tailwindcss -i input.css -o dist.css --minify`），生成轻量化静态 CSS。
2. **图表 Resize 节流**：
   - 为各 ECharts 实例封装通用的 `debounce(chart.resize, 200)` 工具函数。
3. **结构组件化（可选）**：
   - 将各个 Curtain（帷幕）或图表配置抽象为独立 JS/TS 模块。

---

## 本地修复进展（本地验证通过）

页面已移除 Play CDN 及失效的浏览器端 `tailwind.config`，改由 Tailwind CLI 生成静态 CSS 并作为 Worker 文本模块注入。CI、开发和部署脚本会先生成 CSS。窗口与 `ResizeObserver` 共用 200ms debounce。

原始单页已进一步拆成页面壳、6 个 Curtain 片段、鉴权弹窗片段和 4 个浏览器逻辑模块，均控制在 400 行以内；Worker 在响应页面时把这些文本模块组装回单一 HTML 文档。Tailwind 构建、TypeScript 检查、Wrangler dry-run 和本地 Worker 根页面烟测均已通过，页面返回 200 且无未替换模板占位符。

## 完成定义

- [x] 移除 `cdn.tailwindcss.com` 动态编译器并接入静态 CSS 构建
- [x] 窗口 resize 与 ResizeObserver 增加 debounce 节流保护
- [x] 页面结构和浏览器逻辑按职责拆分，单文件不超过 400 行
- [x] 同步更新本文档状态为 DONE，更新日期变更为完成当天
- [x] 同步更新 `docs/KNOWN-ISSUES.md` 看板条目为 DONE
