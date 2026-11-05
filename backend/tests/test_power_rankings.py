"""Tests for NFL team power rankings engine."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting import power_rankings as pr


def _team(tid: str, abbr: str) -> dict:
    return {
        "team_id": tid,
        "team_abbreviation": abbr,
        "team_name": abbr,
    }


def _off_game(
    *,
    team_id: str,
    opponent_id: str,
    week: int,
    points: float,
    epa_per_play: float,
    plays: int = 60,
) -> dict:
    return {
        "team_id": team_id,
        "opponent_id": opponent_id,
        "week": week,
        "points": points,
        "offensive_plays": plays,
        "offensive_epa": epa_per_play * plays,
        "pass_epa": epa_per_play * plays * 0.6,
        "rush_epa": epa_per_play * plays * 0.4,
        "yards": 350,
        "pass_attempts": 35,
        "rush_attempts": 25,
        "pass_rate": 0.58,
        "pace": 65,
        "red_zone_td_rate": 0.55,
        "turnovers": 1,
        "is_home": True,
    }


def _def_game(
    *,
    team_id: str,
    opponent_id: str,
    week: int,
    points_allowed: float,
    epa_allowed: float,
) -> dict:
    return {
        "defensive_team_id": team_id,
        "team_id": team_id,
        "opponent_id": opponent_id,
        "week": week,
        "points_allowed": points_allowed,
        "yards_allowed": 320,
        "pass_yards_allowed": 220,
        "rush_yards_allowed": 100,
        "pass_epa_allowed": epa_allowed * 0.6,
        "rush_epa_allowed": epa_allowed * 0.4,
        "pressure_rate": 0.25,
        "sack_rate": 0.07,
        "is_home": True,
    }


NFL_ABBRS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]


def _all_teams() -> list[dict]:
    return [_team(f"t{i}", abbr) for i, abbr in enumerate(NFL_ABBRS)]


class RecencyAndShrinkageTests(unittest.TestCase):
    def test_recency_decay_half_life(self):
        # age = current_week_ref - game_week - 1
        # age 5 with half-life 5 → weight 0.5
        weight = pr._recency_weight(
            1,
            current_week_ref=7.0,
            half_life_weeks=5.0,
        )
        self.assertAlmostEqual(weight, 0.5, places=5)

        same_week = pr._recency_weight(
            6,
            current_week_ref=7.0,
            half_life_weeks=5.0,
        )
        self.assertAlmostEqual(same_week, 1.0, places=5)

    def test_prior_shrinkage_small_sample(self):
        # lambda = n / (n + k); n=0 → prior only; n large → observed
        k = 5.0
        lam_small = 1.0 / (1.0 + k)
        lam_large = 20.0 / (20.0 + k)
        prior = 2.0
        observed = 10.0
        small = lam_small * observed + (1 - lam_small) * prior
        large = lam_large * observed + (1 - lam_large) * prior
        self.assertLess(small, large)
        self.assertAlmostEqual(small, 3.333, places=2)


class CompositeOrientationTests(unittest.TestCase):
    def test_higher_offense_epa_raises_composite(self):
        weak = pr._offense_composite(
            {
                "epa_per_play": -0.1,
                "explosive_rate": 4.5,
                "scoring_margin_proxy": -7.0,
            }
        )
        strong = pr._offense_composite(
            {
                "epa_per_play": 0.2,
                "explosive_rate": 6.5,
                "scoring_margin_proxy": 10.0,
            }
        )
        self.assertGreater(strong, weak)

    def test_better_defense_raises_composite(self):
        # Lower EPA/yards allowed and points → higher (better) rating
        porous = pr._defense_composite(
            {
                "success_allowed_raw": 0.2,
                "pass_defense_raw": 0.2,
                "rush_defense_raw": 0.2,
                "explosive_allowed_raw": 6.5,
                "points_allowed": 30.0,
            }
        )
        stout = pr._defense_composite(
            {
                "success_allowed_raw": -0.1,
                "pass_defense_raw": -0.1,
                "rush_defense_raw": -0.1,
                "explosive_allowed_raw": 4.5,
                "points_allowed": 15.0,
            }
        )
        self.assertGreater(stout, porous)

    def test_defense_composite_prefers_opp_adjusted_residual(self):
        # Same raw points allowed; residual distinguishes slate quality.
        soft_schedule = pr._defense_composite(
            {
                "success_allowed_raw": 0.0,
                "explosive_allowed_raw": 5.5,
                "points_allowed": 14.0,
                "points_allowed_residual": 2.0,
            }
        )
        tough_schedule = pr._defense_composite(
            {
                "success_allowed_raw": 0.0,
                "explosive_allowed_raw": 5.5,
                "points_allowed": 14.0,
                "points_allowed_residual": 12.0,
            }
        )
        self.assertGreater(tough_schedule, soft_schedule)

    def test_shrinkage_uses_game_count_not_recency_sum(self):
        games = [{"week": w} for w in range(1, 9)]
        n = pr._effective_game_count(
            games,
            games,
            current_week_ref=9.0,
            half_life_weeks=5.0,
        )
        self.assertEqual(n, 8.0)

    def test_prior_lambda_decays_midseason(self):
        early = pr._shrinkage_lambda(effective_games=2.0, prior_k=5.0)
        mid = pr._shrinkage_lambda(effective_games=8.0, prior_k=5.0)
        self.assertGreater(mid, early)
        # By ~8 games, observed should dominate last season.
        self.assertGreaterEqual(mid, 0.85)


class OppScaleAndHfaTests(unittest.TestCase):
    def test_opponent_quality_scales_offense(self):
        # Tough defense (low points allowed) → scale > 1 when invert
        tough = pr._opp_scale(
            16.0,
            league_avg_ppg=22.5,
            invert=True,
        )
        soft = pr._opp_scale(
            28.0,
            league_avg_ppg=22.5,
            invert=True,
        )
        self.assertGreater(tough, soft)
        self.assertGreater(tough, 1.0)
        self.assertLess(soft, 1.0)

    def test_scoring_residual_credits_tough_schedule(self):
        """Same points vs soft D earn less residual than vs tough D."""
        league = 28.0
        points = 35.0
        soft_expected = league + (40.0 - league)  # soft D allows 40
        tough_expected = league + (16.0 - league)  # tough D allows 16
        soft_residual = points - soft_expected
        tough_residual = points - tough_expected
        self.assertGreater(tough_residual, soft_residual)
        self.assertLess(soft_residual, 0.0)
        self.assertGreater(tough_residual, 0.0)

    def test_cfb_opp_scale_stronger_than_nfl(self):
        from app.analysis.insights.betting.betting_sport import (
            resolve_betting_sport,
        )

        soft_pts = 40.0
        league = 28.0
        nfl = pr._opp_scale(
            soft_pts,
            league_avg_ppg=league,
            invert=True,
            sport_config=resolve_betting_sport("NFL"),
        )
        cfb = pr._opp_scale(
            soft_pts,
            league_avg_ppg=league,
            invert=True,
            sport_config=resolve_betting_sport("CFB"),
        )
        # Soft D should discount CFB observations more aggressively.
        self.assertLess(cfb, nfl)

    def test_record_signal_rewards_winning(self):
        off = [
            {
                "week": 1,
                "opponent_id": "weak",
                "points": 35,
            },
            {
                "week": 2,
                "opponent_id": "avg",
                "points": 28,
            },
            {
                "week": 3,
                "opponent_id": "strong",
                "points": 24,
            },
        ]
        deff = [
            {
                "week": 1,
                "opponent_id": "weak",
                "points_allowed": 10,
            },
            {
                "week": 2,
                "opponent_id": "avg",
                "points_allowed": 17,
            },
            {
                "week": 3,
                "opponent_id": "strong",
                "points_allowed": 21,
            },
        ]
        off_means = {
            "weak": {"points": 17.0},
            "avg": {"points": 28.0},
            "strong": {"points": 38.0},
        }
        def_means = {
            "weak": {"points_allowed": 35.0},
            "avg": {"points_allowed": 28.0},
            "strong": {"points_allowed": 18.0},
        }
        undefeated = pr._team_record(
            games_off=off,
            games_def=deff,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=28.0,
        )
        self.assertEqual(undefeated["wins"], 3)
        self.assertEqual(undefeated["losses"], 0)
        self.assertGreater(undefeated["record_signal"], 0.5)

        losing_off = [
            {**row, "points": 10} for row in off
        ]
        losing_def = [
            {**row, "points_allowed": 30} for row in deff
        ]
        winless = pr._team_record(
            games_off=losing_off,
            games_def=losing_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=28.0,
        )
        self.assertEqual(winless["wins"], 0)
        self.assertEqual(winless["losses"], 3)
        self.assertLess(winless["record_signal"], -0.5)

        soft_off = [
            {
                "week": 1,
                "opponent_id": "weak",
                "points": 45,
            },
            {
                "week": 2,
                "opponent_id": "weak",
                "points": 42,
            },
            {
                "week": 3,
                "opponent_id": "weak",
                "points": 38,
            },
        ]
        soft_def = [
            {
                "week": 1,
                "opponent_id": "weak",
                "points_allowed": 7,
            },
            {
                "week": 2,
                "opponent_id": "weak",
                "points_allowed": 10,
            },
            {
                "week": 3,
                "opponent_id": "weak",
                "points_allowed": 14,
            },
        ]
        soft_cfb = pr._team_record(
            games_off=soft_off,
            games_def=soft_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=28.0,
            sport_id="CFB",
        )
        quality_cfb = pr._team_record(
            games_off=off,
            games_def=deff,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=28.0,
            sport_id="CFB",
        )
        self.assertEqual(soft_cfb["wins"], 3)
        self.assertGreater(
            quality_cfb["record_signal"], soft_cfb["record_signal"]
        )

        # Same 7-1 shape: quality win + mild loss beats cupcake parade + bad loss.
        strength = {
            "bama": 8.0,
            "aub": -1.0,
            "cup1": -6.0,
            "cup2": -7.0,
            "cup3": -5.0,
            "jmu": 2.0,
            "filler1": -4.0,
            "filler2": -5.0,
        }
        uga_off = [
            {"week": 1, "opponent_id": "bama", "points": 20},
            {"week": 2, "opponent_id": "aub", "points": 24},
            {"week": 3, "opponent_id": "filler1", "points": 35},
            {"week": 4, "opponent_id": "filler2", "points": 38},
            {"week": 5, "opponent_id": "cup1", "points": 41},
            {"week": 6, "opponent_id": "cup2", "points": 45},
            {"week": 7, "opponent_id": "cup3", "points": 34},
            {"week": 8, "opponent_id": "filler1", "points": 30},
        ]
        uga_def = [
            {"week": 1, "opponent_id": "bama", "points_allowed": 17},
            {"week": 2, "opponent_id": "aub", "points_allowed": 27},
            {"week": 3, "opponent_id": "filler1", "points_allowed": 14},
            {"week": 4, "opponent_id": "filler2", "points_allowed": 10},
            {"week": 5, "opponent_id": "cup1", "points_allowed": 7},
            {"week": 6, "opponent_id": "cup2", "points_allowed": 3},
            {"week": 7, "opponent_id": "cup3", "points_allowed": 13},
            {"week": 8, "opponent_id": "filler1", "points_allowed": 8},
        ]
        lib_off = [
            {"week": 1, "opponent_id": "jmu", "points": 13},
            {"week": 2, "opponent_id": "cup1", "points": 51},
            {"week": 3, "opponent_id": "cup2", "points": 35},
            {"week": 4, "opponent_id": "cup3", "points": 34},
            {"week": 5, "opponent_id": "cup1", "points": 49},
            {"week": 6, "opponent_id": "cup2", "points": 30},
            {"week": 7, "opponent_id": "filler1", "points": 34},
            {"week": 8, "opponent_id": "filler2", "points": 28},
        ]
        lib_def = [
            {"week": 1, "opponent_id": "jmu", "points_allowed": 20},
            {"week": 2, "opponent_id": "cup1", "points_allowed": 15},
            {"week": 3, "opponent_id": "cup2", "points_allowed": 3},
            {"week": 4, "opponent_id": "cup3", "points_allowed": 6},
            {"week": 5, "opponent_id": "cup1", "points_allowed": 10},
            {"week": 6, "opponent_id": "cup2", "points_allowed": 14},
            {"week": 7, "opponent_id": "filler1", "points_allowed": 17},
            {"week": 8, "opponent_id": "filler2", "points_allowed": 14},
        ]
        uga_rec = pr._team_record(
            games_off=uga_off,
            games_def=uga_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=28.0,
            sport_id="CFB",
            opp_strength_by_team=strength,
        )
        lib_rec = pr._team_record(
            games_off=lib_off,
            games_def=lib_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=28.0,
            sport_id="CFB",
            opp_strength_by_team=strength,
        )
        self.assertEqual(uga_rec["wins"], 7)
        self.assertEqual(uga_rec["losses"], 1)
        self.assertEqual(lib_rec["wins"], 7)
        self.assertEqual(lib_rec["losses"], 1)
        self.assertGreater(
            uga_rec["record_signal"], lib_rec["record_signal"]
        )

    def test_cfb_sos_uses_opponent_strength(self):
        games = [
            {"week": 1, "opponent_id": "elite"},
            {"week": 2, "opponent_id": "mid"},
        ]
        strength = {"elite": 6.0, "mid": 1.0, "cup": -5.0}
        hard = pr._team_sos(
            games_off=games,
            games_def=games,
            off_means={},
            def_means={},
            league_avg_ppg=28.0,
            opp_strength_by_team=strength,
        )
        soft = pr._team_sos(
            games_off=[
                {"week": 1, "opponent_id": "cup"},
                {"week": 2, "opponent_id": "cup"},
            ],
            games_def=[
                {"week": 1, "opponent_id": "cup"},
                {"week": 2, "opponent_id": "cup"},
            ],
            off_means={},
            def_means={},
            league_avg_ppg=28.0,
            opp_strength_by_team=strength,
        )
        self.assertGreater(hard, soft)
        self.assertGreater(hard, 0.0)
        self.assertLess(soft, 0.0)

    def test_recent_form_damps_soft_opponents(self):
        games_off = [
            {"week": 8, "opponent_id": "soft", "points": 49},
            {"week": 7, "opponent_id": "soft", "points": 42},
            {"week": 6, "opponent_id": "soft", "points": 38},
        ]
        games_def = [
            {"week": 8, "opponent_id": "soft", "points_allowed": 10},
            {"week": 7, "opponent_id": "soft", "points_allowed": 7},
            {"week": 6, "opponent_id": "soft", "points_allowed": 14},
        ]
        games_off_tough = [
            {"week": 8, "opponent_id": "tough", "points": 31},
            {"week": 7, "opponent_id": "tough", "points": 28},
            {"week": 6, "opponent_id": "tough", "points": 24},
        ]
        games_def_tough = [
            {"week": 8, "opponent_id": "tough", "points_allowed": 17},
            {"week": 7, "opponent_id": "tough", "points_allowed": 21},
            {"week": 6, "opponent_id": "tough", "points_allowed": 20},
        ]
        off_means = {
            "soft": {"points": 18.0},
            "tough": {"points": 34.0},
        }
        def_means = {
            "soft": {"points_allowed": 35.0},
            "tough": {"points_allowed": 18.0},
        }
        soft_form = pr._recent_form(
            games_off=games_off,
            games_def=games_def,
            current_week_ref=9.0,
            half_life_weeks=5.0,
            league_avg_ppg=28.0,
            off_means=off_means,
            def_means=def_means,
            sport_id="CFB",
        )
        tough_form = pr._recent_form(
            games_off=games_off_tough,
            games_def=games_def_tough,
            current_week_ref=9.0,
            half_life_weeks=5.0,
            league_avg_ppg=28.0,
            off_means=off_means,
            def_means=def_means,
            sport_id="CFB",
        )
        # Padding soft foes should not outrank solid play vs tough ones.
        self.assertGreater(tough_form, soft_form)

        # FCS opponents are skipped entirely.
        with_fcs = pr._recent_form(
            games_off=games_off
            + [{"week": 9, "opponent_id": "fcs", "points": 77}],
            games_def=games_def
            + [{"week": 9, "opponent_id": "fcs", "points_allowed": 0}],
            current_week_ref=9.0,
            half_life_weeks=5.0,
            league_avg_ppg=28.0,
            off_means={**off_means, "fcs": {"points": 7.0}},
            def_means={**def_means, "fcs": {"points_allowed": 70.0}},
            exclude_opponent_ids={"fcs"},
            sport_id="CFB",
        )
        self.assertAlmostEqual(with_fcs, soft_form, places=2)

    def test_sos_excludes_fcs_and_shrinks_sparse(self):
        league = 28.0
        games_off = [
            {"week": 1, "opponent_id": "avg", "points": 28},
            {"week": 2, "opponent_id": "fcs", "points": 77},
        ]
        games_def = [
            {"week": 1, "opponent_id": "avg", "points_allowed": 21},
            {"week": 2, "opponent_id": "fcs", "points_allowed": 7},
        ]
        off_means = {
            "avg": {"points": 28.0},
            "fcs": {"points": 7.0},
        }
        def_means = {
            "avg": {"points_allowed": 28.0},
            "fcs": {"points_allowed": 77.0},
        }
        raw = pr._team_sos(
            games_off=games_off,
            games_def=games_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=league,
        )
        excluded = pr._team_sos(
            games_off=games_off,
            games_def=games_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=league,
            exclude_opponent_ids={"fcs"},
        )
        shrunk = pr._team_sos(
            games_off=games_off,
            games_def=games_def,
            off_means=off_means,
            def_means=def_means,
            league_avg_ppg=league,
            opponent_game_counts={"avg": 8, "fcs": 1},
        )
        # One-game FCS 77-allowed blowout should tank raw SOS.
        self.assertLess(raw, -5.0)
        # Dropping FCS leaves near-average schedule.
        self.assertAlmostEqual(excluded, 0.0, places=1)
        # Sample shrink softens the cupcake without excluding it.
        self.assertGreater(shrunk, raw)

    def test_home_field_applied_in_margin(self):
        rankings = {
            "home": {
                "current_adjusted_rating": 3.0,
                "offensive_rating": 2.0,
                "defensive_rating": 1.0,
            },
            "away": {
                "current_adjusted_rating": 1.0,
                "offensive_rating": 0.5,
                "defensive_rating": 0.5,
            },
        }
        with_hfa = pr.project_margin_from_power_rankings(
            home_team_id="home",
            away_team_id="away",
            rankings_by_team=rankings,
            home_field_advantage=2.0,
        )
        no_hfa = pr.project_margin_from_power_rankings(
            home_team_id="home",
            away_team_id="away",
            rankings_by_team=rankings,
            home_field_advantage=0.0,
        )
        self.assertTrue(with_hfa["available"])
        self.assertAlmostEqual(
            with_hfa["expected_margin"],
            no_hfa["expected_margin"] + 2.0,
            places=3,
        )
        # home rating 3 - away 1 + HFA 2 = 4
        self.assertAlmostEqual(with_hfa["expected_margin"], 4.0, places=3)


class BuildRankingsTests(unittest.TestCase):
    def _offense_pool(self) -> list[dict]:
        rows: list[dict] = []
        # Strong team t0 vs weak defenses; weak team t1 vs strong.
        for week in range(1, 6):
            rows.append(
                _off_game(
                    team_id="t0",
                    opponent_id="t2",
                    week=week,
                    points=31,
                    epa_per_play=0.18,
                )
            )
            rows.append(
                _off_game(
                    team_id="t1",
                    opponent_id="t3",
                    week=week,
                    points=14,
                    epa_per_play=-0.12,
                )
            )
            rows.append(
                _off_game(
                    team_id="t2",
                    opponent_id="t0",
                    week=week,
                    points=20,
                    epa_per_play=0.0,
                )
            )
            rows.append(
                _off_game(
                    team_id="t3",
                    opponent_id="t1",
                    week=week,
                    points=22,
                    epa_per_play=0.02,
                )
            )
        return rows

    def _defense_pool(self) -> list[dict]:
        rows: list[dict] = []
        for week in range(1, 6):
            rows.append(
                _def_game(
                    team_id="t0",
                    opponent_id="t2",
                    week=week,
                    points_allowed=14,
                    epa_allowed=-0.1,
                )
            )
            rows.append(
                _def_game(
                    team_id="t1",
                    opponent_id="t3",
                    week=week,
                    points_allowed=30,
                    epa_allowed=0.15,
                )
            )
            rows.append(
                _def_game(
                    team_id="t2",
                    opponent_id="t0",
                    week=week,
                    points_allowed=28,
                    epa_allowed=0.1,
                )
            )
            rows.append(
                _def_game(
                    team_id="t3",
                    opponent_id="t1",
                    week=week,
                    points_allowed=17,
                    epa_allowed=-0.05,
                )
            )
        return rows

    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_all_thirty_two_teams_rated(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        teams = _all_teams()
        mock_teams.return_value = teams
        # Give every team one modest game so no team is fabricated blank.
        off_rows = []
        def_rows = []
        for i, team in enumerate(teams):
            opp = teams[(i + 1) % 32]["team_id"]
            off_rows.append(
                _off_game(
                    team_id=team["team_id"],
                    opponent_id=opp,
                    week=3,
                    points=22,
                    epa_per_play=0.0,
                )
            )
            def_rows.append(
                _def_game(
                    team_id=team["team_id"],
                    opponent_id=opp,
                    week=3,
                    points_allowed=22,
                    epa_allowed=0.0,
                )
            )
        # Boost t0 so ranking is ordered.
        off_rows[0] = _off_game(
            team_id="t0",
            opponent_id="t1",
            week=3,
            points=35,
            epa_per_play=0.25,
        )
        mock_off.return_value = off_rows
        mock_def.return_value = def_rows

        payload = pr.build_nfl_power_rankings(
            season=2024,
            week=4,
            persist=False,
            include_personnel=False,
        )
        self.assertEqual(payload["team_count"], 32)
        self.assertEqual(len(payload["rankings"]), 32)
        ranks = {row["rank"] for row in payload["rankings"]}
        self.assertEqual(ranks, set(range(1, 33)))
        for row in payload["rankings"]:
            self.assertAlmostEqual(
                row["baseline_power_rating"],
                row["offensive_rating"]
                + row["defensive_rating"]
                + row["special_teams_rating"]
                + row.get("sos_adjustment", 0.0)
                + row.get("record_adjustment", 0.0),
                places=2,
            )
            self.assertAlmostEqual(
                row["current_adjusted_rating"],
                row["baseline_power_rating"]
                + row["personnel_adjustment"]
                + row.get("form_adjustment", 0.0),
                places=2,
            )
            self.assertIn("wins", row)
            self.assertIn("losses", row)
            self.assertIn("win_pct", row)

    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_strong_offense_ranks_higher(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        mock_teams.return_value = [
            _team("t0", "AAA"),
            _team("t1", "BBB"),
            _team("t2", "CCC"),
            _team("t3", "DDD"),
        ]
        mock_off.return_value = self._offense_pool()
        mock_def.return_value = self._defense_pool()

        payload = pr.build_nfl_power_rankings(
            season=2024,
            week=6,
            persist=False,
            include_personnel=False,
        )
        by_id = {row["team_id"]: row for row in payload["rankings"]}
        self.assertGreater(
            by_id["t0"]["overall_power_rating"],
            by_id["t1"]["overall_power_rating"],
        )
        self.assertLess(by_id["t0"]["rank"], by_id["t1"]["rank"])

    @patch.object(
        pr,
        "_personnel_adjustments",
        return_value={"t0": {"adjustment": -2.5, "source": "test"}},
    )
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_personnel_separate_from_baseline(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        mock_teams.return_value = [
            _team("t0", "AAA"),
            _team("t1", "BBB"),
        ]
        mock_off.return_value = [
            _off_game(
                team_id="t0",
                opponent_id="t1",
                week=2,
                points=24,
                epa_per_play=0.05,
            ),
            _off_game(
                team_id="t1",
                opponent_id="t0",
                week=2,
                points=20,
                epa_per_play=0.0,
            ),
        ]
        mock_def.return_value = [
            _def_game(
                team_id="t0",
                opponent_id="t1",
                week=2,
                points_allowed=20,
                epa_allowed=0.0,
            ),
            _def_game(
                team_id="t1",
                opponent_id="t0",
                week=2,
                points_allowed=24,
                epa_allowed=0.05,
            ),
        ]
        payload = pr.build_nfl_power_rankings(
            season=2024,
            week=3,
            persist=False,
            include_personnel=True,
        )
        row = next(r for r in payload["rankings"] if r["team_id"] == "t0")
        self.assertAlmostEqual(row["personnel_adjustment"], -2.5, places=3)
        expected = (
            row["baseline_power_rating"]
            - 2.5
            + float(row.get("form_adjustment") or 0.0)
        )
        self.assertAlmostEqual(
            row["current_adjusted_rating"],
            expected,
            places=3,
        )
        self.assertNotEqual(
            row["baseline_power_rating"],
            row["current_adjusted_rating"],
        )

    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_no_future_leakage_in_loaders(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        mock_teams.return_value = [_team("t0", "AAA"), _team("t1", "BBB")]
        mock_off.return_value = []
        mock_def.return_value = []
        payload = pr.build_nfl_power_rankings(
            season=2024,
            week=8,
            persist=False,
        )
        mock_off.assert_called()
        kwargs = mock_off.call_args.kwargs
        self.assertEqual(kwargs.get("before_week"), 8)
        self.assertEqual(payload["team_count"], 0)
        self.assertTrue(payload.get("error") or payload.get("data_limitations"))

    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(
        pr,
        "_load_prior_ratings",
        return_value={
            "t0": {
                "offensive_rating": 4.0,
                "defensive_rating": 2.0,
                "special_teams_rating": 0.0,
            },
            "t1": {
                "offensive_rating": -2.0,
                "defensive_rating": -1.0,
                "special_teams_rating": 0.0,
            },
        },
    )
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_missing_games_do_not_fabricate_from_thin_air(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        """Empty performance window returns empty rankings, not invented values."""
        mock_teams.return_value = _all_teams()
        mock_off.return_value = []
        mock_def.return_value = []
        payload = pr.build_nfl_power_rankings(
            season=2024,
            week=2,
            persist=False,
        )
        self.assertEqual(payload["rankings"], [])
        self.assertEqual(payload["team_count"], 0)

    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_persist_flag_invokes_snapshot(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        mock_teams.return_value = [
            _team("t0", "AAA"),
            _team("t1", "BBB"),
        ]
        mock_off.return_value = [
            _off_game(
                team_id="t0",
                opponent_id="t1",
                week=1,
                points=27,
                epa_per_play=0.1,
            ),
            _off_game(
                team_id="t1",
                opponent_id="t0",
                week=1,
                points=17,
                epa_per_play=-0.05,
            ),
        ]
        mock_def.return_value = [
            _def_game(
                team_id="t0",
                opponent_id="t1",
                week=1,
                points_allowed=17,
                epa_allowed=-0.05,
            ),
            _def_game(
                team_id="t1",
                opponent_id="t0",
                week=1,
                points_allowed=27,
                epa_allowed=0.1,
            ),
        ]
        with patch(
            "app.canonical.fact_team_power_ranking.persist_power_ranking_snapshot"
        ) as persist_mock:
            payload = pr.build_nfl_power_rankings(
                season=2024,
                week=2,
                persist=True,
                include_personnel=False,
            )
            self.assertGreaterEqual(payload["team_count"], 2)
            persist_mock.assert_called_once()
            snap = persist_mock.call_args.args[0]
            self.assertEqual(snap["season"], 2024)
            # Snapshot week is before_week - 1 when before_week > 1
            self.assertEqual(snap["week"], 1)


class RankTrendTests(unittest.TestCase):
    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_trend_is_week_over_week_rank_change(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        mock_teams.return_value = [
            _team("t0", "AAA"),
            _team("t1", "BBB"),
            _team("t2", "CCC"),
        ]
        # Previous week ranks: t1 #1, t0 #2, t2 #3
        previous = {
            "t0": {"rank": 2, "overall_power_rating": 1.0},
            "t1": {"rank": 1, "overall_power_rating": 2.0},
            "t2": {"rank": 3, "overall_power_rating": 0.0},
        }
        # Current games: t0 clearly strongest → should become #1 (↑1)
        mock_off.return_value = [
            _off_game(
                team_id="t0",
                opponent_id="t2",
                week=4,
                points=35,
                epa_per_play=0.25,
            ),
            _off_game(
                team_id="t1",
                opponent_id="t2",
                week=4,
                points=21,
                epa_per_play=0.05,
            ),
            _off_game(
                team_id="t2",
                opponent_id="t0",
                week=4,
                points=10,
                epa_per_play=-0.15,
            ),
        ]
        mock_def.return_value = [
            _def_game(
                team_id="t0",
                opponent_id="t2",
                week=4,
                points_allowed=10,
                epa_allowed=-0.15,
            ),
            _def_game(
                team_id="t1",
                opponent_id="t2",
                week=4,
                points_allowed=17,
                epa_allowed=0.0,
            ),
            _def_game(
                team_id="t2",
                opponent_id="t0",
                week=4,
                points_allowed=35,
                epa_allowed=0.2,
            ),
        ]
        with patch.object(
            pr, "_load_previous_snapshot", return_value=previous
        ):
            payload = pr.build_nfl_power_rankings(
                season=2024,
                week=5,
                persist=False,
                include_personnel=False,
            )
        by_id = {row["team_id"]: row for row in payload["rankings"]}
        self.assertEqual(by_id["t0"]["previous_rank"], 2)
        self.assertEqual(by_id["t1"]["previous_rank"], 1)
        # Trend mirrors week-over-week rank change (prev - current).
        self.assertEqual(
            by_id["t0"]["rating_trend"], by_id["t0"]["rank_change"]
        )
        self.assertEqual(
            by_id["t0"]["rank_change"],
            2 - int(by_id["t0"]["rank"]),
        )
        self.assertEqual(
            by_id["t1"]["rating_trend"], by_id["t1"]["rank_change"]
        )
        # Stronger current profile should not fall behind the prior #1
        # without cause — at worst stays near the top.
        self.assertLessEqual(by_id["t0"]["rank"], 2)

    def test_previous_snapshot_rebuilds_when_db_empty(self):
        rebuilt = {
            "rankings": [
                {"team_id": "t0", "rank": 2},
                {"team_id": "t1", "rank": 1},
            ]
        }
        with patch(
            "app.canonical.fact_team_power_ranking.load_power_rankings_snapshot",
            return_value={"rankings": []},
        ), patch.object(
            pr,
            "build_power_rankings",
            return_value=rebuilt,
        ) as rebuild:
            prior = pr._load_previous_snapshot(
                season=2024,
                week=5,
                sport="NFL",
                include_personnel=False,
            )
        rebuild.assert_called_once()
        self.assertEqual(rebuild.call_args.kwargs.get("week"), 5)
        self.assertEqual(rebuild.call_args.kwargs.get("sport"), "NFL")
        self.assertFalse(rebuild.call_args.kwargs.get("compare_previous"))
        self.assertEqual(prior["t0"]["rank"], 2)
        self.assertEqual(prior["t1"]["rank"], 1)


class CfbPowerRankingsTests(unittest.TestCase):
    @patch.object(pr, "_personnel_adjustments", return_value={})
    @patch.object(pr, "_load_previous_snapshot", return_value={})
    @patch.object(pr, "_load_prior_ratings", return_value={})
    @patch.object(pr, "_load_teams")
    @patch.object(pr, "_load_defense_games")
    @patch.object(pr, "_load_offense_games")
    def test_cfb_ranks_teams_with_games(
        self,
        mock_off,
        mock_def,
        mock_teams,
        *_rest,
    ):
        mock_teams.return_value = [
            {
                **_team("c0", "AAA"),
                "conference": "SEC",
                "subdivision": "fbs",
            },
            {
                **_team("c1", "BBB"),
                "conference": "Big Ten",
                "subdivision": "fbs",
            },
            {
                **_team("c2", "CCC"),
                "conference": "ACC",
                "subdivision": "fbs",
            },
        ]
        mock_off.return_value = [
            _off_game(
                team_id="c0",
                opponent_id="c1",
                week=2,
                points=42,
                epa_per_play=0.0,
            ),
            _off_game(
                team_id="c1",
                opponent_id="c0",
                week=2,
                points=17,
                epa_per_play=0.0,
            ),
            _off_game(
                team_id="c2",
                opponent_id="c0",
                week=2,
                points=24,
                epa_per_play=0.0,
            ),
        ]
        mock_def.return_value = [
            _def_game(
                team_id="c0",
                opponent_id="c1",
                week=2,
                points_allowed=17,
                epa_allowed=0.0,
            ),
            _def_game(
                team_id="c1",
                opponent_id="c0",
                week=2,
                points_allowed=42,
                epa_allowed=0.0,
            ),
            _def_game(
                team_id="c2",
                opponent_id="c0",
                week=2,
                points_allowed=24,
                epa_allowed=0.0,
            ),
        ]
        payload = pr.build_cfb_power_rankings(
            season=2025,
            week=3,
            persist=False,
            include_personnel=False,
            compare_previous=False,
        )
        self.assertEqual(payload["sport"], "CFB")
        self.assertEqual(payload["team_count"], 3)
        self.assertTrue(
            all(row.get("conference") for row in payload["rankings"])
        )
        by_id = {row["team_id"]: row for row in payload["rankings"]}
        self.assertIn("sos_adjustment", by_id["c0"])
        self.assertEqual(len(payload["rankings"]), 3)

    def test_cfb_offense_weights_ignore_epa(self):
        from app.analysis.insights.betting.betting_sport import (
            resolve_betting_sport,
        )

        cfb = resolve_betting_sport("CFB")
        weights = pr._offense_weights(cfb)
        self.assertEqual(weights["epa_per_play"], 0.0)
        self.assertGreater(weights["scoring_margin_proxy"], 0.5)


class MatchupOrientationTests(unittest.TestCase):


    def test_higher_home_rating_projects_positive_margin(self):
        rankings = {
            "h": {
                "current_adjusted_rating": 5.0,
                "offensive_rating": 3.0,
                "defensive_rating": 2.0,
            },
            "a": {
                "current_adjusted_rating": -2.0,
                "offensive_rating": -1.0,
                "defensive_rating": -1.0,
            },
        }
        result = pr.project_margin_from_power_rankings(
            home_team_id="h",
            away_team_id="a",
            rankings_by_team=rankings,
            home_field_advantage=2.0,
        )
        self.assertTrue(result["available"])
        self.assertGreater(result["expected_margin"], 0)
        self.assertGreater(
            result["home_projected_score"],
            result["away_projected_score"],
        )

    def test_missing_ratings_unavailable(self):
        result = pr.project_margin_from_power_rankings(
            home_team_id="h",
            away_team_id="a",
            rankings_by_team={},
        )
        self.assertFalse(result["available"])
        self.assertIsNone(result["expected_margin"])


if __name__ == "__main__":
    unittest.main()
