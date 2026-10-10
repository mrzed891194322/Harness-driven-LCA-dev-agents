"""Generated prompts: ``harness/rules/generated/*.md.tmpl`` rendered per session.

Templates hold fixed wording plus ``{{var}}``; each has a default and an optional
``harness/.user/`` override (same overlay as rules). Variables come from the
session's effective spec permissions (``permissions.md.tmpl``) and the user
preferences file ``harness/settings.yaml`` (``language.md.tmpl``). Rendering is
fresh at every session creation (no cache, so a preference edit applies to the
next session without a restart), in the fixed order ``TEMPLATE_ORDER``. A
missing variable is an error, never an empty string.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from backend.core.runtime import harness_fs

GENERATED_DIR = "harness/rules/generated"
SETTINGS = "harness/settings.yaml"
TEMPLATE_ORDER = ("permissions", "language")
_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
DEFAULT_SETTINGS: dict[str, Any] = {"version": 1, "language": {"output": "中文", "documents": "中文"}}


class TemplateError(ValueError):
    pass


def template_rel(name: str) -> str:
    if name not in TEMPLATE_ORDER:
        raise TemplateError(f"unknown template {name!r}")
    return f"{GENERATED_DIR}/{name}.md.tmpl"


def template_vars(text: str) -> list[str]:
    return sorted(set(_VAR.findall(text)))


def render(text: str, variables: dict[str, Any], *, label: str = "template") -> str:
    missing = [v for v in template_vars(text) if v not in variables or variables[v] is None]
    if missing:
        raise TemplateError(f"{label}: 缺少变量 {', '.join(missing)}")

    def sub(m: re.Match[str]) -> str:
        value = variables[m.group(1)]
        if isinstance(value, (list, tuple)):
            return "\n".join(f"- {v}" for v in value) if value else "- （无）"
        return str(value)

    return _VAR.sub(sub, text).strip()


def load_settings(project_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    found = harness_fs.resolve(project_root, SETTINGS)
    if found is None:
        return dict(DEFAULT_SETTINGS), {"rel": SETTINGS, "source": "builtin", "sha256": ""}
    try:
        data = yaml.safe_load(found.path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise TemplateError(f"{SETTINGS}: {exc}") from exc
    if not isinstance(data, dict):
        raise TemplateError(f"{SETTINGS}: must be a mapping")
    return data, {"rel": SETTINGS, "source": found.source, "sha256": found.sha256}


def permission_vars(policy: Any, project_root: Path | None = None) -> dict[str, Any]:
    p = policy.to_dict() if hasattr(policy, "to_dict") else dict(policy or {})
    prefixes = []
    if project_root is not None:
        prefixes = sorted({str(project_root).rstrip("/") + "/", str(project_root.resolve()).rstrip("/") + "/"},
                          key=len, reverse=True)

    def rel(paths: Any) -> list[str]:
        out = []
        for item in paths or []:
            text = str(item)
            for prefix in prefixes:
                if text.startswith(prefix):
                    text = text[len(prefix):]
                    break
            out.append(text)
        return out

    return {
        "readable_paths": rel(p.get("allowed_read_globs")),
        "writable_paths": rel(p.get("allowed_write_globs")),
        "allowed_tools": list(p.get("allowed_tools") or []),
        "official_deliverables": rel(p.get("denied_write_globs")),
        "shell_note": "\n不能使用 shell。" if p.get("deny_shell") else "",
    }


def language_vars(settings: dict[str, Any]) -> dict[str, Any]:
    lang = settings.get("language") if isinstance(settings.get("language"), dict) else {}
    return {"output_language": lang.get("output"), "document_language": lang.get("documents")}


def render_session(project_root: Path, policy: Any, *, require_all: bool = False) -> list[dict[str, Any]]:
    """Render every template in fixed order; returns prompt segments with origin.

    A template file absent from both default and user dirs is skipped (projects
    without generated prompts); ``doctor`` (``require_all``) reports it. A present
    template with a missing variable always raises.
    """
    settings, settings_ref = load_settings(project_root)
    variables = {"permissions": permission_vars(policy, project_root), "language": language_vars(settings)}
    segments: list[dict[str, Any]] = []
    for name in TEMPLATE_ORDER:
        rel = template_rel(name)
        found = harness_fs.resolve(project_root, rel)
        if found is None:
            if require_all:
                raise TemplateError(f"{rel}: 模板不存在")
            continue
        text = found.path.read_text(encoding="utf-8")
        segments.append({
            "id": f"generated:{name}",
            "kind": "generated",
            "source": rel,
            "origin": found.source,
            "file_sha256": found.sha256,
            "variables_from": "spec permissions.yaml（本会话生效）" if name == "permissions" else f"{SETTINGS}（{settings_ref['source']}）",
            "content": render(text, variables[name], label=rel),
        })
    return segments


def fingerprint_refs(project_root: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for rel in [template_rel(n) for n in TEMPLATE_ORDER] + [SETTINGS]:
        found = harness_fs.resolve(project_root, rel)
        out[rel] = {"source": found.source, "sha256": found.sha256} if found else {"source": "missing", "sha256": "missing"}
    return out


def doctor_check(project_root: Path) -> list[str]:
    """Every template exists and renders with sample permissions + current settings."""
    sample = {"allowed_tools": ["read"], "allowed_read_globs": ["harness/**"], "allowed_write_globs": [],
              "denied_write_globs": [], "deny_shell": False}
    try:
        render_session(project_root, sample, require_all=True)
    except TemplateError as exc:
        return [str(exc)]
    return []


# --------------------------------------------------------------------------- GUI helpers


def read_item(project_root: Path, rel: str) -> dict[str, Any]:
    _check_editable(rel)
    found = harness_fs.resolve(project_root, rel)
    default = harness_fs.default_path(project_root, rel)
    return {
        "rel": rel,
        "source": found.source if found else "missing",
        "text": found.path.read_text(encoding="utf-8") if found else "",
        "default_text": default.read_text(encoding="utf-8") if default.is_file() else "",
        "variables": template_vars(found.path.read_text(encoding="utf-8")) if found and rel.endswith(".tmpl") else [],
    }


def save_item(project_root: Path, rel: str, text: str) -> dict[str, Any]:
    _check_editable(rel)
    if rel.endswith(".tmpl"):
        name = rel.rsplit("/", 1)[-1].removesuffix(".md.tmpl")
        allowed = {"permissions": set(permission_vars({})), "language": {"output_language", "document_language"}}[name]
        unknown = [v for v in template_vars(text) if v not in allowed]
        if unknown:
            raise TemplateError(f"{rel}: 未知变量 {', '.join(unknown)}（可用：{', '.join(sorted(allowed))}）")
    else:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise TemplateError(f"{rel}: {exc}") from exc
        if not isinstance(data, dict):
            raise TemplateError(f"{rel}: must be a mapping")
    path = harness_fs.user_path(project_root, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return read_item(project_root, rel)


def reset_item(project_root: Path, rel: str) -> dict[str, Any]:
    _check_editable(rel)
    path = harness_fs.user_path(project_root, rel)
    if path.is_file():
        path.unlink()
    return read_item(project_root, rel)


def editable_items() -> list[str]:
    return [template_rel(n) for n in TEMPLATE_ORDER] + [SETTINGS]


def _check_editable(rel: str) -> None:
    if rel not in editable_items():
        raise TemplateError(f"not an editable generated-prompt file: {rel}")
