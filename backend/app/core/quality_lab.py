from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _refs(value: Any, key: str) -> set[str]:
    return {
        str(reference).strip()
        for reference in _list(_dict(value).get(key))
        if str(reference).strip()
    }


def _coverage_percent(covered: set[str], required: set[str]) -> float:
    if not required:
        return 0.0
    return round((len(required & covered) / len(required)) * 100, 1)


def evaluate_blueprint_quality(project_id: str, project: dict, artifacts: dict) -> dict:
    """Evaluate the saved blueprint deterministically; never executes generated code."""
    requirements = _dict(artifacts.get("requirements"))
    plan = _dict(artifacts.get("project_plan"))
    architecture = _dict(artifacts.get("architecture"))
    review = _dict(artifacts.get("technical_review") or artifacts.get("review"))

    functional = [
        str(item).strip()
        for item in _list(requirements.get("functional_requirements"))
        if str(item).strip()
    ]
    required_ids = {f"FR-{index:03d}" for index in range(1, len(functional) + 1)}

    milestones = _list(plan.get("milestones"))
    plan_refs: set[str] = set()
    for milestone in milestones:
        plan_refs.update(_refs(milestone, "requirement_refs"))
        for task in _list(_dict(milestone).get("tasks")):
            plan_refs.update(_refs(task, "requirement_refs"))

    components = _list(architecture.get("components"))
    endpoints = _list(architecture.get("api_endpoints"))
    decisions = _list(architecture.get("architecture_decisions"))
    component_refs = set().union(*(_refs(item, "related_requirements") for item in components)) if components else set()
    api_refs = set().union(*(_refs(item, "related_requirements") for item in endpoints)) if endpoints else set()
    decision_refs = set().union(*(_refs(item, "related_requirements") for item in decisions)) if decisions else set()
    all_references = plan_refs | component_refs | api_refs | decision_refs

    coverage_rows = _list(review.get("requirement_coverage"))
    coverage_by_id = {
        str(_dict(row).get("requirement_id", "")).strip(): _dict(row)
        for row in coverage_rows
        if _dict(row).get("requirement_id")
    }

    checks: list[dict] = []

    def add(check_id: str, title: str, status: str, summary: str, details: list[str] | None = None) -> None:
        checks.append({
            "id": check_id,
            "title": title,
            "status": status,
            "summary": summary,
            "details": details or [],
        })

    if requirements:
        add("requirements-present", "Requirements artifact", "PASS", f"{len(functional)} functional requirement(s) are available.")
    else:
        add("requirements-present", "Requirements artifact", "BLOCKED", "Generate requirements before evaluating downstream artifacts.")

    missing_plan = sorted(required_ids - plan_refs)
    unknown_plan = sorted(plan_refs - required_ids)
    add(
        "plan-coverage",
        "Plan traceability",
        "PASS" if required_ids and not missing_plan and not unknown_plan else ("BLOCKED" if not plan else "NEEDS_ATTENTION"),
        f"{len(required_ids & plan_refs)} of {len(required_ids)} functional requirements are referenced by milestones or tasks.",
        ([f"Missing from plan: {', '.join(missing_plan)}"] if missing_plan else [])
        + ([f"Unknown plan references: {', '.join(unknown_plan)}"] if unknown_plan else []),
    )

    missing_architecture = sorted(required_ids - component_refs)
    unknown_architecture = sorted(component_refs - required_ids)
    add(
        "architecture-coverage",
        "Architecture component traceability",
        "PASS" if required_ids and not missing_architecture and not unknown_architecture else ("BLOCKED" if not architecture else "NEEDS_ATTENTION"),
        f"{len(required_ids & component_refs)} of {len(required_ids)} functional requirements are referenced by architecture components.",
        ([f"Missing from components: {', '.join(missing_architecture)}"] if missing_architecture else [])
        + ([f"Unknown component references: {', '.join(unknown_architecture)}"] if unknown_architecture else []),
    )

    missing_api = sorted(required_ids - api_refs)
    unknown_api = sorted(api_refs - required_ids)
    add(
        "api-coverage",
        "API capability traceability",
        "PASS" if required_ids and not missing_api and not unknown_api else ("BLOCKED" if not architecture else "NEEDS_ATTENTION"),
        f"{len(required_ids & api_refs)} of {len(required_ids)} functional requirements are referenced by API capabilities.",
        ([f"Missing from API capabilities: {', '.join(missing_api)}"] if missing_api else [])
        + ([f"Unknown API references: {', '.join(unknown_api)}"] if unknown_api else []),
    )

    unknown_refs = sorted(all_references - required_ids)
    add(
        "reference-integrity",
        "Requirement reference integrity",
        "PASS" if all_references and not unknown_refs else ("BLOCKED" if not all_references else "NEEDS_ATTENTION"),
        "All artifact requirement references must resolve to IDs generated from the current requirements.",
        ([f"Unknown references: {', '.join(unknown_refs)}"] if unknown_refs else []),
    )

    clarifications = _list(requirements.get("clarifications_needed"))
    add(
        "clarifications",
        "Open clarification questions",
        "NEEDS_ATTENTION" if clarifications else "PASS",
        f"{len(clarifications)} open clarification question(s).",
        [str(item) for item in clarifications],
    )

    unsupported = _list(review.get("unsupported_additions"))
    consistency = _list(review.get("architecture_consistency_issues"))
    findings = _list(review.get("findings"))
    severe_findings = [
        _dict(item) for item in findings
        if str(_dict(item).get("severity", "")).lower() in {"high", "critical"}
    ]
    review_status = str(review.get("overall_status", "NOT_AVAILABLE"))
    review_ok = review_status == "PASS" and not unsupported and not consistency and not severe_findings
    review_details = []
    if unsupported:
        review_details.append(f"{len(unsupported)} unsupported addition(s) flagged.")
    if consistency:
        review_details.append(f"{len(consistency)} architecture consistency issue(s) flagged.")
    if severe_findings:
        review_details.append(f"{len(severe_findings)} high/critical finding(s) recorded.")
    add(
        "technical-review",
        "Technical review",
        "PASS" if review_ok else ("BLOCKED" if review_status == "NOT_AVAILABLE" else "NEEDS_ATTENTION"),
        f"Reviewer status: {review_status}.",
        review_details or ([str(item) for item in _list(review.get("recommended_actions"))] if not review_ok else []),
    )

    required_count = len(required_ids)
    coverage_percentages = {
        "project_plan": _coverage_percent(plan_refs, required_ids),
        "architecture_components": _coverage_percent(component_refs, required_ids),
        "api_capabilities": _coverage_percent(api_refs, required_ids),
    }
    blocked = any(item["status"] == "BLOCKED" for item in checks)
    needs_attention = any(item["status"] == "NEEDS_ATTENTION" for item in checks)
    overall_status = "NOT_READY" if blocked else ("NEEDS_ATTENTION" if needs_attention else "PASS")

    actions = []
    for check in checks:
        if check["status"] in {"BLOCKED", "NEEDS_ATTENTION"}:
            actions.append(f"{check['title']}: {check['summary']}")
            actions.extend(check["details"])
    if overall_status == "PASS":
        actions.append("Blueprint checks passed. Generate application code in an isolated workspace and run its test suite before claiming implementation-level test success.")
    else:
        actions.append("This assessment checks saved blueprint consistency only; no generated application code was executed.")

    return {
        "project_id": project_id,
        "project_name": requirements.get("project_name") or project.get("project_name"),
        "overall_status": overall_status,
        "scope": "blueprint",
        "execution_note": "Deterministic blueprint checks only. This endpoint does not execute generated application code or replace unit/integration testing.",
        "metrics": {
            "functional_requirements": required_count,
            "plan_milestones": len(milestones),
            "plan_tasks": sum(len(_list(_dict(item).get("tasks"))) for item in milestones),
            "architecture_components": len(components),
            "api_capabilities": len(endpoints),
            "review_findings": len(findings),
            "unsupported_additions": len(unsupported),
            "architecture_consistency_issues": len(consistency),
            "open_clarifications": len(clarifications),
            "coverage_percentages": coverage_percentages,
        },
        "checks": checks,
        "recommended_actions": list(dict.fromkeys(actions)),
    }
