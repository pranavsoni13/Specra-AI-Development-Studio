from app.agents.requirement_analyst.agent import RequirementAnalyst
from app.agents.project_planner.agent import ProjectPlanner
from app.agents.software_architect.agent import SoftwareArchitect


def main():
    idea = """
    I want to build an online food delivery platform where
    customers can discover restaurants, browse menus,
    place orders, make payments, and track deliveries.
    """

    requirement_agent = RequirementAnalyst()
    planner_agent = ProjectPlanner()
    architect_agent = SoftwareArchitect()

    print("\n=== STEP 1: REQUIREMENT ANALYSIS ===\n")

    requirements = requirement_agent.analyze(idea)

    print(
        requirements.model_dump_json(indent=2)
    )

    print("\n=== STEP 2: PROJECT PLAN ===\n")

    project_plan = planner_agent.plan(
        requirements
    )

    print(
        project_plan.model_dump_json(indent=2)
    )

    print("\n=== STEP 3: SYSTEM ARCHITECTURE ===\n")

    architecture = architect_agent.design(
        requirements,
        project_plan,
    )

    print(
        architecture.model_dump_json(indent=2)
    )


if __name__ == "__main__":
    main()