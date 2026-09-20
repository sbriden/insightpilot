import {
  AIInsightContract,
  DataProductInsight,
  PromotedInsight,
} from "@/types/report";

/**
 * Product-wide insight presentation layers.
 *
 * Keeping these separate is a trust requirement: InsightPilot must
 * never blend deterministic facts with AI interpretation or actions.
 */
export const INSIGHT_LAYER_LABELS = {
  fact: "Fact",
  interpretation: "Interpretation",
  recommendation: "Recommendation",
} as const;

export type InsightLayerKey = keyof typeof INSIGHT_LAYER_LABELS;

export interface InsightLayers {
  title: string;
  /** Deterministic observation — never AI prose. */
  fact: string;
  /** What the fact may mean — never invents numbers. */
  interpretation: string;
  /** Suggested next action. */
  recommendation: string;
  potentialDrivers: string[];
  caveats: string[];
}

type InsightLike = {
  title?: string | null;
  finding?: string | null;
  what_happened?: string | null;
  message?: string | null;
  business_impact?: string | null;
  why_it_matters?: string | null;
  recommendation?: string | null;
  recommended_action?: string | null;
  potential_drivers?: string[] | null;
  ai_interpretation?: AIInsightContract | null;
  explanation?:
    | AIInsightContract
    | {
        summary?: string;
        what_happened?: string;
        why_it_matters?: string;
        potential_drivers?: string[];
        drivers?: string[];
        recommended_action?: string;
        next_action?: string;
        caveats?: string[];
      }
    | null;
};

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function uniqueTexts(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const cleaned = text(value);
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(cleaned);
  }
  return result;
}

function resolveAiContract(insight: InsightLike): AIInsightContract | null {
  const ai = insight.ai_interpretation;
  if (ai && (ai.summary || ai.why_it_matters || ai.recommended_action)) {
    return ai;
  }

  const explanation = insight.explanation;
  if (!explanation) {
    return null;
  }

  return {
    summary:
      text(explanation.summary) ||
      text(
        "what_happened" in explanation
          ? explanation.what_happened
          : ""
      ),
    why_it_matters: text(explanation.why_it_matters),
    potential_drivers:
      explanation.potential_drivers ??
      ("drivers" in explanation ? explanation.drivers : undefined) ??
      [],
    recommended_action:
      text(explanation.recommended_action) ||
      text(
        "next_action" in explanation ? explanation.next_action : ""
      ),
    caveats: explanation.caveats ?? [],
    layer: "interpretation",
    source: "fallback",
  };
}

/**
 * Resolve the three visible insight layers from any insight payload.
 *
 * Fact stays deterministic. Interpretation and recommendation may come
 * from the AI contract or legacy product-insight fields.
 */
export function resolveInsightLayers(
  insight: InsightLike | PromotedInsight | DataProductInsight
): InsightLayers {
  const payload = insight as InsightLike;
  const ai = resolveAiContract(payload);

  const fact =
    text(payload.finding) ||
    text(payload.what_happened) ||
    text(payload.title) ||
    text(payload.message);

  const interpretationParts = uniqueTexts([
    ai?.summary,
    ai?.why_it_matters,
    payload.business_impact,
    payload.why_it_matters,
  ]).filter((part) => part.toLowerCase() !== fact.toLowerCase());

  const recommendation =
    text(ai?.recommended_action) ||
    text(payload.recommendation) ||
    text(payload.recommended_action);

  const potentialDrivers = uniqueTexts([
    ...(ai?.potential_drivers ?? []),
    ...(payload.potential_drivers ?? []),
  ]);

  return {
    title: text(payload.title) || fact || "Insight",
    fact,
    interpretation: interpretationParts.join(" "),
    recommendation,
    potentialDrivers,
    caveats: uniqueTexts(ai?.caveats ?? []),
  };
}

export function hasInsightLayers(layers: InsightLayers): boolean {
  return Boolean(
    layers.fact ||
      layers.interpretation ||
      layers.recommendation ||
      layers.potentialDrivers.length > 0
  );
}
