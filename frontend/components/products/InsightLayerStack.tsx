"use client";

import { ReactNode } from "react";

import {
  INSIGHT_LAYER_LABELS,
  InsightLayers,
} from "@/lib/insightLayers";

type Variant = "full" | "compact" | "inline";

interface Props {
  layers: InsightLayers;
  variant?: Variant;
  /** Optional supporting notes under Interpretation. */
  showDrivers?: boolean;
  showCaveats?: boolean;
  /** Rendered after Fact (e.g. Show Evidence). */
  afterFact?: ReactNode;
  className?: string;
}

const LAYER_STYLES: Record<
  keyof typeof INSIGHT_LAYER_LABELS,
  { wrap: string; label: string; body: string }
> = {
  fact: {
    wrap: "border-slate-200 bg-slate-50",
    label: "text-slate-600",
    body: "text-slate-900",
  },
  interpretation: {
    wrap: "border-amber-200 bg-amber-50/70",
    label: "text-amber-800",
    body: "text-amber-950",
  },
  recommendation: {
    wrap: "border-teal-200 bg-teal-50/70",
    label: "text-teal-800",
    body: "text-teal-950",
  },
};

export default function InsightLayerStack({
  layers,
  variant = "full",
  showDrivers = true,
  showCaveats = true,
  afterFact,
  className = "",
}: Props) {
  if (variant === "inline") {
    return (
      <div className={`space-y-2 text-sm ${className}`}>
        {layers.fact ? (
          <p>
            <span className="font-semibold text-slate-700">
              {INSIGHT_LAYER_LABELS.fact}.{" "}
            </span>
            <span className="text-slate-800">{layers.fact}</span>
          </p>
        ) : null}
        {afterFact}
        {layers.interpretation ? (
          <p>
            <span className="font-semibold text-amber-800">
              {INSIGHT_LAYER_LABELS.interpretation}.{" "}
            </span>
            <span className="text-amber-950">{layers.interpretation}</span>
          </p>
        ) : null}
        {layers.recommendation ? (
          <p>
            <span className="font-semibold text-teal-800">
              {INSIGHT_LAYER_LABELS.recommendation}.{" "}
            </span>
            <span className="text-teal-950">{layers.recommendation}</span>
          </p>
        ) : null}
      </div>
    );
  }

  if (variant === "compact") {
    return (
      <div className={`space-y-2 ${className}`}>
        {layers.fact ? (
          <CompactLayer
            layer="fact"
            value={layers.fact}
          />
        ) : null}
        {afterFact}
        {layers.interpretation ? (
          <CompactLayer
            layer="interpretation"
            value={layers.interpretation}
          />
        ) : null}
        {layers.recommendation ? (
          <CompactLayer
            layer="recommendation"
            value={layers.recommendation}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {layers.fact ? (
        <LayerBlock layer="fact" value={layers.fact} />
      ) : null}

      {afterFact}

      {layers.interpretation ||
      (showDrivers && layers.potentialDrivers.length > 0) ||
      (showCaveats && layers.caveats.length > 0) ? (
        <section
          className={`rounded-lg border px-3 py-2 ${LAYER_STYLES.interpretation.wrap}`}
        >
          <p
            className={`text-xs font-semibold uppercase tracking-wide ${LAYER_STYLES.interpretation.label}`}
          >
            {INSIGHT_LAYER_LABELS.interpretation}
          </p>
          {layers.interpretation ? (
            <p
              className={`mt-1 text-sm leading-6 ${LAYER_STYLES.interpretation.body}`}
            >
              {layers.interpretation}
            </p>
          ) : null}
          {showDrivers && layers.potentialDrivers.length > 0 ? (
            <div className="mt-2">
              <p className="text-xs font-medium text-amber-800">
                Potential drivers include
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-amber-950">
                {layers.potentialDrivers.map((driver, index) => (
                  <li key={`${driver}-${index}`}>{driver}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {showCaveats && layers.caveats.length > 0 ? (
            <div className="mt-2">
              <p className="text-xs font-medium text-amber-800">
                Caveats
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-amber-950">
                {layers.caveats.map((caveat, index) => (
                  <li key={`${caveat}-${index}`}>{caveat}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      {layers.recommendation ? (
        <LayerBlock
          layer="recommendation"
          value={layers.recommendation}
        />
      ) : null}
    </div>
  );
}

function LayerBlock({
  layer,
  value,
}: {
  layer: keyof typeof INSIGHT_LAYER_LABELS;
  value: string;
}) {
  const styles = LAYER_STYLES[layer];
  return (
    <section className={`rounded-lg border px-3 py-2 ${styles.wrap}`}>
      <p
        className={`text-xs font-semibold uppercase tracking-wide ${styles.label}`}
      >
        {INSIGHT_LAYER_LABELS[layer]}
      </p>
      <p className={`mt-1 text-sm leading-6 ${styles.body}`}>{value}</p>
    </section>
  );
}

function CompactLayer({
  layer,
  value,
}: {
  layer: keyof typeof INSIGHT_LAYER_LABELS;
  value: string;
}) {
  const styles = LAYER_STYLES[layer];
  return (
    <div>
      <p
        className={`text-[10px] font-semibold uppercase tracking-wide ${styles.label}`}
      >
        {INSIGHT_LAYER_LABELS[layer]}
      </p>
      <p className={`mt-0.5 line-clamp-3 text-xs leading-relaxed ${styles.body}`}>
        {value}
      </p>
    </div>
  );
}
