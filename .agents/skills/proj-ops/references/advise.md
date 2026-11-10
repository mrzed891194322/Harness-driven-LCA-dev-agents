# 怎么诊断使用中的问题

工作目录是仓库根。只诊断，不改代码，不打开或关闭项目，不替用户执行 LCA。先读日志，再查 openLCA。两边都做完再写建议。不要粘贴密钥，不要粘贴整份 JSON，不要改 `.env`。

面板打不开、要启动或关闭时，改读同目录的 [process.md](process.md)。

## 工作记录（优先）

工作流跑挂或结果不对时，**先**看 `workspace/runs/_run/work-record.md`（及同目录 `events.jsonl`）：步数、各 agent 注入 planned vs actual、逐步事件。GUI 在「结果浏览 → 工作记录」。详见 `docs/ops/WORK_LOG_AND_ALT_PORTS.md`。

## 后端日志

读 `.local/logs/backend.log` 的末尾约 80 行。用户指出了某句报错或某个时间时，在这份日志里搜那一句，往上看到该错误的开头。

日志不存在或末尾没有新的报错时，照实写明。不要改去读 `.local/logs/web.log` 或 `pi-runtime.log`，除非后端日志里点名了那一项。

从日志里只摘错误原因：异常类型、失败的操作、openLCA 或 IPC 相关的那一句。路径、数据库名可以写。密钥、令牌、请求头不要写。

## openLCA

后端能连上时，请求诊断接口，只看 `openlca`：

```bash
curl -sS "http://127.0.0.1:${GUI_API_PORT:-8800}/api/diagnostics/environment"
```

`GUI_API_PORT` 以仓库根 `.env` 为准，没有就用 `8800`。接口失败时写明后端没有响应，不要为此去启动项目。

`openlca.status` 只有三种：

| 状态 | 含义 | 建议 |
| --- | --- | --- |
| `ok` | IPC 已连上。`database` 有值时写出当前数据库名 | 问题不在「openLCA 没开」。按后端日志里的报错说明下一步 |
| `busy` | 本仓库的 IPC 互斥锁或不确定标记占用中（清理 / 导入 / 计算，或残留的 `.uncertain`），**不是**「TCP 端口有人在听」 | 有进行中的写入时等它结束；确认没有操作却仍 busy 时，可重启控制面板后再查；不要再开一次写入或清理 |
| `down` | 连不上 `host:port`（默认 `127.0.0.1:8080`，以返回的 `host`、`port` 为准） | 打开 openLCA，在偏好设置里启用 IPC Server，并确认端口与诊断结果一致 |

`down` 不表示控制面板没有启动。

## 建议怎么写

用中文，短，只依据上面拿到的日志和 `openlca` 状态：

- 发生了什么：日志里的那一句错误，加上 openLCA 状态
- 这说明什么
- 用户可以做什么：一到三条，每条是用户自己能做的动作

日志和 openLCA 对不上时，两件事都写上，不要只选一边。看不出原因时写明还缺哪一段日志，不要编原因。
