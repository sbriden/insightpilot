# Guided Market Slate — implementation report

## Summary

Guided Market Slate sits beside the existing Auto daily generator. Users pick ticket count, exposure, risk, and sports; the backend selects an internal odds-bucket template and walks them through single/parlay requirements using market-implied probabilities only (no model edge).

## Persistence

- **v1:** browser `localStorage` key `ip-guided-slate:v1`
- Server is **stateless**: each mutating call sends the full session blob; response returns the updated session
- **No DB migration** in this pass
- Session shape keeps `template_id` / `template_version` for a future `fact_guided_slate_session` sync without redesign

## Backend files

| File | Role |
|------|------|
| `app/analysis/insights/betting/slate_template.py` | Odds buckets, Low/Medium/High template builders, validation |
| `app/analysis/insights/betting/template_selector.py` | Inventory-aware template scoring + fallback messaging |
| `app/analysis/insights/betting/template_builder.py` | Ticket/leg requirements + stake allocation (sum = exposure) |
| `app/analysis/insights/betting/guided_slate.py` | Session start/select/replace/back/review/confirm |
| `app/sources/router.py` | Guided endpoints under `/daily-slate/guided/*` |
| `tests/test_guided_slate.py` | Deterministic unit/workflow coverage |

## Odds buckets (American)

| Bucket | Range |
|--------|-------|
| strong_favorite | −220 to −150 |
| moderate_favorite | −149 to −110 |
| near_even | −109 to +110 |
| moderate_underdog | +111 to +175 |
| larger_underdog | +176 to +250 |

## Template families (internal; names hidden from UI)

- **Low:** ~75–82% singles / rest 2-leg; favorites + near-even
- **Medium:** ~62–65% singles / parlays including optional 3-leg; mixed buckets
- **High:** ~37–45% singles / heavier parlays; underdogs when inventory allows

Selector fallbacks shrink ticket count for budget, relax buckets via substitutes, and return user-facing copy without template names.

## API

- `POST .../daily-slate/guided/start`
- `POST .../daily-slate/guided/candidates`
- `POST .../daily-slate/guided/select`
- `POST .../daily-slate/guided/replace`
- `POST .../daily-slate/guided/back`
- `POST .../daily-slate/guided/review` (odds-drift alerts)
- `POST .../daily-slate/guided/confirm` (marks complete; no wager placement)

## Frontend

- `DailyBetSlate.tsx` — Auto | Guided Market Slate toggle; Auto path unchanged
- `GuidedMarketSlate.tsx` — config → step picks → review/replace → confirm; localStorage resume
- `services/api.ts` — guided client helpers

## Tests covered

- Bucket eligibility
- Risk family selection (Low vs High composition)
- Stakes sum to exposure; tickets vs picks vs legs
- Budget shrink messaging
- Select / replace / back / confirm flow
- No duplicate candidates across steps
- Session resume round-trip
- Inventory shortfall still yields a template

## Out of scope (follow-ups)

- Automatic wager placement
- Model edge / projection ranking
- Server DB session table
- Games / Markets / Portfolio tab redesign
