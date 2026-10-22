# harness v5 设计草稿 v2：目录 · 注入 · GUI（2026-10-20 讨论整理）

> 状态说明：【已定】是 Du Yuan 明确同意的；【建议】是 Grok Bot 提出、尚待确认的。
> v2 相对 v1 的主要变化：会话注入顺序、统一反馈文件、角色目录化（prompt.md + access.yaml）、权限用默认值 + GUI 开关、agent 卡片布局。

## 总原则
- 【已定】harness/ 只有五个目录：rules、specs、knowledge、tools、workflows。
- 【已定】先做最简版：去掉现有全部 rules、tools、specs，只加必要的，先把工作跑通。
- 【已定】可以放开设计，充分利用 pi 原生功能（原生 MCP、会话事件等）。
- 【已定】最小元素、自由组合：规则、角色、权限、工具、交付内容各自独立，在节点/agent 上拼接。
- 【已定】格式约定：给模型读的提示词一律 md；给宿主用的结构化配置（权限、schema、checks、节点）一律 yaml/json。
- 【已定】前后端有必要的状态变化都写进合适的日志，核心是便于开发调试、出错时能定位。
- 【已定】宿主关掉 pi 的自动加载：不注入 AGENTS.md（noContextFiles），不读 ~/.pi 和项目 .pi（【建议】用项目专用 agentDir、projectTrusted:false）。

## 〇、一个 pi 会话的注入顺序（生命周期）
【已定】按以下顺序注入：

| 顺序 | 内容 | 来源 | 注入方式 |
|---|---|---|---|
| 1 | 顶层规则 | `rules/global/` | 系统提示词 |
| 2 | 权限 | 全局默认 + 角色 `access.yaml` + 节点覆盖 + 宿主锁定 | 宿主 tool_call 拦截（不靠提示词） |
| 3 | 角色提示词 | `rules/roles/<角色>/prompt.md` | 系统提示词追加 |
| 4 | 工具和技能 | agent 的 `tools` | 宿主只注册列出的 MCP/技能 |
| 5 | 任务上下文 | `artifacts/plan/` + requires 上游产物 | `<plan>` 分段（全文）+ `<inputs>` 分段（路径+简述） |
| 6 | 交付内容 | `specs/<交付>/` | 命名分段（如 `<deliverable_bom>`，见第二节） |
| 7 | 返工意见（如有） | `runs/<节点>/feedback/round_N.md` | `<rework>` 分段，第 1 轮不注入 |

- 【已定】任务上下文与方法学约定合并：计划里已规定数据库版本、影响评价方法、阶段规则等，不另设方法学规则。
- 【已定】上游产物不注入全文，只在 `<inputs>` 列出本节点 requires 的文件路径和简要说明，并给读权限，由 agent 自己去读。
- 【已定】做法步骤 = 角色提示词（短要点）+ 技能（长步骤），目前覆盖够用。

## 一、rules（提示词）
| 层面 | 内容 |
|---|---|
| harness 目录 | 【已定】`rules/` 下平行子目录：`global/`（红线、语言、日志、知识库读取说明）、`roles/`。每个角色一个子目录 `roles/<角色>/`，内含 `prompt.md`（角色提示词）和 `access.yaml`（该角色默认读写权限，可没有，没有就用全局默认）。结构与 `specs/<交付>/` 一致。以后需要再并列新子目录。 |
| 注入 | 【已定】rules 进系统提示词（或其他提示词）。【建议】global 进系统提示词主体，role 的 prompt.md 按 agent 选一份追加。access.yaml 不进提示词，交给宿主执行（见第六节）。 |
| GUI | 【已定】agent 卡片上“角色说明”（prompt.md）和“权限”（access.yaml）分成两块显示（见第八节）。【建议】角色下拉选择，可查看/编辑文件内容。 |

## 二、specs（交付内容）
| 层面 | 内容 |
|---|---|
| harness 目录 | 【已定】每个交付内容一个目录（bom、lci 或用户自定义名），内含：交付说明提示词（`spec.md`，可空）、交付物结构 `schema.json`、检查声明 `checks.yaml`。【已定】每个交付内容先只有一套固定要求。【建议】检查的实现代码放 tools/，checks.yaml 只写 id + 参数。 |
| 注入 | 【已定】spec 首先是结构化文档，交付物要按它做结构化校验，才能判定交付或返工。【建议】spec.md + 宿主从 schema 生成的结构摘要进命名分段（如 `<deliverable_bom>`）；完整 schema 可按需读；checks 由宿主在节点结束时执行，不过就生成反馈文件、下一轮进 `<rework>`（见第五节）；审核者额外拿到检查结果，检查全过才交给审核者。以后可加“从 schema 生成的提交工具”。 |
| GUI | 【已定】用户在 GUI 设置交付内容时，填一段提示词（可空）和配套的交付物结构。【已定】spec 挂在节点层（produces），执行者和审核者共用，不在 agent 卡片里编辑。【建议】同时勾选检查、填参数；新建交付内容就是新建一个目录。 |

## 三、knowledge（知识库）
| 层面 | 内容 |
|---|---|
| harness 目录 | 【已定】`harness/knowledge/` 没有子目录，只放知识文件；计划（main_plan、revise_plan）挪到 `workspace/artifacts/plan/`。 |
| 注入 | 【已定】knowledge 是有读权限的目录，不作为提示词也不做成技能；专门写一条 rule 说明知识库内容和何时去读。 |
| GUI | 【已定】上传列表每个文件加类型按钮（知识/BOM/LCI），BOM/LCI 文件进 artifacts 对应目录（后做）。【已定】知识库默认可读，可在 GUI 中按 agent 关掉（见第六节）。 |

## 四、tools（技能 + MCP）
| 层面 | 内容 |
|---|---|
| harness 目录 | 【已定】`tools/` 只有 `mcp/` 和 `skills/`。能力型知识做成技能（`skills/<名字>/SKILL.md`），角色身份写在 rules/roles。 |
| 注入 | 【已定】每个 agent 的配置里列出 `tools: {mcp: [...], skills: [...]}`，宿主只把这些交给它。【建议】MCP 用 pi 原生 createMcpExtension，由宿主给配置、暴露方式设 direct；有技能的 agent 必须保留读文件工具。【建议】按 agent 设 MCP 工具白名单（如审核者只给 openLCA 查询类工具）。 |
| 最简起步 | 【已定】先最简：读写文件的基础工具 + openLCA MCP。【建议】openLCA MCP 先由代码编写专家导出工具清单逐个定去留：读、查、在本项目分类内建或改的保留；碰背景库、根目录或删除的去掉或由宿主拦截。旧的 artifact 相关 MCP 看清单再定。之后按顺序加：结构化校验 MCP、格式化操作 MCP、代码执行 MCP（受限 Python，只写本节点目录）。 |
| GUI | 【已定】agent 卡片“工具”块多选 MCP 和技能。 |

## 五、workflows（工作流、节点、agent）
| 层面 | 内容 |
|---|---|
| harness 目录 | 【已定】主工作流 YAML 只列节点名；节点 YAML 在 `workflows/nodes/`，含 requires、produces、inject、agents、flow、accept。工作流严格线性；节点停了整体重跑；修订模式以后再做。 |
| 注入 / 运行 | 【已定】每个节点执行者 + 审核者各一个 pi 会话，通过文件交接；审核结论为通过、送回、停止；流程表有最多轮数。开跑前预检 requires，缺失、为空或无法解析就快速失败。workspace 不设 run_id，每次开跑先清空再生成计划。写权限 = 本节点 `runs/<节点>/` + produces 对应的 artifacts 子目录，重跑时一起清空。【建议】用 agent_settled（含 aborted）判断节点结束。 |
| 返工反馈 | 【已定】三种来源统一成反馈文件：宿主检查不过、审核者送回、以后的用户修订要求。每轮一份 `runs/<节点>/feedback/round_N.md`，全部保留并写日志。下一轮开始前宿主把最新一份注入 `<rework>` 分段，并写明“只改这些问题，其他保持不变”；第 1 轮不注入。送回时执行者沿用同一个会话；节点中途停了就整体重跑、开新会话，并清掉旧反馈。用户修订模式以后做，格式相同。 |
| GUI | 【已定】预置的工作流 YAML 可在编辑器里选；流程表先写 YAML，以后再做 GUI 编辑。【已定】节点详情里按轮次查看每份反馈文件。 |

## 六、权限（access）
| 层面 | 内容 |
|---|---|
| YAML | 【已定】暂不建 `permissions/` 目录，用“默认值 + GUI 开关”。默认一律只读；写权限由 produces 自动给。agent 默认可读：计划、本节点 requires 的上游产物、自己的 `runs/<节点>/`；知识库和其他 artifacts 默认可读，可按 agent 关掉。角色 `access.yaml` 给角色默认值；GUI 中的覆盖写进节点 YAML 里该 agent 的 `access`。【建议】以后多个 agent 需要同一套特殊权限时，再抽成可复用元素。 |
| 执行 | 【已定】读和写限制都由宿主通过 pi 的 tool_call 事件拦截（同一处代码），拦截写日志；不靠提示词。需要严格隔离的 agent 不给 bash（bash 命令里的路径难拦全）。【建议】关掉的目录也不在提示词里提到。 |
| 宿主锁定 | 【已定】高于一切、任何配置都改不了：①计划永远可读；②只能写 produces 对应目录（+ 自己的 runs 目录）；③openLCA 只能在 `202606-harness-agent-LCA` 分类内改动。 |
| 工具权限 | 【建议】按 agent 设 MCP 工具白名单（如审核者只给 openLCA 查询类）。 |
| GUI | 【已定】agent 卡片“权限”块一排读写开关，默认值来自 access.yaml/全局；宿主锁定项显示为锁定、不可改。【建议】显示继承状态，改过的标“已修改”。 |

## 七、配置层级（GUI 模板的三层）
- 全局：模型和凭据、global rules、知识库读取说明、计划、日志级别、默认 access。
- 节点：requires、produces（即 spec）、节点级 rules/技能/MCP、流程表。
- agent（执行者/审核者）：模型与思考深度、role、access、tools（mcp/skills）、rules。
- 【建议】全局打底，节点追加，agent 细调；GUI 按同样层级显示和编辑。

## 八、GUI 上的 agent 卡片
【已定】从上到下：

| 顺序 | 块 | 内容 |
|---|---|---|
| 1 | 模型 | 模型 + 思考深度（thinkingLevel）。思考深度 GUI 目前没做，待办；pi 支持 thinkingLevel，注入时传入即可。 |
| 2 | 角色说明 | 角色提示词 `prompt.md` |
| 3 | 权限 | 读写开关（默认值来自 access.yaml，宿主锁定项显示锁定）；与角色说明分开两块，虽同在一个角色目录 |
| 4 | 工具 | MCP + 技能 |
| 5 | 规则 | 继承的全局规则 + 节点额外加的规则 |

- 【已定】spec 不在卡片上，挂在节点层；卡片只显示一行只读提示：执行者“交付什么”、审核者“审核什么”，点开可查看对应 spec。

## 待定问题
1. spec 注入细节（第二节【建议】部分）待确认。
2. openLCA MCP 工具清单待导出、逐个定去留。
3. MCP 工具白名单的粒度（按 MCP 还是按单个工具）。
4. 待办：GUI 模型设置加思考深度（thinkingLevel）下拉。


## Update (Commit A)
Rules, roles and specs are YAML files, not Markdown: see COMMIT_PLAN.md › Commit A.

## 九、目录重组（2026-10-22，Du Yuan 已定，I-50）
- 【已定】`harness/workflows/` 分三级子目录：`orchestrations/`（编排：节点有序列表）→ `nodes/`（节点）→ `agents/`（agent 模板：prompt / access / deliver）。
- 【已定】原 `harness/rules/roles/*.yaml` 移到 `harness/workflows/agents/`，`rules/roles/` 删除。`rules/` 只放注入的规则正文（`global/`、`lca/`），节点 `inject:` 写法不变。
- 【已定】三级都可「引用或内联」，不用 `$ref` 路径：
  - 编排 `nodes: [lca-intake, {id: bom, ...}]`：字符串 = `nodes/<名>.yaml`，对象 = 内联节点。
  - 节点 `agents: {executor: executor, reviewer: reviewer}`：字符串 = `agents/<名>.yaml`；对象含 `prompt` = 内联 agent；对象含 `agent: <名>` = 引用模板并在节点上覆盖（model、thinking、max_turns、tools、rules、access）。
  - 未知短名、内联缺字段：报错带文件和行号（能定位时）。
- 【已定】技能一律放 `harness/tools/`（LCA 规格类、编程/计算类都在这里），不建 `harness/skills/`。
- 【已定】GUI 文案「角色说明」改为「agent 说明」，只改文字，样式按 599ed0a 不变。
- 上文第一节 `rules/roles/<角色>/` 的写法以本节为准。
