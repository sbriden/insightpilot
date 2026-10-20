"use client";

import { useState } from "react";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";

const TEAM_ABBREVIATION_ALIASES: Record<string, string> = {
  LAR: "LA",
  OAK: "LV",
  SD: "LAC",
  SDG: "LAC",
  STL: "LA",
  WSH: "WAS",
  JAC: "JAX",
  ARZ: "ARI",
  GNB: "GB",
  KAN: "KC",
  NOR: "NO",
  NWE: "NE",
  SFO: "SF",
  TAM: "TB",
  RAM: "LA",
  RAI: "LV",
  PHX: "ARI",
};

const ESPN_LOGO_ABBREVIATIONS: Record<string, string> = {
  LA: "lar",
  WAS: "wsh",
};

const NON_TEAM_ABBREVIATIONS = new Set([
  "FA",
  "FREE",
  "UNA",
  "UNK",
  "XXX",
  "NA",
  "N/A",
  "NONE",
  "RET",
  "RETIRED",
  "UFA",
  "RFA",
  "PRACTICE",
  "PS",
]);

export function canonicalTeamAbbreviation(
  value: string | null | undefined
): string | null {
  const text = (value || "").trim().toUpperCase();
  if (!text || NON_TEAM_ABBREVIATIONS.has(text)) {
    return null;
  }
  const abbr = TEAM_ABBREVIATION_ALIASES[text] || text;
  if (!/^[A-Z]{2,3}$/.test(abbr)) {
    return null;
  }
  return abbr;
}

export function teamLogoUrl(
  abbreviation: string | null | undefined
): string | null {
  const abbr = canonicalTeamAbbreviation(abbreviation);
  if (!abbr) {
    return null;
  }
  const espn = (
    ESPN_LOGO_ABBREVIATIONS[abbr] || abbr
  ).toLowerCase();
  return `https://a.espncdn.com/i/teamlogos/nfl/500/${espn}.png`;
}

export function teamInSelection(
  selection: string | null | undefined,
  teams: Array<string | null | undefined>
): string | null {
  const text = (selection || "").trim().toUpperCase();
  if (!text) {
    return null;
  }
  const candidates = teams
    .map(canonicalTeamAbbreviation)
    .filter((team): team is string => Boolean(team))
    .sort((left, right) => right.length - left.length);
  for (const team of candidates) {
    if (
      text === team
      || text.startsWith(`${team} `)
      || text.startsWith(`${team}+`)
      || text.startsWith(`${team}-`)
    ) {
      return team;
    }
  }
  return null;
}

export function parseTeamMatchup(
  label?: string | null,
  away?: string | null,
  home?: string | null
): { away: string; home: string } | null {
  const awayAbbr = canonicalTeamAbbreviation(away);
  const homeAbbr = canonicalTeamAbbreviation(home);
  if (awayAbbr && homeAbbr) {
    return { away: awayAbbr, home: homeAbbr };
  }
  const match = (label || "").match(
    /^([A-Za-z]{2,3})\s*@\s*([A-Za-z]{2,3})$/
  );
  if (!match) {
    return null;
  }
  const parsedAway = canonicalTeamAbbreviation(match[1]);
  const parsedHome = canonicalTeamAbbreviation(match[2]);
  if (!parsedAway || !parsedHome) {
    return null;
  }
  return { away: parsedAway, home: parsedHome };
}

export default function TeamLogo({
  abbreviation,
  logoUrl,
  size = 20,
}: {
  abbreviation?: string | null;
  logoUrl?: string | null;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const abbr = canonicalTeamAbbreviation(abbreviation);
  const src = logoUrl || teamLogoUrl(abbreviation);
  const fallback = abbr || "";

  if (!abbr && !logoUrl) {
    return null;
  }

  if (!src || failed) {
    if (!fallback) {
      return null;
    }
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full text-[10px] font-semibold"
        style={{
          width: size,
          height: size,
          background: snapshotTokens.blueLight,
          color: snapshotTokens.blue,
        }}
      >
        {fallback}
      </span>
    );
  }

  return (
    // External ESPN team logo
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      className="shrink-0 object-contain"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}

export function TeamWithLogo({
  abbreviation,
  size = 18,
  empty = "—",
}: {
  abbreviation?: string | null;
  size?: number;
  empty?: string;
}) {
  const label = (abbreviation || "").trim();
  if (!label) {
    return <>{empty}</>;
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <TeamLogo abbreviation={label} size={size} />
      <span>{label}</span>
    </span>
  );
}

export function TeamMatchupLabel({
  label,
  away,
  home,
  size = 18,
}: {
  label?: string | null;
  away?: string | null;
  home?: string | null;
  size?: number;
}) {
  const matchup = parseTeamMatchup(label, away, home);
  if (!matchup) {
    return <>{label || "—"}</>;
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <TeamLogo abbreviation={matchup.away} size={size} />
      <span>{matchup.away}</span>
      <span className="text-[10px] font-semibold opacity-60">@</span>
      <TeamLogo abbreviation={matchup.home} size={size} />
      <span>{matchup.home}</span>
    </span>
  );
}
