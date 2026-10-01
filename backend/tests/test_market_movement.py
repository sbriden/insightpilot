"""Tests for opening vs current market movement."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.analysis.insights.betting.market_movement import (
    build_market_movement,
    classify_move_vs_model,
    spread_to_home_moneyline,
)
from app.analysis.insights.betting.slate import _enrich_event


class MarketMovementTests(unittest.TestCase):
    def test_builds_opening_current_and_moves(self):
        move = build_market_movement(
            opening_spread=-3.0,
            current_spread=-4.5,
            opening_total=47.0,
            current_total=48.5,
        )
        self.assertEqual(move["opening_spread"], -3.0)
        self.assertEqual(move["current_spread"], -4.5)
        self.assertEqual(move["spread_move"], -1.5)
        self.assertEqual(move["total_move"], 1.5)
        self.assertTrue(move["moved"])
        self.assertIsNotNone(move["opening_moneyline"])
        self.assertIsNotNone(move["current_moneyline"])
        self.assertIsNotNone(move["moneyline_move"])
        # Eventual fields are present as stubs.
        self.assertIsNone(move["spread_velocity"])
        self.assertIsNone(move["consensus_move"])

    def test_line_toward_model_when_same_direction(self):
        # Negative spread move = toward home; positive residual = model likes home.
        vs = classify_move_vs_model(
            spread_move=-1.5,
            residual_home=1.2,
        )
        self.assertEqual(vs["label"], "line_toward_model")
        self.assertTrue(vs["aligned"])

    def test_line_away_from_model_when_opposite(self):
        vs = classify_move_vs_model(
            spread_move=1.5,
            residual_home=1.2,
        )
        self.assertEqual(vs["label"], "line_away_from_model")
        self.assertFalse(vs["aligned"])

    def test_moneyline_derived_from_spread(self):
        fav = spread_to_home_moneyline(-3.0)  # home favored
        dog = spread_to_home_moneyline(3.0)
        assert fav is not None and dog is not None
        self.assertLess(fav, 0)
        self.assertGreater(dog, 0)

    def test_seconds_since_move(self):
        moved_at = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        now = datetime(2026, 9, 30, 14, 0, tzinfo=timezone.utc)
        move = build_market_movement(
            opening_spread=-3.0,
            current_spread=-4.0,
            opening_total=45.0,
            current_total=45.0,
            line_moved_at=moved_at.isoformat(),
            now=now,
        )
        self.assertEqual(move["seconds_since_move"], 7200.0)

    def test_enrich_event_exposes_movement_fields(self):
        raw = {
            "event_id": "ip_game_move",
            "season": 2026,
            "week": 4,
            "spread": 4.5,  # nflverse: home favored
            "over_under": 48.5,
            "opening_spread": 3.0,
            "opening_over_under": 47.0,
            "opening_home_implied_total": 25.0,
            "opening_away_implied_total": 22.0,
            "home_implied_total": 26.5,
            "away_implied_total": 22.0,
            "home_team": "BUF",
            "away_team": "MIA",
            "home_team_id": "t-buf",
            "away_team_id": "t-mia",
            "start_time": "2026-09-28",
            "market_timestamp": "2026-09-28T13:00:00",
            "status": "scheduled",
            "source": "nflverse_schedules",
            "line_moved_at": "2026-09-27T18:00:00",
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
        # Event convention: away − home.
        self.assertEqual(event["opening_spread"], -3.0)
        self.assertEqual(event["current_spread"], -4.5)
        self.assertEqual(event["spread_move"], -1.5)
        self.assertEqual(event["total_move"], 1.5)
        self.assertTrue(event["market_movement"]["moved"])

        spread_mkt = next(
            m for m in built["markets"] if m["market_type"] == "spread"
        )
        self.assertIsNotNone(spread_mkt["opening_line"])
        self.assertEqual(spread_mkt["line_move"], -1.5)

        drivers = " ".join(event["model_drivers"])
        self.assertIn("Market move since open", drivers)


if __name__ == "__main__":
    unittest.main()
