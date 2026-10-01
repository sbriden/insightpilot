"""Unit tests for Sports Betting pricing helpers and slate builders."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting.pricing import (
    american_to_implied_prob,
    expected_value,
    implied_prob_to_american,
    spread_to_cover_probability,
    total_to_over_probability,
)
from app.analysis.insights.betting.game_scripts import (
    normalize_script_weights,
    project_game_scripts,
)
from app.analysis.insights.betting.player_context import (
    INJURY_MARKET_WEIGHT,
    apply_injury_adjustment,
)
from app.analysis.insights.betting.slate import (
    _enrich_event,
    build_betting_slate,
    find_betting_event_by_matchup,
)


class BettingPricingTests(unittest.TestCase):
    def test_american_favorites(self):
        p = american_to_implied_prob(-110)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertAlmostEqual(p, 0.5238, places=3)

    def test_fair_price_round_trip(self):
        fair = implied_prob_to_american(0.6)
        self.assertIsNotNone(fair)
        assert fair is not None
        self.assertLess(fair, 0)

    def test_expected_value_positive(self):
        # Model 60% at -110 should be +EV.
        ev = expected_value(0.60, -110)
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertGreater(ev, 0.0)

    def test_total_over_probability(self):
        p = total_to_over_probability(51.0, 47.5)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertGreater(p, 0.5)

    def test_spread_cover_probability(self):
        # Model more home-favored than market.
        p = spread_to_cover_probability(-5.0, -3.0)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertGreater(p, 0.5)


class BettingGameScriptTests(unittest.TestCase):
    def test_favorite_blowout_raises_control_and_lowers_upset(self):
        scripts = project_game_scripts(
            projected_home=31.0,
            projected_away=17.0,
            projected_total=48.0,
            market_total=47.5,
            market_spread=-7.0,
            home_team="BUF",
            away_team="MIA",
        )
        by_id = {row["script_id"]: row for row in scripts}
        self.assertIn("favorite_controls", by_id)
        self.assertIn("contrarian_upset", by_id)
        self.assertGreater(
            by_id["favorite_controls"]["probability"],
            by_id["contrarian_upset"]["probability"],
        )
        self.assertEqual(by_id["favorite_controls"]["favorite"], "BUF")

    def test_high_total_raises_shootout(self):
        low = project_game_scripts(
            projected_home=20.0,
            projected_away=17.0,
            projected_total=37.0,
            market_spread=-3.0,
            home_team="KC",
            away_team="DEN",
        )
        high = project_game_scripts(
            projected_home=31.0,
            projected_away=28.0,
            projected_total=59.0,
            market_spread=-3.0,
            home_team="KC",
            away_team="DEN",
        )
        low_shoot = next(
            row for row in low if row["script_id"] == "shootout"
        )
        high_shoot = next(
            row for row in high if row["script_id"] == "shootout"
        )
        self.assertGreater(
            high_shoot["probability"],
            low_shoot["probability"],
        )

    def test_enrich_event_includes_game_scripts(self):
        raw = {
            "event_id": "ip_game_test",
            "season": 2026,
            "week": 3,
            "spread": -3.5,
            "over_under": 47.5,
            "home_implied_total": 25.5,
            "away_implied_total": 22.0,
            "home_team": "BUF",
            "away_team": "MIA",
            "home_team_id": "t-buf",
            "away_team_id": "t-mia",
            "start_time": "2026-09-28T13:00:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=None,
        ):
            built = _enrich_event(
                raw,
                recent_ppg={"t-buf": 28.0, "t-mia": 21.0},
            )
        scripts = built["event"].get("game_scripts") or []
        self.assertGreaterEqual(len(scripts), 6)
        labels = {row["label"] for row in scripts}
        self.assertIn("Favorite controls game", labels)
        self.assertIn("Shootout", labels)
        self.assertIn("Contrarian upset", labels)

    def test_enrich_event_uses_frozen_snapshot_only(self):
        raw = {
            "event_id": "ip_game_atl_gb",
            "season": 2026,
            "week": 3,
            "spread": -5.5,
            "over_under": 42.5,
            "home_implied_total": 24.0,
            "away_implied_total": 18.5,
            "home_team": "GB",
            "away_team": "ATL",
            "home_team_id": "t-gb",
            "away_team_id": "t-atl",
            "start_time": "2026-09-28T20:20:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        frozen = {
            "game_id": "ip_game_atl_gb",
            "projected_home_score": 23.1,
            "projected_away_score": 19.4,
            "projected_total": 42.5,
            "model_spread": -3.7,
            "frozen": True,
        }
        # Live PPG + active calibration would otherwise shift scores.
        calibration = {
            "active": True,
            "total_bias": 4.0,
            "spread_bias": -2.0,
        }
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=frozen,
        ):
            built = _enrich_event(
                raw,
                recent_ppg={"t-gb": 30.0, "t-atl": 14.0},
                calibration=calibration,
            )
        event = built["event"]
        self.assertEqual(event["projected_home_score"], 23.1)
        self.assertEqual(event["projected_away_score"], 19.4)
        self.assertEqual(event["projected_total"], 42.5)
        self.assertEqual(event["model_spread"], -3.7)
        self.assertTrue(
            any(
                "locked pregame projection" in driver.lower()
                for driver in event["model_drivers"]
            )
        )

    def test_enrich_event_unfrozen_snapshot_does_not_block_recompute(self):
        raw = {
            "event_id": "ip_game_atl_gb",
            "season": 2026,
            "week": 3,
            "spread": -5.5,
            "over_under": 42.5,
            "home_implied_total": 24.0,
            "away_implied_total": 18.5,
            "home_team": "GB",
            "away_team": "ATL",
            "home_team_id": "t-gb",
            "away_team_id": "t-atl",
            "start_time": "2026-09-28T20:20:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        unfrozen = {
            "game_id": "ip_game_atl_gb",
            "projected_home_score": 23.1,
            "projected_away_score": 19.4,
            "projected_total": 42.5,
            "model_spread": -3.7,
            "frozen": False,
        }
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=unfrozen,
        ):
            built = _enrich_event(
                raw,
                recent_ppg={"t-gb": 30.0, "t-atl": 14.0},
            )
        event = built["event"]
        # Live recompute should not echo the stale unfrozen snapshot.
        self.assertNotEqual(event["projected_home_score"], 23.1)
        self.assertFalse(
            any(
                "locked pregame projection" in driver.lower()
                for driver in event["model_drivers"]
            )
        )

    def test_normalize_script_weights_sums_to_one_and_count(self):
        scripts = project_game_scripts(
            projected_home=28.0,
            projected_away=21.0,
            projected_total=49.0,
            market_total=47.5,
            market_spread=-6.5,
            home_team="BUF",
            away_team="MIA",
        )
        allocated = normalize_script_weights(
            scripts,
            lineup_count=20,
        )
        self.assertEqual(len(allocated), 6)
        self.assertAlmostEqual(
            sum(row["weight"] for row in allocated),
            1.0,
            places=3,
        )
        self.assertEqual(
            sum(row["lineup_count"] for row in allocated),
            20,
        )

    @patch(
        "app.analysis.insights.betting.slate.build_betting_slate"
    )
    def test_find_betting_event_by_matchup(self, mock_slate):
        mock_slate.return_value = {
            "events": [
                {
                    "event_id": "ip_game_atl_gb",
                    "home_team": "GB",
                    "away_team": "ATL",
                    "market_spread": -5.5,
                    "market_total": 42.5,
                    "game_scripts": [
                        {
                            "script_id": "low_scoring",
                            "probability": 0.49,
                            "favorite": "GB",
                            "underdog": "ATL",
                        }
                    ],
                }
            ]
        }
        detail = find_betting_event_by_matchup(
            home_team="GB",
            away_team="ATL",
            season=2026,
            week=3,
        )
        self.assertIsNotNone(detail)
        event = detail["event"]
        self.assertEqual(event["event_id"], "ip_game_atl_gb")
        self.assertEqual(event["market_total"], 42.5)
        # Team order mismatch still resolves.
        swapped = find_betting_event_by_matchup(
            home_team="ATL",
            away_team="GB",
            season=2026,
            week=3,
        )
        self.assertEqual(
            swapped["event"]["event_id"], "ip_game_atl_gb"
        )


class BettingInjuryContextTests(unittest.TestCase):
    def test_apply_injury_adjustment(self):
        self.assertEqual(apply_injury_adjustment(27.4, -1.8), 25.6)
        self.assertIsNone(apply_injury_adjustment(None, -1.0))

    def test_enrich_event_applies_qb_out_adjustment(self):
        raw = {
            "event_id": "ip_game_test",
            "season": 2026,
            "week": 3,
            "spread": -3.5,
            "over_under": 47.5,
            "home_implied_total": 25.5,
            "away_implied_total": 22.0,
            "home_team": "BUF",
            "away_team": "MIA",
            "home_team_id": "t-buf",
            "away_team_id": "t-mia",
            "home_team_name": "Buffalo Bills",
            "away_team_name": "Miami Dolphins",
            "start_time": "2026-09-28",
            "market_timestamp": "2026-09-28T13:00:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        qb_out_impact = round(-5.5 * INJURY_MARKET_WEIGHT, 2)
        context = {
            "season": 2026,
            "week": 3,
            "by_team": {
                "t-buf": {
                    "adjustment_pts": qb_out_impact,
                    "opponent_adjustment_pts": 0.0,
                    "raw_adjustment_pts": -5.5,
                    "raw_opponent_adjustment_pts": 0.0,
                    "injuries": [
                        {
                            "player_id": "p-allen",
                            "player_name": "Josh Allen",
                            "team_id": "t-buf",
                            "position": "QB",
                            "depth_order": 1,
                            "depth_label": "QB1",
                            "game_status": "Out",
                            "injury_type": "Elbow",
                            "is_starter": True,
                            "projection_impact_pts": qb_out_impact,
                            "own_score_delta": qb_out_impact,
                            "opponent_score_delta": 0.0,
                        }
                    ],
                    "drivers": [
                        "Josh Allen (QB1) listed Out — Elbow; "
                        f"own projection {qb_out_impact:+g} pts"
                    ],
                }
            },
        }
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=None,
        ):
            baseline = _enrich_event(
                raw,
                recent_ppg={"t-buf": 28.0, "t-mia": 21.0},
            )
            adjusted = _enrich_event(
                raw,
                recent_ppg={"t-buf": 28.0, "t-mia": 21.0},
                player_context=context,
            )
        self.assertAlmostEqual(
            adjusted["event"]["projected_home_score"],
            baseline["event"]["projected_home_score"] + qb_out_impact,
            places=1,
        )
        self.assertEqual(
            adjusted["event"]["injury_adjustment_home"],
            qb_out_impact,
        )
        self.assertTrue(adjusted["event"]["injuries"])
        self.assertEqual(adjusted["event"]["injuries"][0]["team"], "BUF")
        signal_types = {
            signal["signal_type"] for signal in adjusted["signals"]
        }
        self.assertIn("INJURY_IMPACT", signal_types)
        self.assertTrue(
            any(
                "Josh Allen" in driver
                for driver in adjusted["event"]["model_drivers"]
            )
        )

    def test_spread_opportunity_language(self):
        raw = {
            "event_id": "ip_game_test",
            "season": 2026,
            "week": 3,
            "spread": -7.0,
            "over_under": 47.5,
            "home_implied_total": 27.25,
            "away_implied_total": 20.25,
            "home_team": "BUF",
            "away_team": "MIA",
            "home_team_id": "t-buf",
            "away_team_id": "t-mia",
            "start_time": "2026-09-28T13:00:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        # Strong home PPG pulls model margin past the market -7.
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=None,
        ):
            built = _enrich_event(
                raw,
                recent_ppg={"t-buf": 34.0, "t-mia": 14.0},
            )
        spread = next(
            market
            for market in built["markets"]
            if market["market_type"] == "spread"
        )
        self.assertIsNotNone(spread.get("opportunity"))
        self.assertIn("projected to win by", spread["opportunity"])
        self.assertIn("increased likelihood", spread["opportunity"])

    @patch("nflreadpy.get_current_week", return_value=3)
    @patch("nflreadpy.get_current_season", return_value=2026)
    def test_current_week_prefers_nflverse_over_latest_market_week(
        self,
        _mock_season,
        _mock_week,
    ):
        from app.analysis.insights.betting.slate import (
            _current_betting_week,
        )

        self.assertEqual(
            _current_betting_week(
                season=2026,
                available_weeks=[1, 2, 3, 4],
            ),
            3,
        )


class BettingSlateTests(unittest.TestCase):
    def test_enrich_event_emits_three_markets(self):
        raw = {
            "event_id": "ip_game_test",
            "season": 2026,
            "week": 3,
            "spread": -3.5,
            "over_under": 47.5,
            "home_implied_total": 25.5,
            "away_implied_total": 22.0,
            "home_team": "BUF",
            "away_team": "MIA",
            "home_team_id": "t-buf",
            "away_team_id": "t-mia",
            "home_team_name": "Buffalo Bills",
            "away_team_name": "Miami Dolphins",
            "start_time": "2026-09-28",
            "market_timestamp": "2026-09-28T13:00:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
        }
        with patch(
            "app.analysis.insights.betting.slate._load_projection_snapshot",
            return_value=None,
        ):
            built = _enrich_event(
                raw,
                recent_ppg={"t-buf": 28.0, "t-mia": 21.0},
            )
        event = built["event"]
        self.assertEqual(event["start_time"], "2026-09-28T13:00:00")
        markets = built["markets"]
        self.assertEqual(event["label"], "MIA @ BUF")
        self.assertIsNotNone(event["projected_total"])
        types = {m["market_type"] for m in markets}
        self.assertEqual(
            types,
            {"spread", "total", "moneyline"},
        )
        for market in markets:
            self.assertIn(market["confidence"], {
                "High",
                "Moderate",
                "Low",
            })
            self.assertIsNotNone(market["model_probability"])

        # Residual architecture: projection = market + residual.
        residuals = event.get("residuals") or {}
        self.assertEqual(
            residuals.get("architecture"),
            "market + residual",
        )
        self.assertIsNotNone(event.get("residual_home"))
        self.assertIsNotNone(event.get("residual_away"))
        # PPG fallback: home 28 vs market 25.5 → raw +2.5;
        # away 21 vs market 22 → raw -1.0. Low confidence
        # shrinks at 15%.
        self.assertAlmostEqual(
            event["projected_home_score"],
            round(25.5 + 0.15 * (28.0 - 25.5), 1),
            places=1,
        )
        self.assertAlmostEqual(
            event["projected_away_score"],
            round(22.0 + 0.15 * (21.0 - 22.0), 1),
            places=1,
        )
    @patch("app.analysis.insights.betting.slate.load_week_player_context")
    @patch("app.analysis.insights.betting.slate.load_team_strength_context")
    @patch("app.analysis.insights.betting.slate._load_events")
    def test_build_slate_summary(
        self,
        mock_events,
        mock_strength,
        mock_injuries,
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
        self.assertEqual(slate["game_count"], 1)
        self.assertEqual(slate["market_count"], 3)
        self.assertEqual(slate["sport"], "NFL")
        self.assertTrue(slate["markets"])
        self.assertEqual(slate["injury_report_week"], 3)
        self.assertIn(
            "model residual",
            slate["source_note"],
        )
        self.assertIn(
            "market baseline",
            slate["source_note"],
        )


if __name__ == "__main__":
    unittest.main()
