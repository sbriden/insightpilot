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

          {market.prediction || market.bet_qualification ? (
            <div
              className="rounded-xl border p-4 space-y-3"
              style={{
                borderColor: snapshotTokens.border,
                background: snapshotTokens.background,
              }}
            >
              <div>
                <p
                  className="text-xs font-semibold uppercase tracking-[0.14em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Prediction
                </p>
                <p
                  className="mt-1 text-sm"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {market.prediction?.note
                    || "Directional model view only."}
                </p>
              </div>
              <div>
                <p
                  className="text-xs font-semibold uppercase tracking-[0.14em]"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Bet classification
                  {market.bet_label
                    ? ` · ${market.bet_label}`
                    : market.bet_status
                      ? ` · ${String(market.bet_status)}`
                      : ""}
                </p>
                <p
                  className="mt-1 text-sm font-medium"
                  style={{
                    color:
                      market.bet_status === "strong_bet"
                        ? snapshotTokens.success
                        : market.bet_status === "lean"
                          ? snapshotTokens.blue
                          : snapshotTokens.textPrimary,
                  }}
                >
                  {market.no_bet
                    ? (market.bet_qualification?.summary
                      || "Pass / No Bet — no actionable edge.")
                    : (market.bet_qualification?.summary
                      || "Not evaluated.")}
                </p>
                {market.bet_qualification?.reasons_fail?.length ? (
                  <ul
                    className="mt-2 space-y-1 text-xs"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {market.bet_qualification.reasons_fail
                      .slice(0, 4)
                      .map((reason) => (
                        <li key={reason}>• {reason}</li>
                      ))}
                  </ul>
                ) : null}
                {market.data_quality?.label ? (
                  <p
                    className="mt-1 text-xs"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    Data quality: {market.data_quality.label}
                    {market.data_quality.score != null
                      ? ` (${Math.round(market.data_quality.score * 100)}%)`
                      : ""}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}

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

          <ModelDisagreementPanel market={market} event={event} />

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
                {(event.residual_home != null
                  || event.residual_away != null) && (
                  <>
                    <Stat
                      label={`${event.away_team || "Away"} Residual`}
                      value={fmtAdj(event.residual_away)}
                    />
                    <Stat
                      label={`${event.home_team || "Home"} Residual`}
                      value={fmtAdj(event.residual_home)}
                    />
                  </>
                )}
                {(event.spread_move != null
                  || event.total_move != null) && (
                  <>
                    <Stat
                      label="Spread Move"
                      value={fmtAdj(event.spread_move)}
                    />
                    <Stat
                      label="Total Move"
                      value={fmtAdj(event.total_move)}
                    />
                  </>
                )}
                {event.market_movement?.vs_model?.label
                  && event.market_movement.vs_model.label !== "unknown"
                  && event.market_movement.vs_model.label !== "stable" ? (
                  <div className="col-span-2">
                    <p
                      className="text-xs"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      {event.market_movement.vs_model.explanation}
                    </p>
                  </div>
                ) : null}
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
  const own = injury.own_score_delta;
  const opp = injury.opponent_score_delta;
  const impact =
    own != null && own !== 0
      ? own
      : opp != null && opp !== 0
        ? opp
        : injury.projection_impact_pts;
  const impactLabel =
    opp != null && opp !== 0 && !(own != null && own !== 0)
      ? "opp"
      : "pts";
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
            {injury.team || injury.depth_label || injury.position ? (
              <span
                className="ml-1 text-xs font-normal"
                style={{ color: snapshotTokens.textMuted }}
              >
                {[injury.team, injury.depth_label || injury.position]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            ) : null}
          </p>
          <p
            className="mt-0.5 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {[
              injury.game_status,
              injury.injury_type,
              injury.impact_side === "defense" ? "defense" : null,
            ]
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
            {impact.toFixed(1)} {impactLabel}
          </span>
        ) : null}
      </div>
    </li>
  );
}

function ModelDisagreementPanel({
  market,
  event,
}: {
  market: BettingMarket;
  event: BettingEvent | null;
}) {
  const fromMarket = market.model_disagreement;
  const eventBlock =
    market.market_type === "total"
      ? event?.model_disagreement?.total
      : event?.model_disagreement?.spread;
  const block = fromMarket || eventBlock || null;
  const estimates =
    market.ensemble_estimates
    || block?.estimates
    || null;
  const mean = market.projection_mean ?? block?.projection_mean;
  const stddev = market.projection_stddev ?? block?.projection_stddev;
  const agreement =
    market.model_agreement ?? block?.model_agreement;
  const label =
    market.model_agreement_label ?? block?.label ?? null;

  if (!estimates || Object.keys(estimates).length === 0) {
    return null;
  }

  const rows = Object.entries(estimates).sort(([a], [b]) =>
    a.localeCompare(b)
  );
  const estimateLabels: Record<string, string> = {
    market: "Market",
    team_strength: "Team strength",
    efficiency: "Efficiency",
    recent_form: "Recent form",
    injury: "Injury",
    matchup: "Matchup",
  };

  return (
    <div>
      <p
        className="text-xs font-semibold uppercase tracking-[0.14em]"
        style={{ color: snapshotTokens.textMuted }}
      >
        Model disagreement
      </p>
      <p
        className="mt-1 text-sm"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Independent estimates — mean and σ matter more than any
        single number. Low agreement dampens confidence.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat
          label="Mean"
          value={
            mean != null
              ? `${mean > 0 ? "+" : ""}${mean}`
              : "—"
          }
        />
        <Stat
          label="Std Dev"
          value={stddev != null ? String(stddev) : "—"}
        />
        <Stat
          label="Agreement"
          value={
            agreement != null
              ? `${Math.round(agreement * 100)}%${label ? ` · ${label}` : ""}`
              : "—"
          }
        />
      </div>
      <ul className="mt-3 space-y-1.5 text-sm">
        {rows.map(([key, value]) => (
          <li
            key={key}
            className="flex items-center justify-between gap-3"
          >
            <span style={{ color: snapshotTokens.textSecondary }}>
              {estimateLabels[key] || key}
            </span>
            <span
              className="tabular-nums font-medium"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {value != null
                ? `${Number(value) > 0 ? "+" : ""}${value}`
                : "—"}
            </span>
          </li>
        ))}
      </ul>
    </div>
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
