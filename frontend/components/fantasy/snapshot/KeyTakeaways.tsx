"use client";

import {
  ArrowUpRight,
  Sparkles,
  TrendingUp,
  Activity,
  ShieldAlert,
  Lightbulb,
} from "lucide-react";

import {
  FantasyPlayerTakeaway,
} from "@/services/api";

import { snapshotTokens } from "./tokens";

function iconForType(type: string) {
  switch (type) {
    case "trend":
      return TrendingUp;
    case "performance":
      return Activity;
    case "availability":
      return ShieldAlert;
    case "recommendation":
      return ArrowUpRight;
    case "usage":
      return Activity;
    default:
      return Lightbulb;
  }
}

export function InsightCard({
  takeaway,
}: {
  takeaway: FantasyPlayerTakeaway;
}) {
  const Icon = iconForType(takeaway.type);
  const isAi = takeaway.source === "insightpilot";

  return (
    <div
      className="rounded-[10px] border bg-white p-3.5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex items-start gap-3">
        <div
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
          style={{
            background: isAi
              ? snapshotTokens.purpleLight
              : snapshotTokens.blueLight,
            color: isAi
              ? snapshotTokens.purple
              : snapshotTokens.blue,
          }}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          {isAi && (
            <p
              className="mb-1 flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide"
              style={{ color: snapshotTokens.purple }}
            >
              <Sparkles className="h-3 w-3" />
              InsightPilot Analysis
            </p>
          )}
          <p
            className="text-[15px] font-semibold leading-snug"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {takeaway.headline}
          </p>
          <p
            className="mt-1 text-[13px] leading-5"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {takeaway.body}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function KeyTakeaways({
  takeaways,
}: {
  takeaways: FantasyPlayerTakeaway[];
}) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Key Takeaways
      </h3>
      <div className="mt-3 space-y-2.5">
        {takeaways.length === 0 ? (
          <p
            className="text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            InsightPilot doesn&apos;t have enough profile
            evidence for takeaways yet.
          </p>
        ) : (
          takeaways.map((takeaway, index) => (
            <InsightCard
              key={`${takeaway.headline}-${index}`}
              takeaway={takeaway}
            />
          ))
        )}
      </div>
    </section>
  );
}
