"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";

const STEPS = [
  "Loading player projections",
  "Evaluating matchups",
  "Calculating correlations",
  "Optimizing lineup",
  "Generating insights",
] as const;

interface Props {
  active: boolean;
  stepIndex: number;
}

export default function OptimizationProgress({
  active,
  stepIndex,
}: Props) {
  if (!active) {
    return null;
  }

  return (
    <div
      className="rounded-[10px] border px-4 py-3"
      style={{
        borderColor: snapshotTokens.blue,
        background: snapshotTokens.blueLight,
      }}
    >
      <p
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Analyzing Slate
      </p>
      <ul className="mt-2 space-y-1">
        {STEPS.map((step, index) => {
          const done = index < stepIndex;
          const current = index === stepIndex;
          return (
            <li
              key={step}
              className="flex items-center gap-2 text-xs"
              style={{
                color: current
                  ? snapshotTokens.blue
                  : done
                    ? snapshotTokens.success
                    : snapshotTokens.textMuted,
              }}
            >
              <span className="w-3">
                {done ? "✓" : current ? "●" : "○"}
              </span>
              {step}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
