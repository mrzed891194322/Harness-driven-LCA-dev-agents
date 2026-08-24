# 01 Whole-LCA 计划质量门禁规范

本规范只判断 `workspace/inputs/plan.md` 能否启动端到端执行。计划制定阶段的交付验收仍由计划制定规范管理。

## 1. 文件格式

- 唯一输入为 `workspace/inputs/plan.md`，该文件由用户直接维护，不创建同步副本。
- 文件为 Markdown；YAML front matter 可省略。若文件包含 front matter，
  不以 `template_kind`、`template_version` 或其他 metadata 作为格式门禁。
- Markdown 的章节数量、标题文字和排序不作为格式门禁；计划可使用 GUI 默认模板（包括 `PLAN_TEXTBOX` 包裹的旧“用户填写内容区”）、带 `PLAN_INPUT` 标记的上传模板，或不含输入标记的普通 Markdown。审查必须依据下节的语义内容，而不能依赖固定六章标题。
- 计划中引用的参考文档，Agent 应主动在 `harness/knowledge/inputs/user_ref/file/` 和 `harness/knowledge/inputs/user_ref/data/` 中按文件名关键词匹配查找。用户可写完整路径、相对路径、文件名、简称，或旧前缀 `user_file` / `user_data`；Agent 负责解析和定位，不因路径格式、目录前缀或是否使用现行 `user_ref` 路径而阻断。
- 计划审查前必须运行本阶段 `validation.py`，并把完整结果（包括
  `reference_inventory.roots` 和 `reference_inventory.files`）作为请求 handoff 的证据交给
  reviewer。inventory 必须使用不受 `.gitignore` 影响的文件系统遍历；不得用默认遵循
  ignore 规则的文件列表替代。
- reviewer 对用户资料作“不存在”结论前，必须给出覆盖上述两个固定根目录的 inventory
  负向结果，或状态为 `complete` 的 `input`/`data` RAG 负向查询证据。仅因某次目录枚举、
  默认文件搜索或 Git 列表未返回文件，不得创建 `PLAN-REFERENCE-NOT-LOCATED` 或将审查置为
  `needs_input`。

## 2. 阻断性信息

下列内容必须在计划中给出确定值，不能作为自动检索缺口：

- 研究对象和研究目的；
- 功能单位的数值、基准流/功能描述和物理单位；
- 系统边界及纳入/排除的生命周期阶段；
- 截断规则或明确的“不采用截断”决定；
- 多产出是否存在，以及适用时的分配原则；
- 预期应用、结果解释范围和至少一种完成判断方式。

任一项缺失、仍为模板占位符、相互矛盾或无法唯一解释时，记录稳定 issue ID，保存 `reviews/plan-review.json`，将 manifest 置为 `needs_input` 并停止。

## 3. 可检索工作

用户计划是自由格式 Markdown，不要求出现 `GAP-*`、`gap_type`、`retrieval_target`、`source_domain` 或固定章节标题。这些符号只用于审查 JSON 与第 02 阶段交接的内部追踪，不是用户填写门禁。

第 02 阶段的默认工作包括：从用户资料提取前景数据（物料、质量、运输、地域、建模关系等），以及在活动数据库中匹配背景 Process、Flow、Provider 或 LCIA 方法。计划用自然语言表达这些任务即有效，例如“从资料提取”“匹配背景数据”“由 Agent 完成 Provider 映射”。不得因为计划缺少 `GAP-*` 字面量而创建 `PLAN-RETRIEVABLE-GAPS-UNTRACKED`，也不得因此将审查置为 `needs_input`。

审查员在 `review.retrievable_gaps` 中为检索任务分配稳定 ID，格式为 `GAP-<大写字母或数字及连字符>`。优先沿用计划中已出现的 `GAP-*`；否则按任务铸造，常用 ID 为：

- `GAP-USER-REF-EXTRACT`：从用户资料或 RAG 提取已给定数据；
- `GAP-OPENLCA-BACKGROUND`：在活动数据库中匹配背景实体；
- `GAP-LCIA-METHOD`：在活动数据库中定位 LCIA 方法。

可检索工作不得改写第 2 节的用户价值判断或目标范围。典型项包括背景 Process/Flow/Provider 候选、UUID、活动数据库中的 LCIA 方法，以及用户资料中已给出但尚未写入计划正文的数据位置。检索不到时不得编造；将其转为未解决项，并根据影响置为 `needs_input` 或 `needs_review`。

## 4. 审查输出

计划审查必须使用 `harness/specs/public/references/schemas/review.schema.json`，`review_type` 为 `plan`、`attempt` 为 `1`。每个问题都必须包含 issue ID、严重度、规范引用、证据位置和可执行修正要求。

- `passed`：无第 2 节阻断问题；自然语言描述的检索任务已写入 `retrievable_gaps`（若计划已给出全部确定值且无检索任务，该数组可为空）；可进入第 02 阶段。
- `needs_input`：存在第 2 节阻断性缺失。不得把路径写法或缺少 `GAP-*` 符号当作阻断。
- `needs_review`：内容完整但存在需要人类判断且不适合自动检索的风险。
