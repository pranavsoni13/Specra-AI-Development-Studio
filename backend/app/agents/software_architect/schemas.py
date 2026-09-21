from pydantic import BaseModel, Field


class ArchitectureComponent(BaseModel):
    name: str = Field(
        description="Name of a major logical system component or module"
    )

    responsibility: str = Field(
        description="Primary responsibility of the component"
    )

    related_requirements: list[str] = Field(
        min_length=1,
        description=(
            "Exact functional requirements addressed by this component"
        ),
    )


class APIEndpoint(BaseModel):
    name: str = Field(
        description="Logical name of an API capability"
    )

    purpose: str = Field(
        description="Purpose of the API capability"
    )

    related_requirements: list[str] = Field(
        min_length=1,
        description=(
            "Exact functional requirements addressed by this API capability"
        ),
    )


class ArchitectureDecision(BaseModel):
    decision: str = Field(
        description="A major technical architecture decision"
    )

    rationale: str = Field(
        description="Why the decision is appropriate for the requirements"
    )


class SystemArchitecture(BaseModel):
    project_name: str = Field(
        description="Name of the project"
    )

    architecture_style: str = Field(
        description="Recommended high-level architecture style"
    )

    frontend: str = Field(
        description="Recommended frontend technology or approach"
    )

    backend: str = Field(
        description="Recommended backend technology or approach"
    )

    database: str = Field(
        description=(
            "Recommended database technology or "
            "'Not required based on current requirements'"
        )
    )

    authentication: str = Field(
        description=(
            "Recommended authentication approach or "
            "'Not required based on current requirements'"
        )
    )

    components: list[ArchitectureComponent] = Field(
        min_length=1,
        description=(
            "Major logical components required to satisfy the project"
        ),
    )

    api_endpoints: list[APIEndpoint] = Field(
        default_factory=list,
        description="Major API capabilities required by the project",
    )

    data_flow: list[str] = Field(
        min_length=1,
        description="High-level movement of information through the system",
    )

    external_integrations: list[str] = Field(
        default_factory=list,
        description=(
            "External systems or services required by the architecture"
        ),
    )

    architectural_assumptions: list[str] = Field(
        default_factory=list,
        description=(
            "Technical assumptions inferred by the architect that were "
            "not explicitly stated by the user"
        ),
    )

    architecture_decisions: list[ArchitectureDecision] = Field(
        min_length=1,
        description=(
            "Important architecture decisions and their rationale"
        ),
    )