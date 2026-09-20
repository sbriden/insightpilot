"use client";

import {
  PriorityCounts,
} from "@/lib/prioritySummary";


interface Props {
  counts: PriorityCounts;
  emptyLabel?: string;
}


export default function PrioritySummaryBadges({
  counts,
  emptyLabel = "No items",
}: Props) {

  if (counts.total === 0) {

    return (
      <span className="text-sm text-gray-500">
        {emptyLabel}
      </span>
    );

  }


  return (
    <div className="flex flex-wrap items-center gap-2">

      {counts.high > 0 && (

        <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-800">
          {counts.high} high
        </span>

      )}

      {counts.medium > 0 && (

        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900">
          {counts.medium} medium
        </span>

      )}

      {counts.low > 0 && (

        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
          {counts.low} low
        </span>

      )}

      <span className="text-xs text-gray-400">
        {counts.total} total
      </span>

    </div>

  );

}
