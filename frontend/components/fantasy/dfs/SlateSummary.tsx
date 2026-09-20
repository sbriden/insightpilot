"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsLineup } from "@/services/api";

interface Props {
  lineup: DfsLineup | null;
  showEdge?: boolean;
}

export default function SlateSummary({
  lineup,
  showEdge = false,
}: Props) {
  const salaryCap = lineup?.salary_cap ?? 50000;
  const salaryUsed = lineup?.salary_used ?? 0;
  const utilization =
    salaryCap > 0 ? Math.min(1, salaryUsed / salaryCap) : 0;

  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Metric
          label="Projected Points"
          value={
            lineup?.projected_points != null
              ? lineup.projected_points.toFixed(1)
              : "—"
          }
        />
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Salary Used
          </p>
          <p
            className="mt-1 text-lg font-semibold tabular-nums"
            style={{ color: snapshotTokens.navy }}
          >
            ${salaryUsed.toLocaleString()}
            <span
              className="text-sm font-medium"
              style={{ color: snapshotTokens.textMuted }}
            >
              {" "}
              / ${salaryCap.toLocaleString()}
            </span>
          </p>
          <div
            className="mt-2 h-1.5 overflow-hidden rounded-full"
            style={{ background: snapshotTokens.divider }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${utilization * 100}%`,
                background: snapshotTokens.blue,
              }}
            />
          </div>
        </div>
        <Metric
          label="Players Selected"
          value={
            lineup
              ? `${lineup.roster_filled} / ${lineup.roster_size}`
              : "— / —"
          }
        />
        <Metric
          label="Projected Ownership"
          value={
            lineup?.projected_ownership != null
              ? `${lineup.projected_ownership.toFixed(0)}%`
              : "—"
          }
          hint="Sum of projected field shares"
        />
        <div className="sm:col-span-2 lg:col-span-1">
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            InsightPilot Edge
          </p>
          <p
            className="mt-1 text-sm leading-snug"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {showEdge && lineup?.edge_summary
              ? lineup.edge_summary
              : "Click Analyze to see InsightPilot edge analysis for this lineup."}
          </p>
        </div>
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div>
      <p
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </p>
      <p
        className="mt-1 text-lg font-semibold tabular-nums"
        style={{ color: snapshotTokens.navy }}
      >
        {value}
      </p>
      {hint && (
        <p
          className="mt-0.5 text-[11px]"
          style={{ color: snapshotTokens.textMuted }}
        >
          {hint}
        </p>
      )}
    </div>
  );
}
