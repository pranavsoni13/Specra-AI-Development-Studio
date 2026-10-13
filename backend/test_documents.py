from app.core.documents import render_project_document


def sample_project_and_artifacts():
    project = {"project_id": "project-123", "project_name": "Campus Portal", "status": "completed"}
    artifacts = {
        "requirements": {
            "project_name": "Campus Portal",
            "objective": "Help students view course announcements.",
            "user_roles": ["Student", "Instructor"],
            "functional_requirements": ["Students can view course announcements."],
            "non_functional_requirements": ["Pages should load promptly."],
            "constraints": ["Use the college identity provider."],
            "assumptions": [],
            "risks": ["Announcement delivery may be delayed."],
            "clarifications_needed": ["Confirm whether archived announcements are searchable."],
        },
        "project_plan": {
            "milestones": [{
                "name": "Announcements",
                "description": "Implement announcement viewing.",
                "requirement_refs": ["FR-001"],
                "tasks": [{"description": "Create announcement list API.", "requirement_refs": ["FR-001"]}],
            }],
        },
        "architecture": {
            "architecture_style": "Layered",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "authentication": "College identity provider",
            "components": [{"name": "Announcement Page", "responsibility": "Displays announcements.", "related_requirements": ["FR-001"]}],
            "api_endpoints": [{"name": "GET /announcements", "purpose": "List announcements.", "related_requirements": ["FR-001"]}],
            "data_flow": ["The page requests announcements from the API."],
            "external_integrations": ["College identity provider"],
            "architectural_assumptions": [],
            "architecture_decisions": [{"decision": "Use a layered architecture.", "rationale": "Separate UI, business rules, and storage.", "related_requirements": ["FR-001"]}],
        },
        "technical_review": {
            "overall_status": "PASS",
            "summary": "The blueprint covers the requirement.",
            "requirement_coverage": [{
                "requirement_id": "FR-001",
                "requirement": "Students can view course announcements.",
                "in_project_plan": True,
                "in_architecture": True,
                "in_api": True,
            }],
            "unsupported_additions": [],
            "architecture_consistency_issues": [],
            "recommended_actions": [],
        },
    }
    return project, artifacts


def test_srs_export_contains_source_requirements_and_safe_filename():
    project, artifacts = sample_project_and_artifacts()
    filename, content = render_project_document("srs", project, artifacts)
    assert filename == "campus-portal-srs.md"
    assert "Software Requirements Specification (SRS)" in content
    assert "Students can view course announcements." in content
    assert "Confirm whether archived announcements are searchable." in content


def test_sdd_export_contains_architecture_and_traceability():
    project, artifacts = sample_project_and_artifacts()
    filename, content = render_project_document("sdd", project, artifacts)
    assert filename == "campus-portal-sdd.md"
    assert "Software Design Description (SDD)" in content
    assert "GET /announcements" in content
    assert "FR-001" in content
    assert "Announcements" in content


def test_test_report_never_claims_proposed_tests_have_run():
    project, artifacts = sample_project_and_artifacts()
    filename, content = render_project_document("test-report", project, artifacts)
    assert filename == "campus-portal-test-report.md"
    assert "NOT RUN" in content
    assert "not evidence that generated application code has been executed" in content
    assert "TC-001" in content
    assert "FR-001" in content


def test_unknown_document_type_is_rejected():
    project, artifacts = sample_project_and_artifacts()
    try:
        render_project_document("pdf", project, artifacts)
    except ValueError as exc:
        assert "Unknown document type" in str(exc)
    else:
        raise AssertionError("Expected an unknown document type to be rejected.")
