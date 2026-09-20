"use client";

import {
  INSIGHT_TIER_LABELS,
  PromotedInsight,
} from "@/types/report";
import { sortPromotedInsights } from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";
import InsightLayerStack from "@/components/products/InsightLayerStack";


interface Props {
  insights?: PromotedInsight[];
}


function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return "—";
    }

    if (Math.abs(value) > 0 && Math.abs(value) < 1) {
      return `${(value * 100).toFixed(1)}%`;
    }

    if (Number.isInteger(value)) {
      return value.toLocaleString();
    }

    return value.toLocaleString(undefined, {
      maximumFractionDigits: 2,
    });
  }

  return String(value);
}


function shortTierLabel(tier: string | undefined): string {
  if (tier === "critical") return "Tier 1";
  if (tier === "important") return "Tier 2";
  if (tier === "supporting") return "Tier 3";
  return INSIGHT_TIER_LABELS[tier ?? ""] ?? "Insight";
}


function tierAccent(tier: string | undefined): string {
  if (tier === "critical") {
    return "border-red-200 bg-red-50/60";
  }
  if (tier === "important") {
    return "border-amber-200 bg-amber-50/50";
  }
  return "border-gray-200 bg-white";
}


export default function RecommendedInsightCards({
  insights = [],
}: Props) {
  const ranked = sortPromotedInsights(insights);

  if (ranked.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
        No recommended insights to surface yet.
      </div>
    );
  }

  return (
    <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-1">
      {ranked.map((insight, index) => {
        const scoreTotal =
          typeof insight.scoring?.total === "number"
            ? insight.scoring.total
            : null;
        const layers = resolveInsightLayers(insight);

        return (
          <article
            key={`${insight.insight_id}-${index}`}
            className={`flex w-[min(19rem,82vw)] shrink-0 flex-col rounded-xl border p-4 shadow-sm ${tierAccent(insight.tier)}`}
          >
            <div className="flex items-start justify-between gap-2">
              <span className="rounded-md bg-white/80 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-gray-700">
                {shortTierLabel(insight.tier)}
              </span>
              {scoreTotal !== null ? (
                <span className="text-xs tabular-nums text-gray-500">
                  {scoreTotal.toFixed(0)}
                </span>
              ) : null}
            </div>

            <h3 className="mt-3 line-clamp-2 text-sm font-semibold leading-snug text-gray-950">
              {layers.title}
            </h3>

            <div className="mt-3 flex-1">
              <InsightLayerStack
                layers={layers}
                variant="compact"
                showDrivers={false}
                showCaveats={false}
              />
            </div>

            <div className="mt-3 border-t border-black/5 pt-3 text-xs text-gray-500">
              <div className="truncate">
                {insight.category}
                {insight.insight_type
                  ? ` · ${insight.insight_type}`
                  : ""}
              </div>
              <div className="mt-1 tabular-nums text-gray-700">
                {insight.metric}: {formatValue(insight.observed_value)}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
