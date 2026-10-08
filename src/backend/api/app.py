"""FastAPI application — sole browser business API."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.runtime.model_profiles import load_profiles
from services.diagnostics_service import environment_report
from services.project_paths import PROJECT_ROOT
from services.workflow_service import WorkflowService
from utils.env import parse_env_file, upsert_env_keys

app = FastAPI(title="Harness LCA API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_workflow = WorkflowService()
_run_events: list[dict[str, Any]] = []
_event_id = 0


class CredentialUpdate(BaseModel):
    provider: str
    api_key: str = Field(min_length=1)


class ModelSelection(BaseModel):
    profile_id: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/diagnostics/environment")
def diagnostics_environment() -> dict[str, Any]:
    return environment_report(PROJECT_ROOT)


@app.get("/api/models/profiles")
def model_profiles() -> dict[str, Any]:
    return {"profiles": load_profiles(PROJECT_ROOT)}


@app.post("/api/models/selection")
def set_model_selection(body: ModelSelection) -> dict[str, str]:
    upsert_env_keys(PROJECT_ROOT / ".env", {"PI_MODEL": body.profile_id})
    return {"profile_id": body.profile_id}


@app.post("/api/credentials")
def write_credentials(body: CredentialUpdate) -> dict[str, str]:
    cred_dir = PROJECT_ROOT / ".local" / "credentials"
    cred_dir.mkdir(parents=True, exist_ok=True)
    path = cred_dir / f"{body.provider}.json"
    path.write_text(
        json.dumps({"provider": body.provider, "api_key_set": True}, indent=2),
        encoding="utf-8",
    )
    # Secrets are written for runtime consumption; never return the key.
    auth_path = cred_dir / "pi-auth.json"
    existing: dict[str, Any] = {}
    if auth_path.is_file():
        existing = json.loads(auth_path.read_text(encoding="utf-8"))
    providers = existing.get("providers") or {}
    providers[body.provider] = {"apiKey": body.api_key}
    existing["providers"] = providers
    auth_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"status": "saved"}


@app.get("/api/workflow/manifest")
def workflow_manifest() -> dict[str, Any]:
    return _workflow.manifest()


@app.get("/api/events")
async def event_stream(request: Request) -> StreamingResponse:
    async def generate():
        global _event_id
        last = int(request.headers.get("last-event-id") or 0)
        while True:
            if await request.is_disconnected():
                break
            for item in _run_events:
                if int(item["id"]) > last:
                    yield f"id: {item['id']}\nevent: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
                    last = int(item["id"])
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")


def push_event(event: str, data: dict[str, Any]) -> None:
    global _event_id
    _event_id += 1
    _run_events.append({"id": _event_id, "event": event, "data": data})


@app.get("/api/plan")
def read_plan() -> dict[str, str]:
    plan = PROJECT_ROOT / "harness" / "knowledge" / "plan" / "main_plan.md"
    if not plan.is_file():
        raise HTTPException(status_code=404, detail="plan not found")
    return {"path": str(plan.relative_to(PROJECT_ROOT)), "content": plan.read_text("utf-8")}


@app.put("/api/plan")
def write_plan(content: str) -> dict[str, str]:
    plan = PROJECT_ROOT / "harness" / "knowledge" / "plan" / "main_plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(content, encoding="utf-8")
    return {"status": "saved"}


@app.get("/api/settings/env")
def read_env_keys() -> dict[str, str]:
    return parse_env_file(PROJECT_ROOT / ".env")
