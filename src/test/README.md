# 运行测试

本目录包含 `src/GUI` 与相关脚本的回归测试。

从仓库根目录运行全部测试：

```bash
uv run python -m unittest discover -s src/test -v
```

修改 GUI 代码后必须重新运行上述命令。测试使用只读源码检查和 Gradio
界面构建冒烟检查，不会读取或改写真实 `workspace` 运行产物。
