"use client";

import {
  DataProductMetric,
} from "@/types/report";

import {
  formatMetricValue,
  getRemainingKpis,
  selectHeadlineKpis,
} from "@/lib/productKpis";


interface Props {
  metrics?: DataProductMetric[];
  productName?: string;
  limit?: number;
  showRemaining?: boolean;
  embedded?: boolean;
}


export default function ProductKPIs({
  metrics = [],
  productName,
  limit = 6,
  showRemaining = true,
  embedded = false,
}: Props) {

  const headline =
    selectHeadlineKpis(
      metrics,
      limit
    );

  const remaining =
    showRemaining
      ? getRemainingKpis(
          metrics,
          headline
        )
      : [];


  if (
    metrics.length === 0
  ) {
    return null;
  }


  return (
    <section className={`overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm ${embedded ? "" : "mt-8"}`}>

      <div className="border-b border-gray-100 bg-gray-50 px-6 py-5">

        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500">
          Key KPIs
        </p>

        <h2 className="mt-2 text-2xl font-semibold text-gray-950">
          Headline measures
        </h2>

        <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-600">
          {productName
            ? `The most important metrics for ${productName}, pulled from its supporting analyses.`
            : "The most important metrics for this data product."}
        </p>

      </div>


      <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">

        {headline.map(
          (metric, index) => (

            <article
              key={metric.id}
              className={`rounded-xl border p-4 ${
                index === 0
                  ? "border-gray-900 bg-gray-900 text-white"
                  : "border-gray-200 bg-gray-50"
              }`}
            >

              <p
                className={`text-xs font-semibold uppercase tracking-wide ${
                  index === 0
                    ? "text-gray-300"
                    : "text-gray-500"
                }`}
              >
                {metric.name}
              </p>

              <p
                className={`mt-2 text-3xl font-bold tracking-tight ${
                  index === 0
                    ? "text-white"
                    : "text-gray-950"
                }`}
              >
                {formatMetricValue(
                  metric.value
                )}
              </p>

              {(metric.unit ||
                metric.description) && (

                <p
                  className={`mt-2 text-xs leading-5 ${
                    index === 0
                      ? "text-gray-300"
                      : "text-gray-500"
                  }`}
                >
                  {metric.unit ??
                    metric.description}
                </p>

              )}

            </article>

          )
        )}

      </div>


      {remaining.length > 0 && (

        <div className="border-t border-gray-100 px-6 py-5">

          <p className="text-sm font-medium text-gray-700">
            Additional metrics
          </p>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">

            {remaining.map(
              metric => (

                <div
                  key={metric.id}
                  className="rounded-lg border border-gray-200 px-4 py-3"
                >

                  <p className="text-xs font-medium text-gray-500">
                    {metric.name}
                  </p>

                  <p className="mt-1 text-lg font-semibold text-gray-950">
                    {formatMetricValue(
                      metric.value
                    )}
                  </p>

                </div>

              )
            )}

          </div>

        </div>

      )}

    </section>

  );

}
