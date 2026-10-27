"""Unit tests for NFL opponent-strength performance tendency layer."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting.opponent_tendency import (
    MIN_N_ELITE_SOFT,
    MIN_SITUATIONAL_PTS,
    assign_opponent_tiers,
    event_tendency_payload,
    shrink_mean,
    tendency_feature_values,
    tendency_situational_adjustments,
)
from app.analysis.insights.betting.residual_features import (
    FEATURE_NAMES,
    build_residual_features,
)


class OpponentTendencyTests(unittest.TestCase):
    def test_tier_assignment_quartiles(self):
        scores = {
            "A": 2.0,
            "B": 1.0,
            "C": 0.5,
            "D": 0.0,
            "E": -0.5,
            "F": -1.0,
            "G": -1.5,
            "H": -2.0,
        }
        tiers = assign_opponent_tiers(scores)
        self.assertEqual(tiers["A"], "elite")
        self.assertEqual(tiers["H"], "below_avg")
        self.assertIn(tiers["D"], {"average", "above_avg", "below_avg"})
        self.assertEqual(len(tiers), 8)

    def test_shrink_mean_gates_and_shrinkage(self):
        self.assertEqual(shrink_mean([1.0, 2.0], min_n=6), 0.0)
        vals = [3.0] * 6
        shrunk = shrink_mean(vals, k=12.0, min_n=6)
        # n/(n+k) * mean = 6/18 * 3 = 1.0
        self.assertAlmostEqual(shrunk, 1.0, places=5)

    def test_residual_split_model_vs_market(self):
        """Market and model residuals stay independent."""

        from app.analysis.insights.betting.opponent_tendency import (
            _game_to_team_rows,
        )

        game = {
            "home_team_id": "H",
            "away_team_id": "A",
            "home_implied_total": 24.0,
            "away_implied_total": 20.0,
            "home_score": 30.0,
            "away_score": 17.0,
        }
        context = {
            "profiles": {
                "H": {
                    "offensive_efficiency": 0.8,
                    "defensive_efficiency": 0.4,
                    "defense": {"pass_defense": 0.5},
                },
                "A": {
                    "offensive_efficiency": -0.6,
                    "defensive_efficiency": -0.8,
                    "defense": {"pass_defense": -0.4},
                },
            }
        }

        with patch(
            "app.analysis.insights.betting.opponent_tendency.project_strength_scores",
            return_value=(27.0, 21.0, {"available": True}),
        ):
            rows = _game_to_team_rows(game, strength_context=context)

        self.assertEqual(len(rows), 2)
        home = next(r for r in rows if r["team_id"] == "H")
        # actual margin 13; market margin 4; model margin 6
        self.assertAlmostEqual(home["margin_resid_market"], 9.0)
        self.assertAlmostEqual(home["margin_resid_model"], 7.0)
        away = next(r for r in rows if r["team_id"] == "A")
        self.assertAlmostEqual(away["margin_resid_market"], -9.0)
        self.assertAlmostEqual(away["margin_resid_model"], -7.0)

    def test_feature_builder_zeros_when_tendency_unavailable(self):
        payload = build_residual_features(
            home_team_id="H",
            away_team_id="A",
            market_home=24.0,
            market_away=21.0,
            market_spread=-3.0,
            market_total=45.0,
            week=6,
            tendency_context=None,
        )
        for name in FEATURE_NAMES:
            if "elite_margin" in name or "soft_margin" in name:
                self.assertEqual(payload["features"][name], 0.0)
            if "resid_vol_mkt" in name or "pass_d_tier" in name:
                self.assertEqual(payload["features"][name], 0.0)
        self.assertIn(
            "home_elite_margin_resid_mkt", payload["features"]
        )
        self.assertEqual(
            len(payload["vector"]), len(FEATURE_NAMES)
        )

    def test_feature_builder_reads_tendency_profiles(self):
        tendency = {
            "profiles": {
                "H": {
                    "available": True,
                    "elite_margin_resid_mkt": 1.5,
                    "soft_margin_resid_mkt": -0.8,
                    "elite_margin_resid_model": 1.1,
                    "soft_margin_resid_model": -0.4,
                    "resid_vol_mkt": 4.2,
                    "pass_d_tier_resid_mkt": 0.6,
                },
                "A": {
                    "available": True,
                    "elite_margin_resid_mkt": -0.5,
                    "soft_margin_resid_mkt": 0.3,
                    "elite_margin_resid_model": -0.2,
                    "soft_margin_resid_model": 0.1,
                    "resid_vol_mkt": 3.0,
                    "pass_d_tier_resid_mkt": -0.3,
                },
            }
        }
        payload = build_residual_features(
            home_team_id="H",
            away_team_id="A",
            market_home=24.0,
            market_away=21.0,
            tendency_context=tendency,
        )
        self.assertEqual(
            payload["features"]["home_elite_margin_resid_mkt"], 1.5
        )
        self.assertEqual(
            payload["features"]["away_soft_margin_resid_mkt"], 0.3
        )
        self.assertEqual(
            payload["features"]["home_resid_vol_mkt"], 4.2
        )

    def test_cfb_situational_is_diagnostics_only(self):
        h, a, meta = tendency_situational_adjustments(
            home_team_id="H",
            away_team_id="A",
            strength_context={"sport": "CFB", "profiles": {}},
            tendency_context={
                "sport": "CFB",
                "profiles": {
                    "H": {
                        "available": True,
                        "elite_n": 10,
                        "soft_n": 10,
                        "elite_margin_resid_mkt": 2.0,
                        "soft_margin_resid_mkt": -2.0,
                    },
                    "A": {
                        "available": True,
                        "elite_n": 10,
                        "soft_n": 10,
                        "elite_margin_resid_mkt": 2.0,
                        "soft_margin_resid_mkt": -2.0,
                    },
                },
            },
        )
        self.assertEqual(h, 0.0)
        self.assertEqual(a, 0.0)
        self.assertFalse(meta["applied"])
        self.assertEqual(meta["reason"], "cfb_diagnostics_only")

    def test_situational_requires_both_sides_available(self):
        strength = {
            "profiles": {
                "H": {
                    "offensive_efficiency": 1.2,
                    "defensive_efficiency": 0.8,
                },
                "A": {
                    "offensive_efficiency": -1.2,
                    "defensive_efficiency": -0.8,
                },
            }
        }
        tendency = {
            "profiles": {
                "H": {
                    "available": True,
                    "elite_n": 8,
                    "soft_n": 8,
                    "elite_margin_resid_mkt": 2.0,
                    "soft_margin_resid_mkt": -1.5,
                },
                "A": {
                    "available": False,
                    "elite_n": 2,
                    "soft_n": 1,
                    "elite_margin_resid_mkt": 0.0,
                    "soft_margin_resid_mkt": 0.0,
                },
            }
        }
        h, a, meta = tendency_situational_adjustments(
            home_team_id="H",
            away_team_id="A",
            strength_context=strength,
            tendency_context=tendency,
        )
        self.assertEqual(h, 0.0)
        self.assertEqual(a, 0.0)
        self.assertFalse(meta["applied"])
        self.assertEqual(meta["reason"], "sample_gate")

    def test_situational_applies_when_gates_pass(self):
        # Build 4+4 strength pool so quartile tiers resolve.
        strength = {
            "profiles": {
                "H": {
                    "offensive_efficiency": 1.5,
                    "defensive_efficiency": 1.0,
                },
                "A": {
                    "offensive_efficiency": -1.5,
                    "defensive_efficiency": -1.0,
                },
                "X1": {
                    "offensive_efficiency": 0.8,
                    "defensive_efficiency": 0.5,
                },
                "X2": {
                    "offensive_efficiency": 0.2,
                    "defensive_efficiency": 0.1,
                },
                "X3": {
                    "offensive_efficiency": -0.2,
                    "defensive_efficiency": -0.1,
                },
                "X4": {
                    "offensive_efficiency": -0.8,
                    "defensive_efficiency": -0.5,
                },
            }
        }
        tendency = {
            "profiles": {
                "H": {
                    "available": True,
                    "elite_n": MIN_N_ELITE_SOFT + 2,
                    "soft_n": MIN_N_ELITE_SOFT + 2,
                    "elite_margin_resid_mkt": 2.0,
                    "soft_margin_resid_mkt": -1.2,
                },
                "A": {
                    "available": True,
                    "elite_n": MIN_N_ELITE_SOFT + 2,
                    "soft_n": MIN_N_ELITE_SOFT + 2,
                    "elite_margin_resid_mkt": 1.5,
                    "soft_margin_resid_mkt": -0.9,
                },
            }
        }
        h, a, meta = tendency_situational_adjustments(
            home_team_id="H",
            away_team_id="A",
            strength_context=strength,
            tendency_context=tendency,
            shrink=1.0,
        )
        self.assertTrue(meta["applied"])
        self.assertEqual(meta["reason"], "gates_passed")
        # Raw gate still uses full tier signals; applied points are
        # dampened / margin-focused and may be below MIN_SITUATIONAL.
        self.assertGreaterEqual(
            max(
                abs(float(meta.get("home_pts_raw") or 0.0)),
                abs(float(meta.get("away_pts_raw") or 0.0)),
            ),
            MIN_SITUATIONAL_PTS,
        )
        self.assertNotEqual(h, 0.0)
        self.assertNotEqual(a, 0.0)

    def test_situational_below_threshold(self):
        strength = {
            "profiles": {
                "H": {
                    "offensive_efficiency": 1.5,
                    "defensive_efficiency": 1.0,
                },
                "A": {
                    "offensive_efficiency": -1.5,
                    "defensive_efficiency": -1.0,
                },
                "X1": {
                    "offensive_efficiency": 0.5,
                    "defensive_efficiency": 0.4,
                },
                "X2": {
                    "offensive_efficiency": 0.1,
                    "defensive_efficiency": 0.0,
                },
                "X3": {
                    "offensive_efficiency": -0.1,
                    "defensive_efficiency": 0.0,
                },
                "X4": {
                    "offensive_efficiency": -0.5,
                    "defensive_efficiency": -0.4,
                },
            }
        }
        tiny = MIN_SITUATIONAL_PTS / 4.0
        tendency = {
            "profiles": {
                "H": {
                    "available": True,
                    "elite_n": 10,
                    "soft_n": 10,
                    "elite_margin_resid_mkt": tiny,
                    "soft_margin_resid_mkt": -tiny,
                },
                "A": {
                    "available": True,
                    "elite_n": 10,
                    "soft_n": 10,
                    "elite_margin_resid_mkt": tiny,
                    "soft_margin_resid_mkt": -tiny,
                },
            }
        }
        h, a, meta = tendency_situational_adjustments(
            home_team_id="H",
            away_team_id="A",
            strength_context=strength,
            tendency_context=tendency,
        )
        self.assertFalse(meta["applied"])
        self.assertEqual(meta["reason"], "below_threshold")
        self.assertEqual(h, 0.0)
        self.assertEqual(a, 0.0)

    def test_leak_safe_before_week_excludes_slate_week(self):
        from app.analysis.insights.betting import opponent_tendency as ot

        captured: list[dict] = []

        def fake_load(*, season, through_week=None, schema=None):
            captured.append(
                {
                    "season": season,
                    "through_week": through_week,
                    "schema": schema,
                }
            )
            return []

        ot._TENDENCY_CACHE.clear()
        with patch.object(
            ot,
            "load_team_strength_context",
            return_value={"profiles": {}},
        ):
            with patch(
                "app.analysis.insights.betting.residual_challenger_dataset._load_completed_market_games",
                side_effect=fake_load,
            ):
                ot.load_opponent_tendency_context(
                    season=2024,
                    before_week=8,
                    include_prior_season=True,
                )

        # Current season capped at before_week - 1; prior season full.
        current = [
            c for c in captured if c["season"] == 2024
        ]
        prior = [c for c in captured if c["season"] == 2023]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["through_week"], 7)
        self.assertEqual(len(prior), 1)
        self.assertIsNone(prior[0]["through_week"])

    def test_cfb_passes_college_schema(self):
        from app.analysis.insights.betting import opponent_tendency as ot
        from app.canonical.cfb.schema import COLLEGE_SCHEMA

        captured: list[dict] = []

        def fake_load(*, season, through_week=None, schema=None):
            captured.append({"schema": schema, "season": season})
            return []

        ot._TENDENCY_CACHE.clear()
        with patch.object(
            ot,
            "load_team_strength_context",
            return_value={"profiles": {}},
        ):
            with patch(
                "app.analysis.insights.betting.residual_challenger_dataset._load_completed_market_games",
                side_effect=fake_load,
            ):
                ctx = ot.load_opponent_tendency_context(
                    season=2024,
                    before_week=5,
                    include_prior_season=False,
                    sport="CFB",
                )

        self.assertEqual(ctx["sport"], "CFB")
        self.assertEqual(ctx["strength_mode"], "season_snapshot")
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["schema"], COLLEGE_SCHEMA)

    def test_cfb_uses_one_strength_snapshot_per_season(self):
        from app.analysis.insights.betting import opponent_tendency as ot

        strength_calls: list[dict] = []

        def fake_strength(*, season, before_week=None, sport=None):
            strength_calls.append(
                {"season": season, "before_week": before_week}
            )
            return {
                "profiles": {
                    "H": {
                        "offensive_efficiency": 1.0,
                        "defensive_efficiency": 0.5,
                        "defense": {"pass_defense": 0.2},
                    },
                    "A": {
                        "offensive_efficiency": -1.0,
                        "defensive_efficiency": -0.5,
                        "defense": {"pass_defense": -0.2},
                    },
                }
            }

        games = [
            {
                "week": 1,
                "home_team_id": "H",
                "away_team_id": "A",
                "home_implied_total": 28.0,
                "away_implied_total": 24.0,
                "home_score": 31.0,
                "away_score": 20.0,
            },
            {
                "week": 2,
                "home_team_id": "A",
                "away_team_id": "H",
                "home_implied_total": 27.0,
                "away_implied_total": 25.0,
                "home_score": 24.0,
                "away_score": 27.0,
            },
            {
                "week": 3,
                "home_team_id": "H",
                "away_team_id": "A",
                "home_implied_total": 30.0,
                "away_implied_total": 22.0,
                "home_score": 35.0,
                "away_score": 14.0,
            },
        ]

        ot._TENDENCY_CACHE.clear()
        with patch.object(
            ot, "load_team_strength_context", side_effect=fake_strength
        ):
            with patch(
                "app.analysis.insights.betting.residual_challenger_dataset._load_completed_market_games",
                return_value=games,
            ):
                with patch.object(
                    ot,
                    "project_strength_scores",
                    return_value=(28.0, 24.0, {"available": True}),
                ):
                    ot.load_opponent_tendency_context(
                        season=2024,
                        before_week=4,
                        include_prior_season=False,
                        sport="CFB",
                    )

        # Coarse CFB path: one strength load, not one per week.
        self.assertEqual(len(strength_calls), 1)
        self.assertEqual(strength_calls[0]["before_week"], 4)

    def test_tendency_feature_values_and_event_payload(self):
        feats = tendency_feature_values(None)
        self.assertEqual(feats["elite_margin_resid_mkt"], 0.0)
        payload = event_tendency_payload(
            home_team_id="H",
            away_team_id="A",
            tendency_context={
                "profiles": {
                    "H": {"available": True, "elite_n": 8},
                    "A": {"available": True, "elite_n": 8},
                },
                "games_used": 40,
                "before_week": 9,
            },
            situational_meta={
                "applied": True,
                "home_pts": 1.2,
                "away_pts": -0.8,
                "away_tier": "elite",
                "home_tier": "below_avg",
                "reason": "gates_passed",
            },
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertTrue(payload["available"])
        self.assertTrue(payload["situational"]["applied"])
        self.assertEqual(payload["situational"]["home_faces_tier"], "elite")


if __name__ == "__main__":
    unittest.main()
