# Cleanup Output Entities (cleanup_output)

This tool deletes entities created under an openLCA project category through the IPC Server. By default it uses the current working directory name as the project category and only targets:

- `ProductSystem`
- `Process`
- `Flow`

The script runs in preview mode by default. Add `--yes` to execute deletion after reviewing the matched entities.

## Usage

Preview entities under the default project category:

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py
```

Delete product systems, processes, and flows under the default project category:

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py --yes
```

Specify a project category:

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py --project 202606-Multi-agent-LCA --yes
```

Also delete `FlowProperty` and `UnitGroup` entities under the same category:

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py --include-supporting --yes
```

Specify the IPC Server endpoint:

```bash
uv run python harness/tools/control_openlca/cleanup_output/main.py --host 127.0.0.1 --port 8080
```

## Arguments

- `--project` / `-P`: openLCA project category to clean up. Defaults to the current working directory name.
- `--host` / `-H`: openLCA IPC Server host. Default: `127.0.0.1`.
- `--port` / `-p`: openLCA IPC Server port. Default: `8080`.
- `--include-supporting`: also delete `FlowProperty` and `UnitGroup` entities under the same category.
- `--yes`: confirm deletion. Without this flag, the script only previews matching entities.
