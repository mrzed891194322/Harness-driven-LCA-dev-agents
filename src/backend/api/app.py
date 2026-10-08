"""FastAPI application — sole browser business API."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.agents.config import load_worker_model
from core.runtime.model_profiles import load_profiles, resolve_model_profile
from pi_agents.process import shared_runtime
from services.credentials_service import credentials_status, save_provider_key
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


class ModelTestRequest(BaseModel):
    profile_id: str | None = None
    provider: str | None = None
    model_id: str | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/diagnostics/environment")
def diagnostics_environment() -> dict[str, Any]:
    return environment_report(PROJECT_ROOT)


@app.get("/api/models/profiles")
def model_profiles() -> dict[str, Any]:
    return {
        "profiles": load_profiles(PROJECT_ROOT),
        "selected": load_worker_model("pi", PROJECT_ROOT),
    }


@app.post("/api/models/selection")
def set_model_selection(body: ModelSelection) -> dict[str, str]:
    profiles = load_profiles(PROJECT_ROOT)
    if body.profile_id not in profiles:
        raise HTTPException(status_code=400, detail=f"未知模型档案：{body.profile_id}")
    upsert_env_keys(PROJECT_ROOT / ".env", {"PI_MODEL": body.profile_id})
    return {"profile_id": body.profile_id}


@app.post("/api/models/test")
def test_model_connection(body: ModelTestRequest) -> dict[str, Any]:
    profile_id = (body.profile_id or load_worker_model("pi", PROJECT_ROOT)).strip()
    profile = resolve_model_profile(profile_id, project_root=PROJECT_ROOT)
    provider = (body.provider or profile.provider).strip()
    model_id = (body.model_id or profile.model_id).strip()
    cred_dir = PROJECT_ROOT / ".local" / "credentials"
    runtime = shared_runtime(PROJECT_ROOT)
    try:
        result = runtime.request(
            "models.test_connection",
            {
                "provider": provider,
                "model_id": model_id,
                "api_type": profile.api_type,
                "base_url": profile.base_url,
                "credentials_dir": str(cred_dir.resolve()),
            },
            timeout=60.0,
        )
    except Exception as exc:
        return {"ok": False, "message": str(exc), "provider": provider, "model_id": model_id}
    if isinstance(result, dict):
        return {
            "ok": bool(result.get("ok")),
            "message": str(result.get("message") or ("连接成功" if result.get("ok") else "失败")),
            "provider": provider,
            "model_id": model_id,
            "mode": result.get("mode"),
        }
    return {"ok": False, "message": "unexpected runtime response", "provider": provider}


@app.get("/api/credentials/status")
def get_credentials_status() -> dict[str, Any]:
    return {"providers": credentials_status(PROJECT_ROOT)}


@app.post("/api/credentials")
def write_credentials(body: CredentialUpdate) -> dict[str, str]:
    try:
        save_provider_key(PROJECT_ROOT, body.provider, body.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved", "provider": body.provider.strip()}


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
