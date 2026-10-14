---
name: code-dev
description: >-
  在本仓库里改控制面板、启动流程、编排器、进度日志或结果展示，并把同一次运行的上下游接上。
  用户要修 GUI、启动、进度、结果页，或让某一跳走通时使用。
---

# 开发

用户不通过 IDE 当主编排。改动落在下面这条闭环的哪一跳，就只补那一跳，不要另起一套运行路径。

```
GUI 里的计划、资料、工作流
        │  POST /api/workflow/start
        ▼
FastAPI（src/backend）保存计划、清理上一次运行、拉起编排器
        │  uv run python src/scripts/workflow.py
        ▼
Python 编排器（src/backend/core/workflow）按 harness YAML 逐阶段派工
        │  NDJSON over .local/run/pi-runtime.sock
        ▼
Pi SDK（src/pi-runtime，createAgentSession）
        │  progress.txt + manifest.json
        ▼
GUI「运行详情」流式渲染；「结果浏览」展示 workspace 里的产物与记录
```

改 GUI、启动、编排或展示时，用同一次运行把上下游对上，不要只改其中一层的内部格式。业务入口只在 `src/backend/api/app.py`。编排逻辑在 `src/backend/core`，api 与 services 只做适配，子进程入口是 `src/scripts/workflow.py`。不要在 Next.js 里直接调 Pi，也不要再加一套启动脚本。

按这次要补的内容只打开一份参考：

| 要补的内容 | 再读 |
| --- | --- |
| 不知道改哪些文件 | [references/locate.md](references/locate.md) |
| 已接通行为不能被改断 | [references/wired.md](references/wired.md) |
| 用户要「走通」尚未接通的缺口 | [references/gaps.md](references/gaps.md) |
| 查某次运行里 agent 实际收到了什么、做了什么 | [references/debug.md](references/debug.md) |
| 改动约束，或改完怎么验 | [references/constraints.md](references/constraints.md) |

开始改代码前读约束。改完再按约束里的验证做。产物地图见 `docs/ARTIFACTS.md`，改了产物就同步更新。
