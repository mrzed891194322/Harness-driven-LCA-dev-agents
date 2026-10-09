# Frontend

- **`web/`**：Next.js 控制面板（设置、计划、运行状态、结果）。开发：`npm run dev -w @harness/web`。

浏览器经 Next 代理访问 **`src/backend`** 的 FastAPI（默认 `127.0.0.1:8800`，由根目录 `.env` 的 `GUI_API_PORT` 决定）。Python 编排与执行逻辑不在此目录，统一在 backend / pi-runtime / scripts。一起启动前后端用仓库根目录的 `npm run dev`。
