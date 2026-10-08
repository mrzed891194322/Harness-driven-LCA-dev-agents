# `src/` 布局

```
src/
  frontend/                 # 浏览器与已拆分的旧 GUI
    web/                    # Next.js 控制面板
    legacy/gui/             # 原 Gradio GUI（仅遗留参考，不参与运行）
  backend/                  # Python 编排 + FastAPI + Pi SDK runtime
    api/                    # FastAPI
    pi-runtime/             # Node Pi SDK（NDJSON）
    core/                   # workflow / agents / runtime
    services/               # 应用服务
    scripts/                # 薄 CLI
    config/                 # 模型档案等非敏感配置
    contracts/              # 跨语言 JSON schema
    utils/
  tests/                    # 回归测试
```

## 常用命令

```bash
# 后端 API
uv run uvicorn api.app:app --app-dir src/backend --host 127.0.0.1 --port 8000

# 主编排（无浏览器）
uv run python src/backend/scripts/workflow.py --workflow harness/LCA-main.yaml

# 前端 + API
pnpm dev
```

跨语言契约：`backend/contracts/session_launch_spec.schema.json`；Python 类型在 `backend/core/contracts/`。
