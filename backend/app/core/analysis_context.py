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

        }
