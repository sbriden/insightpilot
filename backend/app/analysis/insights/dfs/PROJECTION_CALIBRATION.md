# Projection Calibration / Guardrails

## Why this exists

Early-season DFS projections that equal current-season FPPG
can explode after 1–2 outlier games (e.g. a QB projecting ~45
for week 3). InsightPilot keeps the **raw** signal but routes
all DFS scoring through a **calibration / guardrail layer**
before the weekly game environment is applied.

## Pipeline

```text
NFL / DFS data
      ↓
Canonical fantasy model + opportunity
      ↓
Raw projection (current-season FPPG)
      ↓
Projection Calibration  ← this document
  • sample-size regression toward historical baseline
  • opportunity-support validation
  • historical / positional distribution checks
  • confidence + floor / ceiling
      ↓
InsightPilot projection (skill prior)
      ↓
Role and opportunity forecast
  • depth chart, availability, teammate absences
  • historical role as the prior, current usage as the present
  • opportunities capped by the game forecast
      ↓
Component production
  • yards and catches = opportunities × shrunk efficiency
  • touchdowns from goal-line / red-zone chances and team scoring
  • calibrated FPPG sets efficiency only when the rate sample is thin
      ↓
Final `projection` / `insightpilot_projection`
(matchup/environment multiplier only if no game forecast)
      ↓
Forecast contract (`player_forecast_v1`)
  • mean, median, and percentile floor / ceiling
  • position- and contest-specific outcome probabilities
  • workload, role change, and uncertainty
      ↓
DFS optimizer uses the joint distribution for showdown
lineups. Salary still has to fit. Points per dollar is
one input, not the reason a player is included.
      ↓
DFS Analyzer / Optimizer / Portfolio
```

## Modules

| File | Role |
|------|------|
| `projection_calibration.py` | Guardrail engine + `CalibrationConfig` |
| `projection_baselines.py` | Prior-season FPPG / p90 loader |
| `game_forecast.py` | Shared game scoring environment |
| `player_game_projection.py` | Player opportunity, efficiency, and touchdowns |
| `slate.py` `_to_dfs_player` | Calibration, then game forecast or matchup fallback |

## Configurable weights

Edit `CalibrationConfig` in `projection_calibration.py`
(or `with_config(...)` in tests). Do not hardcode weights
inside slate/optimizer code.

Default current-season weight by games played:

| Games | Current-season weight |
|------:|----------------------:|
| 1–2   | 20% |
| 3–5   | 40% |
| 6–9   | 60% |
| 10+   | 80% |

Historical weight = `1 − current_season_weight`
(rookies use positional priors instead of player history).

## Output fields on DFS players

- `raw_projection` — uncalibrated season FPPG
- `base_projection` — calibrated InsightPilot median (pre-game)
- `projection` / `insightpilot_projection` — simulation median when a game forecast exists, otherwise the component projection or the matchup fallback
- `adjustment_source` — `game_forecast` or `matchup_fallback`
- `projection_drivers` — why the weekly environment changed the projection
- `scoring_components` — fantasy points by opportunity, efficiency, and scoring event
- `simulation` — percentile floor, ceiling, and upside / bust probabilities
- `projection_adjustment` — `insightpilot − raw` (points)
- `projection_floor` / `floor`, `projection_ceiling` / `ceiling` — 10th and 90th percentiles of simulated fantasy points when a game is simulated; confidence multipliers otherwise
- `projection_confidence`, `sample_size_confidence`

## What the percentiles are

Floor and ceiling are configurable percentiles of the joint
game simulation (`SimulationConfig`). A 10th-percentile
outcome is a point in that distribution, not a guarantee
the player scores at least that many points. Confidence
stays the calibration label from sample size and input quality.
