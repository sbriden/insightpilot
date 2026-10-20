"""Tests for continuous learning snapshots and model promotion."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.model_learning import (
    build_enriched_prediction_snapshot,
    evaluate_settled_learning,
)
from app.analysis.insights.betting.model_promotion import (
    decide_residual_promotion,
    walk_forward_residual_eval,
)


def _settled_row(**overrides):
    base = {
        "market_id": "m1",
        "game_id": "g1",
        "event_id": "g1",
        "week": 3,
        "market_type": "spread",
        "selection": "BUF -3.5",
        "result": "won",
        "model_correct": True,
        "model_probability": 0.58,
        "raw_model_probability": 0.56,
        "market_probability": 0.524,
        "edge_probability": 5.6,
        "edge": 5.6,
        "confidence": "High",
        "bet_status": "strong_bet",
        "bet_label": "Strong Bet",
        "expected_value": 4.0,
        "price": -110,
        "bet_price": -110,
        "clv": 1.5,
        "clv_unit": "points",
        "beat_close": True,
        "home_score": 27,
        "away_score": 20,
        "model_home_score": 25.0,
        "model_away_score": 21.0,
        "model_total": 46.0,
        "model_spread": -4.0,
        "actual_total": 47,
        "actual_spread": -7.0,
        "total_error": -1.0,
        "spread_error": 3.0,
    }
    base.update(overrides)
    return base


class PredictionSnapshotTests(unittest.TestCase):
    def test_enriched_snapshot_includes_features_versions_odds(self):
        event = {
            "event_id": "ip_game_1",
            "season": 2026,
            "week": 4,
            "home_team": "MIA",
            "away_team": "BUF",
            "projected_home_score": 22.0,
            "projected_away_score": 26.0,
            "projected_total": 48.0,
            "model_spread": -4.0,
            "market_spread": -3.5,
            "market_total": 47.5,
            "market_home_score": 22.0,
            "market_away_score": 25.5,
            "status": "scheduled",
            "team_strength": {
                "residuals": {
                    "applied_model": "champion",
                    "feature_snapshot": {
                        "available": True,
                        "features": {"pace_z": 0.2},
                        "vector": [0.2],
                    },
                    "challenger": {
                        "model_version": "challenger_ridge_v1",
                        "method": "ridge",
                    },
                }
            },
            "score_distribution": {
                "model_version": "score_dist_v1"
            },
        }
        markets = [
            {
                "market_id": "ip_game_1:spread",
                "market_type": "spread",
                "selection": "BUF -3.5",
                "line": -3.5,
                "price": -110,
                "model_probability": 0.57,
                "raw_model_probability": 0.55,
                "market_probability": 0.524,
                "expected_value": 3.2,
                "edge_probability": 4.6,
                "confidence": "High",
                "bet_status": "strong_bet",
                "bet_qualified": True,
                "probability_calibrated": True,
            }
        ]
        snap = build_enriched_prediction_snapshot(event, markets)
        self.assertEqual(snap["game_id"], "ip_game_1")
        payload = snap["payload"]
        self.assertIn("feature_snapshot", payload)
        self.assertTrue(payload["feature_snapshot"]["available"])
        self.assertEqual(
            payload["model_versions"]["residual_challenger"],
            "challenger_ridge_v1",
        )
        self.assertEqual(len(payload["probabilities"]), 1)
        self.assertEqual(
            payload["probabilities"][0]["offered_odds"], -110
        )
        self.assertIsNotNone(payload["decision_at"])
        self.assertIsNotNone(snap["decision_at"])


class SettledLearningTests(unittest.TestCase):
    def test_evaluate_includes_residuals_and_cohorts(self):
        rows = [
            _settled_row(market_id="a", game_id="g1", week=1),
            _settled_row(
                market_id="b",
                game_id="g2",
                week=2,
                market_type="total",
                result="lost",
                model_correct=False,
                edge_probability=2.0,
                confidence="Moderate",
                bet_status="lean",
                total_error=2.5,
                spread_error=-1.0,
            ),
            _settled_row(
                market_id="c",
                game_id="g3",
                week=3,
                edge_probability=6.0,
                result="won",
            ),
        ]
        report = evaluate_settled_learning(rows)
        self.assertTrue(report["available"])
        self.assertEqual(report["n_settled"], 3)
        self.assertIn("residuals", report)
        self.assertGreaterEqual(report["residuals"]["games"], 2)
        self.assertTrue(report["by_market"])
        self.assertTrue(report["by_edge_bucket"])
        self.assertTrue(report["by_confidence"])
        self.assertIsNotNone(report["betting_results"]["win_rate"])


class PromotionGateTests(unittest.TestCase):
    def test_hold_without_enough_sample_or_gain(self):
        decision = decide_residual_promotion(
            {
                "available": True,
                "n": 20,
                "aggregate": {
                    "champion_projection_mae": 10.0,
                    "challenger_projection_mae": 9.9,
                    "bootstrap": {"p_challenger_better": 0.55},
                },
            },
            candidate_model={
                "active": True,
                "model_version": "challenger_ridge_v1",
                "method": "ridge",
                "sample_size": 20,
            },
            current_active="champion",
        )
        self.assertFalse(decision["promoted"])
        self.assertEqual(decision["decision"], "hold")
        self.assertEqual(decision["active_model"], "champion")
        self.assertTrue(decision["reasons"])

    def test_promote_when_gates_clear(self):
        decision = decide_residual_promotion(
            {
                "available": True,
                "n": 80,
                "aggregate": {
                    "champion_projection_mae": 10.0,
                    "challenger_projection_mae": 8.5,
                    "bootstrap": {"p_challenger_better": 0.92},
                },
            },
            candidate_model={
                "active": True,
                "model_version": "challenger_ridge_v1",
                "method": "ridge",
                "sample_size": 80,
            },
            current_active="champion",
        )
        self.assertTrue(decision["promoted"])
        self.assertEqual(decision["decision"], "promote")
        self.assertEqual(decision["active_model"], "challenger")

    def test_walk_forward_is_time_ordered_not_random(self):
        from app.analysis.insights.betting.residual_features import (
            FEATURE_NAMES,
        )

        n_feat = len(FEATURE_NAMES)
        rows = []
        for week in range(1, 10):
            for game in range(6):
                signal = 0.4 * week + 0.1 * game
                vector = [0.0] * n_feat
                # Put signal on a known strength-ish slot if present.
                if "pace_z" in FEATURE_NAMES:
                    vector[FEATURE_NAMES.index("pace_z")] = signal
                else:
                    vector[0] = signal
                rows.append(
                    {
                        "week": week,
                        "game_id": f"w{week}g{game}",
                        "market_home": 24.0,
                        "market_away": 21.0,
                        "actual_home": 24.0 + signal,
                        "actual_away": 21.0 - 0.2 * signal,
                        "y_home": signal,
                        "y_away": -0.2 * signal,
                        "available": True,
                        "features": {"pace_z": signal, "min_games": 8},
                        "vector": vector,
                        "home_team_id": "t-home",
                        "away_team_id": "t-away",
                    }
                )
        report = walk_forward_residual_eval(rows, mode="expanding")
        self.assertEqual(report["mode"], "expanding")
        self.assertTrue(report.get("available"))
        # Weeks only move forward across folds when multi-fold.
        for fold in report.get("folds") or []:
            train_max = max(fold["train_weeks"])
            test_min = min(fold["test_weeks"])
            self.assertLess(train_max, test_min)


if __name__ == "__main__":
    unittest.main()
