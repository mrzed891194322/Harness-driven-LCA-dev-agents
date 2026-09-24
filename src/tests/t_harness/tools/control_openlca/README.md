# control_openlca MCP tests

Run the offline test suite from the repository root:

    uv run pytest src/tests/t_harness/tools/control_openlca -v

The tests mock the openLCA IPC client and validate endpoint handling, health diagnostics,
descriptor filtering, compact Process/Flow Provider reads, pagination, MCP annotations,
canonical and temporary LCI path guards, read-only preflight behavior, hash gates, structured
import failures, bounded health probes with three reconnects, ProductSystem
`auto + defaultProvider` linking, exchange direction validation, model-graph checks,
long timeouts for provider and cleanup scans, IPC tool profiles with session-following
HTTP reads, fail-closed cleanup scope collection,
and calculation-handle disposal without requiring a running openLCA instance.

V2 tests additionally cover explicit request/preflight receipts, stale content rejection,
cross-process locks, uncertain endpoint probes, bounded envelopes and file integrity,
batch scan deduplication, profile invalidation and same-run report-only reuse.
All tests use temporary workspaces; no live database is modified.
