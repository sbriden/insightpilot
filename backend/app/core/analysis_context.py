from dataclasses import dataclass, asdict, field
from datetime import datetime
import pandas as pd

from app.core.responsibilities import (
    NARRATIVE_PROMPT_FACT_KEYS,
    build_narrative_constraints,
)
from app.datasets.semantic_context import (
    build_semantic_understanding,
)


@dataclass
class AnalysisContext:

    profile: dict
    metrics: dict
    classification: dict

    recommendations: list = field(
        default_factory=list
    )

    insights: list = field(
        default_factory=list
    )

    column_profiles: list = field(
        default_factory=list
    )

    visualizations: list = field(
        default_factory=list
    )

    analysis_dashboards: list = field(
        default_factory=list
    )

    executive_brief: dict | None = None

    quality: dict | None = None

    created_at: datetime | None = None

    analysis_metadata: dict | None = None

    # Optional dataset lineage for Insight/product comparison.
    dataset_id: str | None = None
    dataset_version: str | int | None = None
    dataset_identity: str | None = None
    source_dataset: str | None = None

    dataframe: pd.DataFrame | None = field(
        default=None,
        repr=False,
    )

    data_products: list = field(
        default_factory=list
    )

    selected_product_ids: list[str] = field(
        default_factory=list
    )

    # Semantic analysis layer — structured facts shared by
    # analytical modules regardless of dataset archetype.
    # Produced and validated by deterministic code.
    semantic_model: dict = field(
        default_factory=dict
    )

    capabilities: list = field(
        default_factory=list
    )

    dataset_archetype: dict = field(
        default_factory=dict
    )

    # Analyses applicable for this dataset, derived from
    # semantic capabilities + archetype (not a hardcoded sales suite).
    analytical_candidates: list = field(
        default_factory=list
    )

    # Structured findings emitted by analytical modules.
    # Always plain dicts (see serialize_candidate_finding).
    candidate_findings: list = field(
        default_factory=list
    )

    # Validated subset of candidate findings (structural gate).
    # Not every validated finding becomes an Insight.
    validated_findings: list = field(
        default_factory=list
    )

    # Promoted Insights derived from insight-eligible
    # validated findings only.
    promoted_insights: list = field(
        default_factory=list
    )

    # Alpha Initial Results Contract (recommended surface set).
    insight_initial_results: dict | None = None

    def normalized_candidate_findings(self) -> list:
        """JSON-safe findings for API / prompt / persistence."""

        from app.analysis.insights.findings import (
            serialize_candidate_finding,
        )

        return [
            serialized
            for serialized in (
                serialize_candidate_finding(item)
                for item in self.candidate_findings
            )
            if serialized is not None
        ]

    def normalized_validated_findings(self) -> list:
        """JSON-safe validated findings for API / prompt."""

        from app.analysis.insights.validation import (
            serialize_validated_finding,
            validate_findings,
        )

        if self.validated_findings:
            return [
                serialized
                for serialized in (
                    serialize_validated_finding(item)
                    for item in self.validated_findings
                )
                if serialized is not None
            ]

        return validate_findings(
            self.normalized_candidate_findings()
        )

    def normalized_promoted_insights(self) -> list:
        """JSON-safe Insights promoted from eligible findings."""

        from app.analysis.insights.insight import (
            promote_findings,
            serialize_insight,
        )

        if self.promoted_insights:
            return [
                serialized
                for serialized in (
                    serialize_insight(item)
                    for item in self.promoted_insights
                )
                if serialized is not None
            ]

        # Only insight-eligible validated findings promote.
        return promote_findings(
            self.normalized_validated_findings(),
            require_insight_eligible=True,
        )

    def normalized_insight_initial_results(self) -> dict:
        """Alpha Initial Results Contract for recommended surfacing."""

        from app.analysis.insights.initial_results import (
            build_initial_results,
        )

        if isinstance(self.insight_initial_results, dict):
            return self.insight_initial_results

        return build_initial_results(
            self.normalized_promoted_insights()
        )


    def to_dict(self):
        """
        Complete internal representation.

        Useful for persistence and debugging.
        """

        return asdict(
            self
        )


    def analytical_facts(self) -> dict:
        """
        Precomputed analytical facts owned by deterministic code.

        Counts, aggregations, distributions, comparisons, trends,
        anomalies, and related statistics live here (or in module
        dashboards built from those calculations). Narrative /
        LLM layers may only consume these facts — never recompute
        or invent them.
        """

        return {
            "profile": self.profile,
            "metrics": self.metrics,
            "insights": self.insights,
            "analysis_dashboards": self.analysis_dashboards,
            "classification": self.classification,
            "semantic_model": self.semantic_model,
            "capabilities": self.capabilities,
            "dataset_archetype": self.dataset_archetype,
            "analytical_candidates": self.analytical_candidates,
            "candidate_findings":
                self.normalized_candidate_findings(),
            "validated_findings":
                self.normalized_validated_findings(),
            "promoted_insights":
                self.normalized_promoted_insights(),
            "insight_initial_results":
                self.normalized_insight_initial_results(),
            "recommendations": self.recommendations,
        }


    def to_prompt_context(self):
        """
        Narrative-only context for LLM generation.

        Contains precomputed structured facts only. Never includes
        the raw dataframe or calculation inputs. The LLM must not
        invent numbers, aggregations, trends, or other analytical
        results — see ``narrative_constraints``.
        """

        payload = {
            "profile":
                self.profile,

            "metrics":
                self.metrics,

            "classification":
                self.classification,

            "semantic_model":
                self.semantic_model,

            "capabilities":
                self.capabilities,

            "dataset_archetype":
                self.dataset_archetype,

            "analytical_candidates":
                self.analytical_candidates,

            "candidate_findings":
                self.normalized_candidate_findings(),

            "validated_findings":
                self.normalized_validated_findings(),

            "promoted_insights":
                self.normalized_promoted_insights(),

            "recommendations":
                self.recommendations,

            "insights":
                self.insights,

            "analysis_dashboards":
                self.analysis_dashboards,

            "narrative_constraints":
                build_narrative_constraints(),
        }

        # Guardrail: prompt context stays within the fact surface.
        unexpected = set(payload) - NARRATIVE_PROMPT_FACT_KEYS
        if unexpected:
            raise ValueError(
                "Prompt context includes non-fact keys: "
                f"{sorted(unexpected)}"
            )

        return payload


    def to_api_response(self):
        """
        Public API contract.
        """

        semantic_layer = {
            "semantic_model": self.semantic_model,
            "capabilities": self.capabilities,
            "dataset_archetype": self.dataset_archetype,
        }

        return {

            "profile":
                self.profile,

            "metrics":
                self.metrics,

            "classification":
                self.classification,

            "semantic_model":
                self.semantic_model,

            "capabilities":
                self.capabilities,

            "dataset_archetype":
                self.dataset_archetype,

            "analytical_candidates":
                self.analytical_candidates,

            "candidate_findings":
                self.normalized_candidate_findings(),

            "validated_findings":
                self.normalized_validated_findings(),

            "promoted_insights":
                self.normalized_promoted_insights(),

            "insight_initial_results":
                self.normalized_insight_initial_results(),

            # Developer inspection surface for semantic engine
            # correctness (concepts, grain, role buckets, etc.).
            "semantic_understanding":
                build_semantic_understanding(
                    semantic_layer
                ),

            "recommendations":
                self.recommendations,

            "insights":
                self.insights,

            "column_profiles":
                self.column_profiles,

            "visualizations":
                self.visualizations,

            "analysis_dashboards":
                self.analysis_dashboards,

            "executive_brief":
                self.executive_brief,

            "quality":
                self.quality,

            "data_products":
                self.data_products,

            "selected_product_ids":
                self.selected_product_ids,

            "created_at":
                self.created_at,

            "dataset_id":
                self.dataset_id,

            "dataset_version":
                self.dataset_version,

            "dataset_identity":
                self.dataset_identity,

            "source_dataset":
                self.source_dataset,

        }
