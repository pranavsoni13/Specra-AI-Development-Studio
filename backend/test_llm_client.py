from app.core.llm.client import LocalLLMClient
from app.agents.requirement_analyst.schemas import RequirementAnalysis


def main():
    client = LocalLLMClient()

    result = client.generate_structured(
        system_prompt="""
You are a software requirements analyst.
Analyze the provided software idea conservatively.
Return only the required structured output.
""",
        user_prompt="""
Software idea:
Build a simple notes application where users can
create, edit, delete, and search notes.
""",
        output_schema=RequirementAnalysis,
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()