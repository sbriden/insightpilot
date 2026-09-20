"use client";

import {
  ReactNode,
} from "react";

import {
  DataProduct,
} from "@/types/report";

import {
  InsightPriority,
  normalizePriority,
} from "@/lib/insightModel";

import {
  resolveProductExecutiveSummary,
  resolveRecommendedInsights,
} from "@/lib/productExecutiveSummary";

import { INSIGHT_LAYER_LABELS } from "@/lib/insightLayers";

import RecommendedInsightCards from "@/components/products/RecommendedInsightCards";


interface Props {
  product: Pick<
    DataProduct,
    | "name"
    | "business_purpose"
    | "description"
    | "analyses"
    | "dashboards"
    | "metrics"
    | "insights"
    | "promoted_insights"
    | "insight_initial_results"
    | "change_summary"
    | "executive_summary"
  >;
  embedded?: boolean;
}


export default function ProductExecutiveSummary({
  product,
  embedded = false,
}: Props) {

  const summary =
    resolveProductExecutiveSummary(
      product
    );

  const recommendedInsights =
    resolveRecommendedInsights(product);

  const highPriorityCount =
    recommendedInsights.length > 0
      ? recommendedInsights.filter(
          insight =>
            insight.tier === "critical" ||
            normalizePriority(insight.importance) ===
              "high"
        ).length
      : summary.what_matters.filter(
          item =>
            normalizePriority(
              item.priority
            ) === "high"
        ).length;


  return (
    <section className={`overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm ${embedded ? "" : "mt-8"}`}>

      <div className="border-b border-gray-100 bg-gray-50 px-6 py-5">

        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500">
          Executive Summary
        </p>

        <h2 className="mt-2 text-2xl font-semibold text-gray-950">
          {product.name}
        </h2>

        {highPriorityCount > 0 && (

          <p className="mt-2 text-sm font-medium text-red-700">
            {highPriorityCount} high-priority item
            {highPriorityCount === 1 ? "" : "s"} need attention
          </p>

        )}

      </div>


      <div className="space-y-8 px-6 py-6">

        <SummarySection
          title="Facts"
          description="Deterministic observations from this product's analyses."
        >

          <p className="max-w-4xl text-sm leading-7 text-gray-700">
            {summary.what_we_found}
          </p>

        </SummarySection>


        <SummarySection
          title="Interpretation"
          description="What those facts may mean — kept separate from the numbers."
        >

          {recommendedInsights.length > 0 ? (

            <RecommendedInsightCards
              insights={recommendedInsights}
            />

          ) : summary.what_matters.length === 0 ? (

            <p className="text-sm text-gray-500">
              No prioritized insights were generated for this product.
            </p>

          ) : (

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">

              {summary.what_matters.map(
                (item, index) => (

                  <article
                    key={`${item.headline}-${index}`}
                    className={`flex min-w-0 flex-col rounded-lg border p-4 ${PRIORITY_CONTAINER[normalizePriority(item.priority)]}`}
                  >

                    <div className="flex flex-wrap items-center gap-2">

                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${PRIORITY_BADGE[normalizePriority(item.priority)]}`}>
                        {normalizePriority(item.priority)}
                      </span>

                      <span className="text-xs font-medium text-gray-600">
                        {item.category}
                      </span>

                    </div>

                    <p className="mt-3 text-sm font-semibold leading-6 text-gray-950">
                      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        {INSIGHT_LAYER_LABELS.fact}
                      </span>
                      <span className="mt-1 block">
                        {item.headline}
                      </span>
                    </p>

                    {item.detail && (

                      <p className="mt-2 line-clamp-4 text-sm leading-6 text-gray-700">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                          {INSIGHT_LAYER_LABELS.interpretation}
                        </span>
                        <span className="mt-1 block">
                          {item.detail}
                        </span>
                      </p>

                    )}

                  </article>

                )
              )}

            </div>

          )}

        </SummarySection>


        <SummarySection
          title="Recommendations"
          description="Suggested next actions, separate from facts and interpretation."
        >

          <ol className="grid gap-3 sm:grid-cols-2">

            {summary.what_to_do_next.map(
              (action, index) => (

                <li
                  key={`${action}-${index}`}
                  className="flex gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm leading-6 text-gray-800"
                >

                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
                    {index + 1}
                  </span>

                  <span>
                    {action}
                  </span>

                </li>

              )
            )}

          </ol>

        </SummarySection>

      </div>

    </section>

  );

}


function SummarySection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {

  return (
    <div>

      <h3 className="text-lg font-semibold text-gray-950">
        {title}
      </h3>

      <p className="mt-1 text-sm text-gray-500">
        {description}
      </p>

      <div className="mt-4">
        {children}
      </div>

    </div>
  );

}


const PRIORITY_CONTAINER: Record<
  InsightPriority,
  string
> = {
  high: "border-red-200 bg-red-50",
  medium: "border-amber-200 bg-amber-50",
  low: "border-gray-200 bg-gray-50",
};


const PRIORITY_BADGE: Record<
  InsightPriority,
  string
> = {
  high: "bg-red-600 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-gray-300 text-gray-800",
};
