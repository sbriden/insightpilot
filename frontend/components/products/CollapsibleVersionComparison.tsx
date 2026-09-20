"use client";

import {
  useState,
} from "react";

import {
  ProductChangeSummary,
} from "@/types/report";

import VersionComparisonModal from "@/components/products/VersionComparisonModal";


interface Props {
  changeSummary: ProductChangeSummary;
  variant?: "dropdown";
}


export default function CollapsibleVersionComparison({
  changeSummary,
  variant,
}: Props) {

  const [
    modalOpen,
    setModalOpen,
  ] = useState(false);

  const metricCount =
    changeSummary.finding_count ?? 0;

  const dataQualityCount =
    changeSummary.data_quality_finding_count ??
    changeSummary.data_quality_findings?.length ??
    0;

  const totalFindings =
    metricCount + dataQualityCount;

  const summaryText =
    buildSummaryText(
      changeSummary,
      totalFindings
    );

  const isDropdown =
    variant === "dropdown";


  return (
    <>

      <button
        type="button"
        onClick={() =>
          setModalOpen(true)
        }
        className={
          isDropdown
            ? "group w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 text-left transition-colors hover:border-gray-300 hover:bg-gray-100"
            : "group shrink-0 rounded-lg px-3 py-2 text-right transition-colors hover:bg-white/80"
        }
      >

        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
          Version comparison
        </p>

        <p className="mt-1 text-sm font-medium text-gray-950">
          v{changeSummary.previous_version} → v{changeSummary.current_version}
        </p>

        <p className={`mt-1 text-xs leading-5 text-gray-500 group-hover:text-gray-700${isDropdown ? "" : " max-w-xs"}`}>
          {summaryText}
        </p>

        <p className="mt-1 text-xs font-medium text-gray-400 group-hover:text-gray-600">
          View details
        </p>

      </button>


      {modalOpen && (

        <VersionComparisonModal
          changeSummary={changeSummary}
          onClose={() =>
            setModalOpen(false)
          }
        />

      )}

    </>
  );

}


function buildSummaryText(
  changeSummary: ProductChangeSummary,
  totalFindings: number
): string {

  const overview =
    changeSummary.overview?.trim() ??
    "";

  if (
    overview &&
    totalFindings === 0
  ) {
    return overview;
  }

  if (totalFindings === 0) {
    return "No meaningful changes detected.";
  }

  const parts = [
    overview,
    `${totalFindings} meaningful change${totalFindings === 1 ? "" : "s"}`,
  ].filter(Boolean);

  return parts.join(" · ");

}
