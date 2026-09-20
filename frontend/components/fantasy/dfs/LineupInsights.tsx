"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsLineupInsight, DfsSignal } from "@/services/api";

interface Props {
  insights: DfsLineupInsight[];
  signals: DfsSignal[];
  waiting?: boolean;
}

export default function LineupInsights({
  insights,
  signals,
  waiting = false,
}: Props) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Lineup Insights
      </h3>
      <ul className="mt-3 space-y-2">
        {waiting || insights.length === 0 ? (
          <li
            className="text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {waiting
              ? "Click Analyze to generate InsightPilot edge and lineup insights."
              : "No insights available yet."}
          </li>
        ) : (
          insights.map((insight) => (
            <li
              key={insight.id}
              className="flex gap-2 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              <span
                style={{
                  color:
                    insight.tone === "warning"
                      ? snapshotTokens.warning
                      : snapshotTokens.success,
                }}
              >
                {insight.tone === "warning" ? "!" : "✓"}
              </span>
              <span>{insight.text}</span>
            </li>
          ))
        )}
      </ul>

      {!waiting && signals.length > 0 && (
        <div className="mt-4 space-y-2">
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            InsightPilot Signals
          </p>
          {signals.map((signal) => (
            <div
              key={signal.id}
              className="rounded-lg border px-3 py-2"
              style={{
                borderColor: snapshotTokens.divider,
                background: snapshotTokens.background,
              }}
            >
              <p
                className="text-sm font-semibold"
                style={{ color: snapshotTokens.navy }}
              >
                {signal.label}
              </p>
              {signal.body && (
                <p
                  className="mt-0.5 text-xs"
                  style={{
                    color: snapshotTokens.textSecondary,
                  }}
                >
                  {signal.body}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
