"use client";

import { DatasetType } from "@/types/dataset";


interface DatasetTypeSelectorProps {
  datasetTypes: DatasetType[];
  selectedType: string | null;
  onSelect: (
    datasetType: DatasetType
  ) => void;
  /** Dataset type id recommended by classification. */
  recommendedTypeId?: string | null;
  /** Confidence 0–1 keyed by dataset type id. */
  confidenceByTypeId?: Record<
    string,
    number
  >;
  /** Short classifier explanation shown above the grid. */
  recommendationExplanation?: string | null;
  recommendationLoading?: boolean;
}


function confidenceLabel(
  confidence: number
): string {

  return `${Math.round(confidence * 100)}% confidence`;

}


export default function DatasetTypeSelector({
  datasetTypes,
  selectedType,
  onSelect,
  recommendedTypeId = null,
  confidenceByTypeId = {},
  recommendationExplanation = null,
  recommendationLoading = false,
}: DatasetTypeSelectorProps) {

  const hasRecommendation =
    !!recommendedTypeId &&
    (confidenceByTypeId[recommendedTypeId] ?? 0) > 0;


  return (
    <div>

      <div className="mb-6">

        <p className="text-gray-600">
          {hasRecommendation
            ? "InsightPilot classified your dataset and pre-selected a type. Confirm or choose a different type to continue."
            : "Select the type of business data you're working with. InsightPilot will show you the data products available for your dataset."}
        </p>

        {recommendationLoading && (

          <p className="mt-3 text-sm text-gray-500">
            Classifying your dataset…
          </p>

        )}

        {!recommendationLoading &&
          hasRecommendation &&
          recommendationExplanation && (

          <p className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
            {recommendationExplanation}
          </p>

        )}

      </div>


      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">

        {datasetTypes.map(
          (datasetType) => {

            const selected =
              selectedType ===
              datasetType.id;

            const recommended =
              recommendedTypeId ===
              datasetType.id;

            const confidence =
              confidenceByTypeId[
                datasetType.id
              ];

            const showConfidence =
              typeof confidence === "number" &&
              confidence > 0;


            return (
              <button
                key={datasetType.id}
                type="button"
                onClick={() =>
                  onSelect(
                    datasetType
                  )
                }
                className={[
                  "rounded-xl border p-5 text-left",
                  "transition",
                  "hover:border-gray-400",
                  selected
                    ? "border-gray-900 bg-gray-50"
                    : recommended
                      ? "border-gray-400 bg-white"
                      : "border-gray-200 bg-white",
                ].join(" ")}
              >

                <div className="flex items-start justify-between gap-3">

                  <div className="min-w-0">

                    <h3 className="font-semibold">
                      {datasetType.name}
                    </h3>

                    <p className="mt-2 text-sm leading-6 text-gray-600">
                      {datasetType.description}
                    </p>

                  </div>


                  <div className="flex shrink-0 flex-col items-end gap-1.5">

                    {selected && (
                      <span className="rounded-full bg-gray-900 px-2 py-1 text-xs text-white">
                        Selected
                      </span>
                    )}

                    {recommended &&
                      !selected && (
                      <span className="rounded-full bg-gray-200 px-2 py-1 text-xs font-medium text-gray-800">
                        Recommended
                      </span>
                    )}

                    {recommended &&
                      selected && (
                      <span className="rounded-full bg-emerald-700 px-2 py-1 text-xs text-white">
                        Recommended
                      </span>
                    )}

                    {showConfidence && (
                      <span
                        className={[
                          "rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset",
                          recommended
                            ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                            : "bg-gray-50 text-gray-600 ring-gray-200",
                        ].join(" ")}
                      >
                        {confidenceLabel(
                          confidence
                        )}
                      </span>
                    )}

                  </div>

                </div>

              </button>
            );

          }
        )}

      </div>

    </div>
  );
}
