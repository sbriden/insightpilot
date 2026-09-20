"""Tests for InsightPilot fantasy_signal generation."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.analytics.fantasy_signal import (
    SIGNAL_TYPES,
    build_fantasy_signal,
)
from app.canonical.ids import (
    is_signal_id,
    make_player_id,
    make_signal_id,
    player_resolution_key,
    signal_resolution_key,
)


class FantasySignalTests(unittest.TestCase):

    def test_signal_ids_are_stable_and_wide(self):
        key = signal_resolution_key(
            player_id="ip_player_00000001",
            season=2025,
            week=15,
            signal_type="SIT",
        )
        first = make_signal_id(key)
        second = make_signal_id(key)
        self.assertEqual(first, second)
        self.assertTrue(is_signal_id(first))
        self.assertTrue(first.startswith("ip_signal_"))
        self.assertEqual(len(first), len("ip_signal_") + 16)

        other = make_signal_id(
            signal_resolution_key(
                player_id="ip_player_00000002",
                season=2025,
                week=15,
                signal_type="SIT",
            )
        )
        self.assertNotEqual(first, other)

    def test_emits_typed_signals_from_profile(self):
        player_id = make_player_id(
            player_resolution_key(gsis_id="00-0037777")
        )

        # Breakout / waiver / surge style profile
        surge = {
            "player_id": player_id,
            "season": 2024,
            "week": 4,
            "production_score": 40.0,
            "opportunity_score": 78.0,
            "efficiency_score": 62.0,
            "trend_score": 72.0,
            "matchup_score": 60.0,
            "environment_score": 58.0,
            "risk_score": 20.0,
            "fantasy_value_score": 68.0,
        }
        # Sell-high / regression style profile
        sell = {
            "player_id": make_player_id(
                player_resolution_key(gsis_id="00-0037778")
            ),
            "season": 2024,
            "week": 4,
            "production_score": 82.0,
            "opportunity_score": 42.0,
            "efficiency_score": 38.0,
            "trend_score": 30.0,
            "matchup_score": 40.0,
            "environment_score": 50.0,
            "risk_score": 25.0,
            "fantasy_value_score": 48.0,
        }
        # Sit / high risk
        sit = {
            "player_id": make_player_id(
                player_resolution_key(gsis_id="00-0037779")
            ),
            "season": 2024,
            "week": 4,
            "production_score": 55.0,
            "opportunity_score": 50.0,
            "efficiency_score": 50.0,
            "trend_score": 50.0,
            "matchup_score": 40.0,
            "environment_score": 45.0,
            "risk_score": 85.0,
            "fantasy_value_score": 35.0,
        }

        profiles = pd.DataFrame([surge, sell, sit])

        with patch(
            "app.canonical.analytics.fantasy_signal.upsert_fantasy_signal"
        ):
            frame = build_fantasy_signal(
                [2024],
                persist=True,
                source_frames={"profiles": profiles},
            )

        types = set(frame["signal_type"].tolist())
        self.assertTrue(
            types.issubset(set(SIGNAL_TYPES)),
            types,
        )
        self.assertIn("OPPORTUNITY_SURGE", types)
        self.assertIn("BREAKOUT_CANDIDATE", types)
        self.assertIn("BUY_LOW", types)
        self.assertIn("WAIVER_TARGET", types)
        self.assertIn("START", types)
        self.assertIn("OPPORTUNITY_DECLINE", types)
        self.assertIn("SELL_HIGH", types)
        self.assertIn("REGRESSION_RISK", types)
        self.assertIn("SIT", types)

        self.assertTrue(
            all(is_signal_id(value) for value in frame["signal_id"])
        )
        self.assertEqual(
            list(frame.columns),
            [
                "signal_id",
                "player_id",
                "season",
                "week",
                "signal_type",
                "signal_strength",
                "direction",
                "confidence",
                "supporting_metrics",
                "source_ids",
            ],
        )

        sample = frame.iloc[0]
        metrics = sample["supporting_metrics"]
        if isinstance(metrics, str):
            metrics = json.loads(metrics)
        self.assertIsInstance(metrics, dict)
        self.assertGreater(float(sample["signal_strength"]), 0)
        self.assertLessEqual(float(sample["signal_strength"]), 100)
        self.assertIn(
            sample["direction"],
            {"bullish", "bearish", "neutral"},
        )


if __name__ == "__main__":
    unittest.main()
