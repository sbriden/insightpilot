"use client";

import {
  SemanticUnderstanding,
} from "@/types/report";

interface SemanticUnderstandingDebugProps {
  understanding?: SemanticUnderstanding | null;
}

/**
 * Unpolished developer inspection surface for what the semantic
 * engine believes about the uploaded dataset. Not product UI.
 */
export default function SemanticUnderstandingDebug({
  understanding,
}: SemanticUnderstandingDebugProps) {
  if (!understanding) {
    return null;
  }

  const archetype = understanding.archetype_classification;
  const grain = understanding.inferred_grain;
  const supportedCapabilities =
    understanding.detected_capabilities.filter(
      (item) => item.supported,
    );

  return (
    <details className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-700">
      <summary className="cursor-pointer font-medium text-gray-900">
        Semantic understanding (developer)
      </summary>

      <div className="mt-4 space-y-3">
        <p>
          Archetype:{" "}
          <code>
            {archetype?.primary ?? "unknown"}
          </code>{" "}
          (
          {(archetype?.confidence ?? 0).toFixed(2)}
          )
        </p>

        <p>
          Grain:{" "}
          <code>
            {grain?.grain ?? "unknown"}
          </code>{" "}
          (
          {(grain?.confidence ?? 0).toFixed(2)}
          )
        </p>

        <p>
          Concepts:{" "}
          {understanding.detected_concepts.length}
          {" · "}
          Measures:{" "}
          {understanding.detected_measures.length}
          {" · "}
          Dimensions:{" "}
          {understanding.detected_dimensions.length}
          {" · "}
          Dates:{" "}
          {understanding.detected_dates.length}
          {" · "}
          Entities:{" "}
          {understanding.detected_entities.length}
        </p>

        <p>
          Supported capabilities:{" "}
          {supportedCapabilities.length > 0
            ? supportedCapabilities
                .map((item) => item.capability)
                .join(", ")
            : "(none)"}
        </p>

        <pre className="max-h-96 overflow-auto rounded-lg bg-white p-3 text-xs text-gray-800">
          {JSON.stringify(understanding, null, 2)}
        </pre>
      </div>
    </details>
  );
}
