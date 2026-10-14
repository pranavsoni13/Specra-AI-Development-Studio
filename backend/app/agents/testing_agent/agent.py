import json

from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.core.llm.client import LocalLLMClient
from app.core.model_config import TECHNICAL_REVIEWER_MODEL
from app.core.traceability.requirements import RequirementRegistry

from .prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .quality import TestingQualityController
from .schemas import TestSuite, TestSuiteDraft


class TestingAgent:
    """Create requirement-traceable test cases; it never executes the project code."""

    def __init__(self, model_name: str = TECHNICAL_REVIEWER_MODEL):
        self.model_name = model_name
        self.llm_client = LocalLLMClient(model_name=model_name)
        self.quality_controller = TestingQualityController()

    def generate(
        self,
        requirements: dict | RequirementAnalysis,
        project_plan: dict | None = None,
        architecture: dict | None = None,
    ) -> TestSuite:
        analysis = (
            requirements
            if isinstance(requirements, RequirementAnalysis)
            else RequirementAnalysis.model_validate(requirements)
        )
        registry = RequirementRegistry.from_analysis(analysis)
        requirements_payload = [
            {"requirement_id": item.requirement_id, "text": item.text}
            for item in registry.requirements
        ]
        user_prompt = USER_PROMPT_TEMPLATE.format(
            requirements_json=json.dumps(requirements_payload, ensure_ascii=False),
            plan_json=json.dumps(project_plan or {}, ensure_ascii=False),
            architecture_json=json.dumps(architecture or {}, ensure_ascii=False),
        )
        draft = self.llm_client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            output_schema=TestSuiteDraft,
        )
        suite = self.quality_controller.validate(draft, registry)
        # The model name is included in the summary as provenance, not as proof
        # that the test suite is correct or executed.
        return suite
