import json
from typing import Any

from app.agents.project_copilot.prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.agents.project_copilot.schemas import (
    CopilotAnswerDraft,
    CopilotChangeProposal,
)
from app.core.llm.client import LocalLLMClient
from app.core.model_config import TECHNICAL_REVIEWER_MODEL


ARTIFACT_TITLES = {
    "requirements": "Requirements",
    "project_plan": "Project plan",
    "architecture": "Architecture",
    "technical_review": "Technical review",
    "rag_validation": "RAG validation",
}


def _as_dict(value: Any) -> dict:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return value
    return {}


def _trim_json(value: Any, max_chars: int = 16000) -> str:
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    if len(serialized) <= max_chars:
        return serialized
    return serialized[:max_chars] + "…[truncated to fit project context budget]"


class ProjectCopilotAgent:
    """Answer project-scoped questions with validated source references."""

    def __init__(self, model_name: str = TECHNICAL_REVIEWER_MODEL):
        self.model_name = model_name
        self.client = LocalLLMClient(model_name=model_name)

    @staticmethod
    def build_sources(
        artifacts: dict,
        versions: dict,
        context_records: list[dict],
    ) -> list[dict]:
        sources: list[dict] = []
        for artifact_key, title in ARTIFACT_TITLES.items():
            artifact = artifacts.get(artifact_key)
            if not artifact:
                continue
            payload = _as_dict(artifact)
            version = versions.get(artifact_key, 0)
            source_id = f"artifact:{artifact_key}:v{version}"
            sources.append({
                "source_id": source_id,
                "title": f"{title} (v{version})",
                "kind": "artifact",
                "content": _trim_json(payload, max_chars=7000),
            })

        remaining_budget = 11000
        for record in context_records[:8]:
            raw = str(record.get("content", ""))
            if remaining_budget <= 0:
                break
            excerpt = raw[:remaining_budget]
            source_id = f"context:{record.get('context_id', '')}"
            sources.append({
                "source_id": source_id,
                "title": str(record.get("name") or "Saved project context")[:240],
                "kind": "saved_context",
                "content": excerpt,
            })
            remaining_budget -= len(excerpt)

        return sources

    def answer(
        self,
        *,
        project: dict,
        artifacts: dict,
        versions: dict,
        context_records: list[dict],
        history: list[dict],
        question: str,
    ) -> dict:
        sources = self.build_sources(artifacts, versions, context_records)
        source_catalogue = [
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "kind": source["kind"],
                "content": source["content"],
            }
            for source in sources
        ]
        # A small tail of history is sufficient for conversational reference,
        # and protects both latency and model context on small local models.
        recent_history = [
            {
                "role": item["role"],
                "content": str(item["content"])[:3000],
            }
            for item in history[-8:]
        ]

        prompt = USER_PROMPT_TEMPLATE.format(
            project_name=(
                str(project.get("project_name") or "").strip()
                or str(_as_dict(artifacts.get("requirements")).get("project_name") or "Untitled project")
            ),
            project_id=project.get("project_id", "unknown"),
            project_brief=str(project.get("idea") or "")[:6000],
            sources_json=_trim_json(source_catalogue, max_chars=26000),
            history_json=_trim_json(recent_history, max_chars=10000),
            question=question.strip(),
        )

        draft = self.client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            output_schema=CopilotAnswerDraft,
        )

        source_map = {
            source["source_id"]: {
                "source_id": source["source_id"],
                "title": source["title"],
                "kind": source["kind"],
            }
            for source in sources
        }
        accepted_refs = list(dict.fromkeys(
            reference
            for reference in draft.source_refs
            if reference in source_map
        ))
        if draft.source_refs and len(accepted_refs) != len(set(draft.source_refs)):
            answer = draft.answer.rstrip()
            answer += (
                "\n\nNote: One or more model-suggested source references were "
                "discarded because they were not in the supplied project catalogue."
            )
        else:
            answer = draft.answer

        changes = [
            change.model_dump()
            for change in draft.proposed_changes
        ]
        return {
            "answer": answer,
            "source_refs": [
                {**source_map[reference]}
                for reference in accepted_refs
            ],
            "proposed_changes": changes,
            "model_name": self.model_name,
        }
