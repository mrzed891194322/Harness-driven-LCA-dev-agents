# control_openlca MCP tests

Run the offline test suite from the repository root:

    uv run python -m unittest discover -s harness/tools/control_openlca/tests -v

The tests mock the openLCA IPC client and validate endpoint handling, health diagnostics,
descriptor filtering, pagination, structured errors, MCP tool registration, and environment
configuration without requiring a running openLCA instance.
