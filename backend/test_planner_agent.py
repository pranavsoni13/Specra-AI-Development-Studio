from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.project_planner.agent import ProjectPlanner


def main():
    idea = """
    I want to build an online food delivery platform where
    customers can discover restaurants, browse menus,
    place orders, make payments, and track deliveries.
    """

    requirement_agent = RequirementAnalyst()
    planner_agent = ProjectPlanner()

    print("\n=== STEP 1: REQUIREMENT ANALYSIS ===\n")

    requirements = requirement_agent.analyze(idea)

    print(
        requirements.model_dump_json(indent=2)
    )

    print("\n=== STEP 2: PROJECT PLAN ===\n")

    plan = planner_agent.plan(requirements)

    print(
        plan.model_dump_json(indent=2)
    )


if __name__ == "__main__":
    main()