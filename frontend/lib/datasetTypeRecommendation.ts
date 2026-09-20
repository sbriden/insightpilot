import {
  DatasetClassificationResult,
  DatasetTypeRecommendation,
} from "@/types/dataset";

/**
 * Maps classifier archetypes to catalog dataset type ids.
 * Archetypes without a matching type are omitted from recommendations.
 */
export const ARCHETYPE_TO_DATASET_TYPE: Record<
  string,
  string
> = {
  sales_revenue: "sales",
  customer: "customer",
  operations: "operations",
  finance: "finance",
  workforce: "workforce",
  fantasy_sports: "fantasy_football",
};

export function buildDatasetTypeRecommendation(
  classification: DatasetClassificationResult
): DatasetTypeRecommendation {

  const confidenceByTypeId: Record<
    string,
    number
  > = {};

  for (const score of classification.all_scores ?? []) {

    const typeId =
      ARCHETYPE_TO_DATASET_TYPE[
        score.archetype
      ];

    if (
      !typeId ||
      score.score < 0.3
    ) {
      continue;
    }

    confidenceByTypeId[typeId] = Math.max(
      confidenceByTypeId[typeId] ?? 0,
      score.score
    );

  }

  const primaryTypeId =
    classification.primary_archetype
      ? ARCHETYPE_TO_DATASET_TYPE[
          classification.primary_archetype
        ] ?? null
      : null;

  if (
    primaryTypeId &&
    classification.confidence > 0
  ) {

    confidenceByTypeId[primaryTypeId] =
      Math.max(
        confidenceByTypeId[primaryTypeId] ?? 0,
        classification.confidence
      );

  }

  return {
    datasetTypeId: primaryTypeId,
    label: classification.label,
    confidence: classification.confidence,
    explanation: classification.explanation,
    confidenceByTypeId,
  };

}
