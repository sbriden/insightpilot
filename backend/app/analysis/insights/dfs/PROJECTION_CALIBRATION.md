# Projection Calibration / Guardrails

## Why this exists

Early-season DFS projections that equal current-season FPPG
can explode after 1–2 outlier games (e.g. a QB projecting ~45
for week 3). InsightPilot keeps the **raw** signal but routes
all DFS scoring through a **calibration / guardrail layer**
before matchup adjustments and the optimizer.

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
InsightPilot projection (pre-matchup)
      ↓
Weekly matchup / environment multiplier
      ↓
Final `projection` / `insightpilot_projection`
      ↓
DFS Analyzer / Optimizer / Portfolio
```

## Modules

| File | Role |
|------|------|
| `projection_calibration.py` | Guardrail engine + `CalibrationConfig` |
| `projection_baselines.py` | Prior-season FPPG / p90 loader |
| `slate.py` `_to_dfs_player` | Applies calibration, then matchup |

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
- `base_projection` — calibrated InsightPilot median (pre-matchup)
- `projection` / `insightpilot_projection` — after matchup (optimizer input)
- `projection_adjustment` — `insightpilot − raw` (points)
- `projection_adjustment_reason` — human-readable explanation
- `projection_floor` / `floor`, `projection_ceiling` / `ceiling`
- `projection_confidence`, `sample_size_confidence`
- `historical_baseline`, `current_season_games`, `historical_games`

## What this is not (yet)

Full rate-based component projection (projecting pass
attempts, targets, etc. then converting to fantasy points)
is the next evolution. Today, opportunity scores act as the
**driver validation** signal so fantasy-point spikes without
opportunity support are regressed.

Outcome distribution / Monte Carlo floors & ceilings can
replace the confidence multiplier table later without
changing the DFS consumer contract.
