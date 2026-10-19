import json
import os
from pathlib import PurePosixPath
from typing import Any

from app.agents.code_generator.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.agents.code_generator.quality import CodeGenerationQualityController
from app.agents.code_generator.schemas import CodeBundle, CodeBundleDraft
from app.core.llm.client import LocalLLMClient
from app.core.model_config import SOFTWARE_ARCHITECT_MODEL


def _dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return value if isinstance(value, dict) else {}


def _bounded_json(value: Any, limit: int = 9000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > limit:
        return text[:limit] + "…[truncated to fit code-generation context]"
    return text


class CodeGenerationAgent:
    """Generate a VS Code starter bundle without executing model-produced files."""

    def __init__(self, model_name: str | None = None):
        # Source generation needs more output tokens than blueprint/review tasks.
        # A dedicated model is optional; by default use Specra's architect model.
        self.model_name = (
            (model_name or os.getenv("CODE_GENERATION_MODEL", "")).strip()
            or SOFTWARE_ARCHITECT_MODEL
        )
        self.client = LocalLLMClient(
            model_name=self.model_name,
            num_predict=12000,
            keep_alive="30m",
            debug=False,
        )
        self.quality_controller = CodeGenerationQualityController()

    def generate(
        self,
        *,
        project: dict,
        artifacts: dict,
        test_suite: dict | None = None,
        additional_constraints: str = "",
    ) -> CodeBundle:
        requirements = _dict(artifacts.get("requirements"))
        project_name = (
            str(requirements.get("project_name") or "").strip()
            or str(project.get("project_name") or "").strip()
            or "Specra Generated Project"
        )
        prompt = USER_PROMPT_TEMPLATE.format(
            project_name=project_name,
            brief=str(project.get("idea") or "")[:6000],
            requirements_json=_bounded_json(requirements, 11000),
            plan_json=_bounded_json(artifacts.get("project_plan") or {}, 7000),
            architecture_json=_bounded_json(artifacts.get("architecture") or {}, 9000),
            review_json=_bounded_json(artifacts.get("technical_review") or {}, 5000),
            tests_json=_bounded_json(
                {
                    "summary": (test_suite or {}).get("summary", ""),
                    "cases": [
                        {
                            "test_id": case.get("test_id"),
                            "requirement_id": case.get("requirement_id"),
                            "title": case.get("title"),
                            "steps": case.get("steps"),
                            "expected_result": case.get("expected_result"),
                            "status": case.get("status", "not_run"),
                        }
                        for case in (test_suite or {}).get("cases", [])[:20]
                    ],
                },
                7000,
            ),
            constraints=(additional_constraints.strip() or "No additional constraints supplied.")[:5000],
        )
        draft = self.client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=CodeBundleDraft,
        )
        # Do not silently label a generic health-check scaffold as generated
        # application code. Require real backend and frontend feature modules first.
        source_paths = {
            PurePosixPath(item.path.strip()).as_posix().casefold()
            for item in draft.files
        }
        backend_features = {
            path for path in source_paths
            if path.startswith("backend/app/")
            and path not in {"backend/app/main.py", "backend/app/__init__.py"}
        }
        frontend_features = {
            path for path in source_paths
            if path.startswith("frontend/src/")
            and path not in {
                "frontend/src/app.jsx",
                "frontend/src/main.jsx",
                "frontend/src/styles.css",
            }
        }
        if not backend_features or not frontend_features:
            raise ValueError(
                "The model returned a generic starter instead of project-specific application code. "
                "No bundle was saved. Check the configured code-generation model and output limits, "
                "then retry. The generator must return at least one backend feature module and one "
                "frontend feature module."
            )

        # The active project name wins over any model-invented naming.
        if draft.project_name.strip() != project_name:
            draft = draft.model_copy(update={"project_name": project_name})
        bundle = self.quality_controller.validate(draft)
        return bundle
