from pydantic import BaseModel, Field


class PlanTask(BaseModel):
    """
    One implementation-agnostic planning task.

    Every task is explicitly traceable to one or more canonical
    functional requirement IDs.
    """

    description: str = Field(
        min_length=1,
        description=(
            "Concrete implementation-agnostic task description"
        ),
    )

    requirement_refs: list[str] = Field(
        min_length=1,
        description=(
            "Canonical functional requirement IDs addressed by this task, "
            "such as FR-001"
        ),
    )


class Milestone(BaseModel):
    name: str = Field(
        min_length=1,
        description="Name of the development milestone",
    )

    description: str = Field(
        min_length=1,
        description="Purpose of this milestone",
    )

    requirement_refs: list[str] = Field(
        min_length=1,
        description=(
            "Canonical functional requirement IDs addressed by this "
            "milestone, such as FR-001"
        ),
    )

    tasks: list[PlanTask] = Field(
        min_length=1,
        description=(
            "Concrete implementation-agnostic tasks required to complete "
            "this milestone"
        ),
    )


class ProjectPlan(BaseModel):
    project_name: str = Field(
        min_length=1,
        description="Name of the project being planned",
    )

    milestones: list[Milestone] = Field(
        min_length=1,
        description="Ordered development milestones",
    )

    dependencies: list[str] = Field(
        default_factory=list,
        description=(
            "Dependencies between major milestones or tasks"
        ),
    )

    development_sequence: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered sequence of milestone names"
        ),
    )