# 02 前景清单提取（sub-executor）

产物字段见 `harness/specs/02-inventory-extraction/`。本文件只写执行口径。

- 直接读 `harness/knowledge/` 中的文件（图纸、合同、ERP 导出、PDF 等）。读得出的文本/表格必须抽取并记下位置。
- 读不出的二进制标为 `unreadable`，不得编造数量。
- 本阶段不查询 openLCA、不写 LCI。
