from harness.tools.mcp.submit.schemas import _norm


def test_norm_strips_artifact_prefixes():
    for p in ("bom/claims.json", "workspace/artifacts/bom/claims.json", "artifacts/bom/claims.json",
              "workspace/runs/_run/artifacts/bom/claims.json", "runs/_run/artifacts/bom/claims.json",
              "./bom/claims.json", "./workspace/artifacts/bom/claims.json", "/bom/claims.json/"):
        assert _norm(p, "") == "bom/claims.json"
    assert _norm("/r/out/bom/claims.json", "/r/out") == "bom/claims.json"
