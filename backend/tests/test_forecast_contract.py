"""Forecast contract and showdown use of the joint distribution."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from app.analysis.insights.dfs.forecast_contract import (
    apply_forecast_contract,
    evaluate_lineup_outcomes,
    thresholds_for,
)
from app.analysis.insights.dfs.portfolio import generate_portfolio
from app.analysis.insights.dfs.sites import get_site_config
from tests.test_dfs_portfolio import _fake_player


def _band(center: float, n: int = 40) -> list[float]:
    return [center - 1.0] * 10 + [center] * 20 + [center + 1.0] * 10


class ForecastContractTests(unittest.TestCase):
    def test_contract_keeps_legacy_projections_and_versions_the_forecast(self):
        draws = np.array(_band(12.0)[:28] + [24.0] * 12)
        player = {
            "player_id": "rb1",
            "position": "RB",
            "projection": 11.0,
            "base_projection": 10.5,
            "raw_projection": 14.0,
            "role_forecast": {
                "position": "RB",
                "listed_depth": 2,
                "effective_depth": 1,
                "promoted": True,
                "shares": {"carry_share": 0.48},
                "opportunities": {"carries": 16.0, "targets": 4.0},
            },
        }
        contract = apply_forecast_contract(
            player,
            draws,
            contest_type="showdown",
        )
        self.assertEqual(player["projection"], 11.0)
        self.assertEqual(player["base_projection"], 10.5)
        self.assertEqual(player["raw_projection"], 14.0)
        self.assertEqual(contract["projection_version"], "player_forecast_v1")
        self.assertIn("joint_game_simulation", contract["projection_source"])
        self.assertGreater(player["expected_points"], player["median_projection"])
        self.assertGreater(player["ceiling_projection"], player["median_projection"])
        self.assertGreater(player["median_projection"], player["floor_projection"])
        self.assertGreater(player["probability_20_plus"], 0.2)
        self.assertEqual(player["projected_opportunity"]["components"]["carries"], 16.0)
        self.assertGreater(player["role_change_signal"], 0.0)
        self.assertGreater(player["projection_uncertainty"], 0.0)

    def test_strong_outcome_threshold_follows_position(self):
        self.assertEqual(thresholds_for("QB", "classic")[1], 22.0)
        self.assertEqual(thresholds_for("RB", "showdown")[1], 20.0)
        draws = np.array([18.0] * 25 + [21.0] * 10 + [24.0] * 5)
        player = {"player_id": "qb", "position": "QB"}
        contract = apply_forecast_contract(
            player,
            draws,
            contest_type="classic",
        )
        self.assertEqual(contract["strong_outcome_threshold"], 22.0)
        self.assertLess(
            contract["strong_outcome_probability"],
            contract["probability_20_plus"],
        )
        moved = apply_forecast_contract(
            player,
            draws,
            contest_type="classic",
            threshold_overrides={"QB": (15.0, 18.0)},
        )
        self.assertEqual(moved["strong_outcome_threshold"], 18.0)
        self.assertGreater(
            moved["strong_outcome_probability"],
            contract["strong_outcome_probability"],
        )

    def test_lineup_outcomes_use_one_captain_and_shared_sims(self):
        shared_high = [8.0] * 20 + [22.0] * 20
        quiet = [6.0] * 40
        captain = _fake_player(
            player_id="qb",
            name="QB",
            position="QB",
            salary=7000,
            projection=15.0,
            team="TB",
        )
        back = _fake_player(
            player_id="rb",
            name="RB",
            position="RB",
            salary=6000,
            projection=12.0,
            team="TB",
        )
        apply_forecast_contract(captain, np.array(shared_high), contest_type="showdown")
        apply_forecast_contract(back, np.array(shared_high), contest_type="showdown")
        other = _fake_player(
            player_id="wr",
            name="WR",
            position="WR",
            salary=4000,
            projection=8.0,
            team="ATL",
        )
        apply_forecast_contract(other, np.array(quiet), contest_type="showdown")
        captain["slot"] = "CPT"
        captain["is_captain"] = True
        captain["captain_multiplier"] = 1.5
        back["slot"] = "FLEX"
        other["slot"] = "FLEX"
        outcomes = evaluate_lineup_outcomes([captain, back, other])
        self.assertIsNotNone(outcomes)
        # Captain points are 1.5 times the same sims as the back,
        # so the lineup ceiling is not the sum of three medians.
        self.assertGreater(outcomes["ceiling"], 40.0)
        self.assertGreater(outcomes["mean_pairwise_correlation"], 0.5)
        self.assertIsNotNone(outcomes["captain_upside"])
        self.assertGreater(outcomes["player_importance"]["qb"], 0.0)
        self.assertGreater(outcomes["player_importance"]["rb"], 0.0)


class ShowdownPathExposureTests(unittest.TestCase):
    @patch(
        "app.analysis.insights.dfs.portfolio.load_showdown_script_context"
    )
    @patch("app.analysis.insights.dfs.portfolio.build_dfs_slate")
    def test_a_plausible_spike_earns_exposure_without_leading_value(
        self,
        mock_slate,
        mock_scripts,
    ):
        site = get_site_config("draftkings", contest_type="showdown")
        specs = [
            ("tb_qb", "QB", "TB", 7600, _band(21.0)),
            ("tb_rb", "RB", "TB", 6400, [6.0] * 8 + [9.0] * 8 + [12.0] * 8 + [16.0] * 4 + [26.0] * 12),
            ("tb_wr_value", "WR", "TB", 4000, _band(14.0)),
            ("tb_wr2", "WR", "TB", 5200, _band(11.0)),
            ("tb_te", "TE", "TB", 3800, _band(8.0)),
            ("tb_punt", "WR", "TB", 2800, [0.0] * 32 + [30.0] * 8),
            ("atl_qb", "QB", "ATL", 7000, _band(19.0)),
            ("atl_rb", "RB", "ATL", 6000, _band(12.0)),
            ("atl_wr1", "WR", "ATL", 5400, _band(13.0)),
            ("atl_wr2", "WR", "ATL", 4300, _band(9.0)),
            ("atl_te", "TE", "ATL", 3400, _band(7.0)),
            ("tb_def", "DEF", "TB", 2800, _band(6.0)),
            ("atl_def", "DEF", "ATL", 2600, _band(5.5)),
        ]
        players = []
        for player_id, position, team, salary, sample in specs:
            row = _fake_player(
                player_id=player_id,
                name="Bucky Irving" if player_id == "tb_rb" else player_id,
                position=position,
                salary=salary,
                projection=float(np.median(sample)),
                team=team,
            )
            row["raw_projection"] = row["projection"]
            row["base_projection"] = row["projection"]
            if player_id == "tb_rb":
                row["role_forecast"] = {
                    "position": "RB",
                    "listed_depth": 2,
                    "effective_depth": 1,
                    "promoted": True,
                    "shares": {"carry_share": 0.55},
                    "opportunities": {"carries": 18.0, "targets": 5.0},
                }
            apply_forecast_contract(
                row,
                np.array(sample, dtype=float),
                contest_type="showdown",
            )
            players.append(row)

        by_id = {row["player_id"]: row for row in players}
        self.assertLess(by_id["tb_rb"]["value"], by_id["tb_wr_value"]["value"])
        self.assertGreater(
            by_id["tb_rb"]["probability_20_plus"],
            by_id["tb_wr_value"]["probability_20_plus"],
        )
        mock_slate.return_value = {
            "slate_id": "nfl-2026-6-sd-ATL-TB",
            "label": "Showdown — ATL @ TB",
            "season": 2026,
            "week": 6,
            "site": "draftkings",
            "site_name": "DraftKings",
            "contest_type": "showdown",
            "salary_cap": site["salary_cap"],
            "captain_multiplier": site.get("captain_multiplier", 1.5),
            "roster": site["roster"],
            "players": players,
            "player_count": len(players),
            "home_team": "TB",
            "away_team": "ATL",
            "games": [
                {
                    "game_id": "g-atl-tb",
                    "home_team": "TB",
                    "away_team": "ATL",
                }
            ],
            "freshness": {},
        }
        mock_scripts.return_value = {
            "home_team": "TB",
            "away_team": "ATL",
            "favorite": "TB",
            "underdog": "ATL",
            "market_spread": -3.5,
            "market_total": 47.5,
            "projected_home_score": 26.0,
            "projected_away_score": 21.0,
            "projected_total": 47.0,
            "scripts_raw": [],
            "allocations": [
                {
                    "script_id": "shootout",
                    "label": "Shootout",
                    "code": "B",
                    "weight": 0.5,
                    "lineup_count": 6,
                    "raw_probability": 0.5,
                    "implication": "Both QBs",
                },
                {
                    "script_id": "favorite_run",
                    "label": "Favorite runs",
                    "code": "A",
                    "weight": 0.5,
                    "lineup_count": 6,
                    "raw_probability": 0.5,
                    "implication": "Favorite RB",
                },
            ],
        }
        result = generate_portfolio(
            slate_id="nfl-2026-6-sd-ATL-TB",
            contest_type="showdown",
            lineup_count=12,
            strategy="balanced",
            default_max_exposure=0.7,
            seed=4,
        )
        exposure = {
            row["player_id"]: row
            for row in result["exposure"]["players"]
        }
        self.assertGreaterEqual(len(result["lineups"]), 10)
        for lineup in result["lineups"]:
            self.assertLessEqual(
                lineup["salary_used"],
                lineup["salary_cap"],
            )
            self.assertIn("lineup_outcomes", lineup)
            self.assertIsNotNone(lineup["lineup_outcomes"]["captain_upside"])
            self.assertIsNotNone(lineup["lineup_outcomes"]["flex_upside"])
        rb = exposure["tb_rb"]
        punt = exposure.get("tb_punt") or {"lineups": 0}
        qb = exposure["tb_qb"]
        self.assertGreaterEqual(rb["lineups"], 3)
        self.assertGreater(rb["lineups"], int(punt.get("lineups") or 0))
        self.assertGreaterEqual(qb["lineups"], 3)
        self.assertGreaterEqual(len(rb["script_exposure"]), 1)
        included = [
            lineup
            for lineup in result["lineups"]
            if "tb_rb" in (lineup.get("player_ids") or [])
        ]
        self.assertGreater(
            included[0]["lineup_outcomes"]["player_importance"]["tb_rb"],
            0.0,
        )
        stored = next(
            player
            for player in included[0]["players"]
            if player["player_id"] == "tb_rb"
        )
        self.assertEqual(stored["raw_projection"], by_id["tb_rb"]["raw_projection"])
        self.assertEqual(stored["projection_version"], "player_forecast_v1")


if __name__ == "__main__":
    unittest.main()
