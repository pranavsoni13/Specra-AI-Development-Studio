from typing import Literal

from pydantic import BaseModel, Field


class RAGDecision(BaseModel):
    verdict: Literal[
        "SUPPORTED",
        "QUESTIONABLE",
        "UNSUPPORTED",
    ] = Field(
        description="Evidence-based verdict for the supplied architecture claim"
    )

    recommendation: str = Field(
        description="Recommended action based on the retrieved evidence"
    )


class RAGValidationFinding(BaseModel):
    category: Literal[
        "architecture_style",
        "technology_choice",
        "database",
        "authentication",
        "integration",
        "assumption",
        "general",
    ] = Field(
        description="Category of the technical validation finding"
    )

    verdict: Literal[
        "SUPPORTED",
        "QUESTIONABLE",
        "UNSUPPORTED",
    ] = Field(
        description="Overall evidence-based verdict"
    )

    title: str = Field(
        description="Concise title for the validation result"
    )

    claim: str = Field(
        description="Single architecture claim being validated"
    )

    evidence: str = Field(
        description=(
            "Evidence from the retrieved knowledge that directly supports "
            "or challenges the claim"
        )
    )

    evidence_chunk_ids: list[str] = Field(
        min_length=1,
        description="Exact retrieved knowledge chunk IDs used as evidence"
    )

    recommendation: str = Field(
        description="Recommended action based on the evidence"
    )


class RAGValidationReport(BaseModel):
    project_name: str = Field(
        description="Name of the reviewed project"
    )

    overall_status: Literal[
        "PASS",
        "NEEDS_REVIEW",
    ] = Field(
        description="Overall result of the RAG validation"
    )

    summary: str = Field(
        description="Concise summary of the validation"
    )

    knowledge_sources: list[str] = Field(
        min_length=1,
        description="All knowledge chunks consulted"
    )

    findings: list[RAGValidationFinding] = Field(
        default_factory=list,
        description=(
            "At most one meaningful finding for each major architecture "
            "decision or assumption"
        )
    )

    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Actions recommended after validation"
    )