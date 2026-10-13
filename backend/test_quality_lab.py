from app.core.quality_lab import evaluate_blueprint_quality


def _clean_artifacts():
    return {
        "requirements": {
            "project_name": "Campus Portal",
            "functional_requirements": [
                "Students view announcements.",
                "Instructors publish announcements.",
            ],
            "clarifications_needed": [],
        },
        "project_plan": {
            "milestones": [
                {
                    "name": "Announcements",
                    "requirement_refs": ["FR-001", "FR-002"],
                    "tasks": [
                        {"description": "Build viewing.", "requirement_refs": ["FR-001"]},
                        {"description": "Build publishing.", "requirement_refs": ["FR-002"]},
                    ],
                }
            ]
        },
        "architecture": {
            "components": [
                {"name": "Reader", "related_requirements": ["FR-001"]},
                {"name": "Publisher", "related_requirements": ["FR-002"]},
            ],
            "api_endpoints": [
                {"name": "GET /announcements", "related_requirements": ["FR-001"]},
                {"name": "POST /announcements", "related_requirements": ["FR-002"]},
            ],
            "architecture_decisions": [
                {"decision": "Layered", "related_requirements": ["FR-001", "FR-002"]},
            ],
        },
        "technical_review": {
            "overall_status": "PASS",
            "requirement_coverage": [
                {"requirement_id": "FR-001", "in_project_plan": True, "in_architecture": True, "in_api": True},
                {"requirement_id": "FR-002", "in_project_plan": True, "in_architecture": True, "in_api": True},
            ],
            "unsupported_additions": [],
            "architecture_consistency_issues": [],
            "findings": [],
            "recommended_actions": [],
        },
    }


def test_complete_blueprint_passes_deterministic_quality_checks():
    result = evaluate_blueprint_quality("p-1", {"project_name": "Campus Portal", "status": "completed"}, _clean_artifacts())
    assert result["overall_status"] == "PASS"
    assert result["scope"] == "blueprint"
    assert result["metrics"]["functional_requirements"] == 2
    assert result["metrics"]["coverage_percentages"] == {
        "project_plan": 100.0,
        "architecture_components": 100.0,
        "api_capabilities": 100.0,
    }
    assert all(check["status"] == "PASS" for check in result["checks"])


def test_missing_architecture_coverage_is_flagged():
    artifacts = _clean_artifacts()
    artifacts["architecture"]["components"].pop()
    result = evaluate_blueprint_quality("p-1", {}, artifacts)
    assert result["overall_status"] == "NEEDS_ATTENTION"
    check = next(item for item in result["checks"] if item["id"] == "architecture-coverage")
    assert check["status"] == "NEEDS_ATTENTION"
    assert "FR-002" in " ".join(check["details"])


def test_unknown_requirement_reference_is_flagged():
    artifacts = _clean_artifacts()
    artifacts["project_plan"]["milestones"][0]["tasks"][0]["requirement_refs"].append("FR-999")
    result = evaluate_blueprint_quality("p-1", {}, artifacts)
    check = next(item for item in result["checks"] if item["id"] == "reference-integrity")
    assert check["status"] == "NEEDS_ATTENTION"
    assert "FR-999" in " ".join(check["details"])


def test_missing_requirements_blocks_assessment():
    result = evaluate_blueprint_quality("p-1", {}, {})
    assert result["overall_status"] == "NOT_READY"
    assert next(item for item in result["checks"] if item["id"] == "requirements-present")["status"] == "BLOCKED"


def test_open_clarifications_are_not_silently_ignored():
    artifacts = _clean_artifacts()
    artifacts["requirements"]["clarifications_needed"] = ["Confirm whether archived announcements are searchable."]
    result = evaluate_blueprint_quality("p-1", {}, artifacts)
    check = next(item for item in result["checks"] if item["id"] == "clarifications")
    assert check["status"] == "NEEDS_ATTENTION"
