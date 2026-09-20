"use client";

import {
  DatasetGroup,
} from "@/lib/productLineage";


function coverageColor(
  coverage: number
): string {

  if (coverage >= 80) {
    return "bg-green-600";
  }

  if (coverage >= 50) {
    return "bg-amber-500";
  }

  return "bg-red-500";

}


function qualityColor(
  score: number
): string {

  if (score >= 90) {
    return "bg-green-600";
  }

  if (score >= 75) {
    return "bg-amber-500";
  }

  return "bg-red-500";

}


interface Props {
  dataset: DatasetGroup;
  onClick: () => void;
}


export default function DatasetQualityCard({
  dataset,
  onClick,
}: Props) {

  const products =
    dataset.supportedProducts;


  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-xl border bg-white p-4 text-left transition-colors hover:border-gray-300 hover:bg-gray-50"
    >

      <div className="flex items-start justify-between gap-4">

        <div className="min-w-0">

          <p className="truncate text-sm font-semibold text-gray-950">
            {dataset.classificationType}
          </p>

          <p className="mt-1 text-xs text-gray-500">
            {dataset.rows.toLocaleString()} rows · {dataset.columns} columns
          </p>

        </div>


        <div className="shrink-0 text-right">

          <p className="text-2xl font-bold text-gray-950">
            {dataset.dataQualityScore}%
          </p>

          <p className="text-[10px] uppercase tracking-wide text-gray-400">
            Quality
          </p>

        </div>

      </div>


      <div className="mt-3">

        <div className="mb-1 flex justify-between text-[10px] text-gray-500">

          <span>Completeness</span>

          <span>{dataset.dataQualityScore}%</span>

        </div>

        <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">

          <div
            className={`h-full rounded-full ${qualityColor(dataset.dataQualityScore)}`}
            style={{
              width: `${Math.min(Math.max(dataset.dataQualityScore, 0), 100)}%`,
            }}
          />

        </div>

      </div>


      {products.length > 0 && (

        <div className="mt-4 rounded-lg bg-slate-50 p-3 ring-1 ring-slate-100">

          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Supported products
          </p>


          <div className="space-y-2.5">

            {products.map((product) => (

              <div
                key={product.definitionId}
                title={`${product.name}: ${product.coverage}% field coverage`}
              >

                <div className="mb-1 flex items-center justify-between gap-2">

                  <span className="truncate text-xs font-medium text-slate-700">
                    {product.name}
                  </span>

                  <span className="shrink-0 text-[10px] font-medium text-slate-500">
                    {product.coverage}%
                  </span>

                </div>

                <div className="h-1.5 overflow-hidden rounded-full bg-white ring-1 ring-slate-200/80">

                  <div
                    className={`h-full rounded-full ${coverageColor(product.coverage)}`}
                    style={{
                      width: `${Math.min(Math.max(product.coverage, 0), 100)}%`,
                    }}
                  />

                </div>

              </div>

            ))}

          </div>

        </div>

      )}

    </button>

  );

}
