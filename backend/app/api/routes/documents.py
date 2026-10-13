from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.documents import render_project_document
from app.core.storage.project_store import project_store


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/documents",
    tags=["Project Documents"],
)


@router.get("/{document_type}")
def download_project_document(
    project_id: str,
    document_type: Literal["srs", "sdd", "test-report"],
) -> Response:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_id}' not found.",
        )

    artifacts = project_store.get_artifacts(project_id)
    if not artifacts.get("requirements"):
        raise HTTPException(
            status_code=409,
            detail="Generate requirements before exporting project documents.",
        )

    filename, content = render_project_document(
        document_type,
        project,
        artifacts,
    )
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
