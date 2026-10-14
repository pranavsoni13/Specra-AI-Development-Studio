from __future__ import annotations

import io
import logging
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.agents.code_generator.agent import CodeGenerationAgent
from app.core.code_bundle_store import code_bundle_store
from app.core.document_export import safe_filename
from app.core.security import auth_store, get_current_user, require_project_roles
from app.core.storage.project_store import project_store
from app.core.testing_store import test_store


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/code-bundles",
    tags=["VS Code Export"],
    dependencies=[Depends(get_current_user)],
)


class CodeGenerationRequest(BaseModel):
    stack: Literal["fastapi-react"] = "fastapi-react"
    additional_constraints: str = Field(default="", max_length=5000)


def _project_or_404(project_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _public_bundle(bundle: dict, include_files: bool = False) -> dict:
    result = {
        "bundle_id": bundle.get("bundle_id"),
        "project_id": bundle.get("project_id"),
        "bundle_version": bundle.get("bundle_version"),
        "project_name": bundle.get("project_name"),
        "summary": bundle.get("summary"),
        "stack": bundle.get("stack"),
        "setup_notes": bundle.get("setup_notes", []),
        "test_notes": bundle.get("test_notes", []),
        "validation_warnings": bundle.get("validation_warnings", []),
        "validation_status": bundle.get("validation_status", "needs_review"),
        "execution_status": bundle.get("execution_status", "not_executed"),
        "generation_source": bundle.get("generation_source"),
        "generation_model": bundle.get("generation_model"),
        "created_at": bundle.get("created_at"),
        "files": (
            bundle.get("files", [])
            if include_files
            else [
                {
                    "path": item.get("path"),
                    "purpose": item.get("purpose"),
                    "characters": len(item.get("content", "")),
                }
                for item in bundle.get("files", [])
            ]
        ),
    }
    return result


@router.get(
    "",
    dependencies=[Depends(require_project_roles())],
)
def list_code_bundles(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    _project_or_404(project_id)
    role = auth_store.get_project_role(project_id, user)
    return {
        "bundles": code_bundle_store.list_bundles(project_id),
        "my_role": role,
        "can_generate": role in {
            "admin", "owner", "analyst", "architect", "developer",
        },
    }


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_project_roles("analyst", "architect", "developer"))
    ],
)
def generate_code_bundle(
    project_id: str,
    request: CodeGenerationRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    project = _project_or_404(project_id)
    artifacts = project_store.get_artifacts(project_id)
    missing = [
        stage
        for stage in ("requirements", "project_plan", "architecture", "technical_review")
        if not artifacts.get(stage)
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Generate and save the complete engineering blueprint before generating code. "
                f"Missing artifacts: {', '.join(missing)}."
            ),
        )

    review = artifacts.get("technical_review") or {}
    review_status = str(review.get("overall_status") or "").strip().upper()
    if review_status != "PASS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The latest technical review must pass before code generation. Resolve its findings and run the workflow again.",
        )

    test_suite = test_store.get_suite(project_id)
    try:
        agent = CodeGenerationAgent()
        bundle = agent.generate(
            project=project,
            artifacts=artifacts,
            test_suite=test_suite,
            additional_constraints=request.additional_constraints,
        )
        saved = code_bundle_store.save_bundle(
            project_id=project_id,
            created_by=user["user_id"],
            bundle=bundle.model_dump(),
            generation_model=agent.model_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception(
            "Code bundle generation failed for project %s (%s)",
            project_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The code-generation agent could not produce a safe bundle. Check the configured provider and try again.",
        ) from exc

    return {"bundle": _public_bundle(saved)}


@router.get(
    "/{bundle_id}",
    dependencies=[Depends(require_project_roles())],
)
def get_code_bundle(project_id: str, bundle_id: str) -> dict:
    _project_or_404(project_id)
    bundle = code_bundle_store.get_bundle(
        project_id=project_id,
        bundle_id=bundle_id,
    )
    if bundle is None:
        raise HTTPException(status_code=404, detail="Code bundle not found.")
    return {"bundle": _public_bundle(bundle, include_files=True)}


@router.get(
    "/{bundle_id}/download",
    dependencies=[Depends(require_project_roles())],
)
def download_code_bundle(project_id: str, bundle_id: str) -> Response:
    _project_or_404(project_id)
    bundle = code_bundle_store.get_bundle(
        project_id=project_id,
        bundle_id=bundle_id,
    )
    if bundle is None:
        raise HTTPException(status_code=404, detail="Code bundle not found.")

    payload = io.BytesIO()
    with zipfile.ZipFile(
        payload,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for item in bundle.get("files", []):
            path = str(item.get("path") or "")
            # Stored bundles were validated before insertion; repeat cheap
            # archive path checks at the trust boundary before ZIP creation.
            if not path or path.startswith("/") or "\\" in path or ".." in path.split("/"):
                raise HTTPException(
                    status_code=500,
                    detail="Stored bundle contains an unsafe path and cannot be exported.",
                )
            archive.writestr(path, str(item.get("content") or ""))

    project_name = str(bundle.get("project_name") or "Specra Project")
    filename = safe_filename(project_name, project_id, "zip")
    return Response(
        content=payload.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
