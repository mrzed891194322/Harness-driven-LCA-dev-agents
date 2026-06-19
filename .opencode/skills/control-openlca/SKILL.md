---
name: control-openlca
description: 通过 IPC Server 连接并控制本地运行中的 openLCA，对其指定的产品系统进行计算，并检索其 LCIA 影响评估结果。
---

# 控制 openLCA (control-openlca)

此技能允许通过 Python 客户端连接到运行中的 openLCA IPC Server，触发指定产品系统（Product System）的计算，并获取其影响评估（LCIA）结果。

## 适用场景

当需要自动运行 openLCA 计算、基于特定产品系统和 LCIA 方法获取环境指标，或需要将 openLCA 计算结果导出到 JSON/CSV 等格式以用于后续的分析或评估时使用。

## 前提条件

1. **已安装 `olca-ipc` 库**：确保该库已作为项目依赖配置在 `pyproject.toml` 中，且在虚拟环境中完成安装。
2. **运行 openLCA 并开启 IPC Server**：
   - 启动 openLCA 桌面应用程序。
   - 在菜单中选择 `Tools` -> `Developer Tools` -> `IPC Server`。
   - 启动 IPC Server（默认监听本地的 `8080` 端口）。

## 执行方式

运行技能包含的 Python 脚本，并传入相应参数。主要支持对特定产品系统及其关联的 LCIA 方法进行计算：

```bash
uv run python .opencode/skills/control-openlca/assets/control_openlca.py "产品系统名称或UUID" --method "LCIA方法名称或UUID" [可选参数]
```

### 可用参数

- `system` (位置参数): 目标产品系统（Product System）的名称或 UUID。
- `--method`, `-m`: （可选）生命周期影响评估方法（LCIA Method）的名称或 UUID。
- `--port`, `-p`: IPC 服务端口号，默认值为 `8080`。
- `--host`, `-H`: IPC 服务主机地址，默认值为 `localhost`。
- `--amount`, `-a`: 计算所需的功能单位数量，默认值为 `1.0`。
- `--output`, `-o`: 将结果导出为 CSV 或 JSON 格式的输出文件路径（例如 `output/lcia_results.csv`）。

### 运行示例

在 openLCA 打开了 IPC Server（8080 端口）时，运行：

```bash
uv run python .opencode/skills/control-openlca/assets/control_openlca.py "Product System A" --method "EF 3.1" --output output/results.json
```
