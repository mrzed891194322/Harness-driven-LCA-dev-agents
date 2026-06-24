# LCI 结构化数据构建与导入规范 (LCI Construction README)

本文件是 LCI 数据构建、自检与导入 openLCA 数据库的路由入口。

智能体在根据执行计划设计、生成 LCI 数据及导入数据库时，请根据当前任务查阅对应的规范与模板文件：

---

## 路由导航

1. **核心工作逻辑与步骤指南**
   - 📂 **[doc/lci_construction.md](doc/lci_construction.md)**：包含 LCI 核心执行方案、5步工作逻辑以及输出目录结构要求。

2. **详细映射、自检与导入规范**
   - 📂 **[doc/mapping_specification.md](doc/mapping_specification.md)**：映射规范，指导 Flow、Process 实体的 JSON 构建与 UUID 连接。
   - 📂 **[doc/self_check.md](doc/self_check.md)**：自检规范，在文件输出前必须通过该质量自检校验。
   - 📂 **[doc/import_specification.md](doc/import_specification.md)**：导入规范，数据构建完成后批量导入 openLCA 数据库的指南。

3. **输出模板与示例**
   - 📂 **[template/](template/)**：包含 Flow、Process、Product System 的 JSON 示例，以及人类可读映射解读报告的模板。
