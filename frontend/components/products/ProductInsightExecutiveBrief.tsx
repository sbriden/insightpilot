"use client";

import type { ReactNode } from "react";

import {
  InsightExecutiveBrief,
  InsightExecutiveBriefItem,
} from "@/types/report";

interface Props {
  brief?: InsightExecutiveBrief | null;
  embedded?: boolean;
}

export default function ProductInsightExecutiveBrief({
  brief,
  embedded = false,
}: Props) {
  if (!brief || (brief.what_matters_most?.length ?? 0) === 0) {
    return null;
  }

  const matters = brief.what_matters_most ?? [];
  const investigate = brief.leadership_investigate ?? [];

  return (
    <section
      className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${
        embedded ? "" : "mt-8"
      }`}
    >
      <div className="border-b border-slate-100 bg-slate-50 px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Executive Brief
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">
              What deserves attention
            </h2>
          </div>
          {brief.estimated_reading_seconds ? (
            <p className="text-xs text-slate-500">
              ~{brief.estimated_reading_seconds}s read
            </p>
          ) : null}
        </div>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          A 30–60 second briefing from the top ranked Insights —
          facts first, then synthesis and investigation focus.
          {brief.source === "fallback" ? (
            <span className="ml-1 text-slate-500">
              (Deterministic synthesis — AI enrichment unavailable or unused.)
            </span>
          ) : null}
        </p>
      </div>

      <div className="grid gap-0 lg:grid-cols-3">
        <BriefColumn
          label="What matters most"
          description="Top ranked Insights"
          tone="fact"
        >
          <ol className="space-y-3">
            {matters.map((item) => (
              <MatterItem
                key={`${item.insight_id ?? item.rank}-${item.title}`}
                item={item}
              />
            ))}
          </ol>
        </BriefColumn>

        <BriefColumn
          label="Why it matters"
          description="Cross-insight synthesis"
          tone="interpretation"
        >
          <p className="text-sm leading-6 text-amber-950">
            {brief.why_it_matters || "—"}
          </p>
        </BriefColumn>

        <BriefColumn
          label="What leadership should investigate"
          description="Cross-insight recommendations"
          tone="recommendation"
        >
          {investigate.length === 0 ? (
            <p className="text-sm text-teal-900/70">—</p>
          ) : (
            <ul className="space-y-2">
              {investigate.map((item, index) => (
                <li
                  key={`${item}-${index}`}
                  className="flex gap-2 text-sm leading-6 text-teal-950"
                >
                  <span className="mt-0.5 font-semibold text-teal-700">
                    {index + 1}.
                  </span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </BriefColumn>
      </div>
    </section>
  );
}

function BriefColumn({
  label,
  description,
  tone,
  children,
}: {
  label: string;
  description: string;
  tone: "fact" | "interpretation" | "recommendation";
  children: ReactNode;
}) {
  const styles = {
    fact: "bg-slate-50/80 border-slate-100",
    interpretation: "bg-amber-50/50 border-amber-100",
    recommendation: "bg-teal-50/50 border-teal-100",
  }[tone];
  const labelColor = {
    fact: "text-slate-600",
    interpretation: "text-amber-800",
    recommendation: "text-teal-800",
  }[tone];

  return (
    <div className={`border-t border-slate-100 px-6 py-5 lg:border-l lg:border-t-0 ${styles}`}>
      <p
        className={`text-xs font-semibold uppercase tracking-wide ${labelColor}`}
      >
        {label}
      </p>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function MatterItem({ item }: { item: InsightExecutiveBriefItem }) {
  return (
    <li className="rounded-lg border border-slate-200 bg-white px-3 py-2">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-900 text-[10px] font-semibold text-white">
          {item.rank}
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-950">
            {item.title}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-700">
            <span className="font-semibold uppercase tracking-wide text-slate-500">
              Fact.{" "}
            </span>
            {item.fact}
          </p>
        </div>
      </div>
    </li>
  );
}
