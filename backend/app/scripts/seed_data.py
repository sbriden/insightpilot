"""
Seed InsightPilot Postgres with sports data.

Run on the API service (Render Shell), from /app:

  python -m app.scripts.seed_data
  python -m app.scripts.seed_data --mode historical
  python -m app.scripts.seed_data --nfl-only --mode incremental
  python -m app.scripts.seed_data --cfb-only
  python -m app.scripts.seed_data --odds-only --leagues nfl,ncaaf

Notes:
  - historical can take a long time and a lot of RAM/disk.
  - Prefer incremental for a first cloud seed, then deepen later.
  - Keep the Shell session open until the script finishes.
"""

from __future__ import annotations

import argparse
import sys
import traceback


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed InsightPilot canonical sports tables."
    )
    parser.add_argument(
        "--mode",
        choices=("incremental", "historical", "reprocess"),
        default="incremental",
        help="Ingest mode for NFL/CFB pipelines (default: incremental).",
    )
    parser.add_argument(
        "--nfl-only",
        action="store_true",
        help="Only run the nflverse fantasy pipeline.",
    )
    parser.add_argument(
        "--cfb-only",
        action="store_true",
        help="Only run the sportsdataverse CFB pipeline.",
    )
    parser.add_argument(
        "--odds-only",
        action="store_true",
        help="Only refresh ScoresAndOdds markets.",
    )
    parser.add_argument(
        "--skip-odds",
        action="store_true",
        help="Skip ScoresAndOdds after NFL/CFB.",
    )
    parser.add_argument(
        "--leagues",
        default="nfl,ncaaf",
        help="Comma-separated ScoresAndOdds leagues (default: nfl,ncaaf).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    run_nfl = not args.cfb_only and not args.odds_only
    run_cfb = not args.nfl_only and not args.odds_only
    run_odds = not args.skip_odds and (
        args.odds_only or not (args.nfl_only or args.cfb_only)
    )
    if args.nfl_only:
        run_cfb = False
        run_odds = not args.skip_odds
    if args.cfb_only:
        run_nfl = False
        run_odds = not args.skip_odds
    if args.odds_only:
        run_nfl = False
        run_cfb = False
        run_odds = True

    print(f"seed_data mode={args.mode}")
    failures = 0

    if run_nfl:
        print("→ nflverse refresh…")
        try:
            from app.sources import data_lifecycle

            result = data_lifecycle.refresh_pipeline(mode=args.mode)
            print(
                "  nflverse:",
                result.get("status"),
                "rows=",
                result.get("row_count_total"),
                "datasets=",
                len(result.get("results") or []),
            )
        except Exception as exc:
            failures += 1
            print("  nflverse FAILED:", exc)
            traceback.print_exc()

    if run_cfb:
        print("→ sportsdataverse (CFB) refresh…")
        try:
            from app.sources import cfb_lifecycle

            result = cfb_lifecycle.refresh_pipeline(mode=args.mode)
            print(
                "  cfb:",
                result.get("status"),
                "rows=",
                result.get("row_count_total"),
                "datasets=",
                len(result.get("results") or []),
            )
        except Exception as exc:
            failures += 1
            print("  cfb FAILED:", exc)
            traceback.print_exc()

    if run_odds:
        leagues = [
            part.strip().lower()
            for part in str(args.leagues).split(",")
            if part.strip()
        ]
        for league in leagues:
            print(f"→ ScoresAndOdds {league}…")
            try:
                if league == "nfl":
                    from app.canonical.odds_scoresandodds import (
                        ingest_nfl_scoresandodds_markets,
                    )

                    result = ingest_nfl_scoresandodds_markets(persist=True)
                elif league == "ncaaf":
                    from app.canonical.cfb.odds_scoresandodds import (
                        ingest_scoresandodds_markets,
                    )

                    result = ingest_scoresandodds_markets(persist=True)
                elif league in {"nba", "nhl", "mlb", "ncaab"}:
                    from app.canonical.sports_odds.odds_scoresandodds import (
                        ingest_scoresandodds_markets,
                    )

                    result = ingest_scoresandodds_markets(
                        league, persist=True
                    )
                else:
                    raise ValueError(f"Unsupported league {league!r}")
                print(
                    f"  {league}: matched=",
                    result.get("matched"),
                    "fetched=",
                    result.get("fetched"),
                )
            except Exception as exc:
                failures += 1
                print(f"  {league} FAILED:", exc)
                traceback.print_exc()

    if failures:
        print(f"seed_data finished with {failures} failure(s).")
        return 1
    print("seed_data finished OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
