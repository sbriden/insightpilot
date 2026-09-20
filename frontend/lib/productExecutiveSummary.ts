import {
  AnalysisDashboard,
  DataProduct,
  DataProductInsight,
  InsightInitialResults,
  ProductChangeSummary,
  ProductExecutiveSummary,
  ProductExecutiveSummaryItem,
  PromotedInsight,
} from "@/types/report";

import {
  InsightPriority,
  normalizeInsights,
  normalizePriority,
} from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";


function joinTitles(
  titles: string[]
): string {

  const cleaned =
    titles.filter(Boolean);

  if (cleaned.length === 0) {
    return "";
  }

  if (cleaned.length === 1) {
    return cleaned[0];
  }

  if (cleaned.length === 2) {
    return `${cleaned[0]} and ${cleaned[1]}`;
  }

  return `${cleaned.slice(0, -1).join(", ")}, and ${cleaned[cleaned.length - 1]}`;
}


function tierToPriority(
  tier?: string | null
): InsightPriority {
  const normalized = String(tier ?? "")
    .trim()
    .toLowerCase();

  if (normalized === "critical") {
    return "high";
  }

  if (normalized === "important") {
    return "medium";
  }

  return "low";
}


/**
 * Same Alpha recommended set as the Insights tab top cards.
 */
export function resolveRecommendedInsights(
  product: Pick<
    DataProduct,
    | "insight_initial_results"
    | "promoted_insights"
  >
): PromotedInsight[] {
  const recommended =
    product.insight_initial_results?.recommended_insights;

  if (recommended && recommended.length > 0) {
    return recommended;
  }

  const cap =
    product.insight_initial_results?.recommended_cap ?? 5;

  return (product.promoted_insights ?? []).slice(0, cap);
}


export function whatMattersFromPromotedInsights(
  insights: PromotedInsight[]
): ProductExecutiveSummaryItem[] {
  return insights.slice(0, 5).map((insight) => {
    const layers = resolveInsightLayers(insight);
    const headline = layers.fact || layers.title || "Insight";
    const detail = layers.interpretation;

    return {
      priority:
        normalizePriority(insight.importance) !== "low"
          ? normalizePriority(insight.importance)
          : tierToPriority(insight.tier),
      category: String(insight.category ?? "Analysis"),
      headline,
      detail:
        detail && detail !== headline ? detail : "",
    };
  });
}


function buildWhatWeFound(input: {
  productName: string;
  businessPurpose?: string;
  analyses: DataProduct["analyses"];
  dashboards: AnalysisDashboard[];
  metrics: NonNullable<DataProduct["metrics"]>;
  insights: DataProductInsight[];
  changeSummary?: ProductChangeSummary | null;
}): string {

  const sentences: string[] = [];

  const analysisTitles =
    input.analyses.map(
      analysis =>
        typeof analysis === "string"
          ? analysis
          : analysis.title ??
            analysis.id ??
            ""
    );

  const analysisPhrase =
    joinTitles(
      analysisTitles.slice(0, 3)
    );

  if (analysisPhrase) {
    sentences.push(
      `${input.productName} combines ${analysisPhrase} to assess performance in this business area.`
    );
  } else if (input.businessPurpose) {
    sentences.push(
      `${input.productName} focuses on ${input.businessPurpose.replace(/\.$/, "")}.`
    );
  } else {
    sentences.push(
      `${input.productName} summarizes the most important patterns in this business area.`
    );
  }

  for (const dashboard of input.dashboards) {

    const summary =
      dashboard.summary?.trim() ??
      "";

    if (
      summary &&
      !sentences.includes(summary)
    ) {
      sentences.push(summary);
    }

    if (sentences.length >= 4) {
      break;
    }
  }

  const prioritized =
    normalizeInsights(
      input.insights
    );

  for (const insight of prioritized) {

    const detail =
      insight.why_it_matters?.trim() ||
      insight.message?.trim() ||
      "";

    if (
      detail &&
      !sentences.includes(detail)
    ) {
      sentences.push(detail);
    }

    if (sentences.length >= 4) {
      break;
    }
  }

  if (
    input.changeSummary?.has_meaningful_changes
  ) {

    const overview =
      input.changeSummary.overview?.trim() ??
      "";

    if (
      overview &&
      !sentences.includes(overview) &&
      sentences.length < 4
    ) {
      sentences.push(overview);
    }
  }

  if (
    sentences.length < 2 &&
    input.metrics.length > 0
  ) {

    const metric =
      input.metrics[0];

    if (
      metric?.value !== undefined &&
      metric?.value !== null
    ) {
      sentences.push(
        `The headline measure is ${metric.name ?? "Key metric"} at ${metric.value}.`
      );
    }
  }

  while (sentences.length < 2) {
    sentences.push(
      "Review the prioritized insights below to understand the business impact for this product."
    );
  }

  return sentences.slice(0, 4).join(" ");
}


function buildWhatMatters(
  insights: DataProductInsight[]
): ProductExecutiveSummaryItem[] {

  return normalizeInsights(
    insights
  )
    .slice(0, 5)
    .map(insight => {
      const layers = resolveInsightLayers(insight);
      const headline =
        layers.fact ||
        layers.title ||
        "Analysis finding";

      const detail =
        layers.interpretation.trim() === headline.trim()
          ? ""
          : layers.interpretation;

      return {

        priority:
          normalizePriority(
            insight.priority
          ),

        category:
          insight.category ??
          "Analysis",

        headline,

        detail,

      };

    });
}


function buildWhatToDoNext(
  insights: DataProductInsight[],
  dashboards: AnalysisDashboard[],
  recommendedInsights: PromotedInsight[] = []
): string[] {

  const actions: string[] = [];

  for (const insight of recommendedInsights) {
    const action =
      resolveInsightLayers(insight).recommendation.trim();

    if (action && !actions.includes(action)) {
      actions.push(action);
    }

    if (actions.length >= 4) {
      return actions.slice(0, 4);
    }
  }

  for (const insight of normalizeInsights(
    insights
  )) {

    const action =
      resolveInsightLayers(insight).recommendation.trim();

    if (
      action &&
      !actions.includes(action)
    ) {
      actions.push(action);
    }

    if (actions.length >= 4) {
      return actions.slice(0, 4);
    }
  }

  for (const dashboard of dashboards) {

    for (const action of dashboard.actions ?? []) {

      const text =
        action.trim();

      if (
        text &&
        !actions.includes(text)
      ) {
        actions.push(text);
      }

      if (actions.length >= 4) {
        return actions.slice(0, 4);
      }
    }
  }

  while (actions.length < 2) {
    actions.push(
      actions.length === 0
        ? "Review the supporting analyses and confirm ownership for the highest-priority insight."
        : "Schedule a follow-up to track progress on the recommended actions."
    );
  }

  return actions.slice(0, 4);
}


export function buildProductExecutiveSummary(
  input: {
    productName: string;
    businessPurpose?: string;
    description?: string;
    analyses?: DataProduct["analyses"];
    dashboards?: AnalysisDashboard[];
    metrics?: DataProduct["metrics"];
    insights?: DataProductInsight[];
    changeSummary?: ProductChangeSummary | null;
    recommendedInsights?: PromotedInsight[];
    insightInitialResults?: InsightInitialResults | null;
    promotedInsights?: PromotedInsight[];
  }
): ProductExecutiveSummary {

  const dashboards =
    input.dashboards ?? [];

  const metrics =
    input.metrics ?? [];

  const insights =
    input.insights ?? [];

  const analyses =
    input.analyses ?? [];

  const recommendedInsights =
    input.recommendedInsights?.length
      ? input.recommendedInsights
      : resolveRecommendedInsights({
          insight_initial_results:
            input.insightInitialResults ?? undefined,
          promoted_insights: input.promotedInsights,
        });

  const whatMatters =
    recommendedInsights.length > 0
      ? whatMattersFromPromotedInsights(recommendedInsights)
      : buildWhatMatters(insights);

  return {
    what_we_found: buildWhatWeFound({
      productName: input.productName,
      businessPurpose: input.businessPurpose,
      analyses,
      dashboards,
      metrics,
      insights,
      changeSummary: input.changeSummary,
    }),

    what_matters: whatMatters,

    what_to_do_next: buildWhatToDoNext(
      insights,
      dashboards,
      recommendedInsights
    ),
  };
}


function dedupeWhatMattersItems(
  items: ProductExecutiveSummaryItem[]
): ProductExecutiveSummaryItem[] {

  return items.map(item => {

    const headline =
      item.headline?.trim() ?? "";

    const detail =
      item.detail?.trim() ?? "";

    if (
      detail &&
      headline &&
      detail === headline
    ) {
      return {
        ...item,
        detail: "",
      };
    }

    return item;

  });

}


export function resolveProductExecutiveSummary(
  product: Pick<
    DataProduct,
    | "name"
    | "business_purpose"
    | "description"
    | "analyses"
    | "dashboards"
    | "metrics"
    | "insights"
    | "change_summary"
    | "executive_summary"
    | "insight_initial_results"
    | "promoted_insights"
  >
): ProductExecutiveSummary {

  const recommendedInsights =
    resolveRecommendedInsights(product);

  const recommendedWhatMatters =
    recommendedInsights.length > 0
      ? dedupeWhatMattersItems(
          whatMattersFromPromotedInsights(recommendedInsights)
        )
      : null;

  if (
    product.executive_summary &&
    product.executive_summary.what_we_found
  ) {
    return {
      ...product.executive_summary,
      what_matters:
        recommendedWhatMatters ??
        dedupeWhatMattersItems(
          product.executive_summary.what_matters ?? []
        ),
      what_to_do_next:
        recommendedInsights.length > 0
          ? buildWhatToDoNext(
              product.insights ?? [],
              product.dashboards ?? [],
              recommendedInsights
            )
          : product.executive_summary.what_to_do_next,
    };
  }

  const summary = buildProductExecutiveSummary({
    productName: product.name,
    businessPurpose: product.business_purpose,
    description: product.description,
    analyses: product.analyses,
    dashboards: product.dashboards,
    metrics: product.metrics,
    insights: product.insights,
    changeSummary: product.change_summary,
    recommendedInsights,
  });

  return {
    ...summary,
    what_matters: dedupeWhatMattersItems(
      summary.what_matters
    ),
  };

}
