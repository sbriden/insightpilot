"""Tests for opponent-adjusted team strength projections."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.betting_sport import (
    resolve_betting_sport,
)
from app.analysis.insights.betting.team_strength import (
    blend_market_and_strength,
    project_strength_scores,
    _resolve_league_avg_ppg,
    _strength_of_schedule_raw,
)


def _profile(
    *,
    offense: float,
    defense: float,
    pace_z: float = 0.0,
    sos: float = 0.0,
) -> dict:
    return {
        "offensive_efficiency": offense,
        "defensive_efficiency": defense,
        "strength_of_schedule": sos,
        "offense_sos": sos,
        "defense_sos": sos,
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

    def test_harder_sos_earns_projection_edge(self):
        context = {
            "league_avg_ppg": 22.5,
            "sport": "NFL",
            "profiles": {
                "home": _profile(offense=0.5, defense=0.5, sos=1.5),
                "away": _profile(offense=0.5, defense=0.5, sos=-1.5),
            },
        }
        home, away, detail = project_strength_scores(
            home_team_id="home",
            away_team_id="away",
            context=context,
        )
        assert home is not None and away is not None
        self.assertGreater(home, away)
        self.assertGreater(detail["sos_differential"], 0)
        self.assertGreater(detail["sos_home_points"], 0)

    def test_strength_of_schedule_raw_ranks_tough_slate(self):
        offense_by_team = {
            "soft": [{"opponent_id": "weak_d", "points": 30}],
            "hard": [{"opponent_id": "elite_d", "points": 20}],
        }
        defense_by_team = {
            "soft": [{"opponent_id": "weak_o"}],
            "hard": [{"opponent_id": "elite_o"}],
        }
        raw_off = {
            "weak_o": {"points": 14.0},
            "elite_o": {"points": 30.0},
        }
        raw_def = {
            "weak_d": {"points_allowed": 30.0},
            "elite_d": {"points_allowed": 14.0},
        }
        sos = _strength_of_schedule_raw(
            offense_by_team=offense_by_team,
            defense_by_team=defense_by_team,
            raw_off_baselines=raw_off,
            raw_def_baselines=raw_def,
            league_avg_ppg=22.5,
        )
        self.assertGreater(
            sos["hard"]["strength_of_schedule"],
            sos["soft"]["strength_of_schedule"],
        )

    def test_cfb_league_avg_uses_game_weighted_points(self):
        # Many low-scoring teams would drag an equal-weight mean down.
        offense_by_team = {
            f"low{i}": [{"points": 6.0}] for i in range(20)
        }
        offense_by_team["power"] = [{"points": 35.0}] * 10
        resolved = _resolve_league_avg_ppg(
            offense_by_team=offense_by_team,
            league_off={"points": 8.0},  # equal-weight trap
            league_def={"points_allowed": 8.0},
            default_ppg=28.0,
            sport_config=resolve_betting_sport("CFB"),
        )
        # Game-weighted ≈ (20*6 + 10*35) / 30 = 15.7, floored by
        # CFB band to 0.9 * 28 = 25.2.
        self.assertGreaterEqual(resolved, 25.0)
        self.assertLess(resolved, 28.0 * 1.15)


if __name__ == "__main__":
    unittest.main()
