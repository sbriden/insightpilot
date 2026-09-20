import {
  DataProductInsight,
  PromotedInsight,
} from "@/types/report";


export type InsightPriority =
  | "high"
  | "medium"
  | "low";


const PRIORITY_WEIGHT: Record<
  InsightPriority,
  number
> = {
  high: 3,
  medium: 2,
  low: 1,
};


const DEFAULT_ACTIONS: Record<
  InsightPriority,
  string
> = {
  high:
    "Treat this as an immediate priority and assign an owner to respond.",

  medium:
    "Review this finding and define a follow-up action in the current planning cycle.",

  low:
    "Monitor this pattern and revisit if the trend continues.",
};


function firstSentence(
  value: string
): string {

  const text = value.trim();

  if (!text) {
    return "";
  }

  for (
    const separator
    of [". ", "! ", "? "]
  ) {

    if (
      text.includes(separator)
    ) {

      return (
        text.split(
          separator,
          1
        )[0] + separator.trim()
      );

    }

  }

  return text;

}


export function normalizePriority(
  value?: string | null
): InsightPriority {

  const normalized =
    String(value ?? "low")
      .trim()
      .toLowerCase();

  if (
    normalized === "high" ||
    normalized === "critical"
  ) {
    return "high";
  }

  if (
    normalized === "medium" ||
    normalized === "warning"
  ) {
    return "medium";
  }

  return "low";

}


export function normalizeInsight(
  insight: DataProductInsight,
  defaultCategory = "Analysis"
): DataProductInsight {

  const priority =
    normalizePriority(
      insight.priority ??
      insight.severity
    );

  const message =
    insight.message?.trim() ??
    "";

  const title =
    insight.title?.trim() ??
    "";

  const whatHappened =
    insight.what_happened?.trim() ||
    title ||
    firstSentence(message) ||
    "Analysis finding identified";

  // Keep Interpretation empty rather than copying Fact into it.
  const whyItMatters =
    insight.why_it_matters?.trim() ||
    "";

  return {
    ...insight,

    priority,

    severity: priority,

    category:
      insight.category?.trim() ||
      defaultCategory,

    what_happened:
      whatHappened,

    why_it_matters:
      whyItMatters,

    recommended_action:
      insight.recommended_action?.trim() ||
      DEFAULT_ACTIONS[priority],

    title:
      title || whatHappened,

    message:
      message || whyItMatters || whatHappened,
  };

}


export function sortInsightsByPriority(
  insights: DataProductInsight[]
): DataProductInsight[] {

  return [...insights].sort(
    (left, right) => {

      const leftPriority =
        normalizePriority(
          left.priority ??
          left.severity
        );

      const rightPriority =
        normalizePriority(
          right.priority ??
          right.severity
        );

      return (
        PRIORITY_WEIGHT[rightPriority] -
        PRIORITY_WEIGHT[leftPriority]
      );

    }
  );

}


export function normalizeInsights(
  insights: DataProductInsight[] = [],
  defaultCategory = "Analysis"
): DataProductInsight[] {

  return sortInsightsByPriority(
    insights.map(
      insight =>
        normalizeInsight(
          insight,
          defaultCategory
        )
    )
  );

}


/**
 * Rank promoted Insights by tier (Critical → Important → Supporting),
 * then scoring.total (desc). Backend already sorts; this keeps UI
 * order stable if payloads arrive unsorted.
 */
export function sortPromotedInsights(
  insights: PromotedInsight[] = []
): PromotedInsight[] {

  const tierOrder: Record<string, number> = {
    critical: 0,
    important: 1,
    supporting: 2,
  };

  return [...insights].sort((left, right) => {
    const leftTier =
      tierOrder[String(left.tier ?? "important").toLowerCase()] ?? 1;
    const rightTier =
      tierOrder[String(right.tier ?? "important").toLowerCase()] ?? 1;

    if (leftTier !== rightTier) {
      return leftTier - rightTier;
    }

    const leftScore =
      typeof left.scoring?.total === "number"
        ? left.scoring.total
        : -1;
    const rightScore =
      typeof right.scoring?.total === "number"
        ? right.scoring.total
        : -1;

    if (rightScore !== leftScore) {
      return rightScore - leftScore;
    }

    return left.insight_id.localeCompare(right.insight_id);
  });

}
