"""Unit tests for ScoresAndOdds / Action Network odds ingest."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.sources import scoresandodds as sao


SAMPLE_NCAAF_SCOREBOARD = {
    "league": {
        "name": "ncaaf",
        "current_season": "2026",
        "current_week": 8,
        "current_season_type": "reg",
    },
    "games": [
        {
            "id": 290001,
            "season": 2026,
            "week": 8,
            "type": "reg",
            "status": "scheduled",
            "start_time": "2026-10-22T00:00:00.000Z",
            "home_team_id": 100,
            "away_team_id": 200,
            "teams": [
                {
                    "id": 200,
                    "abbr": "NMSU",
                    "full_name": "New Mexico State Aggies",
                },
                {
                    "id": 100,
                    "abbr": "SHSU",
                    "full_name": "Sam Houston Bearkats",
                },
            ],
            "odds": [
                {
                    "type": "game",
                    "book_id": 15,
                    "spread_home": 2.5,
                    "spread_away": -2.5,
                    "spread_home_line": -105,
                    "total": 45.5,
                    "over": -110,
                    "under": -110,
                    "ml_home": 120,
                    "ml_away": -140,
                    "inserted": "2026-10-21T12:00:00+00:00",
                },
                {
                    "type": "game",
                    "book_id": 30,
                    "spread_home": 3.0,
                    "spread_away": -3.0,
                    "total": 46.0,
                    "ml_home": 115,
                    "ml_away": -135,
                    "inserted": "2026-10-21T12:05:00+00:00",
                },
                {
                    "type": "firsthalf",
                    "book_id": 15,
                    "spread_home": 1.5,
                    "total": 22.5,
                },
            ],
        }
    ],
}

SAMPLE_NFL_SCOREBOARD = {
    "league": {
        "name": "nfl",
        "current_season": "2026",
        "current_week": 7,
        "current_season_type": "reg",
    },
    "games": [
        {
            "id": 401001,
            "season": 2026,
            "week": 7,
            "type": "reg",
            "status": "scheduled",
            "start_time": "2026-10-19T17:00:00.000Z",
            "home_team_id": 10,
            "away_team_id": 20,
            "teams": [
                {
                    "id": 20,
                    "abbr": "NE",
                    "full_name": "New England Patriots",
                },
                {
                    "id": 10,
                    "abbr": "CHI",
                    "full_name": "Chicago Bears",
                },
            ],
            "odds": [
                {
                    "type": "game",
                    "book_id": 15,
                    "spread_home": -3.5,
                    "spread_away": 3.5,
                    "total": 44.5,
                    "ml_home": -175,
                    "ml_away": 150,
                    "inserted": "2026-10-21T12:00:00+00:00",
                },
                {
                    "type": "game",
                    "book_id": 69,
                    "spread_home": -3.0,
                    "total": 45.0,
                    "inserted": "2026-10-21T11:00:00+00:00",
                },
            ],
        }
    ],
}

SAMPLE_NBA_SCOREBOARD = {
    "league": {
        "name": "nba",
        "current_season": "2026",
        "current_week": -1,
        "current_season_type": "reg",
    },
    "games": [
        {
            "id": 501001,
            "season": 2026,
            "week": None,
            "type": "reg",
            "status": "scheduled",
            "start_time": "2026-10-23T20:00:00.000Z",
            "home_team_id": 30,
            "away_team_id": 40,
            "teams": [
                {
                    "id": 40,
                    "abbr": "CHI",
                    "full_name": "Chicago Bulls",
                },
                {
                    "id": 30,
                    "abbr": "DET",
                    "full_name": "Detroit Pistons",
                },
            ],
            "odds": [
                {
                    "type": "game",
                    "book_id": 15,
                    "spread_home": -1.5,
                    "spread_away": 1.5,
                    "total": 240.5,
                    "ml_home": -120,
                    "ml_away": 100,
                    "inserted": "2026-10-23T12:00:00+00:00",
                }
            ],
        }
    ],
}


class ScoresandoddsNormalizeTests(unittest.TestCase):
    def test_normalize_prefers_preferred_book(self):
        rows = sao.normalize_scoreboard_games(
            SAMPLE_NCAAF_SCOREBOARD,
            league="ncaaf",
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["home_abbr"], "SHSU")
        self.assertEqual(row["away_abbr"], "NMSU")
        self.assertEqual(row["week"], 8)
        self.assertEqual(row["spread"], 2.5)
        self.assertEqual(row["over_under"], 45.5)
        self.assertEqual(row["home_moneyline"], 120)
        self.assertEqual(row["book_id"], 15)
        self.assertAlmostEqual(row["home_implied_total"], 21.5)
        self.assertAlmostEqual(row["away_implied_total"], 24.0)
        self.assertEqual(row["source"], "scoresandodds")
        self.assertEqual(row["league"], "ncaaf")

    def test_abbr_aliases_map_to_dim_team(self):
        self.assertEqual(sao.canonical_abbr("BAMA"), "ALA")
        self.assertEqual(sao.canonical_abbr("UCONN"), "CONN")
        self.assertEqual(sao.canonical_abbr("BOISE"), "BOIS")
        self.assertEqual(sao.canonical_abbr("NCST"), "NCSU")
        self.assertEqual(sao.canonical_abbr("JVST"), "JXST")
        self.assertEqual(sao.canonical_abbr("CHA"), "CLT")
        self.assertEqual(sao.canonical_abbr("UMD"), "MD")
        self.assertEqual(sao.canonical_abbr("CC"), "CCU")
        self.assertEqual(sao.canonical_abbr("WF"), "WAKE")
        self.assertEqual(sao.canonical_abbr("SHSU"), "SHSU")
        self.assertEqual(
            sao.canonical_abbr("WSH", league="nfl"),
            "WAS",
        )
        self.assertEqual(
            sao.canonical_abbr("JAC", league="nfl"),
            "JAX",
        )
        self.assertEqual(
            sao.canonical_abbr("LAR", league="nfl"),
            "LA",
        )
        self.assertEqual(
            sao.canonical_abbr("NYGD", league="nfl"),
            "NYG",
        )
        self.assertEqual(
            sao.canonical_abbr("OAK", league="nfl"),
            "LV",
        )

    def test_parse_homepage_openings(self):
        html = """
        <div id="nfl.35986720" class="event-card" data-time="1">
          <table class="event-card-table">
            <tbody>
              <tr class="event-card-row" data-side="away">
                <td>
                  <a href="/nfl/teams/patriots" data-abbr="Patriots">
                    <span>Patriots</span>
                  </a>
                </td>
                <td class="event-card-open">
                  <span class="data-value"> o47.5 </span>
                </td>
              </tr>
              <tr class="event-card-row" data-side="home">
                <td>
                  <a href="/nfl/teams/bears" data-abbr="Bears">
                    <span>Bears</span>
                  </a>
                </td>
                <td class="event-card-open">
                  <span class="data-value"> -1.5 </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        """
        openings = sao.parse_homepage_openings(html, league="nfl")
        self.assertEqual(len(openings), 1)
        row = openings[0]
        self.assertEqual(row["home_abbr"], "CHI")
        self.assertEqual(row["away_abbr"], "NE")
        self.assertEqual(row["opening_spread"], -1.5)
        self.assertEqual(row["opening_over_under"], 47.5)
        self.assertEqual(row["opening_source"], "scoresandodds_open")

    def test_opening_from_earliest_odds_quote(self):
        rows = sao.normalize_scoreboard_games(
            SAMPLE_NFL_SCOREBOARD,
            league="nfl",
        )
        self.assertEqual(len(rows), 1)
        # Preferred book 15 is later; earliest preferred is book 69.
        self.assertEqual(rows[0]["opening_spread"], -3.0)
        self.assertEqual(rows[0]["opening_over_under"], 45.0)
        self.assertEqual(
            rows[0]["opening_source"],
            "actionnetwork_earliest",
        )

    def test_fetch_rows_uses_current_week_when_unspecified(self):
        with patch.object(
            sao,
            "fetch_scoreboard",
            return_value=SAMPLE_NCAAF_SCOREBOARD,
        ) as fetch, patch.object(
            sao,
            "_attach_homepage_openings",
            side_effect=lambda rows, **_kwargs: rows,
        ):
            rows, meta = sao.fetch_odds_rows("ncaaf")
        fetch.assert_called_once()
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta["week"], 8)
        self.assertEqual(meta["row_count"], 1)
        self.assertEqual(meta["league"], "ncaaf")

    def test_cfb_ingest_matches_dim_abbreviations(self):
        from app.canonical.cfb import odds_scoresandodds as ingest

        with patch.object(
            sao,
            "fetch_odds_rows",
            return_value=(
                sao.normalize_scoreboard_games(
                    SAMPLE_NCAAF_SCOREBOARD,
                    league="ncaaf",
                ),
                {"season": 2026, "week": 8},
            ),
        ), patch.object(
            ingest,
            "_matchup_lookup_for_season",
            return_value={(8, "SHSU", "NMSU"): "ip_game_test"},
        ), patch.object(
            ingest,
            "upsert_fact_game_market",
        ) as upsert, patch.object(
            ingest,
            "clear_fact_game_market_cache",
        ):
            result = ingest.ingest_scoresandodds_markets(
                season=2026,
                weeks=[8],
                persist=True,
            )

        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["fetched"], 1)
        self.assertTrue(result["persisted"])
        upsert.assert_called_once()
        frame = upsert.call_args[0][0]
        self.assertEqual(frame.iloc[0]["game_id"], "ip_game_test")
        self.assertEqual(frame.iloc[0]["source"], "scoresandodds")
        self.assertEqual(frame.iloc[0]["spread"], 2.5)

    def test_nfl_normalize_and_ingest(self):
        from app.canonical import odds_scoresandodds as ingest

        rows = sao.normalize_scoreboard_games(
            SAMPLE_NFL_SCOREBOARD,
            league="nfl",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["home_abbr"], "CHI")
        self.assertEqual(rows[0]["away_abbr"], "NE")
        self.assertEqual(rows[0]["spread"], -3.5)
        self.assertEqual(rows[0]["book_id"], 15)
        self.assertEqual(rows[0]["league"], "nfl")

        with patch.object(
            sao,
            "fetch_nfl_odds_rows",
            return_value=(rows, {"season": 2026, "week": 7}),
        ), patch.object(
            ingest,
            "_matchup_lookup_for_season",
            return_value={(7, "CHI", "NE"): "ip_nfl_game"},
        ), patch.object(
            ingest,
            "upsert_fact_game_market",
        ) as upsert, patch.object(
            ingest,
            "clear_fact_game_market_cache",
        ):
            result = ingest.ingest_nfl_scoresandodds_markets(
                season=2026,
                weeks=[7],
                persist=True,
            )

        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["league"], "nfl")
        self.assertTrue(result["persisted"])
        upsert.assert_called_once()
        frame = upsert.call_args[0][0]
        self.assertEqual(frame.iloc[0]["game_id"], "ip_nfl_game")
        self.assertEqual(frame.iloc[0]["season_type"], "REG")
        self.assertEqual(frame.iloc[0]["spread"], -3.5)
        self.assertEqual(frame.iloc[0]["opening_spread"], -3.0)
        self.assertEqual(frame.iloc[0]["opening_over_under"], 45.0)

    def test_nba_normalize_clears_invalid_week(self):
        meta = sao.scoreboard_meta(
            SAMPLE_NBA_SCOREBOARD,
            league="nba",
        )
        self.assertIsNone(meta["week"])
        self.assertEqual(meta["schedule_mode"], "slate")

        rows = sao.normalize_scoreboard_games(
            SAMPLE_NBA_SCOREBOARD,
            league="nba",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["league"], "nba")
        self.assertEqual(rows[0]["home_abbr"], "DET")
        self.assertEqual(rows[0]["away_abbr"], "CHI")
        self.assertIsNone(rows[0]["week"])
        self.assertEqual(rows[0]["spread"], -1.5)
        self.assertEqual(rows[0]["over_under"], 240.5)

    def test_slate_fetch_ignores_weeks(self):
        with patch.object(
            sao,
            "fetch_scoreboard",
            return_value=SAMPLE_NBA_SCOREBOARD,
        ) as fetch, patch.object(
            sao,
            "_attach_homepage_openings",
            side_effect=lambda rows, **_kwargs: rows,
        ):
            rows, meta = sao.fetch_odds_rows(
                "nba",
                weeks=[3],
            )
        fetch.assert_called_once()
        self.assertIsNone(fetch.call_args.kwargs.get("week"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(meta["schedule_mode"], "slate")
        self.assertEqual(meta["row_count"], 1)

    def test_sports_odds_ingest_keys_by_provider_id(self):
        from app.canonical.sports_odds import (
            odds_scoresandodds as ingest,
        )

        rows = sao.normalize_scoreboard_games(
            SAMPLE_NBA_SCOREBOARD,
            league="nba",
        )
        with patch.object(
            sao,
            "fetch_odds_rows",
            return_value=(rows, {"season": 2026, "schedule_mode": "slate"}),
        ), patch.object(
            ingest,
            "upsert_fact_game_market",
        ) as upsert, patch.object(
            ingest,
            "clear_fact_game_market_cache",
        ):
            result = ingest.ingest_scoresandodds_markets(
                "nba",
                season=2026,
                persist=True,
            )

        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["league"], "nba")
        self.assertTrue(result["persisted"])
        upsert.assert_called_once()
        frame = upsert.call_args[0][0]
        self.assertEqual(frame.iloc[0]["game_id"], "sao:nba:501001")
        self.assertEqual(frame.iloc[0]["game_date"], "2026-10-23")
        self.assertEqual(frame.iloc[0]["home_abbr"], "DET")
        self.assertEqual(frame.iloc[0]["spread"], -1.5)

    def test_supported_slate_leagues_registered(self):
        for league in ("nba", "nhl", "mlb", "ncaab"):
            config = sao.get_league(league)
            self.assertEqual(config.schedule_mode, "slate")
            self.assertTrue(config.homepage.endswith(f"/{league}"))


if __name__ == "__main__":
    unittest.main()
