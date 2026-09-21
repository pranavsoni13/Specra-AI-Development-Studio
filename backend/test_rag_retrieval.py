from app.rag.retriever import KnowledgeRetriever


def main():

    retriever = KnowledgeRetriever()

    queries = [
        "Should a small application use microservices?",
        "When should authentication be required?",
        "What kind of database is suitable for transactional structured data?",
        "How should an application integrate electronic payments?",
    ]

    for query in queries:

        print("\n" + "=" * 70)
        print(
            f"QUERY: {query}"
        )
        print("=" * 70)

        results = retriever.retrieve(
            query,
            top_k=2,
        )

        for index, result in enumerate(
            results,
            start=1,
        ):
            print(
                f"\nRESULT {index}"
            )

            print(
                f"Document: {result.chunk.document_id}"
            )

            print(
                f"Distance: {result.distance:.4f}"
            )

            print(
                f"Content:\n{result.chunk.content}"
            )


if __name__ == "__main__":
    main()