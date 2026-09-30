"""Tests for opponent-adjusted team strength projections."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.team_strength import (
    blend_market_and_strength,
    project_strength_scores,
)


def _profile(
    *,
    offense: float,
    defense: float,
    pace_z: float = 0.0,
) -> dict:
    return {
        "offensive_efficiency": offense,
        "defensive_efficiency": defense,
        "pace": 28.0,
        "pace_z": pace_z,
        "offense": {
            "pass_efficiency": offense,
            "rush_efficiency": offense * 0.5,
            "explosive_rate": offense * 0.4,
            "success_rate": offense,
            "red_zone_efficiency": offense * 0.3,
        },
        "defense": {
            "pass_defense": defense,
            "rush_defense": defense * 0.5,
            "pressure": defense * 0.4,
            "explosive_plays_allowed": defense * 0.3,
            "success_rate_allowed": defense,
        },
    }


class TeamStrengthProjectionTests(unittest.TestCase):
    def test_elite_offense_vs_weak_defense_scores_more(self):
        context = {
            "league_avg_ppg": 22.5,
            "profiles": {
                "home": _profile(offense=1.5, defense=0.2),
                "away": _profile(offense=0.0, defense=-1.5),
            },
        }
        home, away, detail = project_strength_scores(
            home_team_id="home",
            away_team_id="away",
            context=context,
        )
        self.assertTrue(detail["available"])
        assert home is not None and away is not None
        # Home offense +1.5 vs away defense -1.5 ⇒ matchup +3.0
        self.assertGreater(home, away)
        self.assertGreater(home, 22.5)
        self.assertGreater(detail["home_matchup"], detail["away_matchup"])

    def test_same_raw_form_diverges_by_opponent_defense(self):
        # Identical offenses; only opponent defense changes.
        strong_d = {
            "league_avg_ppg": 22.5,
            "profiles": {
                "off": _profile(offense=0.8, defense=0.0),
                "elite_d": _profile(offense=0.0, defense=1.8),
                "weak_d": _profile(offense=0.0, defense=-1.8),
            },
        }
        vs_elite, _, detail_elite = project_strength_scores(
            home_team_id="off",
            away_team_id="elite_d",
            context=strong_d,
        )
        vs_weak, _, detail_weak = project_strength_scores(
            home_team_id="off",
            away_team_id="weak_d",
            context=strong_d,
        )
        assert vs_elite is not None and vs_weak is not None
        self.assertGreater(vs_weak, vs_elite)
        self.assertGreater(
            detail_weak["home_matchup"],
            detail_elite["home_matchup"],
        )

    def test_market_blend_weights(self):
        home, away, meta = blend_market_and_strength(
            market_home=24.0,
            market_away=20.0,
            strength_home=30.0,
            strength_away=14.0,
            confidence="Moderate",
        )
        # Market anchor + 25% of model delta:
        # 24 + 0.25*(30-24) = 25.5 ; 20 + 0.25*(14-20) = 18.5
        self.assertEqual(home, 25.5)
        self.assertEqual(away, 18.5)
        self.assertEqual(meta["model_weight"], 0.25)

    def test_missing_profiles_return_unavailable(self):
        home, away, detail = project_strength_scores(
            home_team_id="missing",
            away_team_id="also",
            context={"profiles": {}, "league_avg_ppg": 22.5},
        )
        self.assertIsNone(home)
        self.assertIsNone(away)
        self.assertFalse(detail["available"])


if __name__ == "__main__":
    unittest.main()
