from typing import Literal

from pydantic import BaseModel, Field


class RequirementCoverage(BaseModel):
    requirement: str = Field(
        description="Exact functional requirement being evaluated"
    )

    in_project_plan: bool = Field(
        description="Whether the requirement is represented in the project plan"
    )

    in_architecture: bool = Field(
        description="Whether the requirement is represented in the architecture"
    )


class ReviewFinding(BaseModel):
    category: Literal[
        "requirement",
        "planning",
        "architecture",
        "consistency",
        "assumption",
        "traceability",
    ] = Field(
        description="Category of the review finding"
    )

    severity: Literal[
        "low",
        "medium",
        "high",
        "critical",
    ] = Field(
        description="Severity of the issue"
    )

    title: str = Field(
        description="Short title of the finding"
    )

    evidence: str = Field(
        description="Evidence supporting the finding"
    )

    recommendation: str = Field(
        description="Recommended correction"
    )


class ReviewReport(BaseModel):
    project_name: str = Field(
        description="Name of the reviewed project"
    )

    overall_status: Literal[
        "PASS",
        "NEEDS_REVISION",
    ] = Field(
        description="Overall review result"
    )

    summary: str = Field(
        description="Concise summary of the review"
    )

    requirement_coverage: list[RequirementCoverage] = Field(
        min_length=1,
        description="Coverage of every functional requirement"
    )

    unsupported_additions: list[str] = Field(
        default_factory=list,
        description="Features or claims introduced without adequate support"
    )

    architecture_consistency_issues: list[str] = Field(
        default_factory=list,
        description="Architecture contradictions or inconsistencies"
    )

    findings: list[ReviewFinding] = Field(
        default_factory=list,
        description="Detailed review findings"
    )

    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Actions required before the blueprint can be considered valid"
    )