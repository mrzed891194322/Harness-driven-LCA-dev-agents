# 运行测试

本目录包含 `src/GUI` 与相关脚本的回归测试，按模块拆分：

| 文件 | 覆盖范围 |
| --- | --- |
| `test_gui.py` | GUI 构建、四个共享 Markdown 文档视图及其事件 |
| `test_plan_editor.py` | Markdown 文档解析、metadata 兼容、目录与序列化 |
| `test_initialization.py` | 项目初始化与就绪检查 |
| `test_clean_dir.py` | `clean_dir` 清理目标 |
| `test_lca_result.py` | LCA 结果解析 |

从仓库根目录运行全部测试：

```bash
uv run python -m unittest discover -s src/test -v
```

按模块运行示例：

```bash
uv run python -m unittest discover -s src/test -p 'test_clean_dir.py' -v
uv run python -m unittest discover -s src/test -p 'test_gui.py' -v
```

修改 GUI 或相关脚本后必须重新运行上述命令。测试使用只读源码检查和 Gradio
界面构建冒烟检查，不会读取或改写真实 `workspace` 运行产物。
