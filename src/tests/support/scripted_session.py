"""Shared ScriptedSessionClient and workflow test helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.agents.session import (
    SessionConfig,
    SessionRef,
    SessionResumeError,
    TurnResult,
)
from domains.lca.artifacts.checks import CHECKER_VERSION
from tests.conftest import PROJECT_ROOT

HandoffScript = dict[tuple[str, str, int], Any]

_CHECKER_PROFILES = {
    "lca.inventory": "inventory",
    "lca.mapping": "mapping",
    "lca.report": "report",
}


def passing_validate(ctx: Any, checker_id: str) -> dict[str, Any]:
    profile = _CHECKER_PROFILES.get(checker_id, checker_id.rsplit(".", 1)[-1])
    path = (
        Path(ctx.workspace_root)
        / "memory"
        / "evidence"
        / ctx.run_id
        / "checks"
        / f"{profile}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "check_id": profile,
                "checker_version": CHECKER_VERSION,
                "status": "passed",
                "inputs": {"files": []},
                "executed_at": "2020-01-01T00:00:00Z",
                "summary": f"{checker_id}: 0 issue(s)",
                "errors": [],
                "warnings": [],
                "stage": ctx.stage_id,
                "assignment": ctx.assignment_id,
                "attempt": ctx.attempt,
            }
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "checks": [
            {
                "check_id": checker_id,
                "status": "passed",
                "summary": f"{checker_id}: 0 issue(s)",
            }
        ],
        "errors": [],
        "warnings": [],
        "checks_ref": {
            "path": f"memory/evidence/{ctx.run_id}/checks/{profile}.json",
            "sha256": "0",
            "size_bytes": 1,
        },
    }


# Backward-compatible alias used by older tests.
_passing_validate = passing_validate


class ScriptedSessionClient:
    def __init__(
        self,
        workspace: Path,
        script: Mapping[tuple[str, str, int], Any],
    ) -> None:
        self.workspace = workspace
        self.script = script
        self.created: dict[str, str] = {}
        self.turns: list[tuple[str, str]] = []
        self.prompts: list[str] = []
        self.resume_count = 0
        self.configs: list[SessionConfig] = []
        self._call_counts: dict[tuple[str, str, int], int] = {}

    def create(self, config: SessionConfig) -> SessionRef:
        key = f"{config.worker}-{len(self.created)}"
        ref = SessionRef(
            platform=config.worker,
            session_id=key,
            storage={"dir": "present"},
        )
        self.created[key] = key
        return ref

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        del config
        if ref.storage.get("dir") != "present":
            raise SessionResumeError("storage missing")
        self.resume_count += 1
        return ref

    def run_turn(
        self, ref: SessionRef, prompt: str, config: SessionConfig
    ) -> TurnResult:
        self.configs.append(config)
        self.prompts.append(prompt)
        context = context_from_prompt(prompt)
        stage = context["stage"]
        role = context["role"]
        attempt = int(context["attempt"])
        key = (stage, role, attempt)
        raw = self.script[key]
        if isinstance(raw, list):
            index = self._call_counts.get(key, 0)
            self._call_counts[key] = index + 1
            payload = dict(raw[index])
        else:
            payload = dict(raw)
        self.turns.append((ref.session_id, f"{stage}:{role}:{attempt}"))
        self._write_outputs(payload)
        handoff_rel = context["handoff_path"]
        handoff_path = Path(handoff_rel)
        if not handoff_path.is_absolute():
            if Path(handoff_rel).parts[:1] == ("workspace",):
                handoff_path = self.workspace.joinpath(*Path(handoff_rel).parts[1:])
            else:
                handoff_path = PROJECT_ROOT / handoff_rel
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        if payload.get("skip_handoff"):
            return TurnResult(status="completed", session_ref=ref, text="ok")
        if payload.get("handoff") is not None:
            body = dict(payload["handoff"])
        else:
            body = {
                "schema_version": 1,
                "role": role,
                "stage": stage,
                "attempt": attempt,
                "status": payload["status"],
                "status_reason": payload["status_reason"]
                if "status_reason" in payload
                else "ok",
                "fix_instructions": payload.get("fix_instructions") or "",
                "artifacts": payload.get("artifacts") or [],
            }
            for extra in ("checks_ref", "evidence_manifest_ref", "rework_scope"):
                if extra in payload:
                    body[extra] = payload[extra]
        handoff_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return TurnResult(status="completed", session_ref=ref, text="ok")

    def release(self, ref: SessionRef) -> None:
        del ref

    def _write_outputs(self, payload: dict) -> None:
        for relative in payload.get("write") or []:
            path = self.workspace.joinpath(*Path(relative).parts[1:])
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith("/"):
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.write_text("{}", encoding="utf-8")


def context_from_prompt(prompt: str) -> dict:
    start = prompt.index("{")
    end = prompt.index("\n# 公共任务协议")
    return json.loads(prompt[start:end].strip())


_context_from_prompt = context_from_prompt


def happy_script() -> HandoffScript:
    return {
        ("01-intake-gate", "reviewer", 1): {
            "status": "passed",
            "status_reason": "计划可启动",
        },
        ("02-inventory-extraction", "executor", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        },
        ("02-inventory-extraction", "reviewer", 1): {"status": "passed"},
        ("03-dataset-mapping", "executor", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/process-mapping.json",
                "workspace/outputs/LCI/",
            ],
        },
        ("03-dataset-mapping", "reviewer", 1): {"status": "passed"},
        ("04-openlca-reporting", "executor", 1): {
            "status": "ok",
            "write": ["workspace/outputs/reports/lca_report.md"],
        },
        ("04-openlca-reporting", "reviewer", 1): {"status": "passed"},
    }


_happy_script = happy_script


def revise_happy_script() -> HandoffScript:
    return {
        ("01-intake-gate", "reviewer", 1): {
            "status": "passed",
            "status_reason": "修订可启动",
        },
        ("02-inventory-extraction", "reviser", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        },
        ("02-inventory-extraction", "reviewer", 1): {"status": "passed"},
        ("03-dataset-mapping", "reviser", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/process-mapping.json",
                "workspace/outputs/LCI/",
            ],
        },
        ("03-dataset-mapping", "reviewer", 1): {"status": "passed"},
        ("04-openlca-reporting", "reviser", 1): {
            "status": "ok",
            "write": ["workspace/outputs/reports/lca_report.md"],
        },
        ("04-openlca-reporting", "reviewer", 1): {"status": "passed"},
    }


_revise_happy_script = revise_happy_script
