from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.document_export import (
    render_document_export,
    render_sdd,
    render_srs,
    render_test_report,
    render_traceability_csv,
    safe_filename,
)
from app.core.security import get_current_user, require_project_roles
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/documents",
    tags=["Engineering Documents"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/{document_type}",
    dependencies=[Depends(require_project_roles())],
)
def download_document(
    project_id: str,
    document_type: str,
    format: str = Query(default="pdf", pattern="^(md|markdown|pdf|ppt|pptx|powerpoint)$"),
) -> Response:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    artifacts = project_store.get_artifacts(project_id)
    versions = project_store.get_latest_version_numbers(project_id)
    suite = test_store.get_suite(project_id)
    requirements = artifacts.get("requirements") or {}
    project_name = str(
        requirements.get("project_name")
        or project.get("project_name")
        or "Specra Project"
    )

    if document_type == "srs":
        markdown = render_srs(project, artifacts, versions)
        base_suffix = "srs"
    elif document_type == "sdd":
        markdown = render_sdd(project, artifacts, versions)
        base_suffix = "sdd"
    elif document_type in {"test-report", "test_report"}:
        markdown = render_test_report(project, suite)
        base_suffix = "test-report"
    elif document_type in {"traceability", "traceability.csv"}:
        body = render_traceability_csv(project, artifacts, suite).encode("utf-8")
        filename = safe_filename(project_name, project_id, "traceability.csv")
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="Unknown document type. Use srs, sdd, test-report, or traceability.",
        )

    try:
        body, extension, media_type = render_document_export(markdown, format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = safe_filename(project_name, project_id, f"{base_suffix}.{extension}")

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
