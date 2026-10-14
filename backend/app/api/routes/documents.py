from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.document_export import (
    render_test_report,
    render_traceability_csv,
    safe_filename,
)
from app.core.documents import render_project_document
from app.core.security import get_current_user, require_project_roles
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/documents",
    tags=["Project Documents"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/{document_type}", dependencies=[Depends(require_project_roles())])
def download_project_document(
    project_id: str,
    document_type: Literal["srs", "sdd", "test-report", "traceability"],
) -> Response:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    artifacts = project_store.get_artifacts(project_id)
    if not artifacts.get("requirements"):
        raise HTTPException(
            status_code=409,
            detail="Generate requirements before exporting project documents.",
        )

    suite = test_store.get_suite(project_id)
    project_name = (
        (artifacts.get("requirements") or {}).get("project_name")
        or project.get("project_name")
        or "Specra Project"
    )

    if document_type == "test-report":
        filename = safe_filename(project_name, project_id, "test-report.md")
        content = render_test_report(project, suite)
        media_type = "text/markdown; charset=utf-8"
    elif document_type == "traceability":
        filename = safe_filename(project_name, project_id, "traceability.csv")
        content = render_traceability_csv(project, artifacts, suite)
        media_type = "text/csv; charset=utf-8"
    else:
        filename, content = render_project_document(document_type, project, artifacts)
        media_type = "text/markdown; charset=utf-8"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
