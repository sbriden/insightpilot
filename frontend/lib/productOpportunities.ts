import {
  AnalysisDashboard,
  DataProductInsight,
} from "@/types/report";

import {
  normalizeInsight,
  normalizePriority,
} from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";


export interface RankedProductOpportunity {
  id: string;
  type: string;
  label: string;
  potential: number | null;
  score: number | null;
  source: string;
  priority: "high" | "medium" | "low";
  detail?: string;
}


function toNumber(
  value: unknown
): number | null {

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const parsed =
    Number(value);

  return Number.isFinite(parsed)
    ? parsed
    : null;

}


function resolvePriority(
  score: number | null,
  potential: number | null,
  maxPotential: number
): RankedProductOpportunity["priority"] {

  if (
    score !== null &&
    score >= 0.7
  ) {
    return "high";
  }

  if (
    potential !== null &&
    maxPotential > 0 &&
    potential / maxPotential >= 0.6
  ) {
    return "high";
  }

  if (
    score !== null &&
    score >= 0.4
  ) {
    return "medium";
  }

  if (
    potential !== null &&
    maxPotential > 0 &&
    potential / maxPotential >= 0.3
  ) {
    return "medium";
  }

  return "low";

}


function appendRows(
  rows: RankedProductOpportunity[],
  data: any[],
  config: {
    dashboardId: string;
    source: string;
    type: string;
    labelField: string;
    potentialField: string;
    scoreField: string;
    typeField?: string;
  }
) {

  for (
    let index = 0;
    index < data.length;
    index += 1
  ) {

    const row = data[index];

    if (!row) {
      continue;
    }

    rows.push({
      id:
        `${config.dashboardId}-${index}-${String(row[config.labelField] ?? index)}`,

      type:
        config.typeField
          ? String(
              row[config.typeField] ??
              config.type
            )
          : config.type,

      label:
        String(
          row[config.labelField] ??
          "Opportunity"
        ),

      potential:
        toNumber(
          row[config.potentialField]
        ),

      score:
        toNumber(
          row[config.scoreField]
        ),

      source:
        config.source,

      priority: "medium",
    });

  }

}


function rowsFromDashboard(
  dashboard: AnalysisDashboard
): RankedProductOpportunity[] {

  const rows: RankedProductOpportunity[] = [];

  const datasets =
    dashboard.datasets ?? {};

  const source =
    dashboard.title ??
    dashboard.id;


  if (
    Array.isArray(
      datasets.top_opportunities
    )
  ) {

    appendRows(
      rows,
      datasets.top_opportunities,
      {
        dashboardId:
          dashboard.id,

        source,

        type: "Opportunity",

        typeField: "type",

        labelField: "label",

        potentialField: "potential",

        scoreField: "score",
      }
    );

  }

  if (
    dashboard.id === "cross_sell" &&
    Array.isArray(
      datasets.cross_sell_opportunities
    )
  ) {

    appendRows(
      rows,
      datasets.cross_sell_opportunities,
      {
        dashboardId:
          dashboard.id,

        source,

        type: "Cross-Sell",

        labelField: "label",

        potentialField:
          "estimated_opportunity",

        scoreField:
          "cross_sell_score",
      }
    );

  }

  if (
    dashboard.id ===
      "customer_growth" &&
    Array.isArray(
      datasets.customer_growth_opportunities
    )
  ) {

    appendRows(
      rows,
      datasets.customer_growth_opportunities,
      {
        dashboardId:
          dashboard.id,

        source,

        type: "Customer Growth",

        labelField: "label",

        potentialField:
          "estimated_growth_potential",

        scoreField:
          "growth_score",
      }
    );

  }

  if (
    dashboard.id ===
      "profit_improvement" &&
    Array.isArray(
      datasets.profit_improvement_opportunities
    )
  ) {

    appendRows(
      rows,
      datasets.profit_improvement_opportunities,
      {
        dashboardId:
          dashboard.id,

        source,

        type: "Profit Improvement",

        labelField: "label",

        potentialField:
          "estimated_profit_opportunity",

        scoreField:
          "priority_score",
      }
    );

  }

  return rows;

}


function insightsAsOpportunities(
  insights: DataProductInsight[]
): RankedProductOpportunity[] {

  return insights
    .map(
      (insight, index) =>
        normalizeInsight(
          insight
        )
    )
    .filter(
      insight =>
        normalizePriority(
          insight.priority
        ) !== "low"
    )
    .map(
      (insight, index) => {
        const layers = resolveInsightLayers(insight);

        return {

        id:
          insight.id ??
          `insight-${index}`,

        type:
          insight.category ??
          "Insight",

        label:
          layers.fact ||
          layers.title ||
          "Key insight",

        potential: null,

        score:
          normalizePriority(
            insight.priority
          ) === "high"
            ? 0.85
            : 0.55,

        source:
          "Product insight",

        priority:
          normalizePriority(
            insight.priority
          ),

        detail:
          layers.interpretation ||
          layers.recommendation ||
          undefined,

      };
      }
    );

}


function actionsAsOpportunities(
  dashboards: AnalysisDashboard[]
): RankedProductOpportunity[] {

  const rows: RankedProductOpportunity[] = [];

  for (
    const dashboard
    of dashboards
  ) {

    const actions =
      dashboard.actions ?? [];

    for (
      let index = 0;
      index < actions.length;
      index += 1
    ) {

      const action =
        actions[index];

      if (!action) {
        continue;
      }

      rows.push({
        id:
          `${dashboard.id}-action-${index}`,

        type: "Recommended Action",

        label: action,

        potential: null,

        score: 0.35,

        source:
          dashboard.title ??
          dashboard.id,

        priority: "low",
      });

    }

  }

  return rows;

}


export function extractTopOpportunities(
  dashboards: AnalysisDashboard[] = [],
  insights: DataProductInsight[] = [],
  limit = 5
): RankedProductOpportunity[] {

  const structured =
    dashboards.flatMap(
      rowsFromDashboard
    );

  const candidates =
    structured.length > 0
      ? structured
      : [
          ...insightsAsOpportunities(
            insights
          ),
          ...actionsAsOpportunities(
            dashboards
          ),
        ];

  if (
    candidates.length === 0
  ) {
    return [];
  }

  const maxPotential =
    Math.max(
      0,
      ...candidates.map(
        item =>
          item.potential ?? 0
      )
    );

  const ranked =
    candidates
      .map(
        item => ({
          ...item,

          priority:
            resolvePriority(
              item.score,
              item.potential,
              maxPotential
            ),
        })
      )
      .sort(
        (left, right) => {

          const priorityWeight = {
            high: 3,
            medium: 2,
            low: 1,
          };

          const priorityDelta =
            priorityWeight[right.priority] -
            priorityWeight[left.priority];

          if (
            priorityDelta !== 0
          ) {
            return priorityDelta;
          }

          const potentialDelta =
            (right.potential ?? 0) -
            (left.potential ?? 0);

          if (
            potentialDelta !== 0
          ) {
            return potentialDelta;
          }

          return (
            (right.score ?? 0) -
            (left.score ?? 0)
          );

        }
      );

  const seen =
    new Set<string>();

  const unique: RankedProductOpportunity[] =
    [];

  for (
    const item
    of ranked
  ) {

    const key =
      `${item.type}::${item.label}`;

    if (
      seen.has(key)
    ) {
      continue;
    }

    seen.add(key);
    unique.push(item);

    if (
      unique.length >= limit
    ) {
      break;
    }

  }

  return unique;

}


export function formatOpportunityValue(
  potential: number | null
): string | null {

  if (
    potential === null ||
    potential <= 0
  ) {
    return null;
  }

  return `$${potential.toLocaleString(
    undefined,
    {
      maximumFractionDigits: 0,
    }
  )}`;

}
