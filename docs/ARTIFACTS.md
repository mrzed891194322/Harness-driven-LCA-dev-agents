# 运行产物与调试记录

本文说明每次运行在 `.local/runs/<run_id>/` 下留下什么，以及怎么查。`.local/` 已在 `.gitignore` 里，`workspace` 清理（`whole-lca` 等预设）不碰它，所以这些记录按运行保留。

## 目录

```text
.local/runs/<run_id>/
  events.jsonl               Pi 活动事件 + 编排器事件（含 injection_check / injection_summary）
  injection-summary.json     运行结束时写：会话数、最差等级、全部 mismatch 列表
  pi/<session_key>.mcp.log   MCP 子进程日志
  pi/<session_key>.guard.jsonl  路径守卫记录（拦截与越界）
  sessions/<stage>.<role>.<attempt>/
    prompt.md                最终拼好的完整提示词；每段前有注释：来源文件、默认版/用户版、哈希
    spec.json                作为首段上下文注入的 get_spec() 结果
    tools.json               pi-runtime 反报的、实际暴露给模型的工具名和 schema
    permissions.json         本会话生效的路径与工具白名单
    launch.json              模型、MCP 配置、环境变量名（只有名字）、各项哈希
    transcript.jsonl         完整对话记录（见下）
    transcript.blobs/        单条超过 1 MB 的记录全文
    injection/
      intended.json          宿主打算注入的内容
      effective.json         pi-runtime 从 SDK 真实状态读回的内容
      diff.json              逐项比对结果
      first_request.json     第一次请求模型时的实际 payload（脱敏），以及是否含注入的 system prompt
```

同一个 assignment 在一次运行里复用一个 Pi 会话；返工时（attempt 2、3…）会建新的会话目录，transcript 里早于本 attempt 的记录标 `scope: "earlier_attempt"`。

## 注入清单

- **intended.json（宿主）**：system prompt 全文和哈希；分段 `segments`（`spec_context`、运行协议、运行上下文、每条规则、提交说明、生成式提示词、知识资料），每段写明来源、`origin`（`builtin` / `runtime` / `default` / `user` / `generated`）、文件哈希和内容哈希；首条 user 提示词（第一轮开始时补上）；模型和参数；权限；工具白名单；MCP 配置（环境变量只写名字）；skills；extensions。分段正是 `build_prompt` 实际拼出的段落，按空行连接就是发出去的提示词（有测试保证）。
- **effective.json（pi-runtime）**：会话建好、第一次调模型之前，从 SDK 读：生效的 system prompt 全文（含 SDK 自己加的部分）、实际模型、工具名和 schema、MCP 工具是否注册及 exposure、已加载的 skills/extensions、路径守卫钩子是否挂上、首请求钩子是否挂上。mock 模式下 `captured: false`，不会伪造。
- **first_request.json**：SDK 的 `before_provider_request` 钩子在第一次请求模型时记录 payload（脱敏）。记录的是本项目扩展看到的 payload，排在后面的扩展若再改，不在其中。
- **diff.json**：逐项比对，分 `ok` / `warn` / `mismatch`。计划了但没生效、生效了但不在计划里、哈希对不上，都会列出。关键项：模型、spec_mcp 工具、路径守卫钩子。SDK 在注入内容前后追加的文字记为 `ok / sdk_added`。

**策略**：默认只记录、不中断。设置 `HARNESS_INJECTION_STRICT=1` 时，关键项 mismatch 会让会话启动失败；这个开关给测试和 doctor 用。已有硬拦截（如 MCP 工具等待 90 秒超时）不变。

**暂停后恢复**：恢复时若运行指纹（规则、模板、偏好、spec、实现代码）变了，默认不拒绝，在 `events.jsonl` 记一条 `injection_check`（`phase: resume`，`level: warn`），逐项列出变化的指纹路径和新旧值，然后按新配置继续；旧的 `runtime-config.json` 改名为 `runtime-config.prev-<n>.json`。严格模式下仍拒绝。worker 或模型变化、运行配置缺失，照旧拒绝。

## transcript.jsonl

由 pi-runtime 从 Pi SDK 自己的会话文件（`SessionManager.open` 写的 JSONL）导出，再补上只有实时事件流知道的内容；不从 `events.jsonl` 摘要拼凑。每轮结束和会话释放时重新导出。每行一个对象，`type` 为：

| type | 内容 |
|---|---|
| `header` | Pi 会话头 |
| `system` | 实际生效的 system prompt 全文 |
| `message`（user） | 全文 |
| `message`（assistant） | 文本、thinking（提供方返回时）、工具调用（完整参数）、provider/model、token（输入、输出、缓存读写）、耗时、停止原因、错误 |
| `tool_result` | 工具名、调用 id、完整结果、是否出错、耗时 |
| `entry` | 其他 SDK 条目（模型切换、压缩等）原样保留 |
| `turn` | 每轮开始/结束时间、耗时、状态、错误 |
| `retry` | SDK 自动重试的开始/结束 |
| `summary` | 消息与工具调用计数、模型、总 token 和本 attempt 的 token、交卷结果（handoff 的 status） |

超过 1 MB 的记录写进 `transcript.blobs/NNNN.json`，jsonl 里只留带 `blob` 和 `bytes` 的引用。

## 脱敏

所有快照写盘前统一脱敏：键名像密钥的字段（key、token、secret、password、authorization、signing…）直接替换；已知密钥值（敏感环境变量、MCP 环境里的 token、`.local/run/spec_mcp.key`、`.local/credentials/*.json` 里的值、`.env` 里的敏感项）和常见 token 模式（`sk-…`、`Bearer …` 等）在全文里替换为 `[REDACTED]`。有测试在环境里放假密钥和签名密钥，确认所有快照文件里都搜不到。

## 怎么查

- 命令行：
  - `npm run inspect` 列出所有运行；`npm run inspect -- <run> [--only-anomalies]` 按会话列注入异常；`npm run inspect -- <run> <stage.role.attempt>` 看单个会话的全部比对项和文件。
  - `npm run session -- <run>` 列出会话；`npm run session -- <run> <stage.role.attempt> [-o out.md] [--full]` 导出一份可读的 Markdown（注入、模型、完整对话），方便别的 agent 接手调试。
  - `npm run doctor`：检查生成式提示词模板能否渲染，并对正在运行的 pi-runtime 做一次空会话自检（只建会话、不调模型，比对后释放）。`--skip-runtime` 只查模板。
- GUI：运行详情页下方选运行（有异常的标 ⚠，并显示“注入异常”标记）；“注入”标签页按会话对照计划注入和实际生效，差异标红；“会话”标签页列出快照文件，可查看、下载，也可查看或下载完整对话的 Markdown。
- 接口：`GET /api/runs`、`GET /api/runs/{run}/sessions`、`GET /api/runs/{run}/sessions/{session}/injection`、`GET /api/runs/{run}/sessions/{session}/file?name=&download=`、`GET /api/runs/{run}/sessions/{session}/markdown?download=`。

## 生成式提示词

`harness/rules/generated/*.md.tmpl` 每次建会话现场渲染（见 `harness/rules/README.md`）。预览接口 `GET /api/prompts/generated/preview?stage=&role=` **只支持 `harness/LCA-main.yaml` 里的阶段**（修订工作流 `LCA-revise.yaml` 暂不支持）。
