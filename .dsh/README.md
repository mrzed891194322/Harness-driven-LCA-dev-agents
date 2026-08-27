# 项目级 DSH 配置（仿照 .codex/）

本目录存放本项目在 DeepSeek Harness（DSH，CLI：`dsh`）中的项目级配置，与
`.codex/` 的 Codex 配置、`.opencode/`、`.claude/` 互为镜像：

| Codex | DSH |
|---|---|
| `.codex/config.toml`（`[mcp_servers.control_openlca]`） | `.dsh/cordis.patch.yml`（`mcp-control_openlca` 行） |
| `.codex/agents/*.toml`（角色 adapter） | `.dsh/agent-presets/lca/`（顶层会话 persona）+ `harness/roles/*.md`（角色语义唯一来源，子 agent 由委派 prompt 指定角色并要求先读对应文件） |
| `.codex/skills/`（`$whole-lca` 等） | `.dsh/skills/`（whole-lca / revise-lca / bootstrap-env，自动发现） |

DSH 与三平台的关键差异：没有 `$whole-lca` / `/whole-lca` 这类自动展开的
command，也没有 `--agent major-orchestrator` 式的命名 agent；无人值守入口是
`dsh --profile headless "<任务文本>"`，子 agent 用 `subagent` 工具生成并在
prompt 中写明角色。

## 目录结构

```
.dsh/
├── cordis.patch.yml          # 项目级补丁层（权威源，提交进版本库）
├── skills/                   # 技能（DSH 技能根 rank 100，自动发现，无需配置）
│   ├── whole-lca/SKILL.md    # 与 .codex/skills/whole-lca 同源，平台段为 DSH 版
│   ├── revise-lca/SKILL.md
│   └── bootstrap-env/SKILL.md
└── agent-presets/
    └── lca/                  # 项目 agent preset（复制自发行版 standard 并定制 persona）
```

## 一行 CLI（正式入口）

在仓库根目录执行（`--patch` 等 launcher 标志必须在任务文本之前）：

```bash
# 环境引导
DSH_PERMISSION_MODE=danger-full-access dsh --profile headless --patch .dsh/cordis.patch.yml "读取并执行 .dsh/skills/bootstrap-env/SKILL.md"

# whole-lca / revise-lca
DSH_PERMISSION_MODE=danger-full-access dsh --profile headless --patch .dsh/cordis.patch.yml "读取并执行 .dsh/skills/whole-lca/SKILL.md"
DSH_PERMISSION_MODE=danger-full-access dsh --profile headless --patch .dsh/cordis.patch.yml "读取并执行 .dsh/skills/revise-lca/SKILL.md"
```

「加载并执行 whole-lca 技能」是等价的任务文本写法。任务文本直接读文件是主形式，
不依赖模型额外选择技能工具。

`DSH_PERMISSION_MODE=danger-full-access` 是无人值守必需：DSH 默认
`workspace-write` 沙箱把 `~/.cache` 只读挂载，`uv run` 初始化缓存即失败，且默认
`ask` 审批在无交互时 fail-closed。该模式等价于 codex 的 auto-approve 与
claude 的 `--permission-mode dontAsk` 姿态；LCA 状态机本身不征求用户决定。

## 生效方式（二选一，勿同时）

- **headless（当前唯一激活路径）**：启动时传入 `--patch .dsh/cordis.patch.yml`，
  不写任何 `~/.dsh` 配置。headless 树没有 `agent-presets` 行，补丁中该行被
  「告警并跳过」，属预期；headless 不需要 preset 名单（工具全部来自 base 组合）。
- **web/GUI（暂不启用）**：按 GUI 冻结要求当前不做。日后启用时，把本补丁同样
  的行写入 `~/.dsh/profiles/web/cordis.patch.yml`（会替换其中 Blender 项目的行，
  属既有单项目同步约定），或 `dsh web --patch .dsh/cordis.patch.yml`。

同时使用两者会让 `insert` 的行重复进组合树。

## 已配置内容

### control_openlca MCP（与 `.codex/config.toml` 等价）

```yaml
- insert:
    - id: mcp-control_openlca
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: control_openlca
        transport: stdio
        command: /home/yuandu/.local/bin/uv
        args: [run, python, harness/tools/control_openlca/main.py]
        cwd: /home/yuandu/Programming/202606-harness-agent-LCA
        toolCallTimeoutMs: 300000
```

模型侧工具名为 `mcp__control_openlca__<rawName>`（如
`mcp__control_openlca__health_check`）。包 `@deepseek-ai/dsh-mcp-client` 是 dsh
安装自带的依赖闭包成员，经扁平回退 `~/.dsh/profiles/node_modules` 解析，无需
`dsh plugin` 安装。故意不设 `failOnStartupError: true`：openLCA IPC 未开时由
workflow 把 `health_check` 失败写入 manifest，而不是整进程 boot 失败。

### Agent preset 名单追加项目根

`agent-presets` 行的 `roots` 追加 `.dsh/agent-presets`（`trust: user`），默认
preset 保持 `standard`。web 会话 chip 中可选「LCA 编排」；该 preset 的 persona
只做项目定位，`major-orchestrator` 角色声明由技能文件在 workflow 启动时给出。

### 技能

`.dsh/skills/` 是 DSH 官方优先扫描的项目技能根（rank 100），自动发现。三个技能
与 `.codex/skills/{whole-lca,revise-lca,bootstrap-env}` 同源：业务契约完全相同，
仅平台运行时段为 DSH 版。修改任一侧后需同步另一侧。

## 前置条件（用户侧，只写文档、不代装）

- PATH 上有 `dsh`（Node ≥ 22）；凭证已配置（`DEEPSEEK_API_KEY` 或
  `~/.dsh/.credentials.yaml`，DSH 自身管理，不写进仓库）。
- 首次运行 headless 会自动初始化 `~/.dsh/profiles/headless/`（用户家目录）。
- whole-lca / revise-lca 还需 openLCA 桌面端 + IPC Server（见 `README.md`）。

## 校验命令

```bash
dsh --profile headless --patch .dsh/cordis.patch.yml --dump-config | grep -n mcp-control_openlca
dsh --profile web --dump-config | grep -n agent-presets        # 组合基线（不含本补丁时）
dsh plugin --profile headless why @deepseek-ai/dsh-mcp-client  # 解析来源（可选）
```
