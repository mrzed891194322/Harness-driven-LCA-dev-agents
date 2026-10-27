# Serve / dev worktrees

Live services must never read files that are being edited.

| Worktree | Path (under the main repo) | Checkout | Purpose |
| --- | --- | --- | --- |
| dev | `.local/wt/202606-harness-agent-LCA` | branch `refactor/harness-v5-minimal` | editing, commits, pytest |
| serve | `.local/wt/serve/202606-harness-agent-LCA` | detached HEAD at a tested commit | runs backend / pi-runtime / web on 8800 / 3000 |

Both folders are named `202606-harness-agent-LCA`; the openLCA category is a constant anyway (`category.py`).

## Create / update serve

```bash
cd <main repo>
git worktree add --detach .local/wt/serve/202606-harness-agent-LCA refactor/harness-v5-minimal
S=.local/wt/serve/202606-harness-agent-LCA
ln -s ../../../../node_modules $S/node_modules; ln -s ../../../../.venv $S/.venv   # shared deps, read-only use
# runtime files: copies, not links
cp config.toml $S/config.toml; mkdir -p $S/.local
# credentials: MERGE only — never `cp -r .local/credentials` over serve.
# Panel BYOK writes into the serve worktree; a blind copy from main would wipe
# providers (e.g. google) that only exist there. See I-63.
node src/scripts/merge_serve_credentials.mjs --source .local/credentials --target $S/.local/credentials
cp .local/workflow-models.json .local/model_profiles.json $S/.local/
cp harness/knowledge/inputs/<reference files> $S/harness/knowledge/inputs/
cp workspace/artifacts/plan/main_plan.md $S/workspace/artifacts/plan/
(cd $S/src/pi-runtime && npm run build)
```

**切 tip / 更新 serve 时必须 merge 凭证，禁止整目录覆盖 `pi-auth`。** 一律用
`node src/scripts/merge_serve_credentials.mjs`（默认源/目标即上表路径；可用
`--source` / `--target` 覆盖）。脚本会：保留目标已有 provider；只补目标缺失的；
保留目标多出来的 marker（如 `google.json`）；`pi-agent/` 仅在目标没有时复制。

Update to a newer commit (only when no run is live): `npm run stop` in serve, then in serve
`git checkout --detach <commit>`, rebuild pi-runtime, **re-run the merge script above**
(do not `cp -r` credentials), start again.

## Start / stop

`npm run dev` / `npm start` / `npm run stop` **default** to a short Unix socket under the main
repo when started from a nested worktree (serve → `<main>/.local/run/pi-v5serve.sock`; other
long `.local/wt/...` checkouts → `<main>/.local/run/pi-runtime.sock`). You no longer need to
export `PI_RUNTIME_SOCKET` for the usual serve path. An explicit `PI_RUNTIME_SOCKET` still
overrides that default.

```bash
cd .local/wt/serve/202606-harness-agent-LCA
npm run dev      # start; check curl --noproxy '*' localhost:8800/api/health
npm run stop     # stop (same default short socket)
# optional override:
# export PI_RUNTIME_SOCKET=<main repo>/.local/run/pi-v5serve.sock
```

Before stopping or switching: `GET /api/workflow/status` must not be `running`, and no GUI test may be in progress.

## Switch back to the main repo services

`npm run stop` in serve, then `npm run dev` in the main repo, check `/api/health`.

## Cleanup

Copied secrets live in `serve/.local/credentials/`, `serve/config.toml` and, per session, `serve/workspace/tmp/pi-workflow/*/agent/auth.json`;
the dev worktree holds the same copies. Remove them when the worktrees are retired (`git worktree remove`
without force after deleting untracked copies; never `rm -r` through the `node_modules` / `.venv` links).


## Alternate ports (second stack)

To smoke another checkout without taking 8800/3000 from serve:

```bash
GUI_API_PORT=8810 GUI_WEB_PORT=3010 npm run dev
```

Env vars override `config.toml` `[gui]`. See `docs/ops/WORK_LOG_AND_ALT_PORTS.md`.
