"use client";

import {
  NflverseDataQualityResult,
  NflverseValidationCheck,
} from "@/types/dataset";


interface Props {
  result: NflverseDataQualityResult;
  onClose: () => void;
}


function checkTone(
  check: NflverseValidationCheck
): string {

  if (check.passed) {
    return "border-green-200 bg-green-50";
  }

  if (check.severity === "warning") {
    return "border-amber-200 bg-amber-50";
  }

  return "border-red-200 bg-red-50";

}


export default function FantasyDataQualityModal({
  result,
  onClose,
}: Props) {

  const checks =
    result.validation?.checks ?? [];
  const failed = checks.filter(
    (check) => !check.passed
  );
  const passed = checks.filter(
    (check) => check.passed
  );


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >

      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-xl"
        onClick={(event) =>
          event.stopPropagation()
        }
        role="dialog"
        aria-modal="true"
        aria-labelledby="fantasy-quality-title"
      >

        <div className="border-b px-6 py-5">

          <div className="flex items-start justify-between gap-4">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Data quality details
              </p>

              <h2
                id="fantasy-quality-title"
                className="mt-1 text-xl font-semibold text-gray-950"
              >
                {result.label}
              </h2>

              <p className="mt-1 text-sm text-gray-500">
                {result.description}
              </p>

            </div>


            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Close
            </button>

          </div>

        </div>


        <div className="space-y-6 px-6 py-5">

          <div className="rounded-xl border bg-gray-50 p-4">

            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Validation result
            </p>

            <p className="mt-2 text-lg font-semibold text-gray-950">
              {result.message}
            </p>

            <p className="mt-2 text-xs text-gray-500">
              Source: {result.report_source}
              {result.seasons.length > 0
                ? ` · seasons ${result.seasons[0]}–${result.seasons[result.seasons.length - 1]}`
                : ""}
            </p>

          </div>


          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">

            <DetailItem
              label="Status"
              value={result.status}
            />

            <DetailItem
              label="Errors"
              value={String(
                result.validation?.error_count ?? 0
              )}
            />

            <DetailItem
              label="Warnings"
              value={String(
                result.validation?.warning_count ?? 0
              )}
            />

            <DetailItem
              label="Checks"
              value={String(checks.length)}
            />

          </dl>


          {failed.length > 0 && (

            <CheckSection
              title="Failed checks"
              checks={failed}
            />

          )}


          {passed.length > 0 && (

            <CheckSection
              title="Passed checks"
              checks={passed}
            />

          )}


          {checks.length === 0 && (

            <p className="text-sm text-gray-500">
              No individual checks available yet.
              Run a fantasy football historical or
              incremental load to generate a report.
            </p>

          )}

        </div>

      </div>

    </div>
  );

}


function CheckSection({
  title,
  checks,
}: {
  title: string;
  checks: NflverseValidationCheck[];
}) {

  return (
    <div>

      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
        {title}
      </p>

      <div className="mt-3 space-y-2">

        {checks.map((check) => (

          <div
            key={check.check_id}
            className={`rounded-lg border px-4 py-3 ${checkTone(check)}`}
          >

            <div className="flex items-start justify-between gap-3">

              <div className="min-w-0">

                <p className="text-sm font-medium text-gray-950">
                  {check.label}
                </p>

                <p className="mt-1 text-xs text-gray-600">
                  {check.message}
                </p>

              </div>

              <div className="shrink-0 text-right text-[10px] uppercase tracking-wide text-gray-500">

                <p>{check.severity}</p>

                {check.count != null && check.count > 0 && (
                  <p className="mt-1">{check.count}</p>
                )}

              </div>

            </div>

          </div>

        ))}

      </div>

    </div>
  );

}


function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {

  return (
    <div className="rounded-lg border px-4 py-3">

      <dt className="text-xs font-semibold uppercase tracking-wide text-gray-400">
        {label}
      </dt>

      <dd className="mt-1 text-lg font-semibold capitalize text-gray-950">
        {value}
      </dd>

    </div>
  );

}
