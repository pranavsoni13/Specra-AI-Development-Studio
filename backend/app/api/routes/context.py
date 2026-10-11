from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.context_store import project_context_store
from app.core.storage.project_store import project_store


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/context",
    tags=["Project Context"],
)


# ============================================================
# Request / response schemas
# ============================================================


class ProjectContextCreateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable context source name.",
    )
    kind: str = Field(
        min_length=1,
        max_length=50,
        description="Context type such as note, code, text, or file.",
    )
    content: str = Field(
        min_length=1,
        description="Text content supplied by the user.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Optional source metadata.",
    )


class ProjectContextUpdateRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
    )
    kind: str = Field(
        min_length=1,
        max_length=50,
    )
    content: str = Field(
        min_length=1,
    )
    metadata: dict = Field(
        default_factory=dict,
    )


class ProjectContextResponse(BaseModel):
    context_id: str
    project_id: str
    name: str
    kind: str
    content: str
    metadata: dict
    created_at: datetime
    updated_at: datetime


class ProjectContextSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="Natural-language query over project context.",
    )
    limit: int = Field(
        default=8,
        ge=1,
        le=20,
    )


class ProjectContextSearchResponse(BaseModel):
    query: str
    results: list[ProjectContextResponse]


class ProjectContextRAGSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description=(
            "Natural-language semantic query over this project's "
            "private vectorized context."
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of semantic matches to return.",
    )


class ProjectContextRAGResult(BaseModel):
    context_id: str
    chunk_id: str
    project_id: str
    source_name: str
    source_kind: str
    content: str
    distance: float


class ProjectContextRAGSearchResponse(BaseModel):
    query: str
    project_id: str
    results: list[ProjectContextRAGResult]


# ============================================================
# RAG services
# ============================================================


@lru_cache(maxsize=1)
def _rag_services():
    """
    Lazily create project-context RAG services.

    Heavy embedding/vector-store dependencies load only when a semantic
    context endpoint is used, keeping ordinary API startup lightweight.
    """

    from app.rag.embeddings import LocalEmbeddingModel
    from app.rag.project_context_rag import (
        ProjectContextIndexer,
        ProjectKnowledgeRetriever,
    )

    embedding_model = LocalEmbeddingModel()

    indexer = ProjectContextIndexer(
        embedding_model=embedding_model,
        vector_database_path="knowledge/vector_db",
    )

    retriever = ProjectKnowledgeRetriever(
        embedding_model=embedding_model,
        vector_database_path="knowledge/vector_db",
    )

    return indexer, retriever


def _index_context(record: dict) -> None:
    indexer, _ = _rag_services()
    indexer.index_context(record)


def _delete_context_from_rag(
    project_id: str,
    context_id: str,
) -> None:
    indexer, _ = _rag_services()
    indexer.delete_context(
        project_id,
        context_id,
    )


# ============================================================
# Helpers
# ============================================================


def _ensure_project(project_id: str) -> None:
    if project_store.get_project(project_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_id}' not found.",
        )


def _response(
    record: dict,
) -> ProjectContextResponse:
    return ProjectContextResponse(
        context_id=record["context_id"],
        project_id=record["project_id"],
        name=record["name"],
        kind=record["kind"],
        content=record["content"],
        metadata=record["metadata"],
        created_at=datetime.fromisoformat(
            record["created_at"]
        ),
        updated_at=datetime.fromisoformat(
            record["updated_at"]
        ),
    )


# ============================================================
# CRUD
# ============================================================


@router.get(
    "",
    response_model=list[ProjectContextResponse],
)
def list_project_context(
    project_id: str,
) -> list[ProjectContextResponse]:
    _ensure_project(project_id)

    return [
        _response(record)
        for record in project_context_store.list_context(
            project_id
        )
    ]


@router.post(
    "",
    response_model=ProjectContextResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_context(
    project_id: str,
    request: ProjectContextCreateRequest,
) -> ProjectContextResponse:
    _ensure_project(project_id)

    name = request.name.strip()
    kind = request.kind.strip().lower()
    content = request.content.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Context name cannot be empty.",
        )

    if not kind:
        raise HTTPException(
            status_code=400,
            detail="Context kind cannot be empty.",
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Context content cannot be empty.",
        )

    record = project_context_store.create_context(
        project_id,
        name=name,
        kind=kind,
        content=content,
        metadata=request.metadata,
    )

    _index_context(record)

    return _response(record)


@router.put(
    "/{context_id}",
    response_model=ProjectContextResponse,
)
def update_project_context(
    project_id: str,
    context_id: str,
    request: ProjectContextUpdateRequest,
) -> ProjectContextResponse:
    _ensure_project(project_id)

    name = request.name.strip()
    kind = request.kind.strip().lower()
    content = request.content.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Context name cannot be empty.",
        )

    if not kind:
        raise HTTPException(
            status_code=400,
            detail="Context kind cannot be empty.",
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Context content cannot be empty.",
        )

    record = project_context_store.update_context(
        project_id,
        context_id,
        name=name,
        kind=kind,
        content=content,
        metadata=request.metadata,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Context '{context_id}' not found.",
        )

    _index_context(record)

    return _response(record)


@router.delete(
    "/{context_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_context(
    project_id: str,
    context_id: str,
) -> None:
    _ensure_project(project_id)

    deleted = project_context_store.delete_context(
        project_id,
        context_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Context '{context_id}' not found.",
        )

    _delete_context_from_rag(
        project_id,
        context_id,
    )


# ============================================================
# Lexical / metadata search
# ============================================================


@router.post(
    "/search",
    response_model=ProjectContextSearchResponse,
)
def search_project_context(
    project_id: str,
    request: ProjectContextSearchRequest,
) -> ProjectContextSearchResponse:
    _ensure_project(project_id)

    results = project_context_store.search_context(
        project_id,
        request.query,
        limit=request.limit,
    )

    return ProjectContextSearchResponse(
        query=request.query,
        results=[
            _response(record)
            for record in results
        ],
    )


# ============================================================
# Semantic project-private RAG search
# ============================================================


@router.post(
    "/rag-search",
    response_model=ProjectContextRAGSearchResponse,
)
def rag_search_project_context(
    project_id: str,
    request: ProjectContextRAGSearchRequest,
) -> ProjectContextRAGSearchResponse:
    """
    Search only the private vector collection belonging to project_id.

    Project-private context is isolated from the global engineering
    knowledge collection and from every other project.
    """

    _ensure_project(project_id)

    _, retriever = _rag_services()

    results = retriever.retrieve(
        project_id=project_id,
        query=request.query,
        top_k=request.top_k,
    )

    return ProjectContextRAGSearchResponse(
        query=request.query,
        project_id=project_id,
        results=[
            ProjectContextRAGResult(
                context_id=result.chunk.metadata.get(
                    "context_id",
                    result.chunk.document_id,
                ),
                chunk_id=result.chunk.chunk_id,
                project_id=result.chunk.metadata.get(
                    "project_id",
                    project_id,
                ),
                source_name=result.chunk.metadata.get(
                    "source_name",
                    "Unknown",
                ),
                source_kind=result.chunk.metadata.get(
                    "source_kind",
                    "unknown",
                ),
                content=result.chunk.content,
                distance=result.distance,
            )
            for result in results
        ],
    )
