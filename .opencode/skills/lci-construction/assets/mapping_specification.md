# LCI 映射建立方案与规范 (Mapping Specification)

本文件规定了如何将非结构化文本映射为符合 openLCA schema 规范的结构化 JSON 数据。

## 一、 Flow（流/物质）构建规范

必须为过程网络中提到的每一个独立的物质或能源实体建立单独的 Flow JSON 定义。

- **模板参照**：请严格参照 `template/flow_example.json`。
- **构建法则**：
  - `@type` 必须固定为 `"Flow"`。
  - 为其分配一个全局唯一的 `@id` (UUID)，并**严格记录此 UUID**，以备在关联过程时准确引用。
  - 根据其性质推断并正确设置 `flowType`（常用类型：`"PRODUCT_FLOW"`, `"ELEMENTARY_FLOW"`, `"WASTE_FLOW"` 等）。
  - 在配置流的参考属性（`flowProperties`）时，务必正确引用下方提供的官方常用 UUID（如“质量”与“千克”的组合）。

## 二、 Process（过程）构建规范

为计划中的每一道工艺或生产环节建立 Process JSON 配置，并将相关的物质流连接起来。

- **模板参照**：请严格参照 `template/process_example.json`。
- **构建法则**：
  - `@type` 必须固定为 `"Process"`，并为其分配全局唯一的 `@id` (UUID)。
  - 将物质的消耗与产出录入 `exchanges`（交换）列表中，准确设定数值 `amount` 以及方向标记 `isInput` (`true` 表示消耗/输入, `false` 表示产出/排放)。
  - **核心映射要求**：在每个 `exchange` 的 `flow` 对象内部，**必须准确无误地引用你在 Flow 构建步骤中为该物质生成的 Flow UUID**。
  - **基准量设定**：在当前过程的核心产出（即目标产品）的 `exchange` 中，必须明确添加并设定 `"isQuantitativeReference": true` 标记。这是确保 openLCA 计算准确的绝对核心。
  - **背景数据链接 (Provider Linking)**：若规划中明确指定了该输入项由特定的背景数据（如 ecoinvent 内的特定过程）提供，可在对应 `exchange` 中指定 `defaultProvider`。

## 三、 背景数据链接与产品系统构建规范 (Provider Linking & Product Systems)

除了基本的 Flow 和 Process 映射，Agent 还需要规划并输出相应的背景链接与产品系统构建文件。

- **背景数据链接 (Provider Linking)**：
  - 在过程的 `exchanges` 列表中，若某项输入明确由特定的背景数据集（如 ecoinvent 或区域数据库中的已知过程）提供，应当在相应的 `exchange` 对象中添加 `defaultProvider` 字段，并指定提供该物质的目标过程的 UUID。

- **产品系统构建配置 (Product Systems)**：
  - 为了后续能顺利在 openLCA 中构建拓扑网络，必须在 `src/LCI/` 中输出一个 `product_systems.json` 配置文件。
  - 该配置文件需要明确指定**根过程 (Root Process)** 以及自动连接偏好。请参照如下 JSON 结构生成：
    ```json
    {
      "product_systems": [
        {
          "root_process_id": "<你的核心目标过程的 UUID>",
          "name": "<产品系统的名称，通常与主过程相关>",
          "prefer_default_providers": true
        }
      ]
    }
    ```

## 四、 常用预设 UUID 参照表 (知识库强制规范)

在构建 Flow 或 Process 的嵌套引用时，对于最常见的物理量与单位，请**强制使用**以下 openLCA 官方通用环境 UUID，切勿自行捏造：

- **质量属性 (Mass FlowProperty)**: `bca7e4ea-ad3a-4424-aa61-fb9617300c82`
- **千克单位 (kg Unit)**: `20a8dd24-3405-47d4-9f50-cd467688c69d`

> 注：若任务中遇到复杂单位换算或其他在计划中不甚明朗的高级 Schema 配置需求，Agent 必须通过 `query-rag-database` 进一步在知识库中进行核对。
