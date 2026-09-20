"use client";

import {
  BusinessConcept,
  ConceptIdentificationResult,
  ConceptRole,
} from "@/types/dataset";


const ROLE_LABELS: Record<
  ConceptRole,
  string
> = {
  entity: "Entity",
  measure: "Measure",
  date: "Date",
  category: "Category",
  identifier: "Identifier",
  status: "Status",
  geography: "Geography",
};


const ROLE_STYLES: Record<
  ConceptRole,
  string
> = {
  entity:
    "bg-blue-50 text-blue-700 ring-blue-200",
  measure:
    "bg-emerald-50 text-emerald-700 ring-emerald-200",
  date:
    "bg-violet-50 text-violet-700 ring-violet-200",
  category:
    "bg-amber-50 text-amber-700 ring-amber-200",
  identifier:
    "bg-slate-50 text-slate-700 ring-slate-200",
  status:
    "bg-orange-50 text-orange-700 ring-orange-200",
  geography:
    "bg-cyan-50 text-cyan-700 ring-cyan-200",
};


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


function ConceptRow({
  concept,
}: {
  concept: BusinessConcept;
}) {

  const roleStyle =
    ROLE_STYLES[concept.role] ??
    ROLE_STYLES.category;

  const roleLabel =
    ROLE_LABELS[concept.role] ??
    concept.role;


  return (
    <tr className="border-t border-gray-100">

      <td className="px-4 py-3 text-sm font-medium text-gray-950">
        {concept.sourceColumn}
      </td>

      <td className="px-4 py-3 text-sm text-gray-700">
        {concept.concept}
      </td>

      <td className="px-4 py-3">

        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${roleStyle}`}
        >
          {roleLabel}
        </span>

      </td>

      <td className="px-4 py-3 text-sm text-gray-600">
        {concept.dataType}
      </td>

      <td
        className={`px-4 py-3 text-right text-sm font-medium ${confidenceColor(
          concept.confidence
        )}`}
      >
        {Math.round(
          concept.confidence * 100
        )}
        %
      </td>

    </tr>
  );

}


interface Props {
  result: ConceptIdentificationResult;

  embedded?: boolean;
}


export default function IdentifiedConceptsPanel({
  result,
  embedded = false,
}: Props) {

  if (
    !result.concepts.length
  ) {
    return null;
  }


  return (
    <div className={embedded ? "" : "rounded-xl border bg-white"}>

      <div className={embedded ? "pb-4" : "border-b px-4 py-4 sm:px-6"}>

        {!embedded && (

          <h3 className="text-sm font-semibold text-gray-950">
            Identified business concepts
          </h3>

        )}

        <p className={`text-xs text-gray-500 ${embedded ? "" : "mt-1"}`}>
          Semantic interpretation of your dataset columns. When you map a
          column to a semantic field, its business concept updates to
          reflect that mapping.
        </p>

        <p className="mt-2 text-xs text-gray-600">
          {result.identifiedCount} of{" "}
          {result.columnCount} columns recognized
        </p>

      </div>


      <div className="overflow-x-auto">

        <table className="min-w-full">

          <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">

            <tr>

              <th className="px-4 py-3">
                Source column
              </th>

              <th className="px-4 py-3">
                Concept
              </th>

              <th className="px-4 py-3">
                Role
              </th>

              <th className="px-4 py-3">
                Data type
              </th>

              <th className="px-4 py-3 text-right">
                Confidence
              </th>

            </tr>

          </thead>

          <tbody>

            {result.concepts.map(
              concept => (

                <ConceptRow
                  key={
                    concept.sourceColumn
                  }
                  concept={
                    concept
                  }
                />

              )
            )}

          </tbody>

        </table>

      </div>

    </div>
  );

}
