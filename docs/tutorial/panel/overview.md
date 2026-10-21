# 控制面板总览

启动：

```bash
npm start          # 或 node src/scripts/start.mjs
```

Linux、macOS 或原生 Windows（Windows 需安装 [Git for Windows](https://git-scm.com/download/win)）。启动前会同步 uv 与 Node.js 依赖，并在缺少 `.env` 时从模板复制。停止用 `npm run stop`，重启用 `npm run restart`。

浏览器打开前端端口（默认 `http://127.0.0.1:3000`）。顶栏提供「教程」和「模型设置」（Provider、API Key、自定义端点）。

左侧主导航：

| 页面 | 作用 |
| --- | --- |
| 项目状态 | 环境检查（Node / Pi SDK、Python、openLCA）与可用模型 |
| LCA 计划 | 「新工作」写 `main_plan.md`，「修改工作」写 `revise_plan.md`；上传参考资料；「去运行」跳到运行页 |
| 运行详情 | 选工作流（full-lca / revise-lca）和模型，开始、停止、继续；节点表显示每个节点的状态、轮次和错误 |
| 结果浏览 | 最终交付、中间产物、工作记录（每个节点每一轮的提交与审核结论）；修订运行另有「上一版」 |

一次运行由若干节点组成（full-lca：intake → bom → mapping → report）。每个节点由执行者产出、审核者给出
通过或退回；退回会带着反馈进入下一轮。停止后可「继续」，已通过的节点不会重跑。
