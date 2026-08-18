from app.agents.requirement_analyst.agent import RequirementAnalyst


def main():
    agent = RequirementAnalyst()

    idea = """
    I want to build an online food delivery platform where
    customers can discover restaurants, browse menus,
    place orders, make payments, and track deliveries.
    """

    result = agent.analyze(idea)

    print("\n=== REQUIREMENT ANALYSIS ===\n")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()