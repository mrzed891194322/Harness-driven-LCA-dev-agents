"""Run a real MCP client outside pytest's plugins and shared import state."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
import tempfile
import time


def call(server, name, arguments):
    # Probe the wire protocol directly: no pytest/async client runtime, project
    # imports, private envelope, or workflow context is required by this client.
    inherited = {key: os.environ[key] for key in ("HOME", "PATH") if key in os.environ}
    with tempfile.TemporaryFile() as errors, selectors.DefaultSelector() as selector:
        process = subprocess.Popen(
            [server["command"], *server.get("args", [])],
            env={**inherited, **server.get("env", {})},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            bufsize=0,
        )
        assert process.stdin is not None and process.stdout is not None
        selector.register(process.stdout, selectors.EVENT_READ)
        pending = b""

        def send(message):
            assert process.stdin is not None
            process.stdin.write(
                (json.dumps({"jsonrpc": "2.0", **message}) + "\n").encode()
            )
            process.stdin.flush()

        def request(request_id, method, params):
            nonlocal pending
            send({"id": request_id, "method": method, "params": params})
            deadline = time.monotonic() + 10
            while True:
                while b"\n" not in pending:
                    assert selector.select(max(0, deadline - time.monotonic())), (
                        f"{method} timed out"
                    )
                    assert process.stdout is not None
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        errors.seek(0)
                        raise AssertionError(errors.read().decode())
                    pending += chunk
                line, pending = pending.split(b"\n", 1)
                response = json.loads(line)
                if response.get("id") == request_id:
                    assert "error" not in response, response
                    return response["result"]

        try:
            initialized = request(
                1,
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "independent-probe", "version": "1"},
                },
            )
            assert initialized["serverInfo"]["name"]
            send({"method": "notifications/initialized"})
            listed = request(2, "tools/list", {})
            assert name in {tool["name"] for tool in listed["tools"]}
            result = request(3, "tools/call", {"name": name, "arguments": arguments})
            assert not result.get("isError"), result
            return {
                "result": result.get("structuredContent"),
                "tools": listed["tools"],
            }
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()


if __name__ == "__main__":
    print(json.dumps(call(**json.load(sys.stdin))))
