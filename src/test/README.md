# 运行测试

本目录包含 `src/GUI` 与相关脚本的回归测试，按模块拆分：

| 文件 | 覆盖范围 |
| --- | --- |
| `test_gui.py` | 关键路径存在，以及 `build_ui()` 能构建 Gradio Blocks |
| `test_gui_settings.py` | GUI Agent/RAG 设置回写与工作流 CLI 分发 |
| `test_plan_editor.py` | Markdown 文档解析、metadata 兼容、目录与序列化 |
| `test_initialization.py` | 项目初始化与就绪检查 |
| `test_clean_dir.py` | `clean_dir` 清理目标 |
| `test_lca_result.py` | LCA 结果解析 |
| `test_revise_lca.py` | revise-lca 基线快照与激活 |

从仓库根目录运行全部测试：

```bash
uv run python -m unittest discover -s src/test -v
```

按模块运行示例：

```bash
uv run python -m unittest discover -s src/test -p 'test_clean_dir.py' -v
uv run python -m unittest discover -s src/test -p 'test_gui.py' -v
```

修改 GUI 或相关脚本后必须重新运行上述命令。GUI 测试只做路径与界面构建冒烟；
计划解析、manifest 结果和清理/修订写盘逻辑由其余模块覆盖。测试使用只读源码
检查、临时目录和 Gradio 界面构建冒烟检查，不会读取或改写真实 `workspace`
运行产物。
