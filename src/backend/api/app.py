"""FastAPI application — sole browser business API."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.core.agents.assignment_models import (
    load_default_model,
    load_default_thinking,
    save_default_model,
    save_default_thinking,
)
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
from backend.services.diagnostics_service import (
    environment_report,
    openlca_endpoint,
    save_openlca_port,
)
from backend.services.plan_templates import PlanTemplateError, get_plan_template, list_plan_templates
from backend.services.plan_form import (
    DEFAULT_TEMPLATE_ID,
    PlanFormConflict,
    PlanFormError,
    delete_reference,
    import_plan_bytes,
    list_references,
    read_plan_document,
    save_plan,
    save_reference_note,
    save_reference_type,
    save_references,
    apply_reference_types,
    template_download_filename,
    template_yaml,
)
from backend.services.project_paths import PROJECT_ROOT
from backend.services.tutorial_browser import (
    TutorialPathError,
    read_tutorial_document,
    resolve_tutorial_asset,
    tutorial_catalog,
)
from backend.settings import load_flat, normalize_gui_lang, upsert_flat
from backend.workflow.results import Results


def _web_origins() -> list[str]:
    values = load_flat(PROJECT_ROOT)
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

_results = Results(PROJECT_ROOT)


class CredentialUpdate(BaseModel):
    provider: str
    api_key: str = Field(min_length=1)


class ModelSelection(BaseModel):
    profile_id: str
    thinking: str | None = None


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
    template_id: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowStart(BaseModel):
    workflow: str = ""
    plan: str = ""
    template_id: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)


class ReferenceNoteUpdate(BaseModel):
    note: str = ""


class ReferenceTypeUpdate(BaseModel):
    type: str = "knowledge"


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
        "selected": load_default_model(PROJECT_ROOT),
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
            row: dict[str, Any] = {
                "id": ref,
                "label": label,
                "provider": provider,
                "provider_name": provider_name,
                "model_id": model_id,
                "reasoning": bool(model.get("reasoning")),
            }
            levels = model.get("thinking_levels")
            if isinstance(levels, list):
                row["thinking_levels"] = [str(level) for level in levels if str(level).strip()]
            rows.append(row)
    return rows, warnings


@app.get("/api/workflow/models")
def workflow_models() -> dict[str, Any]:
    """Saved default model plus the models connected providers can serve."""
    stored = load_default_model(PROJECT_ROOT)
    models, warnings = _connected_models(PROJECT_ROOT)
    return {
        "default": stored,
        "default_ref": _selection_ref(PROJECT_ROOT, stored),
        "thinking": load_default_thinking(PROJECT_ROOT),
        "models": models,
        "warnings": warnings,
    }


@app.post("/api/models/selection")
def set_model_selection(body: ModelSelection) -> dict[str, str]:
    if not _accepts_model_ref(PROJECT_ROOT, body.profile_id):
        raise HTTPException(status_code=400, detail=f"未知模型：{body.profile_id}")
    if body.thinking is not None:
        try:
            save_default_thinking(PROJECT_ROOT, body.thinking)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = save_default_model(PROJECT_ROOT, body.profile_id)
    return {"profile_id": saved, "thinking": load_default_thinking(PROJECT_ROOT)}


@app.post("/api/models/test")
def test_model_connection(body: ModelTestRequest) -> dict[str, Any]:
    profile_id = (body.profile_id or load_default_model(PROJECT_ROOT)).strip()
    if not profile_id:
        raise HTTPException(status_code=400, detail="尚未选择默认模型")
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
        save_default_model(PROJECT_ROOT, profile_id)
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


@app.get("/api/results")
def workflow_results() -> dict[str, Any]:
    return _results.results()


@app.get("/api/results/file")
def workflow_result_file(path: str) -> dict[str, Any]:
    try:
        return _results.read_result_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc


@app.get("/api/results/archive")
def workflow_result_archive() -> Response:
    try:
        payload = _results.archive_outputs()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="lca-outputs.zip"'},
    )




def _workflow() -> Any:
    global _workflow_service
    if _workflow_service is None:
        from backend.workflow.service import WorkflowService

        _workflow_service = WorkflowService(PROJECT_ROOT)
    return _workflow_service


_workflow_service: Any = None


@app.post("/api/workflow/start")
def start_workflow(body: WorkflowStart) -> dict[str, Any]:
    """one whole workflow; the plan (form or imported text) becomes artifacts/plan/main_plan.md."""
    from backend.services.plan_form import parse_items, render_plan
    from backend.workflow.config import ConfigError
    from backend.workflow.config import load_workflow as load_workflow_def

    workflow = body.workflow
    plan = body.plan
    try:
        wf_def = load_workflow_def(_workflow().root, workflow)[0]
    except (ValueError, ConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not plan.strip() and wf_def.plan_file == "revise_plan.md":
        try:
            plan = str(read_plan_document(PROJECT_ROOT, workflow="revise-lca").get("content") or "")
        except PlanFormError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not plan.strip():
            raise HTTPException(status_code=400, detail="修订计划为空：请先在计划页「修订」模式填写或导入 revise_plan.md")
    elif not plan.strip() and body.items:
        # Only schema-legal items enter the orchestrator payload.
        legal = parse_items(body.items, require_valid=False)
        if not legal:
            raise HTTPException(status_code=400, detail="计划无效：items 中没有合法条目，无法启动")
        if len(legal) != len(body.items):
            raise HTTPException(
                status_code=400,
                detail="计划无效：items 含非法条目，已拒绝启动（请修正后重试，不会半份下发）",
            )
        try:
            plan = render_plan(
                {"template_id": body.template_id, "items": [item.as_dict() for item in legal]},
                template_id=body.template_id or None,
            )
        except PlanFormError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif not plan.strip():
        try:
            plan = str(read_plan_document(PROJECT_ROOT, workflow=workflow).get("content") or "")
        except PlanFormError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        if body.references:
            apply_reference_types(PROJECT_ROOT, body.references)
        return _workflow().start(workflow, plan_text=plan)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ValueError, ConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/workflow/stop")
def stop_workflow() -> dict[str, str]:
    try:
        return _workflow().stop()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class WorkflowResume(BaseModel):
    workflow: str


@app.post("/api/workflow/resume")
def workflow_resume(body: WorkflowResume) -> dict[str, Any]:
    from backend.workflow.config import ConfigError

    try:
        return _workflow().start(body.workflow, resume=True)
    except (ValueError, ConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/workflow/workflows")
def workflow_workflows() -> dict[str, Any]:
    return {"workflows": _workflow().workflows()}


@app.get("/api/workflow/preview")
def workflow_preview(workflow: str) -> dict[str, Any]:
    """Read-only injection preview for /plan 预览执行 (no run, no writes). <plan> = the saved plan the run would write."""
    try:
        return _workflow().preview(workflow, plan_text=_saved_plan_text(workflow))
    except Exception as exc:  # noqa: BLE001 - ConfigError / unknown workflow
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _saved_plan_text(workflow: str) -> str:
    """Same source /api/workflow/start uses: saved revise plan, or the plan form rendered with references."""
    from backend.services.plan_form import list_references, render_plan
    from backend.workflow.config import load_workflow as load_workflow_def

    try:
        wf_def = load_workflow_def(_workflow().root, workflow)[0]
        if wf_def.plan_file == "revise_plan.md":
            return str(read_plan_document(PROJECT_ROOT, workflow="revise-lca").get("content") or "")
        doc = read_plan_document(PROJECT_ROOT, workflow="full-lca")
        content = str(doc.get("content") or "") if isinstance(doc, dict) else ""
        if content.strip():
            return content
        fields = doc.get("fields") if isinstance(doc, dict) else None
        if isinstance(fields, dict) and fields.get("items"):
            return render_plan(fields, [str(r["name"]) for r in list_references(PROJECT_ROOT)])
        return ""
    except Exception:  # noqa: BLE001 - preview falls back to the workspace plan
        return ""


@app.get("/api/workflow/agent-models")
def workflow_agent_models() -> dict[str, Any]:
    from backend.workflow import agent_models

    return {"agents": agent_models.load(_workflow().root), "thinking_levels": list(agent_models.THINKING_LEVELS)}


@app.post("/api/workflow/agent-models")
def workflow_agent_models_save(body: dict[str, Any]) -> dict[str, Any]:
    from backend.workflow import agent_models

    try:
        data = agent_models.save(_workflow().root, str(body.get("node") or ""), str(body.get("agent") or ""),
                                 str(body.get("model") or ""), str(body.get("thinking") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"agents": data}


@app.get("/api/workflow/progress")
def workflow_progress(after_seq: int = 0, run_id: str = "") -> dict[str, Any]:
    """#1 structured activity stream: status + items after ``after_seq`` (``reset`` when run_id changed)."""
    return _workflow().progress(after_seq, run_id)


@app.get("/api/workflows")
def workflows_list() -> dict[str, Any]:
    """599ed0a workflow list shape: main = full-lca, revise = the workflow with start_rev: next, others demo."""
    out = []
    for w in _workflow().workflows():
        mode = "revise" if w.get("start_rev") == "next" else "main" if w["id"] == "full-lca" else "demo"
        out.append({"name": w["id"], "id": w["id"], "title": w.get("title") or w["id"], "mode": mode,
                    "file": f"workflows/{w['id']}.yaml"})
    out.sort(key=lambda w: {"main": 0, "revise": 1}.get(w["mode"], 2))
    return {"workflows": out}


@app.get("/api/workflow/status")
def workflow_status() -> dict[str, Any]:
    return _workflow().status()


@app.get("/api/workflow/harness")
def workflow_harness() -> dict[str, Any]:
    """Read-only harness YAML (rules, agents, specs, workflows) with load errors."""
    from backend.workflow.harness_view import harness_view

    return harness_view(_workflow().root)


@app.get("/api/workflow/events")
def workflow_events(offset: int = 0) -> dict[str, Any]:
    return _workflow().events(offset)


@app.get("/api/workflow/nodes/{node}/feedback/{round_no}")
def workflow_feedback(node: str, round_no: int) -> dict[str, Any]:
    try:
        return {"node": node, "round": round_no, "text": _workflow().feedback(node, round_no)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="反馈不存在") from exc


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
def read_plan(workflow: str = "full-lca") -> dict[str, Any]:
    try:
        return read_plan_document(PROJECT_ROOT, workflow=workflow)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/plan")
def write_plan(body: PlanUpdate, workflow: str = "full-lca") -> dict[str, Any]:
    """Autosave the plan form; the file is the workflow YAML's ``plan:`` path."""
    from backend.services.plan_form import parse_items

    try:
        # Persist only legal items; reject if the client sent illegal fragments.
        legal = parse_items(body.items, require_valid=False)
        if body.items and len(legal) != len(body.items):
            raise PlanFormError("计划无效：items 含非法条目，已拒绝保存")
        if not legal:
            raise PlanFormError("计划无效：items 中没有合法条目")
        save_plan(
            PROJECT_ROOT,
            {"template_id": body.template_id, "items": [item.as_dict() for item in legal]},
            workflow=workflow,
            template_id=body.template_id or None,
        )
        return {"status": "saved", **read_plan_document(PROJECT_ROOT, workflow=workflow)}
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/plan/template")
def download_plan_template(template_id: str = DEFAULT_TEMPLATE_ID) -> Response:
    """Empty plan YAML per harness/plan-templates section list (items + template_id only)."""
    tid = (template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    filename = template_download_filename(tid)
    return Response(
        content=template_yaml(tid, root=PROJECT_ROOT),
        media_type="application/yaml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/plan/templates")
def plan_templates() -> dict[str, Any]:
    """YAML-driven plan form templates under harness/plan-templates/."""
    return {"templates": list_plan_templates(PROJECT_ROOT)}


@app.get("/api/plan/templates/{template_id}")
def plan_template_detail(template_id: str) -> dict[str, Any]:
    try:
        return get_plan_template(PROJECT_ROOT, template_id)
    except PlanTemplateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/plan/import")
async def import_plan(
    file: UploadFile = File(...),
    workflow: str = "full-lca",
    overwrite: bool = False,
) -> dict[str, Any]:
    data = await file.read()
    try:
        return import_plan_bytes(
            PROJECT_ROOT,
            workflow=workflow,
            filename=file.filename or "",
            data=data,
            overwrite=overwrite,
        )
    except PlanFormConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/references")
def read_references() -> dict[str, Any]:
    return {"files": list_references(PROJECT_ROOT)}


@app.post("/api/references")
async def upload_references(
    files: list[UploadFile] = File(...),
    paths: list[str] | None = Form(default=None),
    types: list[str] | None = Form(default=None),
) -> dict[str, Any]:
    supplied = [item for item in (paths or []) if item is not None]
    if supplied and len(supplied) != len(files):
        raise HTTPException(status_code=400, detail="文件路径数量不匹配")
    if types and len(types) != len(files):
        raise HTTPException(status_code=400, detail="文件类型数量不匹配")
    uploads: list[tuple[str, bytes]] = []
    for index, item in enumerate(files):
        name = supplied[index] if supplied else (item.filename or "")
        uploads.append((name, await item.read()))
    try:
        saved = save_references(PROJECT_ROOT, uploads, types)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved", "saved": saved, "files": list_references(PROJECT_ROOT)}


@app.put("/api/references/{name:path}/type")
def write_reference_type(name: str, body: ReferenceTypeUpdate, ref_type: str = "") -> dict[str, Any]:
    try:
        item = save_reference_type(
            PROJECT_ROOT,
            name,
            body.type,
            current_type=ref_type or None,
        )
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return {"status": "saved", "file": item, "files": list_references(PROJECT_ROOT)}


@app.put("/api/references/{name:path}/note")
def write_reference_note(name: str, body: ReferenceNoteUpdate, ref_type: str = "") -> dict[str, Any]:
    try:
        item = save_reference_note(PROJECT_ROOT, name, body.note, ref_type=ref_type or None)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return {"status": "saved", "file": item, "files": list_references(PROJECT_ROOT)}


@app.delete("/api/references/{name:path}")
def remove_reference(name: str, ref_type: str = "") -> dict[str, Any]:
    try:
        delete_reference(PROJECT_ROOT, name, ref_type=ref_type or None)
    except PlanFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return {"status": "deleted", "files": list_references(PROJECT_ROOT)}


@app.get("/api/settings/env")
def read_env_keys() -> dict[str, str]:
    return load_flat(PROJECT_ROOT)


@app.get("/api/settings/locale")
def read_locale() -> dict[str, str]:
    values = load_flat(PROJECT_ROOT)
    return {"lang": normalize_gui_lang(values.get("GUI_LANG") or "zh")}


class LocaleUpdate(BaseModel):
    lang: str


@app.put("/api/settings/locale")
def write_locale(body: LocaleUpdate) -> dict[str, str]:
    lang = normalize_gui_lang(body.lang)
    upsert_flat(PROJECT_ROOT, {"GUI_LANG": lang})
    return {"lang": lang}
