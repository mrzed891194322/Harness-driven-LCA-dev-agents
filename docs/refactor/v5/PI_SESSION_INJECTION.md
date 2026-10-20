# pi 1.3.0 单个会话可注入内容（依据：@earendil-works/pi-coding-agent@1.3.0 包内文档与源码）

| 注入项 | 怎么注入（SDK） | 替换/追加 | 生效时机 | 中途可改 | 续跑 |
|---|---|---|---|---|---|
| 系统提示词主体 | DefaultResourceLoader.systemPromptOverride / systemPrompt；SYSTEM.md 也会替换 | 只替换开头 preamble，追加、上下文文件、技能、cwd 仍接在后面 | 创建时 | before_agent_start 可每轮改 | 记录回放 |
| 追加提示词 | appendSystemPromptOverride / appendSystemPrompt；默认读 APPEND_SYSTEM.md | 追加（addendum 段） | 创建时 | 同上 | 记录回放 |
| 命名分段 | 扩展 before_agent_start 改 sections，渲染为 <名字>…</名字> | 新增/替换分段 | 每轮开始前 | 是 | 差异写进记录并回放 |
| AGENTS.md/CLAUDE.md | 自动从 cwd 往上找到根目录，不受项目信任控制；noContextFiles 或 agentsFilesOverride（可给虚拟文件） | 追加（project_context 段） | 创建或 reload | reload | — |
| 技能 | SKILL.md 目录；skillsOverride / additionalSkillPaths / noSkills | 提示词里只列 name/description/路径，全文由模型自己读（需要 read 或 bash 工具） | 创建时 | reload | — |
| 提示词模板 | promptsOverride / additionalPromptTemplatePaths | 不进系统提示词，prompt("/名字") 时展开 | 调用时 | — | — |
| 扩展 | extensionFactories 等；需 bindExtensions() | 可挂事件：tool_call 拦截、tool_result、agent_settled、agent_before_settle 等 | session_start | 是 | 扩展状态需自己 appendEntry |
| 自定义工具 | customTools 或 pi.registerTool | promptSnippet/promptGuidelines 会进提示词 | 创建时 | 是 | — |
| 内置工具白名单 | createAgentSession({tools, excludeTools, noTools}) | — | 创建时 | setActiveToolsByName，下一轮生效 | 恢复记录里的工具，显式传 tools 时以传入为准 |
| MCP | createMcpExtension({loadConfig}) 或 registerMcpServer；toolExposure 设 direct | 默认 codemode，模型看不到工具 | session_start 后台连接，首次 prompt 只等 direct 最多 10 秒 | 可注册/注销 | 不恢复，每次重新注册 |
| 模型/思考强度 | createAgentSession({model, thinkingLevel}) | — | 创建时 | setModel / setThinkingLevel | 记录回放 |
| 凭据 | ModelRuntime.create / setRuntimeApiKey | — | — | — | — |
| settings | SettingsManager.inMemory 或 create(..., {projectTrusted}) | 默认信任项目 | 创建时 | 多数需 reload | — |
| 首轮前消息 | SessionManager.inMemory(cwd, opts, entries) 或 sendCustomMessage({triggerTurn:false}) | — | 首轮前 | steer / followUp | — |

## 为了可复现，宿主要主动关掉
- agentDir 不用默认的 ~/.pi/agent，换成项目专用目录。
- SettingsManager.inMemory，或 projectTrusted:false，挡住 .pi/ 下的配置、MCP、扩展、技能。
- noContextFiles（或 agentsFilesOverride 精确给）、appendSystemPromptOverride 返回空、skillsOverride/promptsOverride 只给 harness 的、noExtensions 或筛选。
- MCP 用 loadConfig 由宿主给，不读 mcp.json；显式传 tools 和 model。
- 最彻底：自己实现 ResourceLoader（examples/sdk/12-full-control.ts）。

## 【建议】与 harness 五层的对应
- rules：系统提示词主体或追加提示词（固定总规则）。
- specs：before_agent_start 的命名分段，按节点注入，执行者和审核者各一套。
- knowledge：短的必读内容做虚拟上下文文件；长资料做成技能，按需读。
- tools/skills：skillsOverride 只给本节点技能（要保留 read 或 bash 工具）。
- tools/MCP：createMcpExtension({loadConfig}) + direct + tools 白名单。
- workflows：宿主本身；agent_settled 判结束，tool_call 拦越权写，agent_before_settle 做产出检查。

未证实：SessionManager.inMemory 的 entries 规范构造方式；新 loader 续跑时分段差异的实际表现（需实测）。
