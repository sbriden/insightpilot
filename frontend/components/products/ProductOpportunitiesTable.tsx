"use client";

import { useState, useMemo } from "react";

import {
  RankedProductOpportunity,
  formatOpportunityValue,
} from "@/lib/productOpportunities";


interface Props {
  opportunities: RankedProductOpportunity[];
}


const PRIORITY_CELL: Record<
  RankedProductOpportunity["priority"],
  string
> = {
  high: "text-red-700 font-semibold",
  medium: "text-amber-700 font-medium",
  low: "text-gray-600",
};

const PRIORITIES: RankedProductOpportunity["priority"][] = [
  "high",
  "medium",
  "low",
];


export default function ProductOpportunitiesTable({
  opportunities,
}: Props) {

  const [priorityFilter, setPriorityFilter] =
    useState<RankedProductOpportunity["priority"] | "all">("all");

  const [typeFilter, setTypeFilter] =
    useState<string>("all");

  const types = useMemo(
    () =>
      Array.from(
        new Set(opportunities.map(o => o.type))
      ).sort(),
    [opportunities]
  );

  const rows = useMemo(
    () =>
      opportunities.filter(
        o =>
          (priorityFilter === "all" || o.priority === priorityFilter) &&
          (typeFilter === "all" || o.type === typeFilter)
      ),
    [opportunities, priorityFilter, typeFilter]
  );

  if (opportunities.length === 0) {

    return (
      <div className="px-6 py-8 text-sm text-gray-500">
        No opportunities were identified for this product version.
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
                e.target.value as RankedProductOpportunity["priority"] | "all"
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
            value={typeFilter}
            onChange={e =>
              setTypeFilter(e.target.value)
            }
            className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
          >
            <option value="all">All types</option>
            {types.map(t => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>

        </div>

        {(priorityFilter !== "all" || typeFilter !== "all") && (
          <button
            type="button"
            onClick={() => {
              setPriorityFilter("all");
              setTypeFilter("all");
            }}
            className="text-xs text-gray-500 underline underline-offset-2 hover:text-gray-700"
          >
            Clear
          </button>
        )}

        <span className="ml-auto text-xs text-gray-400">
          {rows.length} of {opportunities.length}
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
              Type
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Opportunity
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Source
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Potential
            </th>

            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              Detail
            </th>

          </tr>

        </thead>


        <tbody className="divide-y divide-gray-100 bg-white">

          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={6}
                className="px-4 py-8 text-center text-sm text-gray-500"
              >
                No opportunities match the selected filters.
              </td>
            </tr>
          ) : (
            rows.map(
              (opportunity) => {

                const potential =
                  formatOpportunityValue(
                    opportunity.potential
                  );

                return (
                  <tr
                    key={opportunity.id}
                    className="align-top hover:bg-gray-50"
                  >

                    <td className={`px-4 py-4 capitalize ${PRIORITY_CELL[opportunity.priority]}`}>
                      {opportunity.priority}
                    </td>

                    <td className="px-4 py-4 text-gray-600">
                      {opportunity.type}
                    </td>

                    <td className="px-4 py-4 font-medium text-gray-950">
                      {opportunity.label}
                    </td>

                    <td className="px-4 py-4 text-gray-600">
                      {opportunity.source}
                    </td>

                    <td className="px-4 py-4 text-gray-900">
                      {potential ?? "—"}
                    </td>

                    <td className="px-4 py-4 text-gray-700">
                      {opportunity.detail ?? "—"}
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
