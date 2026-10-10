"""GUI service for generated prompts: templates + user preferences + preview."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from backend.core.workflow.execution import generated_prompts as gp
from backend.services.project_paths import PROJECT_ROOT


class PromptTemplates:
    def __init__(self, project_root: Path | None = None) -> None:
        self.root = project_root or PROJECT_ROOT

    def list(self) -> dict[str, Any]:
        return {"items": [gp.read_item(self.root, rel) for rel in gp.editable_items()],
                "order": list(gp.TEMPLATE_ORDER)}

    def save(self, rel: str, text: str) -> dict[str, Any]:
        return gp.save_item(self.root, rel, text)

    def reset(self, rel: str) -> dict[str, Any]:
        return gp.reset_item(self.root, rel)

    def preview(self, stage: str, role: str, workflow: str = "harness/LCA-main.yaml") -> dict[str, Any]:
        """Render exactly what a new session for stage+role would get now (no session, no model)."""
        from backend.core.agents.injection import runtime_system_prompt
        from backend.core.runtime.capabilities import base_capabilities
        from backend.core.runtime.launch_spec import build_session_launch_spec
        from backend.core.workflow.config.loader import load_workflow

        wf = load_workflow(self.root / workflow, project_root=self.root, capabilities=base_capabilities())
        st = wf.stage_by_id(stage)
        assignment = next(
            (wf.assignments[a] for a in st.steps if wf.assignments[a].role == role), None
        )
        if assignment is None:
            raise ValueError(f"stage {stage} has no role {role}")
        with tempfile.TemporaryDirectory(prefix="prompt-preview-") as tmp:
            launch = build_session_launch_spec(
                wf, wf.bundles[assignment.assignment_id], project_root=self.root,
                workspace_root=Path(tmp), worker="pi", model="", stage=st, assignment=assignment,
                run_id="preview", attempt=1, session_key="preview", run_context={"run_id": "preview"},
            )
        generated = next((s.content for s in launch.system_sections if s.id == "generated_prompts"), "")
        return {
            "stage": stage,
            "role": role,
            "generated": generated,
            "segments": [{k: v for k, v in s.items() if k != "content"} for s in launch.prompt_segments],
            "system_prompt": runtime_system_prompt(launch),
        }
