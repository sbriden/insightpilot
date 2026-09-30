"use client";

import GameScriptsPanel from "@/components/betting/GameScriptsPanel";
import ModelVsMarket from "@/components/betting/ModelVsMarket";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  BettingEvent,
  BettingInjuryNote,
  BettingMarket,
} from "@/services/api";

interface Props {
  open: boolean;
  market: BettingMarket | null;
  event: BettingEvent | null;
  onClose: () => void;
  onAddToPortfolio?: (market: BettingMarket) => void;
  portfolioImpact?: string | null;
}

export default function MarketDetailDrawer({
  open,
  market,
  event,
  onClose,
  onAddToPortfolio,
  portfolioImpact = null,
}: Props) {
  if (!open || !market) return null;

  const injuries = event?.injuries ?? [];
  const drivers = event?.model_drivers ?? [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/30"
        aria-label="Close market analysis"
        onClick={onClose}
      />
      <aside
        className="relative z-10 flex h-full w-full max-w-md flex-col overflow-y-auto bg-white shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-label="Market analysis"
      >
        <div
          className="border-b px-5 py-4"
          style={{ borderColor: snapshotTokens.divider }}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p
                className="text-xs font-semibold uppercase tracking-[0.16em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                {market.market_type}
              </p>
              <h2
                className="mt-1 text-xl font-semibold"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {market.event_label || "Market"}
              </h2>
              <p
                className="mt-1 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {market.selection}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-2 py-1 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              Close
            </button>
          </div>
          {onAddToPortfolio ? (
            <button
              type="button"
              onClick={() => onAddToPortfolio(market)}
              className="mt-3 w-full rounded-lg px-3 py-2 text-sm font-medium text-white"
              style={{ background: snapshotTokens.blue }}
            >
              Add to Portfolio
            </button>
          ) : null}
        </div>

        <div className="space-y-5 px-5 py-5">
          <ModelVsMarket market={market} />

          <div className="grid grid-cols-2 gap-3">
            <Stat
              label="Market Probability"
              value={pct(market.market_probability)}
            />
            <Stat
              label="InsightPilot Probability"
              value={pct(market.model_probability)}
            />
            <Stat
              label="Market Price"
              value={american(market.price)}
            />
            <Stat
              label="Model Fair Price"
              value={american(market.model_fair_price)}
            />
            <Stat
              label="Difference"
              value={
                market.edge_probability != null
                  ? `${market.edge_probability > 0 ? "+" : ""}${market.edge_probability.toFixed(1)} pts`
                  : market.edge != null
                    ? `${market.edge > 0 ? "+" : ""}${market.edge.toFixed(1)}`
                    : "—"
              }
            />
            <Stat
              label="Expected Value"
              value={
                market.expected_value != null
                  ? `${market.expected_value > 0 ? "+" : ""}${market.expected_value.toFixed(1)}%`
                  : "—"
              }
            />
          </div>

          <div
            className="rounded-xl border p-4"
            style={{
              borderColor: snapshotTokens.border,
              background: snapshotTokens.background,
            }}
          >
            <p
              className="text-sm font-semibold"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {market.confidence || "Low"} Confidence
            </p>
            <p
              className="mt-1 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {market.confidence_explanation
                || "Insufficient context to explain confidence."}
            </p>
          </div>

          {portfolioImpact ? (
            <div
              className="rounded-xl border p-4"
              style={{
                borderColor: snapshotTokens.border,
                background: snapshotTokens.blueLight,
              }}
            >
              <p
                className="text-xs font-semibold uppercase tracking-[0.14em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Portfolio Impact
              </p>
              <p
                className="mt-1 text-sm"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {portfolioImpact}
              </p>
            </div>
          ) : null}

          {event ? (
            <div>
              <p
                className="text-xs font-semibold uppercase tracking-[0.14em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Game Environment
              </p>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <Stat
                  label={`${event.away_team || "Away"} Proj`}
                  value={
                    event.projected_away_score != null
                      ? event.projected_away_score.toFixed(1)
                      : "—"
                  }
                />
                <Stat
                  label={`${event.home_team || "Home"} Proj`}
                  value={
                    event.projected_home_score != null
                      ? event.projected_home_score.toFixed(1)
                      : "—"
                  }
                />
                <Stat
                  label="Model Total"
                  value={
                    event.projected_total != null
                      ? String(event.projected_total)
                      : "—"
                  }
                />
                <Stat
                  label="Market Total"
                  value={
                    event.market_total != null
                      ? String(event.market_total)
                      : "—"
                  }
                />
                {(event.injury_adjustment_away != null
                  || event.injury_adjustment_home != null) && (
                  <>
                    <Stat
                      label={`${event.away_team || "Away"} Injury Δ`}
                      value={fmtAdj(event.injury_adjustment_away)}
                    />
                    <Stat
                      label={`${event.home_team || "Home"} Injury Δ`}
                      value={fmtAdj(event.injury_adjustment_home)}
                    />
                  </>
                )}
              </div>
            </div>
          ) : null}

          {event?.game_scripts && event.game_scripts.length > 0 ? (
            <GameScriptsPanel scripts={event.game_scripts} />
          ) : null}

          {injuries.length > 0 ? (
            <div>
              <p
                className="text-xs font-semibold uppercase tracking-[0.14em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Player Availability
                {event?.injury_report_week != null
                  ? ` · Week ${event.injury_report_week}`
                  : ""}
              </p>
              <ul className="mt-3 space-y-2">
                {injuries.map((injury) => (
                  <InjuryRow key={injury.player_id} injury={injury} />
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <p
              className="text-xs font-semibold uppercase tracking-[0.14em]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Why the Model Differs
            </p>
            <ul
              className="mt-2 list-disc space-y-1 pl-5 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {drivers.length > 0 ? (
                drivers.map((driver) => (
                  <li key={driver}>{driver}</li>
                ))
              ) : (
                <>
                  <li>
                    Projected scores blend market-implied totals with
                    recent team scoring form.
                  </li>
                  <li>
                    Edge reflects the difference between InsightPilot
                    probability and a -110 market price assumption.
                  </li>
                </>
              )}
            </ul>
          </div>
        </div>
      </aside>
    </div>
  );
}

function InjuryRow({ injury }: { injury: BettingInjuryNote }) {
  const impact = injury.projection_impact_pts;
  return (
    <li
      className="rounded-lg border px-3 py-2"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p
            className="text-sm font-medium"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {injury.player_name}
            {injury.team || injury.depth_label ? (
              <span
                className="ml-1 text-xs font-normal"
                style={{ color: snapshotTokens.textMuted }}
              >
                {[injury.team, injury.depth_label]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            ) : null}
          </p>
          <p
            className="mt-0.5 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {[injury.game_status, injury.injury_type]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {impact != null && impact !== 0 ? (
          <span
            className="shrink-0 text-xs font-medium tabular-nums"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {impact > 0 ? "+" : ""}
            {impact.toFixed(1)} pts
          </span>
        ) : null}
      </div>
    </li>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      className="rounded-lg border bg-white px-3 py-2"
      style={{ borderColor: snapshotTokens.border }}
    >
      <p
        className="text-[11px] font-semibold uppercase tracking-[0.12em]"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </p>
      <p
        className="mt-1 text-sm font-semibold tabular-nums"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {value}
      </p>
    </div>
  );
}

function pct(value?: number | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function american(value?: number | null): string {
  if (value == null) return "—";
  return value > 0 ? `+${value}` : String(value);
}

function fmtAdj(value?: number | null): string {
  if (value == null || value === 0) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}
