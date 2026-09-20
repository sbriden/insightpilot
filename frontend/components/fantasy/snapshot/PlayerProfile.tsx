"use client";

import { FantasyPlayerSnapshot } from "@/services/api";

import { snapshotTokens } from "./tokens";

function formatInjuryDisplay(
  injuryType: string | null | undefined,
  injuryStatus: string | null | undefined,
  rosterStatus: string | null | undefined
): string | null {
  const bodyPart = String(injuryType || "").trim();
  const report = String(injuryStatus || "").trim();
  if (!bodyPart && !report) {
    return null;
  }
  if (bodyPart && report) {
    return `${bodyPart} - ${report}`;
  }
  if (bodyPart) {
    const fallback = String(rosterStatus || "").trim() || "Active";
    return `${bodyPart} - ${fallback}`;
  }
  return report;
}

export default function PlayerProfile({
  active,
}: {
  active: FantasyPlayerSnapshot;
}) {
  const fields = [
    { label: "Team", value: active.team },
    { label: "Position", value: active.position },
    { label: "Age", value: active.age },
    {
      label: "Experience",
      value:
        active.experience_years != null
          ? `${active.experience_years} years`
          : null,
    },
    {
      label: "Rookie season",
      value: active.rookie_season,
    },
    { label: "Status", value: active.status },
    {
      label: "Injury",
      value: formatInjuryDisplay(
        active.injury_type,
        active.injury_status,
        active.status
      ),
    },
  ];

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Player Profile
      </h3>
      <dl className="mt-3 grid grid-cols-2 gap-3">
        {fields.map((field) => (
          <div key={field.label}>
            <dt
              className="text-[11px] font-medium uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              {field.label}
            </dt>
            <dd
              className="mt-0.5 text-sm font-semibold"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {field.value == null || field.value === ""
                ? "—"
                : String(field.value)}
            </dd>
          </div>
        ))}
      </dl>
      <p
        className="mt-4 text-[11px] leading-4"
        style={{ color: snapshotTokens.textMuted }}
      >
        Source: NFL / nflverse canonical layer
        {active.season != null
          ? ` · Season ${active.season}`
          : ""}
        {active.week != null ? ` · Week ${active.week}` : ""}
      </p>
    </section>
  );
}
