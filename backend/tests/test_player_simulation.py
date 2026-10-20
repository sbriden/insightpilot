"""Joint game and player simulation."""

from __future__ import annotations

import unittest

import numpy as np

from app.analysis.insights.dfs.player_simulation import (
    SimulationConfig,
    simulate_game_details,
)


def _player(
    player_id: str,
    team: str,
    opponent: str,
    position: str,
    shares: dict[str, float],
    *,
    points: float = 24.0,
    opponent_points: float = 21.0,
    availability: float = 1.0,
) -> dict:
    return {
        "player_id": player_id,
        "team": team,
        "opponent": opponent,
        "position": position,
        "projection": 16.0,
        "adjustment_source": "game_forecast",
        "role_forecast": {
            "position": position,
            "availability": availability,
            "effective_depth": 1 if position != "WR" or player_id.endswith("1") else 2,
            "shares": shares,
        },
        "scoring_components": {
            "rates": {},
            "skill_multiplier": 1.0,
        },
        "game_environment": {
            "team": team,
            "opponent": opponent,
            "projected_points": points,
            "opponent_points": opponent_points,
            "expected_plays": 63.0,
        },
    }


class JointSimulationTests(unittest.TestCase):
    def _roster(self) -> list[dict]:
        return [
            _player(
                "qb",
                "BUF",
                "NYJ",
                "QB",
                {
                    "dropback_share": 0.97,
                    "designed_rush_share": 0.06,
                    "red_zone_pass_share": 0.96,
                },
            ),
            _player(
                "rb",
                "BUF",
                "NYJ",
                "RB",
                {
                    "carry_share": 0.55,
                    "target_share": 0.12,
                    "goal_line_share": 0.58,
                },
            ),
            _player(
                "wr1",
                "BUF",
                "NYJ",
                "WR",
                {
                    "target_share": 0.24,
                    "red_zone_target_share": 0.28,
                },
            ),
            _player(
                "wr2",
                "BUF",
                "NYJ",
                "WR",
                {
                    "target_share": 0.16,
                    "red_zone_target_share": 0.14,
                },
            ),
            _player(
                "qb2",
                "NYJ",
                "BUF",
                "QB",
                {
                    "dropback_share": 0.97,
                    "designed_rush_share": 0.04,
                    "red_zone_pass_share": 0.95,
                },
                points=21.0,
                opponent_points=24.0,
            ),
        ]

    def test_percentiles_replace_a_fixed_range(self):
        details = simulate_game_details(
            self._roster(),
            config=SimulationConfig(n_sims=300, seed=7),
        )
        points = details["points"]["qb"]
        floor = float(np.percentile(points, 10))
        median = float(np.percentile(points, 50))
        ceiling = float(np.percentile(points, 90))
        self.assertLess(floor, median)
        self.assertLess(median, ceiling)
        self.assertGreater(ceiling - floor, 4.0)
        env = details["teams"]["BUF"]
        identity = env["offensive_tds"] * 7.0 + env["field_goals"] * 3.0
        self.assertTrue(np.allclose(identity, env["points"], atol=0.05))

    def test_one_touchdown_has_one_catcher_and_one_passer(self):
        details = simulate_game_details(
            self._roster(),
            config=SimulationConfig(n_sims=200, seed=11),
        )
        parts = details["components"]
        caught = parts["wr1"]["receiving_tds"] + parts["wr2"]["receiving_tds"]
        thrown = parts["qb"]["pass_tds"]
        self.assertTrue(np.allclose(caught, thrown))
        # The two receivers are not each credited with every score.
        both = np.minimum(parts["wr1"]["receiving_tds"], parts["wr2"]["receiving_tds"])
        self.assertLess(float(np.mean(both)), float(np.mean(caught)))

    def test_receiver_yards_match_the_quarterback(self):
        details = simulate_game_details(
            self._roster(),
            config=SimulationConfig(n_sims=80, seed=3),
        )
        parts = details["components"]
        received = (
            parts["wr1"]["receiving_yards"]
            + parts["wr2"]["receiving_yards"]
            + parts["rb"]["receiving_yards"]
        )
        self.assertTrue(
            np.allclose(received, parts["qb"]["pass_yards"], atol=0.05)
        )

    def test_leading_adds_rushes_and_trailing_adds_passes(self):
        details = simulate_game_details(
            self._roster(),
            config=SimulationConfig(n_sims=500, seed=21),
        )
        buf = details["teams"]["BUF"]
        nyj = details["teams"]["NYJ"]
        leading = buf["margin"] > 7
        trailing = buf["margin"] < -7
        self.assertGreater(int(leading.sum()), 30)
        self.assertGreater(int(trailing.sum()), 30)
        self.assertGreater(
            float(buf["rush_attempts"][leading].mean()),
            float(buf["rush_attempts"][trailing].mean()),
        )
        self.assertGreater(
            float(nyj["pass_attempts"][leading].mean()),
            float(nyj["pass_attempts"][trailing].mean()),
        )
        self.assertGreater(
            float(details["components"]["rb"]["carries"][leading].mean()),
            float(details["components"]["rb"]["carries"][trailing].mean()),
        )

    def test_an_absence_moves_targets_to_the_teammate(self):
        healthy = simulate_game_details(
            self._roster(),
            config=SimulationConfig(n_sims=250, seed=5),
        )
        injured_roster = self._roster()
        for player in injured_roster:
            if player["player_id"] != "wr1":
                continue
            player["role_forecast"]["availability"] = 0.25
            player["role_forecast"]["shares"] = {
                "target_share": 0.24 * 0.25,
                "red_zone_target_share": 0.28 * 0.25,
            }
        injured = simulate_game_details(
            injured_roster,
            config=SimulationConfig(n_sims=250, seed=5),
        )
        self.assertGreater(
            float(injured["components"]["wr2"]["targets"].mean()),
            float(healthy["components"]["wr2"]["targets"].mean()),
        )

    def test_percentile_levels_are_configurable(self):
        roster = self._roster()
        low = simulate_game_details(
            roster,
            config=SimulationConfig(n_sims=300, seed=9, floor_percentile=10),
        )
        high = simulate_game_details(
            roster,
            config=SimulationConfig(n_sims=300, seed=9, floor_percentile=25),
        )
        tenth = float(np.percentile(low["points"]["qb"], 10))
        twenty_fifth = float(np.percentile(high["points"]["qb"], 25))
        self.assertGreater(twenty_fifth, tenth)

    def test_published_floor_is_a_percentile_not_a_guarantee(self):
        from app.analysis.insights.dfs.player_simulation import (
            apply_joint_simulation,
        )

        roster = self._roster()
        apply_joint_simulation(
            roster,
            config=SimulationConfig(n_sims=200, seed=4),
        )
        player = roster[0]
        self.assertEqual(player["simulation"]["source"], "joint_game_simulation")
        self.assertLess(player["floor"], player["projection"])
        self.assertLess(player["projection"], player["ceiling"])
        self.assertIn("not a guaranteed", player["simulation"]["note"])


if __name__ == "__main__":
    unittest.main()
