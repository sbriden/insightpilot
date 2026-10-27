"""Unit tests for NFL/CFB sport resolution in Sports Betting."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.analysis.insights.betting.betting_sport import (
    normalize_betting_sport,
    resolve_betting_sport,
)
from app.analysis.insights.betting.player_context import (
    load_week_player_context,
)
from app.analysis.insights.betting.slate import (
    _load_events,
    build_betting_slate,
    list_betting_weeks,
)
from app.canonical.cfb.schema import COLLEGE_SCHEMA
from app.canonical.schema import FANTASY_SCHEMA


class BettingSportResolverTests(unittest.TestCase):
    def test_resolve_nfl_defaults(self):
        config = resolve_betting_sport(None)
        self.assertEqual(config.id, "NFL")
        self.assertEqual(config.schema, FANTASY_SCHEMA)
        self.assertEqual(config.slate_prefix, "nfl")
        self.assertEqual(config.source_label, "nflverse_schedules")
        self.assertTrue(config.has_opening_lines)
        self.assertTrue(config.has_injury_context)
        self.assertTrue(config.has_epa_features)

    def test_resolve_cfb(self):
        config = resolve_betting_sport("CFB")
        self.assertEqual(config.id, "CFB")
        self.assertEqual(config.schema, COLLEGE_SCHEMA)
        self.assertEqual(config.slate_prefix, "cfb")
        self.assertEqual(config.source_label, "sportsdataverse_cfb")
        self.assertTrue(config.has_opening_lines)
        self.assertFalse(config.has_injury_context)
        self.assertFalse(config.has_epa_features)

    def test_normalize_aliases(self):
        self.assertEqual(normalize_betting_sport("ncaaf"), "CFB")
        self.assertEqual(normalize_betting_sport("college"), "CFB")
        self.assertEqual(normalize_betting_sport("nfl"), "NFL")

    def test_unsupported_sport_raises(self):
        with self.assertRaises(ValueError):
            resolve_betting_sport("NBA")


class BettingSportSlateTests(unittest.TestCase):
    @patch("app.analysis.insights.betting.slate.engine")
    def test_list_weeks_uses_college_schema_for_cfb(self, mock_engine):
        connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = (
            connection
        )
        connection.execute.return_value.fetchall.return_value = [
            (1,),
            (2,),
            (3,),
        ]

        with patch(
            "app.analysis.insights.betting.slate._current_betting_week",
            return_value=3,
        ):
            result = list_betting_weeks(season=2025, sport="CFB")

        self.assertEqual(result["sport"], "CFB")
        self.assertEqual(result["league"], "CFB")
        self.assertEqual(result["season"], 2025)
        self.assertEqual(result["weeks"], [1, 2, 3])
        self.assertEqual(result["current_week"], 3)

        sql = str(connection.execute.call_args[0][0])
        self.assertIn(f"{COLLEGE_SCHEMA}.dim_game", sql)
        self.assertNotIn(f"{FANTASY_SCHEMA}.dim_game", sql)

    @patch("app.analysis.insights.betting.slate.engine")
    def test_list_weeks_uses_fantasy_schema_for_nfl(self, mock_engine):
        connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = (
            connection
        )
        connection.execute.return_value.fetchall.return_value = [
            (1,),
            (2,),
        ]

        with patch(
            "app.analysis.insights.betting.slate._current_betting_week",
            return_value=2,
        ):
            result = list_betting_weeks(season=2026, sport="NFL")

        self.assertEqual(result["sport"], "NFL")
        self.assertEqual(result["weeks"], [1, 2])
        sql = str(connection.execute.call_args[0][0])
        self.assertIn(f"{FANTASY_SCHEMA}.dim_game", sql)

    @patch("app.analysis.insights.betting.slate.engine")
    def test_load_events_cfb_selects_opening_lines(self, mock_engine):
        connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = (
            connection
        )
        connection.execute.return_value.mappings.return_value = [
            {
                "event_id": "cfb_g1",
                "season": 2025,
                "week": 4,
                "spread": -7.0,
                "over_under": 52.5,
                "home_implied_total": 29.75,
                "away_implied_total": 22.75,
                "opening_spread": -6.5,
                "opening_over_under": 51.5,
                "opening_home_implied_total": 29.0,
                "opening_away_implied_total": 22.5,
                "opening_captured_at": "2025-09-18T12:00:00Z",
                "line_moved_at": None,
                "market_timestamp": None,
                "source": "scoresandodds",
                "start_time": "2025-09-20",
                "status": "scheduled",
                "home_score": None,
                "away_score": None,
                "home_team_id": "ht",
                "home_team": "ALA",
                "home_team_name": "Alabama",
                "away_team_id": "at",
                "away_team": "UGA",
                "away_team_name": "Georgia",
            }
        ]

        config = resolve_betting_sport("CFB")
        rows = _load_events(
            season=2025,
            week=4,
            sport_config=config,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_id"], "cfb_g1")
        self.assertEqual(rows[0]["opening_spread"], -6.5)
        sql = str(connection.execute.call_args[0][0])
        self.assertIn(f"{COLLEGE_SCHEMA}.dim_game", sql)
        self.assertIn(f"{COLLEGE_SCHEMA}.fact_game_market", sql)
        self.assertIn("m.opening_spread", sql)
        self.assertNotIn(
            "NULL::double precision AS opening_spread",
            sql,
        )

    @patch("app.analysis.insights.betting.slate.engine")
    def test_load_events_nfl_selects_opening_lines(self, mock_engine):
        connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = (
            connection
        )
        connection.execute.return_value.mappings.return_value = []

        config = resolve_betting_sport("NFL")
        _load_events(season=2026, week=3, sport_config=config)

        sql = str(connection.execute.call_args[0][0])
        self.assertIn(f"{FANTASY_SCHEMA}.dim_game", sql)
        self.assertIn(f"{FANTASY_SCHEMA}.fact_game_market", sql)
        self.assertIn("m.opening_spread", sql)

    def test_player_context_empty_for_cfb(self):
        result = load_week_player_context(
            season=2025,
            week=4,
            sport="CFB",
        )
        self.assertEqual(result["sport"], "CFB")
        self.assertFalse(result["available"])
        self.assertEqual(result["teams"], {})

    @patch("app.analysis.insights.betting.slate._load_qualification_thresholds")
    @patch("app.analysis.insights.betting.slate._load_context_ablation")
    @patch("app.analysis.insights.betting.slate.rest_days_by_game")
    @patch("app.analysis.insights.betting.slate._load_score_distribution")
    @patch("app.analysis.insights.betting.slate._load_residual_challenger")
    @patch("app.analysis.insights.betting.slate._load_edge_confidence")
    @patch("app.analysis.insights.betting.slate._load_probability_calibrations")
    @patch("app.analysis.insights.betting.slate._load_calibration_feedback")
    @patch("app.analysis.insights.betting.slate.load_week_player_context")
    @patch("app.analysis.insights.betting.slate.load_team_strength_context")
    @patch("app.analysis.insights.betting.slate._load_events")
    def test_build_slate_cfb_payload(
        self,
        mock_events,
        mock_strength,
        mock_injuries,
        mock_calibration,
        mock_prob_cal,
        mock_edge,
        mock_challenger,
        mock_score_dist,
        mock_rest,
        mock_ablation,
        mock_thresholds,
    ):
        mock_strength.return_value = {
            "profiles": {},
            "league_avg_ppg": 28.0,
            "games_used": 0,
            "sport": "CFB",
        }
        mock_injuries.return_value = {
            "season": 2025,
            "week": 4,
            "teams": {},
            "sport": "CFB",
            "available": False,
        }
        mock_calibration.return_value = None
        mock_prob_cal.return_value = {}
        mock_edge.return_value = None
        mock_challenger.return_value = None
        mock_score_dist.return_value = None
        mock_rest.return_value = {}
        mock_ablation.return_value = None
        mock_thresholds.return_value = None
        mock_events.return_value = [
            {
                "event_id": "cfb_g1",
                "season": 2025,
                "week": 4,
                "spread": -3.5,
                "over_under": 52.5,
                "home_implied_total": 28.0,
                "away_implied_total": 24.5,
                "home_team": "ALA",
                "away_team": "UGA",
                "home_team_id": "ht",
                "away_team_id": "at",
                # Odds scrape time must not replace schedule date.
                "market_timestamp": "2025-09-17T16:37:50",
                "start_time": "2025-09-20",
                "status": "scheduled",
                "source": "sportsdataverse_cfb",
            }
        ]

        slate = build_betting_slate(
            season=2025,
            week=4,
            sport="CFB",
        )

        self.assertEqual(slate["sport"], "CFB")
        self.assertEqual(slate["league"], "CFB")
        self.assertEqual(slate["slate_id"], "cfb-2025-w4")
        self.assertEqual(slate["source"], "sportsdataverse_cfb")
        self.assertIn("College Football", slate["source_note"])
        self.assertEqual(slate["events"][0]["start_time"], "2025-09-20")
        mock_strength.assert_called_once()
        strength_kwargs = mock_strength.call_args.kwargs
        self.assertEqual(strength_kwargs["sport"].id, "CFB")
        mock_injuries.assert_called_once()
        self.assertEqual(
            mock_injuries.call_args.kwargs["sport"],
            "CFB",
        )
        mock_events.assert_called_once()
        self.assertEqual(
            mock_events.call_args.kwargs["sport_config"].id,
            "CFB",
        )

    @patch("app.analysis.insights.betting.slate._load_qualification_thresholds")
    @patch("app.analysis.insights.betting.slate._load_context_ablation")
    @patch("app.analysis.insights.betting.slate.rest_days_by_game")
    @patch("app.analysis.insights.betting.slate._load_score_distribution")
    @patch("app.analysis.insights.betting.slate._load_residual_challenger")
    @patch("app.analysis.insights.betting.slate._load_edge_confidence")
    @patch("app.analysis.insights.betting.slate._load_probability_calibrations")
    @patch("app.analysis.insights.betting.slate._load_calibration_feedback")
    @patch("app.analysis.insights.betting.slate.load_week_player_context")
    @patch("app.analysis.insights.betting.slate.load_team_strength_context")
    @patch("app.analysis.insights.betting.slate._load_events")
    def test_build_slate_nfl_default_regression(
        self,
        mock_events,
        mock_strength,
        mock_injuries,
        mock_calibration,
        mock_prob_cal,
        mock_edge,
        mock_challenger,
        mock_score_dist,
        mock_rest,
        mock_ablation,
        mock_thresholds,
    ):
        mock_strength.return_value = {
            "profiles": {},
            "league_avg_ppg": 22.5,
            "games_used": 0,
        }
        mock_injuries.return_value = {
            "season": 2026,
            "week": 3,
            "by_team": {},
        }
        mock_calibration.return_value = None
        mock_prob_cal.return_value = {}
        mock_edge.return_value = None
        mock_challenger.return_value = None
        mock_score_dist.return_value = None
        mock_rest.return_value = {}
        mock_ablation.return_value = None
        mock_thresholds.return_value = None
        mock_events.return_value = [
            {
                "event_id": "g1",
                "season": 2026,
                "week": 3,
                "spread": -3.5,
                "over_under": 47.5,
                "home_implied_total": 25.5,
                "away_implied_total": 22.0,
                "home_team": "BUF",
                "away_team": "MIA",
                "home_team_id": "t1",
                "away_team_id": "t2",
                "start_time": "2026-09-28",
                "status": "scheduled",
                "source": "nflverse_schedules",
            }
        ]

        slate = build_betting_slate(season=2026, week=3)

        self.assertEqual(slate["sport"], "NFL")
        self.assertEqual(slate["slate_id"], "nfl-2026-w3")
        self.assertEqual(slate["source"], "nflverse_schedules")
        mock_events.assert_called_once()
        self.assertEqual(
            mock_events.call_args.kwargs["sport_config"].id,
            "NFL",
        )


if __name__ == "__main__":
    unittest.main()
