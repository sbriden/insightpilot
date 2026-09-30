# Player Correlation Engine

Reusable pairwise correlation for DFS lineup construction and
portfolio analysis. Sport-agnostic API; NFL structural rules are
the first concrete implementation (Showdown + classic main slate).

## Pipeline

```text
DFS Slate
   │
   ▼
Player Projections + Context
   │
   ├─ Ownership
   ├─ Correlation  ← this document
   └─ Game Script
   │
   ▼
Lineup Optimizer
   • projection / value / leverage
   • lineup_correlation_score (weighted, not binary)
   │
   ▼
Portfolio Optimizer
   • exposure / uniqueness / scripts
   • correlation exposure reporting
```

## Score convention

| Score | Meaning |
|------:|---------|
| -1.0 | Strongly negative |
|  0.0 | Neutral / unrelated |
| +1.0 | Strongly positive |

Every non-neutral edge includes:

- `correlation_type` — `positive` | `negative` | `neutral`
- `correlation_reason` — human-readable explanation
- `confidence` — `High` | `Moderate` | `Low` | `Very Low`
- `confidence_score` — continuous 0–1 evidence quality
- `source` — `structural` | `empirical` | `blended`
- `rule_id` — stable rule key (e.g. `qb_own_wr1`)

## Two evidence forms

### Structural

Football / game relationships that hold even with thin samples:

- QB → own WR/TE
- QB → opposing pass catcher (competitive / shootout)
- QB → opposing DST (negative)
- Skill → opposing DST (negative)
- RB committee (negative opportunity conflict)
- RB → own DST (script-amplified in control / low-scoring)
- WR ↔ opposing WR (shootout bring-backs)
- Soft same-team WR target competition
- Kicker → own offense (mild)
- QB → own DST (mild, script-dependent)

### Empirical

Optional historical co-movement rows blended into the matrix.
Small samples get low confidence and are down-weighted. Rows
can be marked `invalidated` (e.g. player changed teams /
teammates) so stale history does not dominate.

## Confidence

Continuous `confidence_score` maps to labels via
`CorrelationConfig`:

| Label | Default threshold |
|-------|------------------:|
| High | ≥ 0.75 |
| Moderate | ≥ 0.45 |
| Low | ≥ 0.25 |
| Very Low | below |

Empirical confidence saturates with `games_together`
(`min_empirical_games` default 6). Optimizer selection uses
`correlation_score × confidence_score`, so low-confidence
edges move the needle less than high-confidence ones at the
same raw magnitude.

## Lineup scoring

```text
lineup_correlation_score =
    Σ positive pairs (score × confidence)
  + Σ negative pairs (score × confidence)   # already negative
  − concentration_penalty
```

Concentration soft-penalizes many strong positive pairs that
all require the same narrow outcome (`concentration_pair_threshold`,
`concentration_penalty_per_extra`). This is **not** a ban —
it balances correlation vs diversification.

During greedy fill, each candidate gets:

```text
selection_delta =
  mean(pair_score × confidence vs selected)
  × selection_scale
  × strategy correlation weight
```

## Strategy weights

`STRATEGY_WEIGHTS["correlation"]` in `optimize.py`:

| Strategy | Default correlation weight |
|----------|---------------------------:|
| cash | 0.05 |
| gpp | 0.20 |
| balanced | 0.10 |
| custom | 0.12 |

Showdown / GPP lean harder on positive correlation and
game-script upside; cash keeps correlation mild and favors
floor / role certainty.

## Soft constraints (not binary bans)

Optional soft limits live on `CorrelationConfig` /
contest profiles. Examples of knobs you can tune without
rewriting rules:

- `selection_scale` — how strongly pairs move opt-score
- structural magnitudes (`qb_own_wr1`, `qb_opp_dst`, …)
- concentration penalties
- empirical blend caps

Callers may add portfolio / contest filters such as
max same-team or max same-game **as soft preferences**.
Do **not** implement hard “QB+WR always / DST never” rules.

## Game-script layer

When `game_script_id` is set (Showdown), structural edges
aligned with that archetype are lightly amplified:

| Script | Amplified rules |
|--------|-----------------|
| shootout / underdog_comeback | QB↔opp WR, WR↔WR, own stacks |
| favorite_controls / low_scoring | RB↔DST, QB↔own DST |

Portfolio construction already distributes lineups across
script allocations; correlation exposure reporting shows
whether the book is over-concentrated on one stack.

## Persistence

Canonical table: `fantasy_football.player_correlation`
(see `schema.py`). Flatten live edges with
`correlation_edges_as_rows()` and upsert via
`fact_player_correlation.py` when you want slate snapshots
stored for auditing / UI reload.

## Modules

| File | Role |
|------|------|
| `correlation.py` | Engine + `CorrelationConfig` |
| `optimize.py` | Weighted selection + lineup payload |
| `portfolio.py` | Candidate fill + exposure summary |
| `fact_player_correlation.py` | Optional DB persistence |
| `CORRELATION.md` | This methodology |

## Tuning

Edit `CorrelationConfig` (or pass `config=` into
`build_correlation_context`) — do not hardcode magnitudes
inside the optimizer. Strategy correlation weight is tuned
in `STRATEGY_WEIGHTS`.
