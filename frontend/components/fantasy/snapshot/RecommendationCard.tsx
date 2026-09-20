"use client";

import { Sparkles } from "lucide-react";

import {
  FantasyPlayerRecommendation,
} from "@/services/api";

import { snapshotTokens } from "./tokens";

export default function RecommendationCard({
  recommendation,
}: {
  recommendation: FantasyPlayerRecommendation | null | undefined;
}) {
  if (!recommendation) {
    return (
      <section
        className="rounded-[10px] border p-4 sm:p-5"
        style={{
          borderColor: "#DDD6FE",
          background: snapshotTokens.purpleLight,
        }}
      >
        <p
          className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide"
          style={{ color: snapshotTokens.purple }}
        >
          <Sparkles className="h-3.5 w-3.5" />
          InsightPilot Recommendation
        </p>
        <p
          className="mt-2 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Not enough evidence for a recommendation yet.
        </p>
      </section>
    );
  }

  return (
    <section
      className="rounded-[10px] border p-4 sm:p-5"
      style={{
        borderColor: "#DDD6FE",
        background: snapshotTokens.purpleLight,
      }}
    >
      <p
        className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.purple }}
      >
        <Sparkles className="h-3.5 w-3.5" />
        InsightPilot Recommendation
      </p>
      <h3
        className="mt-2 text-[16px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        {recommendation.headline}
      </h3>
      <p
        className="mt-2 text-sm leading-6"
        style={{ color: snapshotTokens.textSecondary }}
      >
        {recommendation.body}
      </p>
    </section>
  );
}
