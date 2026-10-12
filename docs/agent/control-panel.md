# 控制面板进程

任意 agent 在本仓库启动、重启、关闭或诊断 Web 控制面板时，只执行本文命令。工作目录是仓库根目录。

`npm start` 与 `npm run dev` 把后端、唯一的 pi-runtime、前端放到后台后，自己打印 `Ready.` 并退出。关掉终端不会停这些服务。停止只用 `npm run stop`。

## 禁止

- 不要手写 `uvicorn`、`next dev`、`node src/pi-runtime/dist/main.js`，也不要再起一个 pi-runtime。整个项目只有一个。
- 不要加 `--foreground` 或 `-f`。前台进程绑在当前终端上，agent 结束会话时可能把服务一起停掉。
- 不要设置 `PI_RUNTIME_MOCK` 或 `PI_RUNTIME_PRIVATE`。控制面板应打印 `mode=real`。
- 不要 `POST /api/workflow/start`，不要替用户点「执行LCA任务」。那会清理工作区并开始一次 LCA。
- 不要把 `.env`、`.local/credentials/` 里的密钥写进回复、日志或提交。
- 上一次启动或重启还在同步、构建时，不要再开一次。

## 先判断

启动、重启、关闭或诊断之前，先跑只读状态。它不启动也不停止。

```bash
npm run status
```

看第一行 `status=`。三种结果退出码都是 0，不要把 `partial` 或 `stopped` 当成命令失败。

- `status=ready`：后端、pi-runtime、前端都在，并且 API 健康检查是 `ok`。同一段输出里有 `web=`、`api=`、`endpoint=` 和各服务 pid。
- `status=partial`：还有进程，或 API 有响应但三个服务不齐。常见是只剩 pi-runtime。
- `status=stopped`：没有在运行。

| 用户要 | `ready` | `partial` | `stopped` |
| --- | --- | --- | --- |
| 启动 | 不要再启动。回报 `web=`、`api=`、`endpoint=` | 先 `npm run stop`，再 `npm start` | `npm start` |
| 重启 | `npm run restart` | `npm run restart` | `npm start` |
| 关闭 | `npm run stop` | `npm run stop` | 回报「没有在运行」 |
| 诊断 | 按文末诊断步骤，不要停服务 | 按诊断步骤，不要为了诊断去启动 | 按诊断步骤，不要为了诊断去启动 |

`partial` 时不要直接 `npm start`。旧的 pi-runtime 还在，脚本会拒绝，以免叠出第二个。`npm run stop` 应打印 `stopped.`。停完再跑一次 `npm run status`，确认变成 `status=stopped` 后再启动。若仍是 `partial`，按「没有正确启动」告诉用户，不要继续启动。

用户明确说不要重新安装依赖时，把表里的 `npm start` 换成 `npm run dev`（不同步依赖、不构建，其余相同）。默认用 `npm start`。

## 怎么等

`npm start` 和 `npm run restart` 会先同步 uv 与 npm 依赖并构建 pi-runtime。冷启动可能超过 10 分钟（两步同步各有 5 分钟上限）。把命令放在后台，持续看输出，直到出现下面之一：

- `Ready.`：成功。同一段输出里有 `mode=real` 或 `mode=mock`、web / api / pi-runtime 地址，以及各服务的 pid 和日志路径。接着做「启动之后核对」。
- 进程非 0 退出，或没有 `Ready.`：没有正确启动。按「没有正确启动」排查后再告诉用户，不要只说失败了。
- `already running`、`already in use`、`already listening`：已经有一份。不要重启，除非用户要的就是重启。

`npm run stop` 很快。成功是 `stopped.` 或 `nothing was running.`。

## 启动之后核对

再跑一次 `npm run status`。期望 `status=ready` 且 `health=ok`。把 `web=`、`api=`、`endpoint=` 回报用户。

日志在 `.local/logs/backend.log`、`.local/logs/pi-runtime.log`、`.local/logs/web.log`。

输出是 `mode=mock` 时照实回报：当前环境设置了 `PI_RUNTIME_MOCK=1`，这次不会调真实模型。不要擅自改环境变量。

健康检查失败、某个 pid 已退出，或页面地址打不开，都算没有正确启动，按下节排查。

## 没有正确启动

先查出停在哪一步，再告诉用户。不要只说「启动失败」，也不要改用 `uvicorn`、`next` 或第二个 pi-runtime 重试。

对照启动输出，停在下面哪一步：

| 输出或现象 | 问题在 |
| --- | --- |
| `Node.js 22+ is required` | 本机 Node 版本低于 22 |
| `uv was not found` | 未安装 uv，或不在 PATH 里 |
| `uv sync timed out`、`npm install timed out`，或同步、安装非 0 退出 | 依赖下载或安装。超时说明里若有更换下载源的提示，一并告诉用户 |
| `Building pi-runtime` 之后非 0，或 `pi-runtime is not built` | pi-runtime 构建 |
| `请检查是否将Git for Windows安装在默认路径` | Windows 上找不到 Git for Windows 的 `bash.exe` |
| `already running`、`already in use`、`already listening` | 已有一份控制面板，或 web / api 端口被占用。读 `.env` 里的端口。不要再启动 |
| `backend`、`pi-runtime` 或 `web` 出现 `exited during startup` 或 `not ready` | 这一级服务没起来。读 `.local/logs/` 下同名日志的末尾 |
| 已有 `Ready.`，但 `npm run status` 不是 `status=ready` | 进程刚退出，或看错端口。读 `status` 列出的 pid，并读三个日志的末尾 |
| `pi-runtime still running after stop` | 重启时旧的 pi-runtime 没停干净。不要手动再起一个 |

排查只做这三件事：看启动命令的完整输出、`npm run status`、失败那一级日志的末尾约 40 行。不要粘贴密钥。

告诉用户时写清三件事：停在哪一步、依据是哪一句输出或哪一个日志、需要用户处理什么。openLCA 连不上、模型或密钥未就绪，不阻止控制面板打开；这两项在诊断里单独说，不要当成启动失败的原因。

## 关闭

```bash
npm run stop
```

顺序是后端、pi-runtime、前端，然后清本仓库残留进程。不要按 pid 用 `taskkill` 或 `kill` 拆开停。停完再跑 `npm run status`，期望 `status=stopped`。

`npm run restart` 若打印 `pi-runtime still running after stop`，不要手动再起 runtime。把这句话和 `npm run status` 的结果一起回报。

## 诊断

不启动、不停止、不重启，除非用户的原话同时要求。

1. `npm run status`：面板是就绪、残缺，还是没在运行。诊断本身不要因此去停服务。
2. API 能连上时，请求 `http://127.0.0.1:<GUI_API_PORT>/api/diagnostics/environment`。只摘要 `ok` 不为真的项：`node`、`pi_agents`、`python_agent`、`openlca`、`model`、`harness_specs`。`openlca.status` 为 `busy` 时写明数据库正忙。不要粘贴整份 JSON。
3. pi-runtime 在跑时执行 `npm run doctor`（空会话自检，不调模型）。没在跑就执行 `npm run doctor -- --skip-runtime`，并写明注入自检被跳过。出现 `✗` 时附上脚本打印的那几行。
4. 用户问的是某一次运行的注入或会话时，再用 `npm run inspect -- <run> --only-anomalies`。普通诊断不要翻 `.local/runs/`。
5. 健康检查失败或进程已退出时，只读上述三个日志的末尾约 40 行，摘出错误原因。

## 回报

用中文，短：

- 做了哪一个动作（启动 / 重启 / 关闭 / 诊断）
- 结果：就绪、已在运行、已停止；没有正确启动时写明停在哪一步、依据和需要用户处理什么
- `mode`、页面地址、API 地址、pi-runtime 地址
- 诊断里未通过的项
- 失败时的日志路径
