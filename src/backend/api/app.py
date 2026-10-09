"""FastAPI application — sole browser business API."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.agents.config import load_worker_model
from core.runtime.model_profiles import (
    delete_local_profile,
    load_profiles,
    resolve_model_profile,
    upsert_local_profile,
)
from pi_agents.process import shared_runtime
from services.auth_login_service import (
    login_status,
    logout_provider,
    reply_login_prompt,
    start_oauth_login,
)
from services.credentials_service import (
    available_providers,
    clear_provider_key,
    credentials_status,
    list_custom_endpoints,
    list_provider_catalog,
    provider_overrides_status,
    save_custom_endpoint,
    save_provider_key,
    set_provider_base_url,
)
from services.diagnostics_service import (
    environment_report,
    openlca_endpoint,
    save_openlca_port,
)
from services.harness_browser import HarnessPathError, harness_catalog, read_harness_document
from services.project_paths import PROJECT_ROOT
from services.workflow_service import WorkflowService
from utils.env import parse_env_file, upsert_env_keys


def _web_origins() -> list[str]:
    values = parse_env_file(PROJECT_ROOT / ".env")
    port = (
        os.getenv("GUI_WEB_PORT") or values.get("GUI_WEB_PORT") or "3000"
    ).strip() or "3000"
    return [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]


app = FastAPI(title="Harness LCA API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_web_origins(),
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


class OAuthLoginStart(BaseModel):
    provider: str
    auth_type: str = "oauth"


class OAuthPromptReply(BaseModel):
    login_id: str
    prompt_id: str
    value: str = ""


class ProviderBaseUrlUpdate(BaseModel):
    provider: str
    base_url: str = ""


class OpenLcaPortUpdate(BaseModel):
    port: int = Field(ge=1, le=65535)


class CustomEndpointCreate(BaseModel):
    profile_id: str
    provider: str = "custom"
    base_url: str
    api_type: str = "openai-completions"
    model_id: str
    display_name: str = ""
    api_key: str = ""
    set_as_default: bool = False
    previous_profile_id: str = ""
    previous_provider: str = ""
    previous_model_id: str = ""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/diagnostics/environment")
def diagnostics_environment() -> dict[str, Any]:
    return environment_report(PROJECT_ROOT)


@app.get("/api/lca/openlca")
def read_openlca() -> dict[str, Any]:
    host, port = openlca_endpoint(PROJECT_ROOT)
    return {"id": "openlca", "host": host, "port": port}


@app.put("/api/lca/openlca")
def update_openlca_port(body: OpenLcaPortUpdate) -> dict[str, Any]:
    try:
        tool = save_openlca_port(PROJECT_ROOT, body.port)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"tool": tool}


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
        return {
            "ok": False,
            "message": str(exc),
            "provider": provider,
            "model_id": model_id,
        }
    if isinstance(result, dict):
        return {
            "ok": bool(result.get("ok")),
            "message": str(
                result.get("message") or ("连接成功" if result.get("ok") else "失败")
            ),
            "provider": provider,
            "model_id": model_id,
            "mode": result.get("mode"),
        }
    return {"ok": False, "message": "unexpected runtime response", "provider": provider}


@app.get("/api/models/providers")
def read_available_providers() -> dict[str, Any]:
    return {"providers": available_providers(PROJECT_ROOT)}


@app.get("/api/models/providers/{provider}/models")
def list_provider_models(provider: str) -> dict[str, Any]:
    name = provider.strip()
    if not name:
        raise HTTPException(status_code=400, detail="provider required")
    cred_dir = PROJECT_ROOT / ".local" / "credentials"
    runtime = shared_runtime(PROJECT_ROOT)
    try:
        result = runtime.request(
            "models.list_available",
            {
                "provider": name,
                "credentials_dir": str(cred_dir.resolve()),
            },
            timeout=90.0,
        )
    except Exception as exc:
        return {"ok": False, "provider": name, "models": [], "message": str(exc)}
    if isinstance(result, dict):
        models = result.get("models") if isinstance(result.get("models"), list) else []
        return {
            "ok": bool(result.get("ok")),
            "provider": name,
            "models": models,
            "message": str(result.get("message") or ""),
        }
    return {
        "ok": False,
        "provider": name,
        "models": [],
        "message": "unexpected runtime response",
    }


@app.get("/api/credentials/status")
def get_credentials_status() -> dict[str, Any]:
    return {
        "providers": credentials_status(PROJECT_ROOT),
        "catalog": list_provider_catalog(),
        "overrides": provider_overrides_status(PROJECT_ROOT),
    }


@app.post("/api/credentials")
def write_credentials(body: CredentialUpdate) -> dict[str, Any]:
    try:
        info = save_provider_key(PROJECT_ROOT, body.provider, body.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "saved",
        "provider": body.provider.strip(),
        "info": info,
        "providers": credentials_status(PROJECT_ROOT),
        "overrides": provider_overrides_status(PROJECT_ROOT),
    }


@app.delete("/api/credentials/{provider}")
def delete_credentials(provider: str) -> dict[str, Any]:
    try:
        clear_provider_key(PROJECT_ROOT, provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "cleared",
        "provider": provider.strip(),
        "providers": credentials_status(PROJECT_ROOT),
        "overrides": provider_overrides_status(PROJECT_ROOT),
    }


@app.post("/api/credentials/oauth/start")
def oauth_login_start(body: OAuthLoginStart) -> dict[str, Any]:
    try:
        return start_oauth_login(body.provider, auth_type=body.auth_type or "oauth")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/credentials/oauth/{login_id}")
def oauth_login_status(login_id: str) -> dict[str, Any]:
    try:
        return login_status(login_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/credentials/oauth/reply")
def oauth_login_reply(body: OAuthPromptReply) -> dict[str, Any]:
    try:
        return reply_login_prompt(body.login_id, body.prompt_id, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/credentials/oauth/logout")
def oauth_logout(body: OAuthLoginStart) -> dict[str, Any]:
    try:
        return logout_provider(body.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/credentials/base-url")
def update_provider_base_url(body: ProviderBaseUrlUpdate) -> dict[str, Any]:
    try:
        url = set_provider_base_url(PROJECT_ROOT, body.provider, body.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "provider": body.provider.strip(),
        "base_url": url,
        "overrides": provider_overrides_status(PROJECT_ROOT),
    }


@app.get("/api/models/custom-endpoints")
def read_custom_endpoints() -> dict[str, Any]:
    return {"endpoints": list_custom_endpoints(PROJECT_ROOT)}


@app.post("/api/models/custom-endpoint")
def create_custom_endpoint(body: CustomEndpointCreate) -> dict[str, Any]:
    try:
        endpoint = save_custom_endpoint(
            PROJECT_ROOT,
            provider=body.provider,
            base_url=body.base_url,
            api=body.api_type,
            model_id=body.model_id,
            api_key=body.api_key,
            display_name=body.display_name,
            previous_provider=body.previous_provider,
            previous_model_id=body.previous_model_id,
        )
        profile = upsert_local_profile(
            PROJECT_ROOT,
            body.profile_id,
            {
                "display_name": body.display_name or body.profile_id,
                "provider": body.provider,
                "model_id": body.model_id,
                "api_type": body.api_type,
                "base_url": body.base_url,
            },
        )
        previous_profile = body.previous_profile_id.strip()
        if previous_profile and previous_profile != body.profile_id.strip():
            delete_local_profile(PROJECT_ROOT, previous_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.set_as_default:
        upsert_env_keys(PROJECT_ROOT / ".env", {"PI_MODEL": body.profile_id.strip()})
    return {
        "status": "saved",
        "endpoint": endpoint,
        "profile": profile,
        "profiles": load_profiles(PROJECT_ROOT),
        "overrides": provider_overrides_status(PROJECT_ROOT),
        "endpoints": list_custom_endpoints(PROJECT_ROOT),
    }


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


@app.get("/api/harness/catalog")
def read_harness_catalog() -> dict[str, Any]:
    return harness_catalog(PROJECT_ROOT)


@app.get("/api/harness/document")
def read_harness_file(path: str) -> dict[str, str]:
    try:
        return read_harness_document(PROJECT_ROOT, path)
    except HarnessPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@app.get("/api/plan")
def read_plan() -> dict[str, str]:
    plan = PROJECT_ROOT / "harness" / "knowledge" / "plan" / "main_plan.md"
    if not plan.is_file():
        raise HTTPException(status_code=404, detail="plan not found")
    return {
        "path": str(plan.relative_to(PROJECT_ROOT)),
        "content": plan.read_text("utf-8"),
    }


@app.put("/api/plan")
def write_plan(content: str) -> dict[str, str]:
    plan = PROJECT_ROOT / "harness" / "knowledge" / "plan" / "main_plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(content, encoding="utf-8")
    return {"status": "saved"}


@app.get("/api/settings/env")
def read_env_keys() -> dict[str, str]:
    return parse_env_file(PROJECT_ROOT / ".env")
