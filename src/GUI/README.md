# LCA Agent GUI

本目录是项目 Gradio 控制面板的源码目录。GUI 的正确位置是
`src/GUI/`，不要再使用仓库根目录下的 `GUI/` 路径。

## 目录结构

- `main.py`：GUI 启动入口。
- `config.py`：仓库根目录、工作目录和脚本路径的统一配置。
- `ui/`：Gradio 组件、事件绑定和静态资源。
- `functions/`：项目初始化、文件处理、进程管理等后端逻辑。
- `log/`：GUI 运行时日志目录。

## 启动

在仓库根目录运行：

```bash
uv run python src/GUI/main.py
```

Windows 用户也可以运行 `src/scripts/_launch_gui.bat`。启动后访问
<http://127.0.0.1:7860>。

## 当前功能边界

项目初始化、参考资料上传、RAG 构建、环境检查、openLCA 连接检查和终端日志控制仍由 GUI 处理。

计划制定、计划修改以及 LCI 制定的后端按钮功能已经从当前工作流移除。对应组件代码暂时保留，但侧栏和面板内按钮均为禁用状态，不应重新绑定已删除的执行入口。已有 LCI 映射报告仅保留只读展示。

## 开发约定

- 外部路径必须通过 `config.py` 配置；当前脚本路径位于 `src/scripts/`。
- 用户上传文件先写入 `workspace/inputs/references/{file,data}`，初始化时再同步到 RAG 输入目录。
- 修改 GUI 代码后，必须从仓库根目录运行 GUI 测试：

  ```bash
  uv run python -m unittest discover -s src/test -v
  ```

- 提交前同时运行 `git diff --check`。测试不得修改真实 `workspace` 运行产物。
