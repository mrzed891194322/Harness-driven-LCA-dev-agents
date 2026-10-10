"""FastAPI application — sole browser business API."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.core.agents.assignment_models import (
    load_assignment_models,
    save_assignment_models,
)
from backend.core.agents.config import load_worker_model
from backend.core.runtime.model_profiles import (
    allocate_profile_id,
    delete_local_profile,
    load_profiles,
    resolve_model_profile,
    upsert_local_profile,
)
from backend.pi_client.process import close_shared_runtime, shared_runtime
from backend.services.auth_login_service import (
    login_status,
    logout_provider,
    reply_login_prompt,
    start_oauth_login,
)
from backend.services.credentials_service import (
    available_providers,
    clear_provider_key,
    credentials_status,
    delete_custom_endpoint,
    list_custom_endpoints,
    list_provider_catalog,
    provider_overrides_status,
    save_custom_endpoint,
    save_provider_key,
    set_provider_api,
    set_provider_base_url,
)
from backend.services.prompt_templates import PromptTemplates
from backend.services.session_snapshots import SessionSnapshots
from backend.services.diagnostics_service import (
    environment_report,
    openlca_endpoint,
    save_openlca_port,
)
from backend.services.harness_browser import (
    HarnessPathError,
    harness_catalog,
    read_harness_document,
)
from backend.services.plan_form import (
    TEMPLATE_NAME,
    PlanFields,
    PlanFormError,
    decode_plan_upload,
    delete_reference,
    list_references,
    read_plan_document,
    save_plan,
    save_reference_note,
    save_references,
    template_markdown,
)
from backend.services.project_paths import PROJECT_ROOT
from backend.services.spec_service import (
    SpecPartError,
    list_specs,
    read_part,
    reset_override,
    save_override,
    validate_spec,
)
from backend.services.tutorial_browser import (
    TutorialPathError,
    read_tutorial_document,
    resolve_tutorial_asset,
    tutorial_catalog,
)
from backend.services.workflow_launch import launcher
from backend.services.workflow_service import WorkflowService
from backend.settings import parse_env_file, upsert_env_keys


def _web_origins() -> list[str]:
    values = parse_env_file(PROJECT_ROOT / ".env")
    port = (
        os.getenv("GUI_WEB_PORT") or values.get("GUI_WEB_PORT") or "3000"
    ).strip() or "3000"
    return [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    # Release this process's sessions (and their MCP servers) and disconnect from
    # the project's pi-runtime. The runtime itself is stopped by `npm run stop`.
    await asyncio.to_thread(close_shared_runtime)


app = FastAPI(title="Harness LCA API", version="0.2.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_web_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_workflow = WorkflowService()
_snapshots = SessionSnapshots()
_prompt_templates = PromptTemplates()
_run_events: list[dict[str, Any]] = []
_event_id = 0


class CredentialUpdate(BaseModel):
    provider: str
    api_key: str = Field(min_length=1)


class ModelSelection(BaseModel):
    profile_id: str


class WorkflowModelsUpdate(BaseModel):
    assignments: dict[str, str] = Field(default_factory=dict)


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


class ProviderApiUpdate(BaseModel):
    provider: str
    api: str = ""


class OpenLcaPortUpdate(BaseModel):
    port: int = Field(ge=1, le=65535)


class PlanUpdate(BaseModel):
    subject: str = ""
    functional_unit: str = ""
    life_cycle_stages: str = ""
    conditions: str = ""


class WorkflowStart(BaseModel):
    task: str
    subject: str = ""
    functional_unit: str = ""
    life_cycle_stages: str = ""
    conditions: str = ""


class ReferenceNoteUpdate(BaseModel):
    note: str = ""


class CustomEndpointDelete(BaseModel):
    profile_id: str = ""
    provider: str
    model_id: str


class CustomEndpointCreate(BaseModel):
    profile_id: str = ""
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


def _provider_catalog(project_root: Path, provider: str) -> dict[str, Any]:
    """Models a connected provider can actually serve right now."""
    cred_dir = project_root / ".local" / "credentials"
    runtime = shared_runtime(project_root)
    try:
        result = runtime.request(
            "models.list_available",
            {
                "provider": provider,
                "credentials_dir": str(cred_dir.resolve()),
            },
            timeout=90.0,
        )
    except Exception as exc:
        return {"ok": False, "provider": provider, "models": [], "message": str(exc)}
    if isinstance(result, dict):
        models = result.get("models") if isinstance(result.get("models"), list) else []
        return {
            "ok": bool(result.get("ok")),
            "provider": provider,
            "models": models,
            "message": str(result.get("message") or ""),
        }
    return {
        "ok": False,
        "provider": provider,
        "models": [],
        "message": "unexpected runtime response",
    }


def _selection_ref(project_root: Path, model_ref: str) -> str:
    """Map a stored profile alias to the provider/model id the catalog uses."""
    text = (model_ref or "").strip()
    if not text:
        return ""
    profile = resolve_model_profile(text, project_root=project_root)
    if profile.provider and profile.model_id:
        return f"{profile.provider}/{profile.model_id}"
    return text


def _accepts_model_ref(project_root: Path, model_ref: str) -> bool:
    chosen = model_ref.strip()
    if not chosen:
        return True
    if chosen in load_profiles(project_root):
        return True
    provider, model_id = chosen.split("/", 1) if "/" in chosen else ("", "")
    if not provider.strip() or not model_id.strip():
        return False
    connected = {str(item.get("id") or "") for item in available_providers(project_root)}
    return provider.strip() in connected


def _connected_models(project_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Live models from providers that already have credentials."""
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for item in available_providers(project_root):
        provider = str(item.get("id") or "").strip()
        provider_name = str(item.get("name") or provider)
        if not provider:
            continue
        catalog = _provider_catalog(project_root, provider)
        if not catalog.get("ok"):
            message = str(catalog.get("message") or "无法读取模型")
            warnings.append(f"{provider_name}：{message}")
            continue
        models = catalog.get("models") if isinstance(catalog.get("models"), list) else []
        for model in models:
            if not isinstance(model, dict):
                continue
            model_id = str(model.get("id") or "").strip()
            if not model_id:
                continue
            ref = f"{provider}/{model_id}"
            if ref in seen:
                continue
            seen.add(ref)
            label = str(model.get("name") or model_id).strip() or model_id
            rows.append(
                {
                    "id": ref,
                    "label": label,
                    "provider": provider,
                    "provider_name": provider_name,
                    "model_id": model_id,
                }
            )
    return rows, warnings


@app.get("/api/workflow/models")
def workflow_models() -> dict[str, Any]:
    stored = load_worker_model("pi", PROJECT_ROOT)
    models, warnings = _connected_models(PROJECT_ROOT)
    return {
        "default": stored,
        "default_ref": _selection_ref(PROJECT_ROOT, stored),
        "assignments": load_assignment_models(PROJECT_ROOT),
        "models": models,
        "warnings": warnings,
    }


@app.put("/api/workflow/models")
def update_workflow_models(body: WorkflowModelsUpdate) -> dict[str, Any]:
    for profile_id in body.assignments.values():
        if not _accepts_model_ref(PROJECT_ROOT, profile_id):
            raise HTTPException(status_code=400, detail=f"未知模型：{profile_id}")
    try:
        saved = save_assignment_models(PROJECT_ROOT, body.assignments)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"assignments": saved}


@app.post("/api/models/selection")
def set_model_selection(body: ModelSelection) -> dict[str, str]:
    if not _accepts_model_ref(PROJECT_ROOT, body.profile_id):
        raise HTTPException(status_code=400, detail=f"未知模型：{body.profile_id}")
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
    return _provider_catalog(PROJECT_ROOT, name)


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


@app.put("/api/credentials/api-type")
def update_provider_api(body: ProviderApiUpdate) -> dict[str, Any]:
    try:
        api = set_provider_api(PROJECT_ROOT, body.provider, body.api)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "provider": body.provider.strip(),
        "api": api,
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
        profile_id = allocate_profile_id(
            PROJECT_ROOT,
            body.provider,
            body.model_id,
            preferred=body.profile_id,
            keep=body.previous_profile_id,
        )
        profile = upsert_local_profile(
            PROJECT_ROOT,
            profile_id,
            {
                "display_name": body.display_name or profile_id,
                "provider": body.provider,
                "model_id": body.model_id,
                "api_type": body.api_type,
                "base_url": body.base_url,
            },
        )
        previous_profile = body.previous_profile_id.strip()
        if previous_profile and previous_profile != profile_id:
            delete_local_profile(PROJECT_ROOT, previous_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.set_as_default:
        upsert_env_keys(PROJECT_ROOT / ".env", {"PI_MODEL": profile_id})
    return {
        "status": "saved",
        "profile_id": profile_id,
        "endpoint": endpoint,
        "profile": profile,
        "profiles": load_profiles(PROJECT_ROOT),
        "overrides": provider_overrides_status(PROJECT_ROOT),
        "endpoints": list_custom_endpoints(PROJECT_ROOT),
    }


@app.delete("/api/models/custom-endpoint")
def remove_custom_endpoint(body: CustomEndpointDelete) -> dict[str, Any]:
    try:
        delete_custom_endpoint(
            PROJECT_ROOT,
            provider=body.provider,
            model_id=body.model_id,
            profile_id=body.profile_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "deleted",
        "profiles": load_profiles(PROJECT_ROOT),
        "overrides": provider_overrides_status(PROJECT_ROOT),
        "endpoints": list_custom_endpoints(PROJECT_ROOT),
    }


@app.get("/api/workflow/manifest")
def workflow_manifest() -> dict[str, Any]:
    return _workflow.manifest()


@app.get("/api/results")
def workflow_results() -> dict[str, Any]:
    return _workflow.results()


@app.get("/api/results/file")
def workflow_result_file(path: str) -> dict[str, Any]:
    try:
        return _workflow.read_result_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc


@app.get("/api/results/archive")
def workflow_result_archive() -> Response:
    try:
        payload = _workflow.archive_outputs()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="lca-outputs.zip"'},
    )


class GeneratedPromptUpdate(BaseModel):
    rel: str
    text: str


@app.get("/api/prompts/generated")
def generated_prompts_list() -> dict[str, Any]:
    """Generated-prompt templates and the user preferences file (default + user version)."""
    return _prompt_templates.list()


@app.put("/api/prompts/generated")
def generated_prompts_save(body: GeneratedPromptUpdate) -> dict[str, Any]:
    try:
        return _prompt_templates.save(body.rel, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/prompts/generated")
def generated_prompts_reset(rel: str) -> dict[str, Any]:
    try:
        return _prompt_templates.reset(rel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/prompts/generated/preview")
def generated_prompts_preview(stage: str, role: str) -> dict[str, Any]:
    """What a new session for stage+role would get right now (no session is created)."""
    try:
        return _prompt_templates.preview(stage, role)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs")
def runs_list() -> dict[str, Any]:
    """Runs with session snapshots; ``anomaly`` flags any injection warn/mismatch."""
    return {"runs": _snapshots.runs()}


@app.get("/api/runs/{run_id}/sessions")
def run_sessions(run_id: str) -> dict[str, Any]:
    try:
        return _snapshots.run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/sessions/{session}/injection")
def run_session_injection(run_id: str, session: str) -> dict[str, Any]:
    try:
        return _snapshots.injection(run_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/sessions/{session}/markdown")
def run_session_markdown(run_id: str, session: str, download: bool = False) -> Any:
    """Readable Markdown of one session: injection, model, full transcript."""
    try:
        text = _snapshots.markdown(run_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    if download:
        return Response(
            content=text.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.{session}.md"'},
        )
    return {"text": text}


@app.get("/api/runs/{run_id}/sessions/{session}/file")
def run_session_file(run_id: str, session: str, name: str, download: bool = False) -> Any:
    try:
        if download:
            path = _snapshots.file_path(run_id, session, name)
            return FileResponse(path, filename=f"{run_id}.{session}.{name.replace('/', '_')}")
        return _snapshots.read_text(run_id, session, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc


@app.get("/api/workflow/progress")
def workflow_progress(offset: int = 0, epoch: str = "") -> dict[str, Any]:
    return _workflow.progress(offset, epoch)


@app.get("/api/workflow/activity")
def workflow_activity(run_id: str = "", offset: int = 0) -> dict[str, Any]:
    """Structured Pi worker events (tool calls/results, text, handoff) — polling form."""
    try:
        return _workflow.activity(run_id, offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workflow/activity/stream")
async def workflow_activity_stream(
    request: Request, run_id: str = "", offset: int = 0
) -> StreamingResponse:
    """SSE form of /api/workflow/activity. Event ``activity`` carries one record;
    the SSE id is the byte offset to resume from (Last-Event-ID or ?offset=)."""
    try:
        first = _workflow.activity(run_id, offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    resume = request.headers.get("last-event-id")
    position = int(resume) if resume and resume.isdigit() else offset
    target = str(first.get("run_id") or "")

    async def generate():
        nonlocal position
        idle = 0
        while not await request.is_disconnected():
            batch = await asyncio.to_thread(_workflow.activity, target, position)
            if batch.get("reset"):
                yield "event: reset\ndata: {}\n\n"
            next_offset = int(batch.get("offset") or 0)
            for item in batch.get("events") or []:
                yield (
                    f"id: {next_offset}\nevent: activity\n"
                    f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                )
            if next_offset != position or batch.get("reset"):
                idle = 0
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            position = next_offset
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/workflow/start")
def start_workflow(body: WorkflowStart) -> dict[str, str]:
    try:
        return launcher.start(
            task=body.task,
            fields=PlanFields(
                subject=body.subject,
                functional_unit=body.functional_unit,
                life_cycle_stages=body.life_cycle_stages,
                conditions=body.conditions,
            ),
            project_root=PROJECT_ROOT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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


class SpecPartBody(BaseModel):
    path: str
    content: str


@app.get("/api/specs")
def read_specs() -> dict[str, Any]:
    return list_specs(PROJECT_ROOT)


@app.get("/api/specs/{stage}/part")
def read_spec_part(stage: str, path: str) -> dict[str, Any]:
    try:
        return read_part(PROJECT_ROOT, stage, path)
    except SpecPartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="spec part not found") from exc


@app.put("/api/specs/{stage}/part")
def save_spec_part(stage: str, body: SpecPartBody) -> dict[str, Any]:
    try:
        return save_override(PROJECT_ROOT, stage, body.path, body.content)
    except SpecPartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/specs/{stage}/part")
def reset_spec_part(stage: str, path: str) -> dict[str, Any]:
    try:
        return reset_override(PROJECT_ROOT, stage, path)
    except SpecPartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/specs/{stage}/validate")
def validate_spec_endpoint(stage: str) -> dict[str, Any]:
    try:
        return validate_spec(PROJECT_ROOT, stage)
    except SpecPartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tutorial/catalog")
def read_tutorial_catalog() -> dict[str, Any]:
    return tutorial_catalog(PROJECT_ROOT)


@app.get("/api/tutorial/document")
def read_tutorial_file(path: str) -> dict[str, str]:
    try:
        return read_tutorial_document(PROJECT_ROOT, path)
    except TutorialPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@app.get("/api/tutorial/asset")
def read_tutorial_asset(path: str) -> FileResponse:
    try:
        asset = resolve_tutorial_asset(PROJECT_ROOT, path)
    except TutorialPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="asset not found") from exc
    return FileResponse(asset)


@app.get("/api/plan")
def read_plan() -> dict[str, Any]:
    return read_plan_document(PROJECT_ROOT)


@app.put("/api/plan")
def write_plan(body: PlanUpdate) -> dict[str, Any]:
    save_plan(
        PROJECT_ROOT,
        PlanFields(
            subject=body.subject,
            functional_unit=body.functional_unit,
            life_cycle_stages=body.life_cycle_stages,
            conditions=body.conditions,
        ),
    )
    return {"status": "saved", **read_plan_document(PROJECT_ROOT)}


@app.get("/api/plan/template")
def download_plan_template() -> Response:
    return Response(
        content=template_markdown(),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{TEMPLATE_NAME}"'},
    )


@app.post("/api/plan/import")
async def import_plan(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    try:
        fields = decode_plan_upload(file.filename or "", data)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"fields": fields.as_dict(), "filename": Path(file.filename or "").name}


@app.get("/api/references")
def read_references() -> dict[str, Any]:
    return {"files": list_references(PROJECT_ROOT)}


@app.post("/api/references")
async def upload_references(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    uploads: list[tuple[str, bytes]] = []
    for item in files:
        uploads.append((item.filename or "", await item.read()))
    try:
        saved = save_references(PROJECT_ROOT, uploads)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved", "saved": saved, "files": list_references(PROJECT_ROOT)}


@app.put("/api/references/{name}/note")
def write_reference_note(name: str, body: ReferenceNoteUpdate) -> dict[str, Any]:
    try:
        item = save_reference_note(PROJECT_ROOT, name, body.note)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return {"status": "saved", "file": item, "files": list_references(PROJECT_ROOT)}


@app.delete("/api/references/{name}")
def remove_reference(name: str) -> dict[str, Any]:
    try:
        delete_reference(PROJECT_ROOT, name)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return {"status": "deleted", "files": list_references(PROJECT_ROOT)}


@app.get("/api/settings/env")
def read_env_keys() -> dict[str, str]:
    return parse_env_file(PROJECT_ROOT / ".env")
