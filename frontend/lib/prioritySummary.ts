import {
  DataProductInsight,
} from "@/types/report";

import {
  InsightPriority,
  normalizeInsights,
  normalizePriority,
} from "@/lib/insightModel";

import {
  RankedProductOpportunity,
} from "@/lib/productOpportunities";


export interface PriorityCounts {
  high: number;
  medium: number;
  low: number;
  total: number;
}


export function countInsightsByPriority(
  insights: DataProductInsight[] = []
): PriorityCounts {

  const normalized =
    normalizeInsights(insights);

  const counts: PriorityCounts = {
    high: 0,
    medium: 0,
    low: 0,
    total: normalized.length,
  };

  for (const insight of normalized) {

    const priority =
      normalizePriority(
        insight.priority
      );

    counts[priority] += 1;

  }

  return counts;

}


export function countOpportunitiesByPriority(
  opportunities: RankedProductOpportunity[] = []
): PriorityCounts {

  const counts: PriorityCounts = {
    high: 0,
    medium: 0,
    low: 0,
    total: opportunities.length,
  };

  for (const opportunity of opportunities) {

    counts[opportunity.priority] += 1;

  }

  return counts;

}


export const PRIORITY_LABELS: Record<
  InsightPriority,
  string
> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
