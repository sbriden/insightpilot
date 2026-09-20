"use client";

import {
  NflverseDataQualityResult,
} from "@/types/dataset";


function statusTone(
  status: string,
  passed: boolean
): {
  badge: string;
  bar: string;
  label: string;
} {

  if (
    status === "failed"
    || status === "failed_validation"
  ) {
    return {
      badge: "bg-red-100 text-red-800",
      bar: "bg-red-500",
      label: "Failed",
    };
  }

  if (
    status === "passed_with_warnings"
    || status === "succeeded_with_warnings"
  ) {
    return {
      badge: "bg-amber-100 text-amber-900",
      bar: "bg-amber-500",
      label: "Warnings",
    };
  }

  if (
    status === "passed"
    || status === "succeeded"
    || passed
  ) {
    return {
      badge: "bg-green-100 text-green-800",
      bar: "bg-green-600",
      label: "Passed",
    };
  }

  return {
    badge: "bg-gray-100 text-gray-700",
    bar: "bg-gray-400",
    label: "Not run",
  };

}


function passRate(
  result: NflverseDataQualityResult
): number {

  const checks =
    result.validation?.checks ?? [];

  if (checks.length === 0) {
    if (result.status === "not_run") {
      return 0;
    }
    return result.passed ? 100 : 0;
  }

  const passedCount =
    checks.filter(
      (check) => check.passed
    ).length;

  return Math.round(
    (passedCount / checks.length) * 100
  );

}


interface Props {
  result: NflverseDataQualityResult;
  onClick: () => void;
}


export default function FantasyDataQualityCard({
  result,
  onClick,
}: Props) {

  const tone = statusTone(
    result.status,
    result.passed
  );
  const rate = passRate(result);
  const errors =
    result.validation?.error_count ?? 0;
  const warnings =
    result.validation?.warning_count ?? 0;
  const checkCount =
    result.validation?.checks?.length ?? 0;


  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-xl border bg-white p-4 text-left transition-colors hover:border-gray-300 hover:bg-gray-50"
    >

      <div className="flex items-start justify-between gap-4">

        <div className="min-w-0">

          <p className="truncate text-sm font-semibold text-gray-950">
            {result.label}
          </p>

          <p className="mt-1 text-xs text-gray-500">
            Canonical ingestion checks
            {result.seasons.length > 0
              ? ` · ${result.seasons[0]}–${result.seasons[result.seasons.length - 1]}`
              : ""}
          </p>

        </div>


        <div className="shrink-0 text-right">

          <span
            className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${tone.badge}`}
          >
            {tone.label}
          </span>

          <p className="mt-1 text-2xl font-bold text-gray-950">
            {checkCount > 0 ? `${rate}%` : "—"}
          </p>

          <p className="text-[10px] uppercase tracking-wide text-gray-400">
            Checks passed
          </p>

        </div>

      </div>


      <p className="mt-3 line-clamp-2 text-sm text-gray-600">
        {result.message}
      </p>


      <div className="mt-3">

        <div className="mb-1 flex justify-between text-[10px] text-gray-500">

          <span>Validation coverage</span>

          <span>
            {checkCount > 0
              ? `${rate}%`
              : "No checks yet"}
          </span>

        </div>

        <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">

          <div
            className={`h-full rounded-full ${tone.bar}`}
            style={{
              width: `${Math.min(Math.max(rate, 0), 100)}%`,
            }}
          />

        </div>

      </div>


      <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-gray-600">

        <span className="rounded-md bg-slate-50 px-2 py-1 ring-1 ring-slate-100">
          {errors} error{errors === 1 ? "" : "s"}
        </span>

        <span className="rounded-md bg-slate-50 px-2 py-1 ring-1 ring-slate-100">
          {warnings} warning{warnings === 1 ? "" : "s"}
        </span>

        <span className="rounded-md bg-slate-50 px-2 py-1 ring-1 ring-slate-100">
          {checkCount} check{checkCount === 1 ? "" : "s"}
        </span>

      </div>

    </button>
  );

}
