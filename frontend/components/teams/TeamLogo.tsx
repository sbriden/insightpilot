"use client";

import { useState } from "react";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";

const NFL_ABBREVIATION_ALIASES: Record<string, string> = {
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

const NBA_ABBREVIATION_ALIASES: Record<string, string> = {
  GS: "GSW",
  NO: "NOP",
  NY: "NYK",
  SA: "SAS",
  UTAH: "UTA",
  WSH: "WAS",
  PHO: "PHX",
  BRK: "BKN",
  BRO: "BKN",
};

const NHL_ABBREVIATION_ALIASES: Record<string, string> = {
  // ESPN NHL CDN uses short codes (la/nj/sj/tb), so normalize
  // long forms down rather than the reverse.
  NJD: "NJ",
  TBL: "TB",
  LAK: "LA",
  SJS: "SJ",
  VEGAS: "VGK",
  MON: "MTL",
  WAS: "WSH",
};

const MLB_ABBREVIATION_ALIASES: Record<string, string> = {
  AZ: "ARI",
  ARZ: "ARI",
  CWS: "CHW",
  KAN: "KC",
  SFG: "SF",
  SDP: "SD",
  TBR: "TB",
  WAS: "WSH",
};

/** ESPN CDN filename overrides (after canonicalization). */
const ESPN_LOGO_ABBREVIATIONS: Record<
  string,
  Record<string, string>
> = {
  nfl: {
    LA: "lar",
    WAS: "wsh",
  },
  nba: {
    // ESPN uses short / alternate filenames for a few clubs.
    NOP: "no",
    NO: "no",
    UTA: "utah",
    UTAH: "utah",
  },
  nhl: {
    LAK: "la",
    NJD: "nj",
    SJS: "sj",
    TBL: "tb",
  },
  mlb: {
    AZ: "ari",
  },
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

export type TeamSport =
  | "NFL"
  | "CFB"
  | "NBA"
  | "NHL"
  | "MLB"
  | "NCAAB"
  | string;

type EspnLogoLeague = "nfl" | "nba" | "nhl" | "mlb";

export function normalizeTeamSport(
  sport: TeamSport | null | undefined
): string {
  const key = String(sport || "NFL").trim().toUpperCase();
  if (
    key === "NCAAF"
    || key === "CFB"
    || key === "COLLEGE"
    || key === "NCAA"
  ) {
    return "CFB";
  }
  return key || "NFL";
}

function espnLogoLeague(
  sport: TeamSport
): EspnLogoLeague | null {
  switch (normalizeTeamSport(sport)) {
    case "NFL":
      return "nfl";
    case "NBA":
      return "nba";
    case "NHL":
      return "nhl";
    case "MLB":
      return "mlb";
    // College logos need ESPN team ids — never use NFL abbr paths.
    case "CFB":
    case "NCAAB":
      return null;
    default:
      return null;
  }
}

function abbreviationAliasesForSport(
  sport: TeamSport
): Record<string, string> {
  switch (normalizeTeamSport(sport)) {
    case "NBA":
      return NBA_ABBREVIATION_ALIASES;
    case "NHL":
      return NHL_ABBREVIATION_ALIASES;
    case "MLB":
      return MLB_ABBREVIATION_ALIASES;
    case "CFB":
    case "NCAAB":
      return {};
    case "NFL":
    default:
      return NFL_ABBREVIATION_ALIASES;
  }
}

export function canonicalTeamAbbreviation(
  value: string | null | undefined,
  sport: TeamSport = "NFL"
): string | null {
  const text = (value || "").trim().toUpperCase();
  if (!text || NON_TEAM_ABBREVIATIONS.has(text)) {
    return null;
  }
  const normalized = normalizeTeamSport(sport);
  const aliases = abbreviationAliasesForSport(normalized);
  const abbr = aliases[text] || text;
  // College uses 2–5 char school codes (MTSU, KENN, etc.).
  const pattern =
    normalized === "CFB" || normalized === "NCAAB"
      ? /^[A-Z]{2,5}$/
      : /^[A-Z]{2,3}$/;
  if (!pattern.test(abbr)) {
    return null;
  }
  return abbr;
}

export function teamLogoUrl(
  abbreviation: string | null | undefined,
  sport: TeamSport = "NFL"
): string | null {
  const league = espnLogoLeague(sport);
  // College logos must use espn team ids (passed via logoUrl), never
  // abbreviation paths — those collide with NFL assets.
  if (!league) {
    return null;
  }
  const abbr = canonicalTeamAbbreviation(abbreviation, sport);
  if (!abbr) {
    return null;
  }
  const overrides = ESPN_LOGO_ABBREVIATIONS[league] || {};
  const espn = (overrides[abbr] || abbr).toLowerCase();
  return `https://a.espncdn.com/i/teamlogos/${league}/500/${espn}.png`;
}

export function teamInSelection(
  selection: string | null | undefined,
  teams: Array<string | null | undefined>,
  sport: TeamSport = "NFL"
): string | null {
  const text = (selection || "").trim().toUpperCase();
  if (!text) {
    return null;
  }
  const candidates = teams
    .map((team) => canonicalTeamAbbreviation(team, sport))
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
  home?: string | null,
  sport: TeamSport = "NFL"
): { away: string; home: string } | null {
  const awayAbbr = canonicalTeamAbbreviation(away, sport);
  const homeAbbr = canonicalTeamAbbreviation(home, sport);
  if (awayAbbr && homeAbbr) {
    return { away: awayAbbr, home: homeAbbr };
  }
  const normalized = normalizeTeamSport(sport);
  const match = (label || "").match(
    normalized === "CFB" || normalized === "NCAAB"
      ? /^([A-Za-z]{2,5})\s*@\s*([A-Za-z]{2,5})$/
      : /^([A-Za-z]{2,3})\s*@\s*([A-Za-z]{2,3})$/
  );
  if (!match) {
    return null;
  }
  const parsedAway = canonicalTeamAbbreviation(match[1], sport);
  const parsedHome = canonicalTeamAbbreviation(match[2], sport);
  if (!parsedAway || !parsedHome) {
    return null;
  }
  return { away: parsedAway, home: parsedHome };
}

export default function TeamLogo({
  abbreviation,
  logoUrl,
  sport = "NFL",
  size = 20,
}: {
  abbreviation?: string | null;
  logoUrl?: string | null;
  sport?: TeamSport;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const abbr = canonicalTeamAbbreviation(abbreviation, sport);
  const src = logoUrl || teamLogoUrl(abbreviation, sport);
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
        {fallback.slice(0, 3)}
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
  logoUrl,
  sport = "NFL",
  size = 18,
  empty = "—",
}: {
  abbreviation?: string | null;
  logoUrl?: string | null;
  sport?: TeamSport;
  size?: number;
  empty?: string;
}) {
  const label = (abbreviation || "").trim();
  if (!label) {
    return <>{empty}</>;
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <TeamLogo
        abbreviation={label}
        logoUrl={logoUrl}
        sport={sport}
        size={size}
      />
      <span>{label}</span>
    </span>
  );
}

export function TeamMatchupLabel({
  label,
  away,
  home,
  awayLogoUrl,
  homeLogoUrl,
  sport = "NFL",
  size = 18,
}: {
  label?: string | null;
  away?: string | null;
  home?: string | null;
  awayLogoUrl?: string | null;
  homeLogoUrl?: string | null;
  sport?: TeamSport;
  size?: number;
}) {
  const matchup = parseTeamMatchup(label, away, home, sport);
  if (!matchup) {
    return <>{label || "—"}</>;
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <TeamLogo
        abbreviation={matchup.away}
        logoUrl={awayLogoUrl}
        sport={sport}
        size={size}
      />
      <span>{matchup.away}</span>
      <span className="text-[10px] font-semibold opacity-60">@</span>
      <TeamLogo
        abbreviation={matchup.home}
        logoUrl={homeLogoUrl}
        sport={sport}
        size={size}
      />
      <span>{matchup.home}</span>
    </span>
  );
}
