from datetime import datetime

import pandas as pd

from ..core.analysis_context import AnalysisContext

from .classifier import classify_dataset
from .insights import generate_insights
from .metrics import generate_metrics
from .profiler import profile_dataframe
from .recommendations import generate_recommendations
from .visualizations import recommend_visualizations
from .column_profiler import profile_columns
from ..analysis.engine import generate_analysis_dashboards
from ..datasets.semantic_context import (
    build_semantic_layer_from_dataframe,
    log_semantic_understanding,
)
from .ai import generate_executive_brief


def apply_field_mappings(
    df: pd.DataFrame,
    field_mappings: list,
) -> pd.DataFrame:
    """
    Apply user-defined field mappings to the dataframe.

    Each mapping is expected to contain:

        {
            "requiredField": "transaction_date",
            "uploadedField": "Date"
        }

    The uploaded column is renamed to the standardized
    InsightPilot field name.

    Columns without mappings are left unchanged.

    If multiple mappings would result in conflicting column
    names, the original column is preserved rather than
    silently overwriting another field.
    """

    mapped_df = df.copy()

    if not field_mappings:
        return mapped_df

    renamed_columns = {}

    existing_columns = set(
        mapped_df.columns
    )

    for mapping in field_mappings:

        if not isinstance(
            mapping,
            dict,
        ):
            continue

        required_field = mapping.get(
            "requiredField"
        )

        uploaded_field = mapping.get(
            "uploadedField"
        )

        if not required_field or not uploaded_field:
            continue

        # Uploaded column must exist.
        if uploaded_field not in existing_columns:
            continue

        # No rename needed.
        if uploaded_field == required_field:
            continue

        # Don't allow two uploaded columns to map
        # to the same semantic field.
        if (
            required_field
            in renamed_columns.values()
        ):

            print(
                "Skipping conflicting field mapping:"
            )

            print(
                f"  {uploaded_field} -> "
                f"{required_field}"
            )

            continue

        # If the standardized field already exists
        # as a different uploaded column, don't overwrite it.
        if (
            required_field in existing_columns
            and required_field != uploaded_field
        ):

            print(
                "Skipping conflicting field mapping:"
            )

            print(
                f"  {uploaded_field} -> "
                f"{required_field}"
            )

            print(
                f"  Column '{required_field}' "
                f"already exists."
            )

            continue

        renamed_columns[
            uploaded_field
        ] = required_field

    if not renamed_columns:
        return mapped_df

    print(
        "Applying field mappings:"
    )

    for (
        uploaded_field,
        standardized_field,
    ) in renamed_columns.items():

        print(
            f"  {uploaded_field} -> "
            f"{standardized_field}"
        )

    mapped_df = mapped_df.rename(
        columns=renamed_columns
    )

    print(
        "Analysis dataframe columns:"
    )

    print(
        mapped_df.columns.tolist()
    )

    return mapped_df


def analyze_dataframe(
    df: pd.DataFrame,
    field_mappings: list | None = None,
    selected_product_ids: list[str] | None = None,
) -> AnalysisContext:
    """
    Runs the complete InsightPilot analysis pipeline.

    Field mappings are applied before the analysis pipeline
    so downstream services operate against standardized
    InsightPilot field names.

    selected_product_ids contains the data products explicitly
    selected by the user. The selection is carried through the
    analysis context and used when generating data products.
    """

    # ---------------------------------------------------------
    # Normalize selected product IDs
    # ---------------------------------------------------------

    normalized_product_ids = [
        str(product_id).strip()
        for product_id
        in (selected_product_ids or [])
        if str(product_id).strip()
    ]

    print(
        "Analysis selected product IDs:",
        normalized_product_ids,
    )


    # ---------------------------------------------------------
    # Apply field mappings
    # ---------------------------------------------------------

    mapped_df = apply_field_mappings(
        df,
        field_mappings or [],
    )

    print(
        "Analysis dataframe columns:"
    )

    print(
        mapped_df.columns.tolist()
    )


    # ---------------------------------------------------------
    # Profile dataset
    # ---------------------------------------------------------

    profile = profile_dataframe(
        mapped_df
    )


    # ---------------------------------------------------------
    # Profile columns
    # ---------------------------------------------------------

    column_profiles = profile_columns(
        mapped_df
    )


    # ---------------------------------------------------------
    # Generate metrics
    # ---------------------------------------------------------

    metrics = generate_metrics(
        mapped_df
    )


    # ---------------------------------------------------------
    # Classify dataset (legacy keyword classifier)
    # ---------------------------------------------------------

    classification = classify_dataset(
        mapped_df.columns.tolist()
    )


    # ---------------------------------------------------------
    # Semantic analysis layer (structured facts, validated)
    # ---------------------------------------------------------
    # Deterministic concept identification, capabilities,
    # archetype, and grain. Validated before AnalysisContext.
    # LLM is never the calculation engine for analytical facts.

    semantic_layer = build_semantic_layer_from_dataframe(
        mapped_df,
        column_profiles,
    )

    # Developer logging — inspect what the semantic engine
    # believes about this dataset (concepts, grain, etc.).
    log_semantic_understanding(semantic_layer)


    # ---------------------------------------------------------
    # Recommendations
    # ---------------------------------------------------------

    recommendations = generate_recommendations(
        classification,
        metrics,
    )


    # ---------------------------------------------------------
    # Insights
    # ---------------------------------------------------------

    insights = generate_insights(
        metrics
    )


    # ---------------------------------------------------------
    # Visualization recommendations
    # ---------------------------------------------------------

    visualizations = recommend_visualizations(
        mapped_df,
        recommendations,
        column_profiles,
    )


    # ---------------------------------------------------------
    # Build analysis context
    # ---------------------------------------------------------

    context = AnalysisContext(
        dataframe=mapped_df,
        profile=profile,
        metrics=metrics,
        classification=classification,
        semantic_model=semantic_layer["semantic_model"],
        capabilities=semantic_layer["capabilities"],
        dataset_archetype=semantic_layer["dataset_archetype"],
        recommendations=recommendations,
        insights=insights,
        column_profiles=column_profiles,
        visualizations=visualizations,
        selected_product_ids=normalized_product_ids,
        created_at=datetime.utcnow(),
    )


    # ---------------------------------------------------------
    # Generate analysis dashboards
    # ---------------------------------------------------------

    context.analysis_dashboards = (
        generate_analysis_dashboards(
            context
        )
    )


    # ---------------------------------------------------------
    # Generate executive brief (narrative over facts only)
    # ---------------------------------------------------------

    context.executive_brief = (
        generate_executive_brief(
            context
        )
    )


    # ---------------------------------------------------------
    # Generate data products
    # ---------------------------------------------------------

    from app.products.service import (
        generate_data_products
    )

    context.data_products = (
        generate_data_products(
            context,
            selected_product_ids=(
                context.selected_product_ids
            ),
        )
    )


    return context