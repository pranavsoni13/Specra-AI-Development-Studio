from __future__ import annotations

from typing import Literal

from app.agents.project_planner.schemas import ProjectPlan
from app.agents.requirement_analyst.schemas import RequirementAnalysis
from app.agents.software_architect.schemas import SystemArchitecture
from app.rag.retriever import KnowledgeRetriever

from .quality import RAGValidationQualityController
from .schemas import RAGValidationFinding, RAGValidationReport


MODEL_NAME = "qwen3:4b"
TOP_K_PER_CLAIM = 2


ClaimType = Literal[
    "architecture_style",
    "frontend",
    "backend",
    "database",
    "authentication",
    "integration",
    "assumption",
]


Category = Literal[
    "architecture_style",
    "technology_choice",
    "database",
    "authentication",
    "integration",
    "assumption",
    "general",
]


Verdict = Literal[
    "SUPPORTED",
    "QUESTIONABLE",
    "UNSUPPORTED",
]


class RAGValidator:
    """
    Deterministic knowledge-grounded architecture validator.

    The RAG stage intentionally performs NO local LLM generation.

    Pipeline:

        architecture claim
              ↓
        vector retrieval
              ↓
        direct evidence check
              ↓
        deterministic verdict
              ↓
        RAGValidationReport

    This avoids the previous design where one local LLM generation
    happened for every validation claim.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_attempts: int = 2,
        top_k_per_claim: int = TOP_K_PER_CLAIM,
    ) -> None:
        # Kept for compatibility with the existing constructor.
        # RAG validation itself does not use an LLM.
        self.model_name = model_name
        self.max_attempts = max_attempts

        self.top_k_per_claim = max(
            1,
            top_k_per_claim,
        )

        self.retriever = KnowledgeRetriever()

        self.quality_controller = (
            RAGValidationQualityController()
        )

    def validate(
        self,
        requirements: RequirementAnalysis,
        project_plan: ProjectPlan,
        architecture: SystemArchitecture,
    ) -> RAGValidationReport:
        """
        Validate architecture decisions against the knowledge base.
        """

        if not isinstance(
            requirements,
            RequirementAnalysis,
        ):
            raise TypeError(
                "RAG Validator requires a RequirementAnalysis object."
            )

        if not isinstance(
            project_plan,
            ProjectPlan,
        ):
            raise TypeError(
                "RAG Validator requires a ProjectPlan object."
            )

        if not isinstance(
            architecture,
            SystemArchitecture,
        ):
            raise TypeError(
                "RAG Validator requires a SystemArchitecture object."
            )

        claims = self._build_validation_claims(
            architecture
        )

        if not claims:
            raise RuntimeError(
                "RAG Validator could not identify any architecture "
                "decisions to validate."
            )

        findings: list[RAGValidationFinding] = []

        all_retrieved_chunk_ids: set[str] = set()

        # --------------------------------------------------------------
        # Retrieve evidence independently for each claim.
        # --------------------------------------------------------------

        for claim in claims:
            retrieved = self.retriever.retrieve(
                claim["query"],
                top_k=self.top_k_per_claim,
            )

            if not retrieved:
                raise RuntimeError(
                    "RAG Validator could not retrieve knowledge for "
                    f"claim '{claim['id']}'."
                )

            chunk_ids = [
                result.chunk.chunk_id
                for result in retrieved
                if result.chunk.chunk_id
            ]

            if not chunk_ids:
                raise RuntimeError(
                    "RAG Validator retrieved results without valid "
                    f"chunk IDs for claim '{claim['id']}'."
                )

            all_retrieved_chunk_ids.update(
                chunk_ids
            )

            direct_evidence = self._has_direct_evidence(
                claim,
                retrieved,
            )

            verdict: Verdict

            if direct_evidence:
                verdict = "SUPPORTED"
            else:
                verdict = "QUESTIONABLE"

            evidence = self._build_evidence_text(
                retrieved=retrieved,
                direct_evidence=direct_evidence,
            )

            recommendation = self._build_recommendation(
                claim=claim,
                verdict=verdict,
            )

            finding = RAGValidationFinding(
                category=self._category_for_claim(
                    claim["type"]
                ),
                verdict=verdict,
                title=claim["title"],
                claim=claim["claim"],
                evidence=evidence,
                evidence_chunk_ids=chunk_ids,
                recommendation=recommendation,
            )

            findings.append(
                finding
            )

        # --------------------------------------------------------------
        # Overall result.
        # --------------------------------------------------------------

        overall_status = self._calculate_status(
            findings
        )

        summary = self._build_summary(
            findings
        )

        recommended_actions = (
            self._build_recommended_actions(
                findings
            )
        )

        project_name = (
            architecture.project_name
            or requirements.project_name
        )

        report = RAGValidationReport(
            project_name=project_name,
            overall_status=overall_status,
            summary=summary,
            knowledge_sources=list(
                all_retrieved_chunk_ids
            ),
            findings=findings,
            recommended_actions=recommended_actions,
        )

        # Final deterministic quality gate.
        return self.quality_controller.validate(
            report,
            requirements,
            project_plan,
            architecture,
            all_retrieved_chunk_ids,
        )

    # ==================================================================
    # CLAIM BUILDING
    # ==================================================================

    @staticmethod
    def _build_validation_claims(
        architecture: SystemArchitecture,
    ) -> list[dict[str, object]]:
        claims: list[dict[str, object]] = []

        # --------------------------------------------------------------
        # Architecture style
        # --------------------------------------------------------------

        if architecture.architecture_style.strip():
            architecture_style = (
                architecture.architecture_style.strip()
            )

            claims.append(
                {
                    "id": "architecture_style",
                    "type": "architecture_style",
                    "title": (
                        "Architecture style: "
                        f"{architecture_style}"
                    ),
                    "claim": (
                        "The selected architecture style "
                        f"'{architecture_style}' is appropriate "
                        "for this project."
                    ),
                    "query": (
                        "Engineering guidance for selecting and "
                        "evaluating software architecture styles, "
                        f"especially {architecture_style}, based on "
                        "separation of concerns, application "
                        "complexity, requirements, and operational "
                        "trade-offs."
                    ),
                    "evidence_terms": (
                        RAGValidator._architecture_style_terms(
                            architecture_style
                        )
                    ),
                }
            )

        # --------------------------------------------------------------
        # Frontend
        # --------------------------------------------------------------

        if architecture.frontend.strip():
            frontend = architecture.frontend.strip()

            claims.append(
                {
                    "id": "frontend",
                    "type": "frontend",
                    "title": (
                        f"Frontend technology: {frontend}"
                    ),
                    "claim": (
                        "The selected frontend technology "
                        f"'{frontend}' is appropriate "
                        "for this project."
                    ),
                    "query": (
                        "Technical engineering guidance specifically "
                        f"about '{frontend}' as a frontend technology, "
                        "including suitable application types, "
                        "strengths, limitations, and trade-offs."
                    ),
                    "evidence_terms": [
                        frontend.casefold()
                    ],
                }
            )

        # --------------------------------------------------------------
        # Backend
        # --------------------------------------------------------------

        if architecture.backend.strip():
            backend = architecture.backend.strip()

            claims.append(
                {
                    "id": "backend",
                    "type": "backend",
                    "title": (
                        f"Backend technology: {backend}"
                    ),
                    "claim": (
                        "The selected backend technology "
                        f"'{backend}' is appropriate "
                        "for this project."
                    ),
                    "query": (
                        "Technical engineering guidance specifically "
                        f"about '{backend}' as a backend technology, "
                        "including suitable application types, "
                        "strengths, limitations, and trade-offs."
                    ),
                    "evidence_terms": [
                        backend.casefold()
                    ],
                }
            )

        # --------------------------------------------------------------
        # Database
        # --------------------------------------------------------------

        if architecture.database.strip():
            database = architecture.database.strip()

            claims.append(
                {
                    "id": "database",
                    "type": "database",
                    "title": (
                        f"Database: {database}"
                    ),
                    "claim": (
                        "The selected database "
                        f"'{database}' is appropriate "
                        "for this project."
                    ),
                    "query": (
                        "Database selection guidance specifically "
                        f"for '{database}', including structured "
                        "data, relationships, transactions, "
                        "constraints, indexing, and consistency."
                    ),
                    "evidence_terms": [
                        database.casefold()
                    ],
                }
            )

        # --------------------------------------------------------------
        # Authentication
        # --------------------------------------------------------------

        if architecture.authentication.strip():
            claims.append(
                {
                    "id": "authentication",
                    "type": "authentication",
                    "title": "Authentication decision",
                    "claim": (
                        "The architecture does not introduce an "
                        "authentication mechanism that is unsupported "
                        "by the current project requirements."
                    ),
                    "query": (
                        "Engineering guidance about when "
                        "authentication and authorization are required, "
                        "how authentication decisions should be "
                        "derived from project requirements, and when "
                        "authentication should be treated as an "
                        "architectural assumption."
                    ),
                    "evidence_terms": [
                        "authentication"
                    ],
                }
            )

        # --------------------------------------------------------------
        # External integrations
        # --------------------------------------------------------------

        if architecture.external_integrations:
            integration_names = [
                item.strip()
                for item in architecture.external_integrations
                if item.strip()
            ]

            if integration_names:
                integration_text = ", ".join(
                    integration_names
                )

                integration_lower = (
                    integration_text.casefold()
                )

                if "payment" in integration_lower:
                    query = (
                        "Technical guidance about payment "
                        "processing services and payment gateways, "
                        "including when external payment services "
                        "are appropriate, security considerations, "
                        "transaction handling, and provider "
                        "integration."
                    )

                    evidence_terms = [
                        "payment",
                        "payment processing",
                    ]
                else:
                    query = (
                        "Technical guidance about external service "
                        f"integrations relevant to {integration_text}, "
                        "including integration boundaries and when "
                        "external services are appropriate."
                    )

                    evidence_terms = [
                        integration_names[0].casefold()
                    ]

                claims.append(
                    {
                        "id": "external_integrations",
                        "type": "integration",
                        "title": (
                            "External integrations: "
                            f"{integration_text}"
                        ),
                        "claim": (
                            "The selected external integrations "
                            f"'{integration_text}' are technically "
                            "justified by the project requirements."
                        ),
                        "query": query,
                        "evidence_terms": evidence_terms,
                    }
                )

        # --------------------------------------------------------------
        # Architectural assumptions
        # --------------------------------------------------------------

        for index, assumption in enumerate(
            architecture.architectural_assumptions,
            start=1,
        ):
            assumption_text = assumption.strip()

            if not assumption_text:
                continue

            assumption_lower = (
                assumption_text.casefold()
            )

            if "payment" in assumption_lower:
                query = (
                    "Technical guidance about payment processing "
                    "services, payment gateways, and external "
                    "payment dependencies."
                )

                evidence_terms = [
                    "payment",
                    "payment processing",
                ]
            else:
                query = (
                    "Engineering guidance relevant to evaluating "
                    f"this architectural assumption: "
                    f"{assumption_text}"
                )

                evidence_terms = (
                    RAGValidator._extract_evidence_terms(
                        assumption_text
                    )
                )

            claims.append(
                {
                    "id": f"assumption_{index}",
                    "type": "assumption",
                    "title": (
                        "Architectural assumption: "
                        f"{assumption_text}"
                    ),
                    "claim": (
                        "The architectural assumption "
                        f"'{assumption_text}' is reasonable "
                        "and should be explicitly tracked."
                    ),
                    "query": query,
                    "evidence_terms": evidence_terms,
                }
            )

        return claims

    # ==================================================================
    # EVIDENCE CHECKING
    # ==================================================================

    @staticmethod
    def _has_direct_evidence(
        claim: dict[str, object],
        retrieved: list,
    ) -> bool:
        if not retrieved:
            return False

        evidence_terms = claim.get(
            "evidence_terms",
            [],
        )

        if not isinstance(
            evidence_terms,
            list,
        ):
            return False

        if not evidence_terms:
            return False

        combined_text = " ".join(
            result.chunk.content.casefold()
            for result in retrieved
            if result.chunk.content
        )

        # Every required term must actually appear in the
        # retrieved knowledge.
        for term in evidence_terms:
            if str(term).casefold() not in combined_text:
                return False

        return True

    @staticmethod
    def _build_evidence_text(
        retrieved: list,
        direct_evidence: bool,
    ) -> str:
        evidence_parts: list[str] = []

        if not direct_evidence:
            evidence_parts.append(
                "The retrieved knowledge does not directly support "
                "this architecture claim."
            )

        for result in retrieved:
            evidence_parts.append(
                f"[{result.chunk.chunk_id}] "
                f"{result.chunk.content}"
            )

        return "\n\n".join(
            evidence_parts
        )

    # ==================================================================
    # VERDICTS
    # ==================================================================

    @staticmethod
    def _calculate_status(
        findings: list[RAGValidationFinding],
    ) -> Literal["PASS", "NEEDS_REVIEW"]:
        for finding in findings:
            if finding.verdict in {
                "QUESTIONABLE",
                "UNSUPPORTED",
            }:
                return "NEEDS_REVIEW"

        return "PASS"

    # ==================================================================
    # REPORT TEXT
    # ==================================================================

    @staticmethod
    def _build_summary(
        findings: list[RAGValidationFinding],
    ) -> str:
        supported = sum(
            finding.verdict == "SUPPORTED"
            for finding in findings
        )

        questionable = sum(
            finding.verdict == "QUESTIONABLE"
            for finding in findings
        )

        unsupported = sum(
            finding.verdict == "UNSUPPORTED"
            for finding in findings
        )

        if questionable or unsupported:
            return (
                f"Validated {len(findings)} architecture decisions: "
                f"{supported} supported, "
                f"{questionable} questionable, "
                f"{unsupported} unsupported. "
                "One or more decisions require review."
            )

        return (
            f"Validated {len(findings)} architecture decisions. "
            "All decisions have direct supporting evidence in "
            "the knowledge base."
        )

    @staticmethod
    def _build_recommendation(
        claim: dict[str, object],
        verdict: Verdict,
    ) -> str:
        claim_type = claim["type"]

        if verdict == "SUPPORTED":
            if claim_type == "database":
                return (
                    "The retrieved knowledge directly supports "
                    "the selected database technology. Keep the "
                    "choice aligned with the project's data model "
                    "and consistency requirements."
                )

            if claim_type == "architecture_style":
                return (
                    "The retrieved architecture guidance directly "
                    "supports the selected architecture style. "
                    "Keep the decision aligned with project "
                    "requirements and operational constraints."
                )

            if claim_type == "authentication":
                return (
                    "The retrieved authentication guidance supports "
                    "the current authentication decision. Keep the "
                    "decision explicitly tied to the requirements."
                )

            if claim_type == "integration":
                return (
                    "The retrieved integration guidance supports "
                    "the need for the external service. Avoid "
                    "selecting a specific commercial provider "
                    "without project-specific justification."
                )

            if claim_type == "assumption":
                return (
                    "The retrieved knowledge directly supports "
                    "the assumption. Keep the assumption explicit "
                    "so it can be confirmed or changed later."
                )

            return (
                "The retrieved knowledge directly supports this "
                "technical decision. Keep the choice aligned "
                "with project requirements and constraints."
            )

        if verdict == "QUESTIONABLE":
            return (
                "Obtain direct engineering evidence for this "
                "architecture decision before treating it as "
                "validated."
            )

        return (
            "Review and revise this architecture decision because "
            "the available knowledge does not justify it."
        )

    @staticmethod
    def _build_recommended_actions(
        findings: list[RAGValidationFinding],
    ) -> list[str]:
        actions: list[str] = []

        for finding in findings:
            if finding.verdict not in {
                "QUESTIONABLE",
                "UNSUPPORTED",
            }:
                continue

            recommendation = (
                finding.recommendation.strip()
            )

            if (
                recommendation
                and recommendation not in actions
            ):
                actions.append(
                    recommendation
                )

        return actions

    # ==================================================================
    # CATEGORIES
    # ==================================================================

    @staticmethod
    def _category_for_claim(
        claim_type: str,
    ) -> Category:
        mapping: dict[str, Category] = {
            "architecture_style": "architecture_style",
            "frontend": "technology_choice",
            "backend": "technology_choice",
            "database": "database",
            "authentication": "authentication",
            "integration": "integration",
            "assumption": "assumption",
        }

        return mapping.get(
            claim_type,
            "general",
        )

    # ==================================================================
    # TERM HELPERS
    # ==================================================================

    @staticmethod
    def _architecture_style_terms(
        architecture_style: str,
    ) -> list[str]:
        style = architecture_style.casefold()

        if "layered" in style:
            return [
                "layered",
                "architecture",
            ]

        if "microservice" in style:
            return [
                "microservices",
            ]

        if "monolith" in style:
            return [
                "monolith",
            ]

        if "client-server" in style:
            return [
                "client-server",
            ]

        return [
            architecture_style.casefold()
        ]

    @staticmethod
    def _extract_evidence_terms(
        text: str,
    ) -> list[str]:
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "may",
            "might",
            "should",
            "be",
            "to",
            "for",
            "of",
            "and",
            "or",
            "with",
            "this",
            "that",
            "project",
            "system",
            "application",
            "architecture",
        }

        words = [
            word.strip(
                ".,!?():;'\""
            ).casefold()
            for word in text.split()
        ]

        terms = [
            word
            for word in words
            if len(word) >= 4
            and word not in stop_words
        ]

        # Keep the list short so evidence matching remains
        # deterministic and does not become overly strict.
        return terms[:4]