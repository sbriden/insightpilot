"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  Layers,
  Newspaper,
  Users,
} from "lucide-react";

import {
  FantasyNewsCategory,
  FantasyNewsDevelopment,
  FantasyNewsImpactLevel,
  FantasyNewsLookback,
  FantasyPlayerNews,
  getFantasyPlayerNews,
} from "@/services/api";

import { snapshotTokens } from "./tokens";

interface Props {
  playerId: string;
  defaultSeason?: number | null;
  onNavigateTab?: (
    tab: "snapshot" | "usage" | "matchups"
  ) => void;
}

const CATEGORY_OPTIONS: Array<{
  value: FantasyNewsCategory;
  label: string;
}> = [
  { value: "all", label: "All" },
  { value: "injury", label: "Injury" },
  { value: "practice", label: "Practice" },
  { value: "role", label: "Role" },
  { value: "depth_chart", label: "Depth Chart" },
  { value: "team", label: "Team" },
];

const IMPACT_OPTIONS: Array<{
  value: FantasyNewsImpactLevel;
  label: string;
}> = [
  { value: "all", label: "All impact" },
  { value: "high", label: "High" },
  { value: "moderate", label: "Moderate" },
  { value: "low", label: "Low" },
];

const TIME_OPTIONS: Array<{
  value: FantasyNewsLookback;
  label: string;
}> = [
  { value: "last_7d", label: "Last 7 days" },
  { value: "last_30d", label: "Last 30 days" },
  { value: "season", label: "Season" },
];

function categoryMeta(category: string | null | undefined): {
  label: string;
  Icon: typeof Activity;
} {
  switch ((category || "").toLowerCase()) {
    case "injury":
      return { label: "Injury Update", Icon: AlertTriangle };
    case "practice":
      return { label: "Practice Report", Icon: ClipboardList };
    case "depth_chart":
    case "role":
      return { label: "Role Update", Icon: Layers };
    case "team":
      return { label: "Teammate Update", Icon: Users };
    default:
      return { label: "Development", Icon: Newspaper };
  }
}

function impactStyles(level: string | null | undefined): {
  bg: string;
  text: string;
  border: string;
  label: string;
} {
  switch ((level || "").toLowerCase()) {
    case "high":
      return {
        bg: snapshotTokens.negativeLight,
        text: snapshotTokens.negative,
        border: "#FECACA",
        label: "HIGH IMPACT",
      };
    case "moderate":
      return {
        bg: snapshotTokens.warningLight,
        text: "#B45309",
        border: "#FDE68A",
        label: "MODERATE IMPACT",
      };
    case "low":
      return {
        bg: snapshotTokens.background,
        text: snapshotTokens.textSecondary,
        border: snapshotTokens.border,
        label: "LOW IMPACT",
      };
    default:
      return {
        bg: snapshotTokens.background,
        text: snapshotTokens.textSecondary,
        border: snapshotTokens.border,
        label: "IMPACT",
      };
  }
}

function formatCheckedAt(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function weekLabel(week: number | null | undefined): string {
  if (week == null) {
    return "";
  }
  return `Week ${week}`;
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
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
        {title}
      </h3>
      {subtitle && (
        <p
          className="mt-1 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {subtitle}
        </p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ImpactBadge({
  level,
}: {
  level: string | null | undefined;
}) {
  const styles = impactStyles(level);
  return (
    <span
      className="inline-flex items-center rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide"
      style={{
        backgroundColor: styles.bg,
        color: styles.text,
        border: `1px solid ${styles.border}`,
      }}
    >
      {styles.label}
    </span>
  );
}

function InsightImpact({
  development,
  onNavigateTab,
}: {
  development: FantasyNewsDevelopment;
  onNavigateTab?: Props["onNavigateTab"];
}) {
  const impact = development.impact;
  if (!impact?.level || impact.level === "low") {
    return null;
  }

  const related: Array<"usage" | "matchups" | "snapshot"> = [];
  if (
    development.category === "depth_chart"
    || development.category === "role"
    || development.event_type === "teammate_injury"
  ) {
    related.push("usage");
  }
  if (development.category === "injury" || development.category === "practice") {
    related.push("snapshot");
  }
  if (related.length === 0) {
    related.push("snapshot");
  }

  return (
    <div
      className="mt-3 rounded-lg border px-3 py-3"
      style={{
        borderColor: "#BFDBFE",
        backgroundColor: snapshotTokens.blueLight,
      }}
    >
      <p
        className="text-[11px] font-semibold tracking-wide"
        style={{ color: snapshotTokens.blue }}
      >
        ✦ InsightPilot Impact
      </p>
      <p
        className="mt-1 text-sm font-medium"
        style={{ color: snapshotTokens.navy }}
      >
        {impact.label || "Fantasy impact"}
      </p>
      {impact.summary && (
        <p
          className="mt-1 text-xs leading-relaxed"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {impact.summary}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px]">
        {impact.role_impact && (
          <span style={{ color: snapshotTokens.textSecondary }}>
            Role: {impact.role_impact}
          </span>
        )}
        {impact.availability && (
          <span style={{ color: snapshotTokens.textSecondary }}>
            Availability: {impact.availability}
          </span>
        )}
        {impact.confidence && (
          <span style={{ color: snapshotTokens.textSecondary }}>
            Confidence: {impact.confidence}
          </span>
        )}
      </div>
      {onNavigateTab && (
        <div className="mt-3 flex flex-wrap gap-2">
          {related.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => onNavigateTab(tab)}
              className="inline-flex items-center gap-1 text-[11px] font-medium"
              style={{ color: snapshotTokens.blue }}
            >
              {tab === "usage"
                ? "Usage & Trends"
                : tab === "matchups"
                  ? "Matchups"
                  : "Player Snapshot"}
              <ArrowRight className="h-3 w-3" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NewsCard({
  development,
  featured,
  onNavigateTab,
}: {
  development: FantasyNewsDevelopment;
  featured?: boolean;
  onNavigateTab?: Props["onNavigateTab"];
}) {
  const meta = categoryMeta(development.category);
  const Icon = meta.Icon;

  return (
    <article
      className={
        featured
          ? "rounded-[10px] border bg-white p-4 sm:p-5"
          : "rounded-lg border bg-white p-3.5"
      }
      style={{
        borderColor: featured
          ? snapshotTokens.blue
          : snapshotTokens.border,
        boxShadow: featured
          ? "0 0 0 1px rgba(22,119,255,0.12)"
          : undefined,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon
            className="h-3.5 w-3.5 shrink-0"
            style={{ color: snapshotTokens.blue }}
          />
          <span
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {meta.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <ImpactBadge level={development.impact?.level} />
          {development.week != null && (
            <span
              className="text-[11px]"
              style={{ color: snapshotTokens.textMuted }}
            >
              {weekLabel(development.week)}
            </span>
          )}
        </div>
      </div>

      <h4
        className={`mt-2 font-semibold leading-snug ${
          featured ? "text-[16px]" : "text-sm"
        }`}
        style={{ color: snapshotTokens.navy }}
      >
        {development.headline}
      </h4>

      {development.body && (
        <p
          className="mt-1.5 text-xs leading-relaxed"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {development.body}
        </p>
      )}

      <p
        className="mt-2 text-[11px]"
        style={{ color: snapshotTokens.textMuted }}
      >
        {development.source_label || "InsightPilot"}
        {development.occurred_at
          ? ` · ${development.occurred_at}`
          : ""}
      </p>

      <InsightImpact
        development={development}
        onNavigateTab={onNavigateTab}
      />
    </article>
  );
}

function SkeletonCards() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className="animate-pulse rounded-[10px] border bg-white p-4"
          style={{ borderColor: snapshotTokens.border }}
        >
          <div
            className="h-3 w-24 rounded"
            style={{ backgroundColor: snapshotTokens.divider }}
          />
          <div
            className="mt-3 h-4 w-3/4 rounded"
            style={{ backgroundColor: snapshotTokens.divider }}
          />
          <div
            className="mt-2 h-3 w-1/2 rounded"
            style={{ backgroundColor: snapshotTokens.divider }}
          />
        </div>
      ))}
    </div>
  );
}

export default function PlayerNewsTab({
  playerId,
  defaultSeason,
  onNavigateTab,
}: Props) {
  const [season, setSeason] = useState<number | null>(
    defaultSeason ?? null
  );
  const [lookback, setLookback] =
    useState<FantasyNewsLookback>("last_30d");
  const [category, setCategory] =
    useState<FantasyNewsCategory>("all");
  const [impact, setImpact] =
    useState<FantasyNewsImpactLevel>("all");
  const [news, setNews] = useState<FantasyPlayerNews | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await getFantasyPlayerNews(playerId, {
          season,
          lookback,
          category,
          impact,
        });
        if (cancelled) {
          return;
        }
        setNews(result.news);
        if (season == null && result.news.season != null) {
          setSeason(result.news.season);
        }
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setNews(null);
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load player news."
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [playerId, season, lookback, category, impact]);

  const timelineGroups = useMemo(() => {
    if (!news?.developments?.length) {
      return [];
    }
    const groups = new Map<string, FantasyNewsDevelopment[]>();
    for (const item of news.developments) {
      const key =
        item.week != null
          ? `Week ${item.week}`
          : "Recent";
      const list = groups.get(key) || [];
      list.push(item);
      groups.set(key, list);
    }
    return Array.from(groups.entries());
  }, [news]);

  const selectClass =
    "rounded-md border bg-white px-2.5 py-1.5 text-xs outline-none";

  if (loading && !news) {
    return (
      <div className="space-y-4">
        <SkeletonCards />
      </div>
    );
  }

  if (error && !news) {
    return (
      <div
        className="rounded-[10px] border bg-white px-5 py-10 text-center"
        style={{ borderColor: snapshotTokens.border }}
      >
        <p
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          News temporarily unavailable
        </p>
        <p
          className="mt-2 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          We couldn&apos;t retrieve the latest player news.
          Try again shortly.
        </p>
        <p
          className="mt-3 text-xs"
          style={{ color: snapshotTokens.negative }}
        >
          {error}
        </p>
      </div>
    );
  }

  if (!news) {
    return null;
  }

  const seasons = news.available_seasons?.length
    ? news.available_seasons
    : news.season
      ? [news.season]
      : [];

  return (
    <div className="space-y-4">
      {/* Status header */}
      <section
        className="rounded-[10px] border bg-white p-4 sm:p-5"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3
              className="text-[15px] font-semibold"
              style={{ color: snapshotTokens.navy }}
            >
              Player News
            </h3>
            <p
              className="mt-1 text-xs"
              style={{ color: snapshotTokens.textSecondary }}
            >
              Updated {formatCheckedAt(news.last_checked_at)}
              {" · "}
              {news.counts.total} relevant{" "}
              {news.counts.total === 1 ? "story" : "stories"}
            </p>
          </div>
          <div
            className="flex flex-wrap gap-3 text-[11px]"
            style={{ color: snapshotTokens.textMuted }}
          >
            <span>High {news.counts.high}</span>
            <span>Moderate {news.counts.moderate}</span>
            <span>Low {news.counts.low}</span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <select
            className={selectClass}
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
            value={category}
            onChange={(event) =>
              setCategory(
                event.target.value as FantasyNewsCategory
              )
            }
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
            value={impact}
            onChange={(event) =>
              setImpact(
                event.target.value as FantasyNewsImpactLevel
              )
            }
          >
            {IMPACT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
            value={lookback}
            onChange={(event) =>
              setLookback(
                event.target.value as FantasyNewsLookback
              )
            }
          >
            {TIME_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {seasons.length > 0 && (
            <select
              className={selectClass}
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
              value={season ?? news.season}
              onChange={(event) =>
                setSeason(Number(event.target.value))
              }
            >
              {seasons.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          )}
        </div>
      </section>

      {/* Featured + Important Developments */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Section
          title="Featured Development"
          subtitle="Most relevant recent event — ranked by impact, not just recency"
        >
          {news.featured ? (
            <NewsCard
              development={news.featured}
              featured
              onNavigateTab={onNavigateTab}
            />
          ) : (
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textSecondary }}
            >
              No featured development in this window.
            </p>
          )}
        </Section>

        <Section
          title="Important Developments"
          subtitle="Current situation at a glance"
        >
          {news.important_developments.length === 0 ? (
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textSecondary }}
            >
              No summarized developments yet.
            </p>
          ) : (
            <ul className="space-y-3">
              {news.important_developments.map((item) => (
                <li
                  key={`${item.category}-${item.development_id}`}
                  className="flex gap-2"
                >
                  <span
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{
                      backgroundColor: snapshotTokens.blue,
                    }}
                  />
                  <div>
                    <p
                      className="text-[11px] font-semibold uppercase tracking-wide"
                      style={{
                        color: snapshotTokens.textMuted,
                      }}
                    >
                      {item.label}
                    </p>
                    <p
                      className="mt-0.5 text-sm leading-snug"
                      style={{ color: snapshotTokens.navy }}
                    >
                      {item.summary}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      {/* Timeline */}
      <Section
        title="News Timeline"
        subtitle="Injury reports and depth-chart changes that affect fantasy outlook"
      >
        {news.developments.length === 0 ? (
          <div className="py-6 text-center">
            <p
              className="text-sm font-semibold"
              style={{ color: snapshotTokens.navy }}
            >
              No significant recent news
            </p>
            <p
              className="mx-auto mt-2 max-w-md text-xs leading-relaxed"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {news.empty_message
                || "InsightPilot hasn't identified any recent developments likely to materially affect this player's fantasy outlook."}
            </p>
            <p
              className="mt-3 text-[11px]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Last checked: {formatCheckedAt(news.last_checked_at)}
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {timelineGroups.map(([label, items]) => (
              <div key={label}>
                <p
                  className="mb-2 text-[11px] font-semibold uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {label}
                </p>
                <div className="space-y-2.5">
                  {items.map((item) => (
                    <NewsCard
                      key={item.id}
                      development={item}
                      onNavigateTab={onNavigateTab}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {news.data_note && (
        <p
          className="px-1 text-[11px] leading-relaxed"
          style={{ color: snapshotTokens.textMuted }}
        >
          {news.data_note}
        </p>
      )}
    </div>
  );
}
