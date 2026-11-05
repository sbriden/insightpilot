# Team Power Rankings (NFL + CFB) — implementation report

## Summary

Opponent-adjusted team power rankings live in the Sports Betting data product for **NFL and CFB**. Ratings are built from canonical `fact_team_game` / `fact_defensive_game` performance (via shared `team_strength` loaders), not from sportsbook prices. Existing `team_strength` remains the primary matchup projection path; power rankings expose a margin helper for comparison and future calibration.

CFB uses `college_football` facts (no EPA) — composites emphasize opponent-adjusted scoring and yards/play. Rankings cover FBS teams with completed games in the snapshot window.

## Architecture & source data

| Asset | Role |
|-------|------|
| `fantasy_football.dim_team` | Canonical 32 NFL teams |
| `fantasy_football.dim_game` | Completed games / scores / weeks |
| `fantasy_football.fact_team_game` | Offensive EPA, yards, points |
| `fantasy_football.fact_defensive_game` | Defensive EPA allowed, points allowed |
| `app/analysis/insights/betting/team_strength.py` | Shared game loaders + baselines (no duplicate team model) |
| `app/analysis/insights/betting/player_context.py` | Optional personnel adjustment layer |
| `fantasy_football.fact_team_power_ranking` | Versioned weekly ranking snapshots |

## Rating components

Expressed in points above/below league average where practical:

- `offensive_rating` — EPA/play + success proxy + opponent-adjusted scoring residual
- `defensive_rating` — inverted EPA/success allowed + points allowed (higher = better)
- `special_teams_rating` — scoring residual vs EPA expectation (proxy)
- `baseline_power_rating` = offense + defense + special teams
- `current_adjusted_rating` = baseline + personnel + recent-form nudge (`0.15 × form`)
- `overall_power_rating` = current adjusted rating

Calculation version `power_rankings.v1.6`:

- CFB SOS / record quality blend opponent win% with efficiency strength so G5 padding cannot look like a P4 slate.
- Soft schedules take an asymmetric efficiency penalty; cupcake wins ≈ 0 record credit; bad losses hurt; no blanket 7-1 floor.
- **Recent form is opponent-adjusted** (off+def residuals, FCS excluded, soft recent slates dampened).
- **Defense efficiency uses opponent-adjusted points residual** (not raw PPG allowed).

## Engine pipeline (weekly)

1. Load completed games with `week < snapshot_week` (no future leakage).
2. Iterative opponent adjustment (≤4 iterations) with home-aware game rows.
3. Exponential recency: `weight = 2 ** (-age_weeks / half_life)` (default half-life = 5).
4. Prior shrinkage: `λ = n_eff / (n_eff + k)` (default `k = 5`) vs prior-season ratings.
5. Optional personnel layer from `player_context` (zero when unreliable).
6. Rank all teams; compute form, SOS, confidence, trend vs prior snapshot.
7. Persist snapshot when `persist=true` (same season/week/version replaces only that slice).

## Matchup exposure

```
expected_margin = home_rating - away_rating + HFA
```

`project_margin_from_power_rankings` splits projected scores from offensive/defensive components and re-centers to the margin. Does **not** change betting model weights or replace `team_strength` projections.

## API

- `GET /api/sources/nflverse/betting/power-rankings`
  - Query: `sport` (`NFL`|`CFB`), `season`, `week`, `persist`, `half_life_weeks`, `prior_k`
- `GET /api/sources/nflverse/betting/power-rankings/backtest`
  - Chronological MAE/RMSE for one week’s completed games (`sport` supported)

## Frontend

- Registry: `betting.power_rankings` (Sports Betting product)
- `PowerRankings.tsx` — NFL/CFB toggle, week selector, ranking table, limitations
- Wired in `SportsBettingAnalyzer`, `AnalysisRuntime`, `ProductAnalysisTabs`

## Schema

`fact_team_power_ranking` PK: `(season, week, team_id, calculation_version)`. Historical weeks are preserved across weeks; re-running the same version regenerates that week only.

Calculation version: `power_rankings.v1.6`.

## Metric definitions (documented in payload)

| Metric | Direction | Source | Role |
|--------|-----------|--------|------|
| Offensive EPA/play | higher better | `fact_team_game.offensive_epa / plays` | primary |
| Defensive EPA allowed | inverted → higher better | `fact_defensive_game` | primary |
| Success rate proxy | higher better | EPA/plays (PBP success flags not stored) | primary |
| Special teams proxy | higher better | scoring residual vs EPA | secondary / limited |
| Recency weight | n/a | `2 ** (-age / half_life)` | weighting |
| Prior shrinkage | n/a | `λ = n_eff / (n_eff + k)` | regularization |

## Tests

`backend/tests/test_power_rankings.py` covers:

- All 32 teams rated
- Offense/defense orientation
- Opponent scaling
- Home-field margin
- Recency half-life
- Prior shrinkage behavior
- No future-week leakage (`before_week` passed to loaders)
- Personnel separate from baseline
- Empty data does not fabricate rankings
- Persist invokes snapshot writer
- Matchup projection orientation

## Data-quality limitations

- Special teams is a residual proxy (true ST EPA/returns not in fact tables).
- Success / explosive rates are EPA- and yards-based proxies.
- Personnel adjustments stay at zero when player-impact context is missing.
- Rankings are independent of sportsbook prices; market comparison is out of band.
- Garbage-time attenuation is limited to available game-level aggregates (no play-clock filters in facts).

## Out of scope / follow-ups

- Multi-week automated backtest CI job with confidence intervals
- Calibrating HFA / points-per-z from historical MAE
- Richer ST metrics once persisted
- Wiring power ratings as an optional blend input in slate projections (without replacing `team_strength`)
