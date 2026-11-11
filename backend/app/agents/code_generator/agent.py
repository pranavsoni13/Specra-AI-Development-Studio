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


def _missing_application_parts(files: list) -> list[str]:
    """Validate that the model supplied a wired API router and a rendered UI feature."""
    source_by_path = {
        PurePosixPath(item.path.strip()).as_posix().casefold(): item
        for item in files
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
    main_source = main_entry.content if main_entry else ""
    app_source = app_entry.content if app_entry else ""

    wired_router = any(
        "APIRouter" in source_by_path[path].content
        and re.search(
            r"@\w+\.(?:get|post|put|patch|delete)\s*\(",
            source_by_path[path].content,
            re.IGNORECASE,
        )
        and "include_router" in main_source
        and PurePosixPath(path).stem.casefold() in main_source.casefold()
        for path in router_paths
    )
    wired_component = any(
        len(source_by_path[path].content.strip()) >= 80
        and "export" in source_by_path[path].content
        and PurePosixPath(path).stem.casefold() in app_source.casefold()
        for path in ui_component_paths
    )

    missing = []
    if not wired_router:
        missing.append(
            "a project API module under backend/app/routes or backend/app/api/routes "
            "with an APIRouter, an HTTP route, and registration in backend/app/main.py"
        )
    if not wired_component:
        missing.append(
            "a project React component under frontend/src/components or frontend/src/features "
            "imported and rendered by frontend/src/App.jsx"
        )
    return missing


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
        last_generation_error = None
        draft = None
        for attempt in range(2):
            try:
                draft = self.client.generate_structured(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=prompt,
                    output_schema=CodeBundleDraft,
                )
            except RuntimeError as exc:
                # Retry once for malformed/truncated structured output. Provider
                # authentication and connectivity errors should fail immediately.
                if "failed the CodeBundleDraft schema" not in str(exc):
                    raise
                last_generation_error = exc
                if attempt == 0:
                    prompt += (
                        "\n\nCORRECTION REQUEST: Your previous response was not valid "
                        "CodeBundleDraft JSON. Return one complete JSON object matching the "
                        "schema exactly. Keep the application concise, but include every "
                        "required source file and complete file contents."
                    )
                    continue
                break

            missing_parts = _missing_application_parts(draft.files)
            if not missing_parts:
                break

            last_generation_error = ValueError("; ".join(missing_parts))
            if attempt == 0:
                prompt += (
                    "\\n\\nCORRECTION REQUEST: Your previous draft was incomplete. "
                    "Regenerate the complete project source bundle and specifically fix "
                    "these missing integration requirements:\n- "
                    + "\n- ".join(missing_parts)
                    + "\nReturn the complete corrected JSON object, including all files."
                )
                continue
            break

        if draft is None or last_generation_error and _missing_application_parts(draft.files):
            detail = (
                str(last_generation_error)
                if last_generation_error
                else "The model returned no complete project bundle."
            )
            raise ValueError(
                "The coding model did not produce a complete, integrated application after one correction attempt. "
                "No code bundle was saved. Missing or invalid output: "
                + detail
                + ". Check the configured code-generation model and its output capacity, then retry."
            ) from last_generation_error


        # The active project name wins over any model-invented naming.
        if draft.project_name.strip() != project_name:
            draft = draft.model_copy(update={"project_name": project_name})
        bundle = self.quality_controller.validate(draft)
        return bundle
