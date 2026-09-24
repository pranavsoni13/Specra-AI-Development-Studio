from pydantic import BaseModel, Field


class ArchitectureComponent(BaseModel):
    name: str = Field(
        min_length=1,
        description="Name of a major architectural component."
    )
    responsibility: str = Field(
        min_length=1,
        description="Primary responsibility of the component."
    )
    related_requirements: list[str] = Field(
        min_length=1,
        description="Canonical functional requirement IDs addressed by this component, such as FR-001."
    )


class APIEndpoint(BaseModel):
    name: str = Field(
        min_length=1,
        description="An API capability or HTTP-style endpoint required by the stated functional requirements."
    )
    purpose: str = Field(
        min_length=1,
        description="What the API capability enables."
    )
    related_requirements: list[str] = Field(
        min_length=1,
        description="Canonical functional requirement IDs addressed by this API capability, such as FR-001."
    )


class ArchitectureDecision(BaseModel):
    decision: str = Field(
        min_length=1,
        description="A concrete architectural decision."
    )
    rationale: str = Field(
        min_length=1,
        description="Why the architectural decision is appropriate for the stated requirements."
    )
    related_requirements: list[str] = Field(
        min_length=1,
        description="Canonical functional requirement IDs directly affected by this decision."
    )


class SystemArchitecture(BaseModel):
    project_name: str = Field(
        min_length=1,
        description="Project name derived from the requirement analysis."
    )

    architecture_style: str = Field(
        min_length=1,
        description="The overall architectural style."
    )

    frontend: str = Field(
        min_length=1,
        description="Frontend technology or approach."
    )

    backend: str = Field(
        min_length=1,
        description="Backend technology or approach."
    )

    database: str = Field(
        min_length=1,
        description="Primary persistence technology or approach."
    )

    authentication: str = Field(
        min_length=1,
        description="Authentication approach, or an explicit statement that authentication is not required by the current requirements."
    )

    components: list[ArchitectureComponent] = Field(
        min_length=1,
        description="Major architectural components."
    )

    api_endpoints: list[APIEndpoint] = Field(
        min_length=1,
        description="API capabilities or endpoints required to support the functional requirements."
    )

    data_flow: list[str] = Field(
        min_length=1,
        description="Major system data flows."
    )

    external_integrations: list[str] = Field(
        default_factory=list,
        description="External services explicitly required or reasonably necessary to satisfy the requirements."
    )

    architectural_assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions made where the requirements do not provide enough information."
    )

    architecture_decisions: list[ArchitectureDecision] = Field(
        min_length=1,
        description="Major architectural decisions with requirement traceability."
    )