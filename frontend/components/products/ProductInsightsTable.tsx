"use client";

import { useState, useMemo } from "react";

import {
  DataProductInsight,
} from "@/types/report";

import {
  InsightPriority,
  normalizeInsights,
  normalizePriority,
} from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";


interface Props {
  insights?: DataProductInsight[];
}


const PRIORITY_CELL: Record<
  InsightPriority,
  string
> = {
  high: "text-red-700 font-semibold",
  medium: "text-amber-700 font-medium",
  low: "text-gray-600",
};

const PRIORITIES: InsightPriority[] = ["high", "medium", "low"];


export default function ProductInsightsTable({
  insights = [],
}: Props) {

  const [priorityFilter, setPriorityFilter] =
    useState<InsightPriority | "all">("all");

  const [categoryFilter, setCategoryFilter] =
    useState<string>("all");

  const normalized =
    normalizeInsights(insights);

  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          normalized.map(
            r => r.category ?? "Analysis"
          )
        )
      ).sort(),
    [normalized]
  );

  const rows = useMemo(
    () =>
      normalized.filter(
        r =>
          (priorityFilter === "all" ||
            normalizePriority(r.priority) === priorityFilter) &&
          (categoryFilter === "all" ||
            (r.category ?? "Analysis") === categoryFilter)
      ),
    [normalized, priorityFilter, categoryFilter]
  );


  if (normalized.length === 0) {

    return (
      <div className="px-6 py-8 text-sm text-gray-500">
        No insights were generated for this product version.
      </div>
    );

  }


  return (
    <div>

      <div className="flex flex-wrap items-center gap-3 border-b px-4 py-3 bg-gray-50">

        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Filter
        </span>

        <div className="flex flex-wrap gap-2">

          <select
            value={priorityFilter}
            onChange={e =>
              setPriorityFilter(
                e.target.value as InsightPriority | "all"
              )
            }
            className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
          >
            <option value="all">All priorities</option>
            {PRIORITIES.map(p => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>

          <select
            value={categoryFilter}
            onChange={e =>
              setCategoryFilter(e.target.value)
            }
            className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
          >
            <option value="all">All categories</option>
            {categories.map(c => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

        </div>

        {(priorityFilter !== "all" || categoryFilter !== "all") && (
          <button
            type="button"
            onClick={() => {
              setPriorityFilter("all");
              setCategoryFilter("all");
            }}
            className="text-xs text-gray-500 underline underline-offset-2 hover:text-gray-700"
          >
            Clear
          </button>
        )}

        <span className="ml-auto text-xs text-gray-400">
          {rows.length} of {normalized.length}
        </span>

      </div>

    <div className="overflow-x-auto">

      <table className="min-w-full divide-y divide-gray-200 text-sm">

        <thead className="bg-gray-50">

          <tr>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Priority
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Category
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Fact
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Interpretation
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Recommendation
            </th>

          </tr>

        </thead>


        <tbody className="divide-y divide-gray-100 bg-white">

          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={5}
                className="px-4 py-8 text-center text-sm text-gray-500"
              >
                No insights match the selected filters.
              </td>
            </tr>
          ) : (
            rows.map(
              (insight, index) => {

                const priority =
                  normalizePriority(
                    insight.priority
                  );
                const layers = resolveInsightLayers(insight);

                return (
                  <tr
                    key={`${insight.id}-${index}`}
                    className="align-top hover:bg-gray-50"
                  >

                    <td className={`px-4 py-4 capitalize ${PRIORITY_CELL[priority]}`}>
                      {priority}
                    </td>

                    <td className="px-4 py-4 text-gray-600">
                      {insight.category ??
                        "Analysis"}
                    </td>

                    <td className="px-4 py-4 font-medium text-gray-950">
                      {layers.fact || "—"}
                    </td>

                    <td className="px-4 py-4 text-gray-700">
                      {layers.interpretation || "—"}
                    </td>

                    <td className="px-4 py-4 text-gray-900">
                      {layers.recommendation || "—"}
                    </td>

                  </tr>
                );

              }
            )
          )}

        </tbody>

      </table>

    </div>

    </div>

  );

}
