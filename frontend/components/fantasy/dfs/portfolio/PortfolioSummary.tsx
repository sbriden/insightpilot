"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioSummary } from "@/services/api";

interface Props {
  portfolio: DfsPortfolioSummary | null;
}

export default function PortfolioSummary({ portfolio }: Props) {
  if (!portfolio) {
    return null;
  }

  const metrics = [
    { label: "Portfolio Size", value: String(portfolio.lineup_count) },
    {
      label: "Avg Projection",
      value: portfolio.average_projection.toFixed(1),
    },
    {
      label: "Avg Ceiling",
      value: portfolio.average_ceiling.toFixed(1),
    },
    {
      label: "Best Projection",
      value: (portfolio.best_projection ?? portfolio.average_projection).toFixed(1),
    },
    {
      label: "Lowest Projection",
      value: (portfolio.lowest_projection ?? portfolio.average_projection).toFixed(1),
    },
    {
      label: "Avg Salary Used",
      value: `$${Math.round(portfolio.average_salary).toLocaleString()}`,
    },
    {
      label: "Avg Remaining",
      value: `$${Math.round(
        portfolio.average_salary_remaining ?? 0
      ).toLocaleString()}`,
    },
    {
      label: "Unique Lineups",
      value: String(
        portfolio.unique_lineups ?? portfolio.lineup_count
      ),
    },
  ];

  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Portfolio Summary
      </h3>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <p
              className="text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              {metric.label}
            </p>
            <p
              className="mt-1 text-lg font-semibold tabular-nums"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {metric.value}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
