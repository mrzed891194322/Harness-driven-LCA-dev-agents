# 产品系统 LCIA 计算脚本使用指南 (calculate_product_system)

本脚本专门用于对 openLCA 中已配置完毕并保存的**产品系统 (Product System)** 进行环境影响评估（LCIA）计算。

## 目录结构与模块说明

本目录采用高度模块化的包结构设计，具体文件及职责划分如下：

*   **`main.py`**：计算主脚本，负责命令行参数解析与整个计算流程控制。
*   **`README.md`**：本说明文档（包含目录结构与使用方法说明）。
*   **`private_utils/`**：仅当前脚本使用的私有工具包。
    *   **`__init__.py`**：初始化标识文件。
    *   **`calculation.py`**：包含仅针对产品系统计算日志和设置的 `run_calculation` 函数。
    *   **`cli.py`**：专属命令行参数解析定义。
*   **`scripts/utils/` (共享模块)**：存放多个脚本共用的工具函数包，位于上一级脚本目录下。
    *   **`connection.py`**：负责建立与 openLCA IPC Server 的 HTTP 连接并测试可用性。
    *   **`entity.py`**：实现通用实体查找逻辑（`find_entity`）。
    *   **`export.py`**：负责 LCIA 计算结果的格式化提取、控制台 Markdown 打印与 CSV/JSON 文件导出。
    *   **`validation.py`**：负责处理分配方案与参数覆盖输入的预校验（Fail-Fast 逻辑）。

## 运行命令

```bash
uv run python .opencode/skills/control-openlca/scripts/calculate_product_system/main.py "产品系统名称或UUID" --method "LCIA方法名称或UUID" [可选参数]
```

## 参数说明

### 位置参数
* `system`: openLCA 中目标产品系统（Product System）的名称或 UUID。

### 选项参数
* `--method`, `-m`: （可选）生命周期影响评估方法（LCIA Method）的名称或 UUID。如果数据库中该产品系统已默认绑定了计算方法，此参数可省略。
* `--amount`, `-a`: 计算所需的功能单位数量。默认为 `1.0`。
* `--allocation`, `-al`: 显式指定产品系统内的分配方法。支持以下可选值：
  * `physical`: 物理分配 (Physical)
  * `economic`: 经济分配 (Economic)
  * `causal`: 因果分配 (Causal)
  * `none`: 不进行分配 (None)
  * `default`: 使用数据库默认分配设置 (Default)
* `--regionalized`, `-r`: 启用区域化计算（布尔标记，添加该选项即代表开启）。
* `--costs`, `-c`: 启用成本计算（布尔标记，添加该选项即代表开启）。
* `--parameter`, `-param`: 临时重定义/覆盖模型内的参数值。格式为 `参数名=数值`。可多次使用以修改多个参数。例如：
  `-param param_a=1.2 -param param_b=3.5`。
* `--output`, `-o`: 将计算结果以表格格式导出到文件。支持 `.json` 或 `.csv` 后缀。
* `--host`, `-H`: openLCA IPC Server 的主机地址。默认为 `127.0.0.1`。
* `--port`, `-p`: openLCA IPC Server 的端口号。默认为 `8080`。

## 运行示例

### 1. 基础计算
计算名为 "Product System A" 的产品系统，使用 "EF 3.1" 评估方法：
```bash
uv run python .opencode/skills/control-openlca/scripts/calculate_product_system/main.py "Product System A" --method "EF 3.1"
```

### 2. 带有分配方法与参数覆盖的高级计算
使用物理分配，重定义 `electricity_ratio` 参数为 `0.8`，并将结果保存至 JSON：
```bash
uv run python .opencode/skills/control-openlca/scripts/calculate_product_system/main.py "Product System A" -m "EF 3.1" -al physical -param electricity_ratio=0.8 -o output/result.json
```

### 3. 启用区域化与成本计算
```bash
uv run python .opencode/skills/control-openlca/scripts/calculate_product_system/main.py "Product System A" -m "EF 3.1" -r -c
```
