# 过程直接计算脚本使用指南 (calculate_process_direct)

本脚本专门用于直接对 openLCA 中的某个**过程 (Process)** 执行直接计算（Direct Calculation）。

在 openLCA 中，这会在内存中自动、动态地构建一个包含该过程及其整个供应链上游所有关联过程的临时产品系统，并直接计算其环境影响（LCIA）结果。这对于大型数据库（如 ecoinvent, PSILCA, GaBi 等）非常有效率，避免了预先手动创建产品系统对内存的巨大消耗。

> **[!NOTE]**
> 要想通过 Direct Calculation 获得准确的结果，数据库中该过程的所有上游投入（Inputs）都应当具有唯一确定的提供者（Default Provider）。

## 目录结构与模块说明

本目录采用高度模块化的包结构设计，具体文件及职责划分如下：

*   **`main.py`**：计算主脚本，负责命令行参数解析与整个计算流程控制。
*   **`README.md`**：本说明文档（包含目录结构与使用方法说明）。
*   **`private_utils/`**：仅当前脚本使用的私有工具包。
    *   **`__init__.py`**：初始化标识文件。
    *   **`calculation.py`**：包含仅针对过程直接计算日志和设置的 `run_calculation` 函数。
    *   **`cli.py`**：专属命令行参数解析定义。
*   **`assets/utils/` (共享模块)**：存放多个脚本共用的工具函数包，位于上一级资产目录下。
    *   **`connection.py`**：负责建立与 openLCA IPC Server 的 HTTP 连接并测试可用性。
    *   **`entity.py`**：实现通用实体查找逻辑（`find_entity`）。
    *   **`export.py`**：负责 LCIA 计算结果的格式化提取、控制台 Markdown 打印与 CSV/JSON 文件导出。
    *   **`validation.py`**：负责处理分配方案与参数覆盖输入的预校验（Fail-Fast 逻辑）。

## 运行命令

```bash
uv run python .opencode/skills/control-openlca/assets/calculate_process_direct/main.py "过程名称或UUID" --method "LCIA方法名称或UUID" [可选参数]
```

## 参数说明

### 位置参数
* `process`: openLCA 中目标过程（Process）的名称或 UUID。

### 选项参数
* `--method`, `-m`: （可选）生命周期影响评估方法（LCIA Method）的名称或 UUID。
* `--amount`, `-a`: 计算所需的功能单位数量。默认为 `1.0`。
* `--allocation`, `-al`: 指定计算时使用的分配方法。支持：
  * `physical`: 物理分配 (Physical)
  * `economic`: 经济分配 (Economic)
  * `causal`: 因果分配 (Causal)
  * `none`: 不进行分配 (None)
  * `default`: 使用数据库默认分配设置 (Default)
* `--regionalized`, `-r`: 启用区域化计算（布尔标记）。
* `--costs`, `-c`: 启用成本计算（布尔标记）。
* `--parameter`, `-param`: 重定义模型内的参数值，格式为 `参数名=数值`。支持多次指定。例如：
  `-param ratio=0.55`。
* `--output`, `-o`: 将计算结果以表格格式导出到文件。支持 `.json` 或 `.csv` 后缀。
* `--host`, `-H`: openLCA IPC Server 的主机地址。默认为 `127.0.0.1`。
* `--port`, `-p`: openLCA IPC Server 的端口号。默认为 `8080`。

## 运行示例

### 1. 基础过程直接计算
对名为 "Process B" 的过程直接执行生命周期评估，并使用 "EF 3.1" 影响评估方法：
```bash
uv run python .opencode/skills/control-openlca/assets/calculate_process_direct/main.py "Process B" --method "EF 3.1"
```

### 2. 带有分配方法与结果导出的高级计算
使用经济分配计算过程，并将结果导出为 CSV 文件：
```bash
uv run python .opencode/skills/control-openlca/assets/calculate_process_direct/main.py "Process B" -m "EF 3.1" -al economic -o output/process_results.csv
```
