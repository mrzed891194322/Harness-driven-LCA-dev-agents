# control_openlca MCP tests

Run the offline test suite from the repository root:

    uv run python -m unittest discover -s harness/tools/control_openlca/tests -v

The tests mock the openLCA IPC client and validate endpoint handling, health diagnostics,
descriptor filtering, pagination, MCP annotations, read-only preflight behavior, hash gates,
structured import failures, ProductSystem auto-linking, model-graph checks, and calculation-handle disposal without
requiring a running openLCA instance.
