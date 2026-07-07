# LCI 映射建立方案与规范 (Mapping Specification)

本文件规定了如何将非结构化文本映射为符合 openLCA schema 规范的结构化 JSON 数据。

## 一、 Flow（流/物质）构建规范

必须为过程网络中提到的每一个独立的物质或能源实体建立单独的 Flow JSON 定义。

- **模板参照**：请严格参照 `harness/specs/lci-construction/references/templates/flow_example.json`。
- **构建法则**：
  - `@type` 必须固定为 `"Flow"`。
  - **命名规范（Naming Convention）**【强制】：
    - **文件名称**：必须使用 `f<两位数编号>-<英文具体名称（小写，连字符分隔）>.json` 格式，例如：`f01-gold-plated-product.json`。
    - **JSON 内部的 `name` 属性**：必须严格采用 `F + 两位数编号 + 空格 + 具体名称` 的格式，例如：`"F01 Gold-plated product"`。在其他过程（Process）引用该流时，`flow` 对象中的 `name` 字段也必须使用该统一命名的格式。
  - 为其分配一个全局唯一的 `@id` (UUID)，并**严格记录此 UUID**，以备在关联过程时准确引用。
  - 根据其性质推断并正确设置 `flowType`（常用类型：`"PRODUCT_FLOW"`, `"ELEMENTARY_FLOW"`, `"WASTE_FLOW"` 等）。
  - 在配置流的参考属性（`flowProperties`）时，务必正确引用下方提供的官方常用 UUID（如“质量”与“千克”的组合）。

## 二、 Process（过程）构建规范

为计划中的每一道工艺或生产环节建立 Process JSON 配置，并将相关的物质流连接起来。

- **模板参照**：请严格参照 `harness/specs/lci-construction/references/templates/process_example.json`。
- **构建法则**：
  - `@type` 必须固定为 `"Process"`，并为其分配全局唯一的 `@id` (UUID)。
  - **命名规范（Naming Convention）**【强制】：
    - **文件名称**：必须使用 `p<编号>-<英文具体名称（小写，连字符分隔）>.json` 格式，例如：`p1-chemical-degreasing.json`。
    - **JSON 内部的 `name` 属性**：必须严格采用 `P + 编号 + 空格 + 具体名称` 的格式，例如：`"P1 Chemical Degreasing"`。
  - 将物质的消耗与产出录入 `exchanges`（交换）列表中，准确设定数值 `amount` 以及方向标记 `isInput` (`true` 表示消耗/输入, `false` 表示产出/排放)。
  - **核心映射要求**：在每个 `exchange` 的 `flow` 对象内部，**必须准确无误地引用你在 Flow 构建步骤中为该物质生成的 Flow UUID**。
  - **基准量设定**：在当前过程的核心产出（即目标产品）的 `exchange` 中，必须明确添加并设定 `"isQuantitativeReference": true` 标记。这是确保 openLCA 计算准确的绝对核心。
  - **拓扑与链接 (Provider Linking)**：【强制要求】对于任何作为输入（`isInput: true`）的 `exchange`，都**必须**指定 `defaultProvider` 字段。
    - **内部前台流向**：如果该输入流由上一道工序产出，`defaultProvider` 必须填写产出该流的内部 Process 的 UUID。
    - **外部背景数据**：如果该流来自背景库，必须使用 `query_descriptors` 获取精确 UUID 并填入 `defaultProvider`。

## 三、 背景数据链接与产品系统构建规范 (Provider Linking & Product Systems)

除了基本的 Flow 和 Process 映射，构建结果还必须包含相应的背景链接与产品系统构建文件。

- **供应链拓扑与提供者链接 (Provider Linking)**：
  - 在过程的 `exchanges` 列表中，只要 `isInput` 为 `true`，就**必须**添加 `defaultProvider` 字段以建立模型图的连线。
  - `defaultProvider` 格式如下：
    ```json
    "defaultProvider": {
      "@type": "Process",
      "@id": "<提供该流的 Process 的 UUID>"
    }
    ```
  - **Flow ID 强一致性原则**：为了让 openLCA 能够成功连线，**下游输入流的 Flow ID 必须与上游提供方 Process 的对应输出流的 Flow ID 保持绝对一致**。严禁将上游产出设为成品 A，而下游接收端指明消耗中间体 B 并把 Provider 连到该上游。如果阶段间有状态变化，必须输出与输入一致的 Flow ID 或合理设计中间 Flow。
  - **切勿遗漏**：缺失此字段将导致导入 openLCA 后模型图断裂。

- **产品系统构建配置 (Product Systems)**：
  - 为了后续能顺利在 openLCA 中构建拓扑网络，必须在 `workspace/LCI/product_systems/` 目录下输出符合 JSON-LD 规范的配置文件。
  - **命名规范（Naming Convention）**【强制】：
    - **文件名称**：必须使用 `ps<编号>-<英文具体名称（小写，连字符分隔）>.json` 格式，例如：`ps1-gold-plating-product-system.json`。
    - **JSON 内部的 `name` 属性**：必须严格采用 `PS + 编号 + 空格 + 具体名称` 的格式，例如：`"PS1 Gold Plating Product System"`。
  - 该配置文件需要明确指定**参考过程 (Reference Process)** 以及自动连接偏好。请参照如下 JSON 结构生成（切勿使用 `rootProcess` 等非标准字段）：
    ```json
    {
      "@type": "ProductSystem",
      "@id": "<为你建立的产品系统分配一个全局唯一的 UUID>",
      "name": "<产品系统的名称，通常与主过程相关>",
      "refProcess": {
        "@type": "Process",
        "@id": "<你的核心目标过程的 UUID>"
      },
      "preferDefaultProviders": true
    }
    ```

## 四、 常用预设 UUID 参照表 (知识库强制规范)

在构建 Flow 或 Process 的嵌套引用时，对于最常见的物理量与单位，请**强制使用**以下 openLCA 官方通用环境 UUID，切勿自行捏造：

- **质量属性 (Mass FlowProperty)**: `bca7e4ea-ad3a-4424-aa61-fb9617300c82`
- **千克单位 (kg Unit)**: `20a8dd24-3405-47d4-9f50-cd467688c69d`

> 注：若任务中遇到复杂单位换算或其他在计划中不甚明朗的高级 Schema 配置需求，必须使用上游任务允许的正式知识库或 openLCA 查询工具进行核对，并在映射报告中记录依据。
