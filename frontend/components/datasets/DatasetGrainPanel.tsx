"use client";

import {
  GrainDeterminationResult,
} from "@/types/dataset";


interface Props {
  result: GrainDeterminationResult;

  embedded?: boolean;

  loading?: boolean;
}


function confidenceColor(
  confidence: number
): string {

  if (confidence >= 0.85) {
    return "text-green-700";
  }

  if (confidence >= 0.65) {
    return "text-amber-700";
  }

  return "text-gray-500";
}


export default function DatasetGrainPanel({
  result,
  embedded = false,
  loading = false,
}: Props) {

  if (loading) {
    return (
      <p className="text-sm text-gray-500">
        Determining dataset grain…
      </p>
    );
  }

  const isUnknown =
    result.grain === "unknown";

  return (
    <div className={embedded ? "" : "rounded-xl border bg-white"}>

      <div className={embedded ? "pb-4" : "border-b px-4 py-4 sm:px-6"}>

        {!embedded && (

          <h3 className="text-sm font-semibold text-gray-950">
            Dataset grain
          </h3>

        )}

        <p className={`text-xs text-gray-500 ${embedded ? "" : "mt-1"}`}>
          Inferred from identifiers, entity relationships, and
          supporting column evidence. Uncertain cases return
          unknown rather than guessing.
        </p>

        <div className="mt-4 flex flex-wrap items-baseline gap-x-4 gap-y-2">

          <div>

            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
              Inferred grain
            </p>

            <p className="mt-1 text-xl font-semibold text-gray-950">
              {result.label}
            </p>

          </div>

          <div>

            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
              Confidence
            </p>

            <p
              className={`mt-1 text-lg font-semibold ${
                isUnknown
                  ? "text-gray-400"
                  : confidenceColor(
                      result.confidence
                    )
              }`}
            >
              {isUnknown
                ? "—"
                : `${Math.round(
                    result.confidence * 100
                  )}%`}
            </p>

          </div>

        </div>

        <p className="mt-3 text-sm text-gray-600">
          {result.explanation}
        </p>

        {result.alternative_grains.length > 0 && (

          <div className="mt-3 flex flex-wrap gap-2">

            {result.alternative_grains.map(
              alternative => (

                <span
                  key={alternative.grain}
                  className="inline-flex rounded-full bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-600 ring-1 ring-inset ring-gray-200"
                >
                  {alternative.label}
                  {" · "}
                  {Math.round(
                    alternative.confidence * 100
                  )}
                  %
                </span>

              )
            )}

          </div>

        )}

      </div>


      {result.supporting_evidence.length > 0 && (

        <div className="overflow-x-auto">

          <table className="min-w-full">

            <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">

              <tr>

                <th className="px-4 py-3">
                  Signal
                </th>

                <th className="px-4 py-3">
                  Columns
                </th>

                <th className="px-4 py-3">
                  Evidence
                </th>

              </tr>

            </thead>

            <tbody>

              {result.supporting_evidence.map(
                (item, index) => (

                  <tr
                    key={`${item.signal}-${index}`}
                    className="border-t border-gray-100 align-top"
                  >

                    <td className="px-4 py-3 text-sm font-medium text-gray-950">
                      {item.signal.replace(
                        /_/g,
                        " "
                      )}
                    </td>

                    <td className="px-4 py-3 text-sm text-gray-600">
                      {item.columns.length
                        ? item.columns.join(
                            ", "
                          )
                        : "—"}
                    </td>

                    <td className="px-4 py-3 text-sm text-gray-600">
                      {item.detail}
                    </td>

                  </tr>

                )
              )}

            </tbody>

          </table>

        </div>

      )}

    </div>
  );

}
