"use client";

import {
  DataProductInsight,
} from "@/types/report";

import {
  InsightPriority,
  normalizeInsights,
  normalizePriority,
} from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";
import InsightLayerStack from "@/components/products/InsightLayerStack";


interface Props {
  insights?: DataProductInsight[];
  title?: string;
  description?: string;
  compact?: boolean;
  embedded?: boolean;
}


export default function ProductInsightsPanel({
  insights = [],
  title = "Insights",
  description = "Each insight separates Fact, Interpretation, and Recommendation.",
  compact = false,
  embedded = false,
}: Props) {

  const normalized =
    normalizeInsights(insights);

  const highPriority =
    normalized.filter(
      insight =>
        normalizePriority(
          insight.priority
        ) === "high"
    );


  if (
    normalized.length === 0
  ) {

    return (
      <section
        className={
          embedded
            ? "rounded-xl border bg-white p-5"
            : compact
              ? "rounded-xl border bg-white p-5"
              : "mt-12 rounded-xl border bg-white p-6"
        }
      >

        <h2 className="text-2xl font-semibold">
          {title}
        </h2>

        <p className="mt-2 text-sm text-gray-500">
          No insights were generated for this product.
        </p>

      </section>
    );

  }


  return (
    <section
      className={
        embedded
          ? "space-y-6"
          : compact
            ? "space-y-6"
            : "mt-12 space-y-6"
      }
    >

      <div>

        <h2 className="text-2xl font-semibold">
          {title}
        </h2>

        <p className="mt-2 text-gray-600">
          {description}
        </p>

        {highPriority.length > 0 && (

          <p className="mt-3 text-sm font-medium text-red-700">
            {highPriority.length} high-priority insight
            {highPriority.length === 1 ? "" : "s"} require attention
          </p>

        )}

      </div>


      <div className="space-y-4">

        {normalized.map(
          (insight, index) => (

            <InsightCard
              key={`${insight.id}-${index}`}
              insight={insight}
            />

          )
        )}

      </div>

    </section>
  );

}


function InsightCard({
  insight,
}: {
  insight: DataProductInsight;
}) {

  const priority =
    normalizePriority(
      insight.priority
    );

  const layers = resolveInsightLayers(insight);
  const styles =
    PRIORITY_STYLES[priority];


  return (
    <article
      className={`rounded-xl border p-5 ${styles.container}`}
    >

      <div className="flex flex-wrap items-start justify-between gap-3">

        <div className="space-y-2">

          <div className="flex flex-wrap items-center gap-2">

            <span
              className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${styles.badge}`}
            >
              {priority} priority
            </span>

            {insight.category && (

              <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-600">
                {insight.category}
              </span>

            )}

          </div>

          <h3 className={`text-lg font-semibold ${styles.title}`}>
            {layers.title}
          </h3>

        </div>

      </div>

      <div className="mt-4">
        <InsightLayerStack
          layers={layers}
          variant="full"
          showDrivers={false}
          showCaveats={false}
        />
      </div>

    </article>
  );

}


const PRIORITY_STYLES: Record<
  InsightPriority,
  {
    container: string;
    badge: string;
    title: string;
  }
> = {

  high: {
    container:
      "border-red-300 bg-red-50 shadow-sm ring-1 ring-red-100",

    badge:
      "bg-red-600 text-white",

    title:
      "text-red-950",
  },

  medium: {
    container:
      "border-amber-200 bg-amber-50",

    badge:
      "bg-amber-500 text-white",

    title:
      "text-amber-950",
  },

  low: {
    container:
      "border-gray-200 bg-white",

    badge:
      "bg-gray-200 text-gray-700",

    title:
      "text-gray-900",
  },

};
