"use client";

import {
  CapabilityDetectionResult,
} from "@/types/dataset";


interface Props {
  result: CapabilityDetectionResult;

  embedded?: boolean;
}


function CapabilityRow({
  capability,
}: {
  capability: CapabilityDetectionResult["capabilities"][number];
}) {

  const statusStyle = capability.supported
    ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
    : "bg-gray-50 text-gray-500 ring-gray-200";

  const statusLabel = capability.supported
    ? "Supported"
    : "Not supported";


  return (
    <tr className="border-t border-gray-100 align-top">

      <td className="px-4 py-3 text-sm font-medium text-gray-950">
        {capability.label}
      </td>

      <td className="px-4 py-3">

        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${statusStyle}`}
        >
          {statusLabel}
        </span>

      </td>

      <td className="px-4 py-3 text-sm text-gray-600">
        {capability.required_concepts.join(
          ", "
        )}
      </td>

      <td
        className={`px-4 py-3 text-right text-sm font-medium ${
          capability.supported
            ? "text-green-700"
            : "text-gray-400"
        }`}
      >
        {capability.supported
          ? `${Math.round(
              capability.confidence * 100
            )}%`
          : "—"}
      </td>

      <td className="px-4 py-3 text-sm text-gray-600">
        {capability.explanation}
      </td>

    </tr>
  );

}


export default function AnalyticalCapabilitiesPanel({
  result,
  embedded = false,
}: Props) {

  if (!result.capabilities.length) {
    return null;
  }


  const supported = result.capabilities.filter(
    item => item.supported
  );


  return (
    <div className={embedded ? "" : "rounded-xl border bg-white"}>

      <div className={embedded ? "pb-4" : "border-b px-4 py-4 sm:px-6"}>

        {!embedded && (

          <h3 className="text-sm font-semibold text-gray-950">
            Analytical capabilities
          </h3>

        )}

        <p className={`text-xs text-gray-500 ${embedded ? "" : "mt-1"}`}>
          Capabilities inferred from identified business concepts.
          The analysis engine uses these to select appropriate
          analyses dynamically.
        </p>

        <p className="mt-2 text-xs text-gray-600">
          {result.supported_count} of{" "}
          {result.total_count} capabilities supported
        </p>

        {supported.length > 0 && (

          <div className="mt-3 flex flex-wrap gap-2">

            {supported.map(item => (

              <span
                key={item.capability}
                className="inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200"
              >
                {item.label}
              </span>

            ))}

          </div>

        )}

      </div>


      <div className="overflow-x-auto">

        <table className="min-w-full">

          <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">

            <tr>

              <th className="px-4 py-3">
                Capability
              </th>

              <th className="px-4 py-3">
                Status
              </th>

              <th className="px-4 py-3">
                Required concepts
              </th>

              <th className="px-4 py-3 text-right">
                Confidence
              </th>

              <th className="px-4 py-3">
                Explanation
              </th>

            </tr>

          </thead>

          <tbody>

            {result.capabilities.map(
              capability => (

                <CapabilityRow
                  key={
                    capability.capability
                  }
                  capability={
                    capability
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
