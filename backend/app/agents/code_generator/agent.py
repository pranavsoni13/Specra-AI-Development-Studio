import json
import os
import re
from pathlib import PurePosixPath
from typing import Any

from app.agents.code_generator.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.agents.code_generator.quality import CodeGenerationQualityController
from app.agents.code_generator.schemas import CodeBundle, CodeBundleDraft
from app.core.llm.client import LocalLLMClient
from app.core.model_config import CODE_GENERATION_MODEL


def _dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return value if isinstance(value, dict) else {}


def _bounded_json(value: Any, limit: int = 9000) -> str:
    """Return valid compact JSON; never cut a serialized object mid-brace."""
    def compact(node: Any, *, string_limit: int, list_limit: int, depth: int = 0):
        if isinstance(node, str):
            return node if len(node) <= string_limit else node[:string_limit] + " …[text shortened]"
        if isinstance(node, dict):
            if depth >= 8:
                return {"_specra_note": "nested context shortened"}
            return {
                str(key): compact(
                    item,
                    string_limit=string_limit,
                    list_limit=list_limit,
                    depth=depth + 1,
                )
                for key, item in list(node.items())[:64]
            }
        if isinstance(node, (list, tuple)):
            if depth >= 8:
                return []
            return [
                compact(
                    item,
                    string_limit=string_limit,
                    list_limit=list_limit,
                    depth=depth + 1,
                )
                for item in list(node)[:list_limit]
            ]
        if node is None or isinstance(node, (bool, int, float)):
            return node
        return str(node)[:string_limit]

    for string_limit, list_limit in (
        (2400, 16),
        (1600, 12),
        (1000, 8),
        (600, 6),
        (350, 4),
        (180, 2),
        (80, 1),
    ):
        serialized = json.dumps(
            compact(value, string_limit=string_limit, list_limit=list_limit),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        if len(serialized) <= limit:
            return serialized

    original = json.dumps(value, ensure_ascii=False, default=str)
    return json.dumps(
        {
            "_specra_context_truncated": True,
            "original_characters": len(original),
            "summary": original[: max(16, limit - 100)],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


class CodeGenerationAgent:
    """Generate a VS Code starter bundle without executing model-produced files."""

    def __init__(self, model_name: str | None = None):
        # Use a dedicated coding model and a larger output budget; blueprint
        # models often return short explanations instead of complete source trees.
        self.model_name = (
            (model_name or os.getenv("CODE_GENERATION_MODEL", "")).strip()
            or CODE_GENERATION_MODEL
        )
        self.client = LocalLLMClient(
            model_name=self.model_name,
            num_predict=20000,
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
        # Require an integrated application, not just loose files or a validation report.
        source_by_path = {
            PurePosixPath(item.path.strip()).as_posix().casefold(): item
            for item in draft.files
        }
        router_paths = [
            path for path in source_by_path
            if path.endswith(".py")
            and (
                path.startswith("backend/app/routes/")
                or path.startswith("backend/app/api/routes/")
            )
            and not path.endswith("/__init__.py")
        ]
        ui_component_paths = [
            path for path in source_by_path
            if path.endswith((".jsx", ".tsx", ".js", ".ts"))
            and (
                path.startswith("frontend/src/components/")
                or path.startswith("frontend/src/features/")
            )
        ]
        main_entry = source_by_path.get("backend/app/main.py")
        app_entry = source_by_path.get("frontend/src/app.jsx")

        wired_router = False
        main_source = main_entry.content if main_entry else ""
        for path in router_paths:
            module_name = PurePosixPath(path).stem.casefold()
            router_source = source_by_path[path].content
            has_api_router = "APIRouter" in router_source
            has_http_route = bool(
                re.search(
                    r"@\w+\.(?:get|post|put|patch|delete)\s*\(",
                    router_source,
                    re.IGNORECASE,
                )
            )
            if (
                has_api_router
                and has_http_route
                and "include_router" in main_source
                and module_name in main_source.casefold()
            ):
                wired_router = True
                break

        wired_component = False
        app_source = app_entry.content if app_entry else ""
        for path in ui_component_paths:
            component_name = PurePosixPath(path).stem
            component_source = source_by_path[path].content
            if (
                len(component_source.strip()) >= 80
                and "export" in component_source
                and component_name.casefold() in app_source.casefold()
            ):
                wired_component = True
                break

        if not wired_router or not wired_component:
            missing_parts = []
            if not wired_router:
                missing_parts.append(
                    "a backend router imported and registered from backend/app/main.py"
                )
            if not wired_component:
                missing_parts.append(
                    "a project-specific React component imported and rendered from frontend/src/App.jsx"
                )
            raise ValueError(
                "The model did not return a complete, integrated application. "
                "No code bundle was saved. Missing: "
                + "; ".join(missing_parts)
                + ". Retry generation; if this keeps happening, configure a code-generation model "
                "with enough output capacity. Specra will not report a generic scaffold as generated code."
            )

        # The active project name wins over any model-invented naming.
        if draft.project_name.strip() != project_name:
            draft = draft.model_copy(update={"project_name": project_name})
        bundle = self.quality_controller.validate(draft)
        return bundle
