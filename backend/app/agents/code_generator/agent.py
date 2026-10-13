import json
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

    def __init__(self, model_name: str = SOFTWARE_ARCHITECT_MODEL):
        self.model_name = model_name
        self.client = LocalLLMClient(model_name=model_name)
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
        # The active project name wins over any model-invented naming.
        if draft.project_name.strip() != project_name:
            draft = draft.model_copy(update={"project_name": project_name})
        bundle = self.quality_controller.validate(draft)
        return bundle
