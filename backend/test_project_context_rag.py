from __future__ import annotations

import gc
import shutil
import tempfile
from pathlib import Path

from app.core.context_store import ProjectContextStore
from app.rag.embeddings import LocalEmbeddingModel
from app.rag.project_context_rag import (
    ProjectContextIndexer,
    ProjectKnowledgeRetriever,
)


def main() -> None:
    # Chroma's PersistentClient may keep SQLite handles open on Windows.
    # Cleanup is therefore best-effort.
    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="ai_dev_studio_project_rag_"
        )
    )

    try:
        context_db = temp_dir / "context.db"
        vector_db = temp_dir / "vector_db"

        store = ProjectContextStore(
            db_path=context_db
        )

        embedding_model = LocalEmbeddingModel()

        indexer = ProjectContextIndexer(
            embedding_model=embedding_model,
            vector_database_path=str(vector_db),
            chunk_size=500,
            chunk_overlap=50,
        )

        retriever = ProjectKnowledgeRetriever(
            embedding_model=embedding_model,
            vector_database_path=str(vector_db),
        )

        project_a = "project-a-11111111"
        project_b = "project-b-22222222"

        store.create_context(
            project_a,
            name="Payment Notes",
            kind="note",
            content=(
                "The online food delivery platform must "
                "support customer payments. Payment processing "
                "should use a payment gateway when required."
            ),
        )

        store.create_context(
            project_b,
            name="Authentication Notes",
            kind="note",
            content=(
                "This project uses user accounts and "
                "protected resources."
            ),
        )

        project_a_context = store.list_context(project_a)[0]
        project_b_context = store.list_context(project_b)[0]

        assert indexer.index_context(project_a_context) >= 1
        assert indexer.index_context(project_b_context) >= 1

        # Project A semantic retrieval.
        results_a = retriever.retrieve(
            project_a,
            "How should customer payments be handled?",
            top_k=3,
        )

        assert results_a, (
            "Project A should return its indexed payment context."
        )

        assert all(
            result.chunk.metadata.get("project_id") == project_a
            for result in results_a
        ), (
            "Project A retrieval returned data from another project."
        )

        assert any(
            "payment" in result.chunk.content.lower()
            for result in results_a
        ), (
            "Project A payment context was not semantically retrieved."
        )

        # Project B is intentionally non-empty. A vector database can
        # return the nearest result even when the query is a weak match.
        # The isolation contract is that it can ONLY return Project B data.
        results_b = retriever.retrieve(
            project_b,
            "How should customer payments be handled?",
            top_k=3,
        )

        assert all(
            result.chunk.metadata.get("project_id") == project_b
            for result in results_b
        ), (
            "Project B retrieval returned context from another project."
        )

        project_a_context_id = project_a_context["context_id"]

        assert all(
            result.chunk.document_id != project_a_context_id
            for result in results_b
        ), (
            "Project B retrieval leaked Project A context."
        )

        # Delete Project A context and verify it is no longer retrievable.
        indexer.delete_context(
            project_a,
            project_a_context["context_id"],
        )

        after_delete = retriever.retrieve(
            project_a,
            "How should customer payments be handled?",
            top_k=3,
        )

        assert after_delete == [], (
            "Deleted Project A context is still retrievable."
        )

        print("PROJECT CONTEXT RAG TEST: PASS")
        print("Project isolation: PASS")
        print("Semantic retrieval: PASS")
        print("Index update/delete: PASS")

    finally:
        # Best-effort cleanup. Chroma can retain SQLite handles briefly on
        # Windows, so cleanup failures must not turn a successful test into
        # a failure.
        gc.collect()
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )


if __name__ == "__main__":
    main()
