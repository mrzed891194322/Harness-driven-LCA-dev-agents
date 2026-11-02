# BOM 数量抽取 · 04 reviewer

内容取舍统一按已注入的 `BOM extraction 04 · 共同抽取口径`。只读审核，不改产物，不代写另一套 claims。

1. **机械检查**：读取 executor 中间目录的 `checklist.json`（本节点为 `workspace/runs/_run/notes/bom-extract-04/executor/checklist.json`）与当前 claims，先调用 `mcp__bom_claims_check__check_claims(checklist=[清单项...])`。工具无法执行时不能声称检查通过。
2. **独立核对**：读本次 knowledge 的相关完整正文和表格，按共同口径从清单回查全部直接答案，再逐条反查 claims。核实端点、同源数值/单位、表行倍率、总分关系、独立性和适用范围；不能只核已交条目，也不能照抄 executor 的结论。无告警不等于语义正确。
3. **处理告警**：MCP 的覆盖、COUNT、SAME_SLOT、UNMATCHED、sum-split、空交付和证据等告警都是待核线索，不按告警或条数自动裁删。真实漏项补有据答案；真实清单外或未问的总量分项删除；确属称呼不匹配时修准确标签和适用证据。范围端点、独立来源或测量不能仅因数值接近、可相加或共用清单项判为重复；回查原文确认误报时保留并在审核笔记说明 claim_id、原文依据和告警误判原因。空 claims 只有充分回查确无可答数值才通过。不得为消警删真答案、复制数值、伪造覆盖或编造证据。
4. **一次列全问题**：有可修问题就 `reject`，在 issues 中以 claim_id/清单项定位 where，problem 写违反哪项共同口径及原文依据，expected 写具体补、改、合并或删除及须保留条件。不要给条数配额，也不要仅写“重新检查”。复审时重跑整份产物的 MCP，核对上轮全部 issues、变动条目及受影响的覆盖/总分关系；未变动且已有可复核审核记录的内容可沿用其证据，不为纯格式修订重复遍历整篇原文。记录不足或内容改变时仍须独立回查。
5. **提交判定**：完成 MCP 与原文核对、无未解决问题后 `approve`；comment 简述来源覆盖、关键计算/合并和软告警处置，无此项则省略。无法返工的证据缺失或来源冲突按 agent 契约 `terminate` 并说明原因；仅在 `<redo_policy>` 允许时使用 `approve_redo_upstream`。使用 `mcp__submit__submit` 提交 verdict；reject 只传 verdict、issues 和可选 comment，不传 summary。未用可选参数省略，不传 null；不得 submit artifact。
