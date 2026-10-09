# 控制面板总览

启动：

```bash
npm start          # 或 node src/scripts/start.mjs
```

Linux / macOS（Windows 请用 WSL）。启动前会同步 uv 与 Node.js 依赖，并在缺少 `.env` 时从模板复制。停止用 `npm run stop`，重启用 `npm run restart`。

浏览器打开前端端口（默认 `http://127.0.0.1:3000`）。顶栏提供：

- **教程**：本文档
- **Harness**：只读浏览 harness 规则与规格
- **设置**：模型、凭证与环境诊断

左侧主导航：

| 页面 | 作用 |
| --- | --- |
| 项目状态 | 环境与就绪检查 |
| LCA 计划 | 编写 / 保存计划 |
| 运行详情 | 查看运行 manifest |
| 结果与历史 | 查看评估结果 |
