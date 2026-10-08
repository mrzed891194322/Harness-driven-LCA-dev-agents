# `src/` 布局

```
src/
  frontend/                 # 浏览器与已拆分的旧 GUI
    web/                    # Next.js 控制面板
    legacy/gui/             # 原 Gradio GUI（仅遗留参考，不参与运行）
  backend/                  # 仅 FastAPI（api/）
  pi-runtime/               # Node Pi SDK（NDJSON）
  pi_runtime/               # Python Pi runtime 客户端
  core/                     # workflow / agents / runtime
  cli/                      # 薄 CLI（workflow、clean、proj_init）
  services/                 # API 与 CLI 共用应用服务
  config/                   # 模型档案等非敏感配置
  contracts/                # 跨语言 JSON schema
  utils/
  diagnostics.py            # 环境探测（CLI / API 共用）
  scripts/                  # 仓库级开发脚本（如 dev.mjs）
  tests/                    # 回归测试
```

## 常用命令

```bash
# 后端 API
uv run uvicorn api.app:app --app-dir src/backend --host 127.0.0.1 --port 8000

# 主编排（无浏览器）
uv run python src/cli/workflow.py --workflow harness/LCA-main.yaml

# 前端 + API
pnpm dev
```

跨语言契约：`src/contracts/session_launch_spec.schema.json`；Python 类型在 `src/core/contracts/`。
