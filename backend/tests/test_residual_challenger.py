"""Tests for residual challenger (ridge + uncertainty shrink)."""

from __future__ import annotations

import unittest

import numpy as np

from app.analysis.insights.betting.residual_challenger import (
    MIN_FIT_SAMPLES,
    compare_champion_challenger,
    estimate_residual_uncertainty,
    fit_residual_challenger,
    predict_challenger_residuals,
    prior_challenger_model,
)
from app.analysis.insights.betting.residual_challenger_eval import (
    evaluate_challenger_vs_champion,
)
from app.analysis.insights.betting.residual_features import (
    FEATURE_NAMES,
    build_residual_features,
    features_to_vector,
)


def _synthetic_features(
    *,
    home_matchup: float = 0.0,
    min_games: float = 6.0,
    disagreement: float = 0.0,
    injury: float = 0.0,
) -> dict[str, float]:
    feats = {name: 0.0 for name in FEATURE_NAMES}
    feats["home_matchup"] = home_matchup
    feats["away_matchup"] = -home_matchup * 0.4
    feats["min_games"] = min_games
    feats["home_games"] = min_games
    feats["away_games"] = min_games
    feats["early_season"] = 1.0 if min_games < 3 else 0.0
    feats["disagreement_spread_sd"] = disagreement
    feats["home_injury_adj"] = injury
    feats["market_total"] = 45.0
    feats["market_spread"] = -3.0
    return feats


def _make_fit_rows(n: int, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for i in range(n):
        matchup = float(rng.normal(0.0, 1.2))
        games = float(rng.integers(2, 12))
        feats = _synthetic_features(
            home_matchup=matchup,
            min_games=games,
            disagreement=float(rng.uniform(0.0, 3.0)),
            injury=float(rng.choice([0.0, 0.0, 1.5])),
        )
        # True residual roughly tracks matchup + noise.
        noise_h = float(rng.normal(0.0, 2.5))
        noise_a = float(rng.normal(0.0, 2.5))
        y_home = 2.2 * matchup + noise_h
        y_away = -1.4 * matchup + noise_a
        market_home = 24.0
        market_away = 21.0
        rows.append(
            {
                "week": (i % 14) + 1,
                "game_id": f"g{i}",
                "home_team_id": "H",
                "away_team_id": "A",
                "features": feats,
                "vector": features_to_vector(feats),
                "y_home": y_home,
                "y_away": y_away,
                "market_home": market_home,
                "market_away": market_away,
                "actual_home": market_home + y_home,
                "actual_away": market_away + y_away,
                "available": True,
            }
        )
    return rows


class ResidualChallengerTests(unittest.TestCase):
    def test_prior_inactive_below_min_samples(self):
        rows = _make_fit_rows(MIN_FIT_SAMPLES - 5)
        model = fit_residual_challenger(rows)
        self.assertFalse(model["active"])
        self.assertEqual(model["method"], "prior")
        self.assertEqual(model["sample_size"], MIN_FIT_SAMPLES - 5)
        self.assertEqual(len(model["coef_home"]), len(FEATURE_NAMES))

    def test_ridge_active_with_enough_samples(self):
        rows = _make_fit_rows(MIN_FIT_SAMPLES + 10)
        model = fit_residual_challenger(rows)
        self.assertTrue(model["active"])
        self.assertEqual(model["method"], "ridge")
        self.assertIsNotNone(model.get("metrics"))
        self.assertGreater(model["sample_size"], MIN_FIT_SAMPLES - 1)

    def test_shrink_goes_to_zero_as_sigma_rises(self):
        feats = _synthetic_features(home_matchup=2.0, min_games=8.0)
        model = prior_challenger_model()
        # Force a large known μ via home_matchup prior coef.
        pred_base = predict_challenger_residuals(
            feature_payload={
                "available": True,
                "features": feats,
                "vector": features_to_vector(feats),
            },
            model=model,
            market_home=24.0,
            market_away=21.0,
        )
        self.assertNotEqual(pred_base["mu_home"], 0.0)

        # Inject huge base σ → shrink ≈ 0 → applied residual ≈ 0.
        high_sigma_model = {
            **model,
            "sigma_by_bucket": {
                "thin": 50.0,
                "disagreement": 50.0,
                "injury": 50.0,
                "base": 50.0,
            },
        }
        pred_high = predict_challenger_residuals(
            feature_payload={
                "available": True,
                "features": feats,
                "vector": features_to_vector(feats),
            },
            model=high_sigma_model,
            market_home=24.0,
            market_away=21.0,
        )
        self.assertLess(pred_high["shrink"], 0.05)
        self.assertAlmostEqual(pred_high["residual_home"], 0.0, places=1)
        self.assertAlmostEqual(pred_high["residual_away"], 0.0, places=1)
        self.assertLess(pred_high["shrink"], pred_base["shrink"])

    def test_uncertainty_bucket_thin_sample(self):
        model = prior_challenger_model()
        thin = estimate_residual_uncertainty(
            features={"min_games": 1.0},
            model=model,
        )
        base = estimate_residual_uncertainty(
            features={"min_games": 8.0},
            model=model,
        )
        self.assertGreaterEqual(thin, base)

    def test_feature_builder_vector_length_and_names(self):
        payload = build_residual_features(
            home_team_id=None,
            away_team_id=None,
            market_home=24.0,
            market_away=21.0,
            market_spread=-3.0,
            market_total=45.0,
            week=6,
        )
        self.assertEqual(len(payload["vector"]), len(FEATURE_NAMES))
        self.assertEqual(payload["features"]["week_norm"], 6 / 18.0)
        self.assertEqual(payload["features"]["missing_strength"], 1.0)
        self.assertFalse(payload["available"])

    def test_feature_builder_uses_prefiltered_strength_context(self):
        """
        Leak-safety contract: builder only reads profiles already
        filtered by before_week; it does not re-query week W games.
        """

        context = {
            "profiles": {
                "HOME": {
                    "offensive_efficiency": 0.4,
                    "defensive_efficiency": -0.1,
                    "epa_per_play": 0.05,
                    "games": 5,
                    "offense": {
                        "pass_efficiency": 0.3,
                        "rush_efficiency": 0.1,
                        "explosive_rate": 0.2,
                        "red_zone_efficiency": 0.55,
                    },
                    "defense": {
                        "pass_defense": -0.1,
                        "rush_defense": 0.0,
                        "explosive_plays_allowed": 0.15,
                    },
                },
                "AWAY": {
                    "offensive_efficiency": -0.2,
                    "defensive_efficiency": 0.2,
                    "epa_per_play": -0.02,
                    "games": 5,
                    "offense": {
                        "pass_efficiency": -0.1,
                        "rush_efficiency": 0.0,
                        "explosive_rate": 0.1,
                        "red_zone_efficiency": 0.45,
                    },
                    "defense": {
                        "pass_defense": 0.2,
                        "rush_defense": 0.1,
                        "explosive_plays_allowed": 0.2,
                    },
                },
            },
            "before_week": 7,
        }
        payload = build_residual_features(
            home_team_id="HOME",
            away_team_id="AWAY",
            strength_context=context,
            market_home=25.0,
            market_away=20.0,
            market_spread=-5.0,
            market_total=45.0,
            week=7,
        )
        # Uses the provided context only — week feature is slate week,
        # strength games come from profiles (no week-7 leakage path).
        self.assertEqual(payload["features"]["home_games"], 5.0)
        self.assertEqual(payload["features"]["away_games"], 5.0)
        self.assertEqual(payload["features"]["week_norm"], 7 / 18.0)
        self.assertIn("home_matchup", payload["features"])

    def test_compare_block_shape(self):
        block = compare_champion_challenger(
            champion={
                "residual_home": 1.0,
                "residual_away": -0.5,
                "shrink": 0.25,
            },
            challenger={
                "residual_home": 1.4,
                "residual_away": -0.8,
                "mu_home": 2.0,
                "mu_away": -1.0,
                "sigma": 3.0,
                "shrink": 0.5,
                "model_active": False,
                "model_version": "challenger_ridge_v1",
                "features_used": list(FEATURE_NAMES),
            },
            applied="champion",
        )
        self.assertEqual(block["applied"], "champion")
        self.assertEqual(block["delta_points"]["home"], 0.4)
        self.assertEqual(block["delta_points"]["away"], -0.3)
        self.assertIsNotNone(block["challenger"]["sigma"])

    def test_eval_helper_on_synthetic_history(self):
        rows = _make_fit_rows(60, seed=7)
        report = evaluate_challenger_vs_champion(rows, train_ratio=0.7)
        self.assertTrue(report["available"])
        self.assertGreaterEqual(report["n_train"], 40)
        self.assertGreater(report["n_test"], 0)
        self.assertIsNotNone(report["challenger_residual_mae"])
        self.assertIsNotNone(report["champion_residual_mae"])
        # With signal in features, fitted challenger should not be
        # wildly worse than champion PPG-less path on holdout.
        self.assertLess(report["challenger_residual_mae"], 20.0)


if __name__ == "__main__":
    unittest.main()
