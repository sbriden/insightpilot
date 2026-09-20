"use client";

import {
  DatasetGroup,
} from "@/lib/productLineage";


interface Props {
  dataset: DatasetGroup;
  onClose: () => void;
}


function qualityLabel(
  score: number
): string {

  if (score >= 90) {
    return "Strong";
  }

  if (score >= 75) {
    return "Acceptable";
  }

  return "Needs attention";

}


export default function DatasetQualityModal({
  dataset,
  onClose,
}: Props) {

  const duplicateRate =
    dataset.duplicateCount != null &&
    dataset.rows > 0
      ? (
          (dataset.duplicateCount /
            dataset.rows) *
          100
        ).toFixed(1)
      : null;


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >

      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-xl"
        onClick={(event) =>
          event.stopPropagation()
        }
        role="dialog"
        aria-modal="true"
        aria-labelledby="dataset-quality-title"
      >

        <div className="border-b px-6 py-5">

          <div className="flex items-start justify-between gap-4">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Data quality details
              </p>

              <h2
                id="dataset-quality-title"
                className="mt-1 text-xl font-semibold text-gray-950"
              >
                {dataset.classificationType}
              </h2>

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
              Overall score
            </p>

            <p className="mt-2 text-4xl font-bold text-gray-950">
              {dataset.dataQualityScore}%
            </p>

            <p className="mt-2 text-sm text-gray-600">
              {qualityLabel(dataset.dataQualityScore)} completeness based on non-missing cells across the uploaded dataset.
            </p>

          </div>


          <dl className="grid grid-cols-2 gap-4">

            <DetailItem
              label="Rows"
              value={dataset.rows.toLocaleString()}
            />

            <DetailItem
              label="Columns"
              value={String(dataset.columns)}
            />

            <DetailItem
              label="Missing cells"
              value={
                dataset.missingPercentage != null
                  ? `${dataset.missingPercentage}%`
                  : "—"
              }
            />

            <DetailItem
              label="Duplicate rate"
              value={
                duplicateRate != null
                  ? `${duplicateRate}%`
                  : "—"
              }
            />

          </dl>


          <div>

            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Score components
            </p>

            <ul className="mt-3 space-y-2 text-sm text-gray-700">

              <li>
                • Completeness contributes directly to the quality score ({dataset.dataQualityScore}% of cells populated).
              </li>

              {dataset.missingPercentage != null && (
                <li>
                  • {dataset.missingPercentage}% of all cells are missing, reducing analytical reliability.
                </li>
              )}

              {duplicateRate != null && (
                <li>
                  • Duplicate rows represent {duplicateRate}% of the dataset.
                </li>
              )}

              <li>
                • Field coverage varies by supported data product (see below).
              </li>

            </ul>

          </div>


          {dataset.supportedProducts.length > 0 && (

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Supported data products
              </p>

              <div className="mt-3 space-y-2">

                {dataset.supportedProducts.map(
                  (product) => (

                    <div
                      key={product.definitionId}
                      className="rounded-lg border px-4 py-3"
                    >

                      <div className="flex items-center justify-between gap-3">

                        <div>

                          <p className="text-sm font-medium text-gray-950">
                            {product.name}
                          </p>

                          <p className="text-xs text-gray-500">
                            v{product.version} · {product.status}
                          </p>

                        </div>

                        <p className="text-sm font-semibold">
                          {product.coverage}%
                        </p>

                      </div>


                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">

                        <div
                          className={`h-full rounded-full ${
                            product.coverage >= 80
                              ? "bg-green-600"
                              : product.coverage >= 50
                                ? "bg-amber-500"
                                : "bg-red-500"
                          }`}
                          style={{
                            width: `${Math.min(Math.max(product.coverage, 0), 100)}%`,
                          }}
                        />

                      </div>

                    </div>

                  )
                )}

              </div>

            </div>

          )}

        </div>

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

      <dd className="mt-1 text-lg font-semibold text-gray-950">
        {value}
      </dd>

    </div>

  );

}
