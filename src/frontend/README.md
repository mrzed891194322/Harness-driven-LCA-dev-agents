# Frontend

- **`web/`**：Next.js 应用（设置、计划、运行状态、结果入口）。开发：`pnpm --filter @harness/web dev`。
- **`legacy/gui/`**：已下线的 Gradio GUI 源码，仅作拆分参考；运行时不依赖此目录。

浏览器请求经 Next 同源代理到 `src/backend` 的 FastAPI（默认 `127.0.0.1:8000`）。
