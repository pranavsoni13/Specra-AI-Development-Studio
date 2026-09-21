from pydantic import BaseModel, Field


class Milestone(BaseModel):
    name: str = Field(
        description="Name of the development milestone"
    )

    description: str = Field(
        description="Purpose of this milestone"
    )

    requirement_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Requirements from RequirementAnalysis that justify "
            "this milestone"
        )
    )

    tasks: list[str] = Field(
        default_factory=list,
        description="Concrete tasks required to complete the milestone"
    )


class ProjectPlan(BaseModel):
    project_name: str = Field(
        description="Name of the project being planned"
    )

    milestones: list[Milestone] = Field(
        default_factory=list,
        description="Ordered development milestones"
    )

    dependencies: list[str] = Field(
        default_factory=list,
        description="Dependencies between major milestones or tasks"
    )

    development_sequence: list[str] = Field(
        default_factory=list,
        description="Ordered sequence of milestone names"
    )