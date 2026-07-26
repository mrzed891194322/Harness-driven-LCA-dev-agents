# control_openlca MCP tests

Run the offline test suite from the repository root:

    uv run python -m unittest discover -s harness/tools/control_openlca/tests -v

The tests mock the openLCA IPC client and validate endpoint handling, health diagnostics,
descriptor filtering, compact Process/Flow Provider reads, pagination, MCP annotations,
canonical and temporary LCI path guards, read-only preflight behavior, hash gates, structured
import failures, bounded health probes with three reconnects, ProductSystem
`auto + defaultProvider` linking, exchange direction validation, model-graph checks,
and calculation-handle
disposal without requiring a running openLCA instance.
