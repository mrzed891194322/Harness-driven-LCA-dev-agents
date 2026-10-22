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
cp .env $S/.env; mkdir -p $S/.local; cp -r .local/credentials $S/.local/
cp .local/workflow-models.json .local/model_profiles.json $S/.local/
cp harness/knowledge/inputs/<reference files> $S/harness/knowledge/inputs/
cp workspace/artifacts/plan/main_plan.md $S/workspace/artifacts/plan/
(cd $S/src/pi-runtime && npm run build)
```

Update to a newer commit (only when no run is live): `npm run stop` in serve, then in serve
`git checkout --detach <commit>`, rebuild pi-runtime, start again.

## Start / stop

The worktree path is too long for a Unix socket, so always set `PI_RUNTIME_SOCKET` (inside the project):

```bash
cd .local/wt/serve/202606-harness-agent-LCA
export PI_RUNTIME_SOCKET=<main repo>/.local/run/pi-v5serve.sock
npm run dev      # start; check curl --noproxy '*' localhost:8800/api/health
npm run stop     # stop (same PI_RUNTIME_SOCKET)
```

Before stopping or switching: `GET /api/v5/status` must not be `running`, and no GUI test may be in progress.

## Switch back to the main repo services

`npm run stop` in serve (with its `PI_RUNTIME_SOCKET`), then `npm run dev` in the main repo, check `/api/health`.

## Cleanup

Copied secrets live in `serve/.local/credentials/`, `serve/.env` and, per session, `serve/workspace/tmp/pi-v5/*/agent/auth.json`;
the dev worktree holds the same copies. Remove them when the worktrees are retired (`git worktree remove`
without force after deleting untracked copies; never `rm -r` through the `node_modules` / `.venv` links).
