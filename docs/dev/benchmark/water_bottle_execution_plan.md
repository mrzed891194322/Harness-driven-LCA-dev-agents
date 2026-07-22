---
template_kind: lca_execution_plan
template_version: 1
---

# PET 水瓶 Case 1/2/3 LCA 项目执行计划 (Execution Plan)

> [!NOTE]
> 本文档按 `harness/specs/plan-guidelines/references/templates/execution_plan.md` 编写，可直接作为 Agent 的执行输入。它是 [water_bottle_lca_plan.md](water_bottle_lca_plan.md) 的模板化版本，不替代或覆盖原文件。本案例用于内部教学与开发回归，不用于实际产品环境绩效声明、拟向公众披露的比较声明、ISO 认证或关键审查结论。

## 1. 研究目的与范围定义

### 1.1 研究对象与目的

- **研究对象**：向德国销售点交付的 1 L PET 静水瓶；瓶体为 PET、瓶盖为 HDPE、标签为 PP。比较 Case 1、Case 2 和 Case 3 三种粒料供应与运输路线。
- **研究问题**：在物料质量、灌装量、功能单位和前景生产假设固定时，不同粒料地域代理与运输路线如何影响 LCIA 结果、过程贡献和情景排序？
- **研究目的**：验证 Harness LCA Agent 的 `计划 → LCI → openLCA → 结果验证与解释` 工作流，形成可复现的开发回归基线，并暴露 Provider 消歧、单位换算、Product System 连接和空计算结果等问题。
- **预期用途**：内部教学、Agent 能力评测和开发回归。
- **预期受众**：项目开发者、测试人员和内部 LCA 审核者。
- **比较声明状态**：不支持拟向公众披露的比较声明。若用途改变，必须暂停发布比较结论，并重新确定系统等效性、数据质量、敏感性、不确定性和独立关键审查要求。
- **报告形式**：内部技术报告及可复现运行记录；不宣称 ISO 认证或标准合格。

### 1.2 功能单位 (Functional Unit)

- **产品系统功能**：在德国销售点提供以 PET 瓶、HDPE 盖和 PP 标签包装的 1 L 静水。
- **功能单位 (FU)**：在德国销售点交付 **1,000 个 1 L PET 静水瓶**。
- **参考流 (Reference Flow)**：德国销售点交付的灌装水瓶 1,000 item，总质量 1,065 kg。
- **前景建模基准**：建议每个前景过程以 1 个水瓶相关产品为定量参考流，Product System 计算量设为 1,000 item；也可按完整 FU 建模，但三个情景必须采用同一基准并证明等价。
- **设定依据**：三个情景提供相同容量、包装构成、灌装量和销售点交付功能，能够在共同功能基础上比较运输路线。

固定物料如下：

| 物料/产品 | 单瓶数量 | 功能单位数量 | 状态 |
| :--- | ---: | ---: | :--- |
| PET 瓶体 | 0.060 kg | 60 kg | 案例事实 |
| HDPE 瓶盖 | 0.004 kg | 4 kg | 案例事实 |
| PP 标签 | 0.001 kg | 1 kg | 案例事实 |
| 静水 | 1.000 kg | 1,000 kg | 案例事实 |
| 空瓶组件 | 0.065 kg | 65 kg | 确定性质量检查点 |
| 灌装水瓶 | 1.065 kg | 1,065 kg | 确定性质量检查点 |

### 1.3 系统边界 (System Boundary)

- **生命周期阶段**：Cradle-to-Point-of-Sale（从粒料背景供应链到德国销售点）。
- **纳入过程**：PET、HDPE、PP 粒料背景供应链；自来水背景供应链；粒料、空瓶组件和灌装水瓶运输；粒料供应、塑料组件生产、灌装、销售点运输四类前景过程；锁定背景数据库 system model 内含的上游过程。
- **系统边界图/描述**：

  ```text
  PET / HDPE / PP 背景 Provider
                  ↓
             粒料供应
                  ↓  每瓶 0.065 kg 粒料采购组合
         塑料组件生产 + 运输 A
                  ↓  1 套空瓶组件，0.065 kg
       灌装 + 1 kg 水 + 运输 B
                  ↓  1 个灌装水瓶，1.065 kg
          销售点运输 + 运输 C
                  ↓
        德国 POS 的 1 个 1 L 水瓶
                  × 1,000
  ```

- **边界外过程**：塑料成型、贴标、封盖和灌装设备的前景电力/热力/辅助材料；生产损耗和废料处理；二次与三级包装；仓储、销售点运营与制冷；消费者交通与使用阶段；押金返还、回收和最终处置；前景额外资本品。
- **边界限制**：生产能耗缺失和 100% 粒料收率是教学假设，不是已验证工厂事实。不能在未做敏感性分析时宣称这些过程不重要。

### 1.4 截断规则 (Cut-off Criteria)

- **质量/能量截断比例**：本基准不设置“低于 1% 自动删除”等隐式比例。所有已给定的 PET、HDPE、PP、水和运输活动均纳入。
- **特殊排除说明**：任何新增排除必须同时说明质量、能量和潜在环境显著性、排除理由及对结论的影响；不得仅凭质量比例忽略高环境相关性流。
- **边界修订**：如果生产能耗、损耗、包装或其他缺口在敏感性分析中表现显著，应回到范围阶段修订边界，并记录修订前后差异。

### 1.5 分配原则 (Allocation)

- **前景多产出分配**：四类前景过程按单一参考产品建模，不预期产生共同产品，因此不实施额外分配。
- **异常处理**：若实际 LCI 出现共同产品、回收材料或废物，暂停导入并列入 Todo；优先避免分配或进行系统扩展，再由合格人员决定物理或其他分配方法。
- **背景分配**：采用所选 ecoinvent `Cutoff, S` system model 的既有逻辑，并在报告中披露；不得在三个情景间混用不同 system model。

### 1.6 固定运输需求

运输需求按 `货物质量（t） × 距离（km） = t·km` 计算：

| 情景 | 运输段 | 方式与地域 | 单瓶需求 | 功能单位需求 |
| :--- | :--- | :--- | ---: | ---: |
| Case 1 | A：粒料至组件生产 | Europe 卡车，200 km | 0.013 t·km | 13 t·km |
| Case 1 | B：空组件至灌装 | Europe 卡车，200 km | 0.013 t·km | 13 t·km |
| Case 1 | C：灌装瓶至 POS | Europe 卡车，50 km | 0.05325 t·km | 53.25 t·km |
| **Case 1 合计** | A+B+C | **Europe 卡车** | **0.07925 t·km** | **79.25 t·km** |
| Case 2 | A：粒料至组件生产 | China 铁路，5,000 km | 0.325 t·km | **325 t·km** |
| Case 2 | B：空组件至灌装 | Europe 卡车，200 km | 0.013 t·km | 13 t·km |
| Case 2 | C：灌装瓶至 POS | Europe 卡车，2,600 km | 2.769 t·km | 2,769 t·km |
| **Case 2 卡车合计** | B+C | **Europe 卡车** | **2.782 t·km** | **2,782 t·km** |
| Case 3 | A1：粒料陆路段 | RoW 卡车，300 km | 0.0195 t·km | **19.5 t·km** |
| Case 3 | A2：粒料海运段 | Global 海运，13,887 km | 0.902655 t·km | **902.655 t·km** |
| Case 3 | B+C | Europe 卡车 | 2.782 t·km | **2,782 t·km** |

若背景运输 flow 的参考单位为 `kg·km`，交换数值应为表中 `t·km` 的 1,000 倍，并保留单位换算记录。不得只复制数值而忽略单位。

### 1.7 来源、假设与数据状态

案例事实来自[本地水瓶教程](<../../../harness/knowledge/inputs/user_file/水瓶案例学习/水瓶案例学习.md>)：

- 教学用途和 ecoinvent 3.1 背景：第 37–43 行；
- 情景、功能单位和供应路线：第 45–86 行；
- LCIA、运输、物料质量和能耗缺口：第 189–207 行。

| 内容 | 状态 | 处理要求 |
| :--- | :--- | :--- |
| 功能单位、物料质量、运输距离 | `fact` | 按上述固定值建模并做确定性检查 |
| Case 3 RoW 卡车距离 | `resolved_conflict` | 教程表格为 300 km、正文为 200 km；主情景固定 300 km，200 km 进入敏感性方案 |
| Case 2/3 粒料背景地域 | `proxy` | 教程用 RoW 代理中国生产语义；主情景保留并披露，CN 数据仅作敏感性方案 |
| 水的具体 Provider | `unresolved` | Germany 优先、Europe 次之，须在当前数据库中查询并证明地域 |
| 生产能耗、辅助材料、损耗 | `unresolved` | 主情景按教程排除，同时建立有来源的敏感性代理 |
| 100% 粒料收率 | `proxy` | 保留为教学假设并评价影响 |
| 教程 LCIA 数值 | `historical_context` | 不作为当前 ecoinvent 3.11 的严格数值金标 |

ISO 目标与范围依据可回读至 [ISO 14044:2006](<../../../harness/knowledge/inputs/static_ref/standards/ISO14044-2006/ISO 14044-2006_.md>) 第 500–590 行。所有范围修订、假设、限制和人工决定必须保留证据。

---

## 2. 生命周期影响评价方法 (LCIA Method) 与指标

- **选用的 LCIA 方法**：`CML v4.8 2016 no LT`。
- **当前观察到的方法 UUID**：`47f86689-b60a-4d52-9d6a-3db3c5b662fd`；Agent 在计算前必须从活动数据库重新查询，不能把本文 UUID 当作跨环境常量。
- **选择依据**：与原教程 CML 方法域保持可解释连续性，同时使用当前 ecoinvent 3.11 LCIA 方法；不将教程 ecoinvent 3.1/CML 2001 数值作为金标。
- **必报结果**：保存未加权的完整 characterization profile，并至少单列方法中实际存在的以下类别：
  - Global Warming Potential（气候变化）；
  - Fossil resource depletion（化石资源耗竭）；
  - Acidification Potential（酸化）；
  - Eutrophication Potential（富营养化）；
  - Human Toxicity（人类毒性）；
  - Ozone Layer Depletion（臭氧层消耗）。
- **可选元素**：主基准不使用归一化、分组或加权得出单一总体优劣。若用于补充解释，必须保留变换前结果并披露价值选择。
- **结果限制**：LCIA 结果是相对于功能单位的潜在影响指标，不是实际损害、类别终点、阈值、安全边际或风险预测。

---

## 3. openLCA 环境与数据基础

### 3.1 当前 openLCA 环境与连接情况

- **API/连接状态**：2026-07-21 只读健康检查通过，IPC endpoint 为 `http://127.0.0.1:8080`，描述符查询可用。
- **已观察数据库环境**：实体与方法类别显示 `ecoinvent 3.11`，过程名称后缀为 `Cutoff, S`。
- **LCIA 方法状态**：当前同时存在 `CML v4.8 2016 no LT` 与 `CML v4.8 2016`；必须选择前者并保存运行时查询输出。
- **Provider 歧义**：PET bottle-grade granulate 查询当前返回 8 个结果，其中多个生产过程名称完全相同但 UUID 不同。描述符名称不足以证明地域，必须进一步核对 location、参考产品和 system model。
- **运行时要求**：每次执行重新记录 openLCA 版本、活动数据库名称/版本、system model、方法名称与 UUID、Provider 名称/UUID/地域及查询时间。

### 3.2 现有参考资料与可用数据情况

- **主要案例资料**：[本地水瓶教程](<../../../harness/knowledge/inputs/user_file/水瓶案例学习/水瓶案例学习.md>)。
- **标准依据**：[ISO 14040:2006](<../../../harness/knowledge/inputs/static_ref/standards/ISO14040-2006/ISO 14040-2006_.md>) 与 [ISO 14044:2006](<../../../harness/knowledge/inputs/static_ref/standards/ISO14044-2006/ISO 14044-2006_.md>)。
- **背景数据库**：ecoinvent 3.11，`Cutoff, S`；运行时再次确认。
- **固定前景数据**：PET/HDPE/PP/水质量及 A/B/C 三类运输距离和运输方式。
- **数据质量初评**：
  - 物料质量和运输算式适合确定性开发回归，但来自教学案例，不代表具体工厂；
  - 教程时间与数据库版本较旧，Provider 名称和 LCIA 数值不具备当前环境可移植性；
  - Case 2/3 的 RoW 粒料数据是中国生产语义的地域代理；
  - 缺少塑料成型、贴标、封盖、灌装的工厂直接能耗、辅助材料、损耗与不确定性分布；
  - 使用阶段和报废阶段不在研究边界内。

---

## 4. openLCA 模型细节方案

### 4.1 需要创建的流 (Flows)

仅创建前景产品流。所有资源消耗和排放使用背景数据集既有的基本流，不重复新建同义 elementary flow。最终名称和 ID 应遵循 `harness/specs/lci-construction/`。

- **产品流 (Product Flows)**：
  - `Plastic granulates supplied - Case {1|2|3}`：每瓶 PET/HDPE/PP 采购组合，参考单位 `Item(s)`，附属质量 0.065 kg；这是采购组合而非物理混合产品。
  - `Plastic components for 1 L PET bottle - Case {1|2|3}`：一套瓶体、瓶盖和标签，参考单位 `Item(s)`，质量 0.065 kg。
  - `Filled 1 L PET water bottle - Case {1|2|3}`：灌装完成水瓶，参考单位 `Item(s)`，质量 1.065 kg。
  - `1 L PET water bottle at POS Germany - Case {1|2|3}`：销售点交付产品，参考单位 `Item(s)`；作为各 Product System 的参考流。
- **背景输入流**：PET bottle-grade granulate、HDPE granulate、PP granulate、tap water、lorry freight、rail freight 和 transoceanic freight 均复用当前数据库 Provider 的参考产品流。
- **禁止事项**：不得新建名称相似但 ID 不同的背景流来强制连接；下游输入 flow ID 必须与实际 Provider 输出 flow ID 一致。

### 4.2 需要创建的过程 (Processes)

每个情景创建四个前景过程，定量参考输出均为 1 item。表中数量为单瓶数据；Product System 计算 1,000 item 后必须得到第 1.2 和 1.6 节的功能单位总量。

#### 单元过程 1：`Granulate supply - Case {1|2|3}`

- **输入**：PET 0.060 kg、HDPE 0.004 kg、PP 0.001 kg，分别连接经验证的背景 Provider。
- **输出**：`Plastic granulates supplied - Case {n}` 1 item，代表总质量 0.065 kg 的采购组合。
- **地域**：Case 1 使用 RER/Europe；Case 2/3 主情景使用 RoW 教程代理并记录“中国生产语义”。
- **检查**：三种粒料质量合计必须为 0.065 kg。

#### 单元过程 2：`Plastic component production - Case {1|2|3}`

- **输入**：对应情景的粒料采购组合 1 item。
- **运输 A**：
  - Case 1：Europe 卡车 0.013 t·km；
  - Case 2：China 铁路 0.325 t·km；
  - Case 3：RoW 卡车 0.0195 t·km + Global 海运 0.902655 t·km。
- **输出**：`Plastic components for 1 L PET bottle - Case {n}` 1 item，质量 0.065 kg。
- **生产能耗**：主情景暂不加入，明确标记数据缺口；敏感性方案加入有来源的代理。

#### 单元过程 3：`Bottle filling - Case {1|2|3}`

- **输入**：对应情景塑料组件 1 item、自来水 1.000 kg。
- **运输 B**：Europe 卡车 0.013 t·km。
- **输出**：`Filled 1 L PET water bottle - Case {n}` 1 item，质量 1.065 kg。
- **灌装能耗和损耗**：主情景暂不加入，列入 Todo 和敏感性分析。

#### 单元过程 4：`Transport to POS Germany - Case {1|2|3}`

- **输入**：对应情景灌装水瓶 1 item。
- **运输 C**：Case 1 为 Europe 卡车 0.05325 t·km；Case 2/3 为 Europe 卡车 2.769 t·km。
- **输出**：`1 L PET water bottle at POS Germany - Case {n}` 1 item，作为定量参考流。

### 4.3 背景数据链接 (Background Data Links)

| 用途 | 主情景地域/类型 | Agent 查询与选择要求 |
| :--- | :--- | :--- |
| PET bottle-grade granulate | Case 1 RER/Europe；Case 2/3 RoW | 区分 production、market、market group 和 recycled；核对 location 与参考产品 |
| HDPE granulate | 同 PET 地域策略 | 核对 virgin/recycled、market/production、location 与 system model |
| PP granulate | 同 PET 地域策略 | 核对 virgin/recycled、market/production、location 与 system model |
| Tap water | Germany 优先，Europe 代理次之 | 记录技术与地域代表性；不得随意选择搜索首项 |
| Freight lorry | Europe/RoW；16–32 t、diesel、EURO 5 语义优先 | 当前名称可能与教程不同；选择最接近数据集并解释替代 |
| Freight train | China | 核对地域、货运参考产品与单位 |
| Transoceanic freight ship | Global | 核对 GLO、船型和货运参考产品 |

每个背景链接必须保存：查询词、候选总数、候选清单、完整名称、UUID、location、参考产品/流、参考单位、system model、选择理由和查询时间。无法消歧时标记 `unresolved_provider`，停止相关情景导入，严禁猜测 UUID。

### 4.4 产品系统构建 (Product System)

- **Product System 数量**：3 个，Case 1/2/3 各一个，保持结构等价且实体隔离。
- **参考过程**：各情景的 `Transport to POS Germany - Case {n}`。
- **参考流/计算量**：`1 L PET water bottle at POS Germany - Case {n}`，计算量 1,000 item。
- **连接策略**：优先使用已验证的 default Provider，但 Product System 生成后必须读取模型图验证实际节点与边，不能只信任导入 JSON 或自动连接选项。
- **预期前景拓扑**：`Granulate supply → Plastic component production → Bottle filling → Transport to POS Germany`。
- **失败条件**：孤立前景输入、悬空 Provider、错误地域 Provider、参考产品不一致、节点缺失或计算结果为空均不得视为完成。

### 4.5 情景对比分析 (Projects)

- **是否需要 Project 功能**：是。
- **Project 设计**：建立一个内部比较 Project，包含三个 Product System，所有 variant 使用相同 LCIA 方法和 1,000 item 参考量。
- **主情景固定差异**：
  - Case 1：RER/Europe 粒料代理和短距离 Europe 卡车；
  - Case 2：RoW 粒料代理、China 铁路和长距离 Europe 卡车；
  - Case 3：RoW 粒料代理、RoW 卡车、Global 海运和长距离 Europe 卡车。
- **可比性要求**：除了上述 Provider 地域和运输路线外，功能单位、物料质量、水、前景结构、system model、LCIA 方法和计算设置必须一致。
- **输出**：逐影响类别对比，不计算或宣称单一总体环境优越分数。

---

## 5. 结果的验证与解释方案

### 5.1 完整性与一致性检查

- **案例事实检查**：确认 FU 为 1,000 item，PET/HDPE/PP/水分别为 60/4/1/1,000 kg，空瓶和灌装瓶质量分别为 65/1,065 kg。
- **运输换算检查**：独立复算并匹配 Case 1 卡车 79.25 t·km、Case 2 铁路 325 t·km、Case 2/3 Europe 卡车 2,782 t·km、Case 3 RoW 卡车 19.5 t·km、Case 3 海运 902.655 t·km。
- **LCI 结构检查**：验证 schema、交换方向、定量参考流、单位、数量级、flow ID、Provider UUID 和重复实体。
- **导入检查**：记录 Flow、Process、Product System 和 Project 的计划数、成功数、失败数、实际 UUID 与输入/输出哈希；部分失败即停止。
- **模型图检查**：读取三个 Product System 的节点与边，确认四段前景链和所有背景输入连接，无孤立或错误 Provider。
- **计算检查**：保存 Product System、参考流、计算量、方法、方法 UUID、分配设置和参数；命令成功但 LCIA 类别结果为空时判定失败。
- **跨情景一致性**：除声明的地域与运输差异外，三情景的功能、边界、数据质量规则、system model、LCIA 方法和解释方式一致。

### 5.2 热点分析与可视化

- **贡献树分析 (Contribution Tree)**：对每个情景至少分析气候变化、化石资源耗竭、酸化、富营养化、人类毒性和臭氧层消耗中实际存在的类别；识别粒料、水、各运输段及前景过程贡献。
- **模型图**：输出包含 process UUID、provider UUID 和边关系的结构化图，作为 Provider linking 证据。
- **桑基图可视化 (Sankey Diagram)**：展示物料质量流和运输负荷时，应明确二者单位不同，不能把 kg 与 t·km 合并成同一守恒流；LCIA 贡献可另做按类别图。
- **情景对比图**：逐类别显示 Case 1/2/3，保留单位，不用加权总分掩盖类别间权衡。

### 5.3 敏感性与不确定性分析

必须执行以下确定性敏感性方案：

1. **生产能耗代理**：为成型、贴标、封盖和灌装加入有来源的能耗区间，检查热点及各类别排序。
2. **运输距离 ±20%**：对主要长距离运输统一改变距离，检查结论稳定性。
3. **地域 Provider**：在可获得并经验证时，将 RoW 主代理与 CN 或其他合理地域数据集比较。
4. **Case 3 来源冲突**：以 200 km/13 t·km 作为敏感性方案，与主情景 300 km/19.5 t·km 比较。
5. **影响类别完整性**：逐类别检查排序，不以气候变化单项代表总体环境表现。

- **蒙特卡洛模拟**：主基准暂不强制。只有在关键前景输入和代理值具有可解释的不确定性分布、背景数据支持且运行设置可复现时执行；否则记录为待决事项，不伪造分布。
- **结果解释**：识别重大问题，执行完整性、敏感性和一致性检查，再形成限定于内部教学/开发用途的结论和限制。
- **结论门禁**：缺少关键输入、Provider 未消歧、模型图不完整、结果为空或重要敏感性未完成时，状态只能是 `fail`、`conditional_pass` 或 `needs_human_review`，不得宣称 `pass`。

---

## 6. 待完善清单

> [!WARNING]
> Agent 在正式执行时须将以下每项同步写入 `workspace/plan/todo_list.md`，并严格使用 `harness/specs/plan-guidelines/references/templates/todo_list.md`。未解决项不得通过猜测默认值关闭。

1. **背景 Provider 与地域消歧**：为 PET、HDPE、PP、水、Europe/RoW 卡车、China 铁路和 Global 海运确认完整名称、UUID、location、参考产品、单位和 system model。
2. **水 Provider 选择**：确认 Germany 数据集是否适用；若使用 Europe 代理，记录理由和代表性限制。
3. **前景生产能耗与辅助材料**：寻找成型、贴标、封盖、灌装的可引用代理数据，定义主敏感性区间。
4. **生产损耗和 100% 收率**：决定是否维持教程假设，或增加有来源的损耗率敏感性。
5. **RoW 代理中国生产的适用性**：确认主情景保留 RoW，并选择是否增加 CN Provider 敏感性。
6. **运输数据集等价性**：确认 ecoinvent 3.11 中与教程 16–32 t EURO 5、China train 和 transoceanic ship 最接近的数据集。
7. **不确定性分析范围**：决定是否有足够分布数据运行蒙特卡洛；不足时只做确定性敏感性并说明。
8. **关键审查与发布边界**：当前为内部开发用途且不做公开比较；若用途改变，需由人类重新决定审核类型。

---

## 7. Agent 执行阶段、门禁与交付物

| 阶段 | Agent 行动 | 必需证据 | 通过门禁 |
| :--- | :--- | :--- | :--- |
| 计划固化 | 将本文复制/转化为 `workspace/plan/execution_plan.md`，生成对应 `todo_list.md` | 计划、Todo、来源与决定记录 | 模板和 plan-guidelines 自检通过 |
| LCI 设计 | 创建 Flow、Process、Product System、Project 设计和人类可读映射 | JSON、换算表、映射报告 | schema、单位、方向、参考流和 ID 检查通过 |
| Provider 查询 | 查询并消歧所有背景 Provider 与 LCIA 方法 | 查询 manifest、UUID、地域和选择理由 | 无伪造或 unresolved Provider |
| 导入 | 在明确范围内受控导入 | 成功/失败计数、实体 UUID、哈希 | 无部分失败、重复或超范围写入 |
| 模型验证 | 读取三个 Product System 模型图 | 节点/边 JSON 和预期拓扑对照 | 无孤立输入、悬空边或错误 Provider |
| LCIA | 按 1,000 item 和锁定方法计算 | 原始结果、设置、日志、资源释放记录 | 三情景结果均非空且类别/单位一致 |
| 解释 | 热点、完整性、敏感性、一致性和限制分析 | 解释报告及敏感性结果 | 结论不超出用途，限制完整披露 |
| 运行审核 | 填写 benchmark run record 并执行质量评价 | 运行记录、哈希、差异、复审结论 | 状态为四态之一且有充分依据 |

最终至少交付：

- `workspace/plan/execution_plan.md` 与 `workspace/plan/todo_list.md`；
- 前景 Flow、Process、Product System 和 Project 的结构化 LCI 文件；
- Provider/方法查询 manifest 与人类可读映射报告；
- 导入报告、导入后实体清单及模型图；
- LCIA 原始结果、贡献分析、敏感性分析和解释报告；
- 一份填写完整的 [benchmark_run_record_template.md](benchmark_run_record_template.md)；
- 按 [lca_quality_evaluation.md](lca_quality_evaluation.md) 形成的门禁矩阵和最终状态。

Agent 只有在实际证据通过对应门禁后才能宣称完成。文件存在、命令退出码为 0、openLCA 返回 success 或 Agent 自述都不能单独证明任务完成。
