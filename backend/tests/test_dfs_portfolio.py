"""Tests for DFS portfolio generation and analysis."""

from __future__ import annotations

import unittest
from collections import Counter
from unittest.mock import patch

from app.analysis.insights.dfs.portfolio import (
    _jaccard,
    _lineup_key,
    analyze_portfolio,
    generate_portfolio,
)
from app.analysis.insights.dfs.sites import get_site_config


def _fake_player(
    *,
    player_id: str,
    name: str,
    position: str,
    salary: int,
    projection: float,
    ownership: float = 0.1,
    team: str = "KC",
    status: str = "Active",
) -> dict:
    return {
        "dfs_player_id": f"draftkings:{player_id}",
        "player_id": player_id,
        "name": name,
        "position": position,
        "eligible_positions": (
            [position, "FLEX"]
            if position in {"RB", "WR", "TE"}
            else (
                ["DST", "DEF"]
                if position == "DEF"
                else [position]
            )
        ),
        "team": team,
        "opponent": "NYJ",
        "salary": salary,
        "projection": projection,
        "floor": round(projection * 0.7, 1),
        "ceiling": round(projection * 1.4, 1),
        "projected_ownership": ownership,
        "value": round(projection / (salary / 1000.0), 2),
        "matchup_label": "Favorable",
        "signals": [],
        "status": status,
    }


def _fake_slate() -> dict:
    players = [
        _fake_player(
            player_id="qb1",
            name="QB One",
            position="QB",
            salary=7500,
            projection=22.0,
            team="BUF",
        ),
        _fake_player(
            player_id="qb2",
            name="QB Two",
            position="QB",
            salary=6500,
            projection=18.0,
            team="MIA",
        ),
        _fake_player(
            player_id="qb3",
            name="QB Three",
            position="QB",
            salary=6000,
            projection=16.0,
            team="NE",
        ),
        _fake_player(
            player_id="rb1",
            name="RB One",
            position="RB",
            salary=8000,
            projection=20.0,
            team="DET",
        ),
        _fake_player(
            player_id="rb2",
            name="RB Two",
            position="RB",
            salary=7000,
            projection=17.0,
            team="GB",
        ),
        _fake_player(
            player_id="rb3",
            name="RB Three",
            position="RB",
            salary=5500,
            projection=14.0,
            team="CHI",
        ),
        _fake_player(
            player_id="rb4",
            name="RB Four",
            position="RB",
            salary=4800,
            projection=12.0,
            team="MIN",
        ),
        _fake_player(
            player_id="wr1",
            name="WR One",
            position="WR",
            salary=7800,
            projection=19.0,
            team="DAL",
        ),
        _fake_player(
            player_id="wr2",
            name="WR Two",
            position="WR",
            salary=7200,
            projection=17.5,
            team="PHI",
        ),
        _fake_player(
            player_id="wr3",
            name="WR Three",
            position="WR",
            salary=6100,
            projection=15.0,
            team="NYG",
        ),
        _fake_player(
            player_id="wr4",
            name="WR Four",
            position="WR",
            salary=5200,
            projection=13.0,
            team="WAS",
        ),
        _fake_player(
            player_id="wr5",
            name="WR Five",
            position="WR",
            salary=4500,
            projection=11.0,
            team="ATL",
        ),
        _fake_player(
            player_id="te1",
            name="TE One",
            position="TE",
            salary=5600,
            projection=13.5,
            team="KC",
        ),
        _fake_player(
            player_id="te2",
            name="TE Two",
            position="TE",
            salary=4200,
            projection=10.0,
            team="LV",
        ),
        _fake_player(
            player_id="dst1",
            name="DST One",
            position="DEF",
            salary=3000,
            projection=8.0,
            team="SF",
        ),
        _fake_player(
            player_id="dst2",
            name="DST Two",
            position="DEF",
            salary=2700,
            projection=7.0,
            team="SEA",
        ),
        _fake_player(
            player_id="dst3",
            name="DST Three",
            position="DEF",
            salary=2500,
            projection=6.0,
            team="LAR",
        ),
        _fake_player(
            player_id="qb4",
            name="QB Four",
            position="QB",
            salary=5800,
            projection=15.0,
            team="NYJ",
        ),
        _fake_player(
            player_id="rb5",
            name="RB Five",
            position="RB",
            salary=4300,
            projection=10.5,
            team="NO",
        ),
        _fake_player(
            player_id="rb6",
            name="RB Six",
            position="RB",
            salary=4000,
            projection=9.5,
            team="TB",
        ),
        _fake_player(
            player_id="wr6",
            name="WR Six",
            position="WR",
            salary=4100,
            projection=10.0,
            team="CAR",
        ),
        _fake_player(
            player_id="wr7",
            name="WR Seven",
            position="WR",
            salary=3800,
            projection=9.0,
            team="TB",
        ),
        _fake_player(
            player_id="wr8",
            name="WR Eight",
            position="WR",
            salary=3500,
            projection=8.0,
            team="NO",
        ),
        _fake_player(
            player_id="te3",
            name="TE Three",
            position="TE",
            salary=3600,
            projection=8.5,
            team="BAL",
        ),
    ]
    return {
        "slate_id": "nfl-test-main",
        "label": "Test Main",
        "season": 2026,
        "week": 2,
        "site": "draftkings",
        "salary_cap": 50000,
        "roster": [
            {"slot": "QB", "positions": ["QB"]},
            {"slot": "RB", "positions": ["RB"]},
            {"slot": "RB", "positions": ["RB"]},
            {"slot": "WR", "positions": ["WR"]},
            {"slot": "WR", "positions": ["WR"]},
            {"slot": "WR", "positions": ["WR"]},
            {"slot": "TE", "positions": ["TE"]},
            {"slot": "FLEX", "positions": ["RB", "WR", "TE"]},
            {"slot": "DST", "positions": ["DST", "DEF"]},
        ],
        "players": players,
        "player_count": len(players),
        "freshness": {"note": "test"},
    }


class PortfolioTests(unittest.TestCase):
    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_generates_unique_lineups(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=5,
            strategy="balanced",
            seed=42,
        )
        lineups = result["lineups"]
        self.assertGreaterEqual(len(lineups), 3)
        keys = {_lineup_key(item["players"]) for item in lineups}
        self.assertEqual(len(keys), len(lineups))
        self.assertIn("portfolio", result)
        self.assertGreater(
            result["portfolio"]["unique_players"], 9
        )

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_respects_exclude(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=4,
            strategy="gpp",
            excluded_players=["qb1"],
            seed=7,
        )
        for lineup in result["lineups"]:
            ids = {
                player["player_id"]
                for player in lineup["players"]
            }
            self.assertNotIn("qb1", ids)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_fills_requested_gpp_lineups(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=20,
            strategy="gpp",
            default_max_exposure=0.5,
            max_lineup_similarity=0.6,
            seed=21,
        )
        self.assertGreaterEqual(len(result["lineups"]), 18)
        self.assertEqual(
            result["portfolio"]["requested_lineup_count"], 20
        )
        for row in result["exposure"]["players"]:
            self.assertLessEqual(row["exposure"], 0.5 + 1e-9)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_max_similarity_affects_overlap(self, _mock_slate):
        tight = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=8,
            strategy="custom",
            default_max_exposure=0.75,
            max_lineup_similarity=0.35,
            seed=44,
        )
        loose = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=8,
            strategy="custom",
            default_max_exposure=0.75,
            max_lineup_similarity=0.90,
            seed=44,
        )
        self.assertGreaterEqual(len(tight["lineups"]), 4)
        self.assertGreaterEqual(len(loose["lineups"]), 4)
        self.assertLessEqual(
            float(tight["portfolio"]["average_lineup_similarity"]),
            float(loose["portfolio"]["average_lineup_similarity"])
            + 0.05,
        )

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_default_max_exposure_hard_cap(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=8,
            strategy="gpp",
            default_max_exposure=0.5,
            seed=11,
        )
        for row in result["exposure"]["players"]:
            self.assertLessEqual(row["exposure"], 0.5 + 1e-9)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_individual_max_exposure_hard_cap(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=10,
            strategy="balanced",
            default_max_exposure=0.8,
            player_exposure={"max": {"qb1": 0.3}},
            seed=5,
        )
        by_id = {
            row["player_id"]: row
            for row in result["exposure"]["players"]
        }
        if "qb1" in by_id:
            self.assertLessEqual(
                by_id["qb1"]["exposure"], 0.3 + 1e-9
            )
        for row in result["exposure"]["players"]:
            self.assertLessEqual(row["exposure"], 0.8 + 1e-9)

    @patch("app.analysis.insights.dfs.portfolio.build_dfs_slate")
    def test_excludes_non_active_roster_status(self, mock_slate):
        slate = _fake_slate()
        slate["players"].append(
            _fake_player(
                player_id="wr_reserve",
                name="Reserve Wideout",
                position="WR",
                salary=3000,
                projection=40.0,
                status="Reserve",
            )
        )
        mock_slate.return_value = slate
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=4,
            strategy="balanced",
            seed=3,
        )
        for lineup in result["lineups"]:
            ids = {
                player["player_id"]
                for player in lineup["players"]
            }
            self.assertNotIn("wr_reserve", ids)

    @patch("app.analysis.insights.dfs.portfolio.build_dfs_slate")
    def test_showdown_captain_diversity(self, mock_slate):
        site = get_site_config("draftkings", contest_type="showdown")
        players = []
        for index in range(12):
            players.append(
                _fake_player(
                    player_id=f"p{index}",
                    name=f"Player {index}",
                    position=(
                        "QB"
                        if index == 0
                        else "RB"
                        if index < 4
                        else "WR"
                        if index < 8
                        else "TE"
                    ),
                    salary=7000 - index * 200,
                    projection=24.0 - index * 0.8,
                    team="BUF" if index % 2 == 0 else "DET",
                )
            )
        mock_slate.return_value = {
            "slate_id": "nfl-test-sd",
            "label": "Showdown",
            "site": "draftkings",
            "site_name": "DraftKings",
            "contest_type": "showdown",
            "salary_cap": site["salary_cap"],
            "captain_multiplier": site.get(
                "captain_multiplier", 1.5
            ),
            "roster": site["roster"],
            "players": players,
            "player_count": len(players),
            "freshness": {},
        }
        result = generate_portfolio(
            slate_id="nfl-test-sd",
            contest_type="showdown",
            lineup_count=8,
            strategy="balanced",
            seed=3,
        )
        captains = [
            next(
                player["player_id"]
                for player in lineup["players"]
                if player.get("slot") == "CPT"
            )
            for lineup in result["lineups"]
        ]
        self.assertGreaterEqual(len(result["lineups"]), 4)
        self.assertGreaterEqual(len(set(captains)), 3)

    @patch("app.analysis.insights.dfs.portfolio.build_dfs_slate")
    def test_showdown_captain_max_exposure(self, mock_slate):
        site = get_site_config("draftkings", contest_type="showdown")
        players = []
        for index in range(12):
            players.append(
                _fake_player(
                    player_id=f"p{index}",
                    name=f"Player {index}",
                    position=(
                        "QB"
                        if index == 0
                        else "RB"
                        if index < 4
                        else "WR"
                        if index < 8
                        else "TE"
                    ),
                    salary=7000 - index * 200,
                    projection=24.0 - index * 0.8,
                    team="BUF" if index % 2 == 0 else "DET",
                )
            )
        mock_slate.return_value = {
            "slate_id": "nfl-test-sd-cpt",
            "label": "Showdown",
            "site": "draftkings",
            "site_name": "DraftKings",
            "contest_type": "showdown",
            "salary_cap": site["salary_cap"],
            "captain_multiplier": site.get(
                "captain_multiplier", 1.5
            ),
            "roster": site["roster"],
            "players": players,
            "player_count": len(players),
            "freshness": {},
        }
        result = generate_portfolio(
            slate_id="nfl-test-sd-cpt",
            contest_type="showdown",
            lineup_count=10,
            strategy="balanced",
            default_max_exposure=1.0,
            default_max_captain_exposure=0.3,
            seed=7,
        )
        self.assertGreaterEqual(len(result["lineups"]), 4)
        for row in result["exposure"]["players"]:
            self.assertIn("captain_exposure", row)
            self.assertLessEqual(
                row["captain_exposure"], 0.3 + 1e-9
            )

    @patch(
        "app.analysis.insights.dfs.portfolio.load_showdown_script_context"
    )
    @patch("app.analysis.insights.dfs.portfolio.build_dfs_slate")
    def test_showdown_script_weighted_portfolio(
        self,
        mock_slate,
        mock_scripts,
    ):
        site = get_site_config("draftkings", contest_type="showdown")
        players = []
        for index in range(14):
            team = "BUF" if index % 2 == 0 else "MIA"
            position = (
                "QB"
                if index < 2
                else "RB"
                if index < 6
                else "WR"
                if index < 10
                else "TE"
                if index < 12
                else "DEF"
            )
            players.append(
                _fake_player(
                    player_id=f"sd{index}",
                    name=f"SD Player {index}",
                    position=position,
                    salary=7200 - index * 180,
                    projection=23.0 - index * 0.7,
                    team=team,
                )
            )
        mock_slate.return_value = {
            "slate_id": "nfl-2026-3-sd-MIA-BUF",
            "label": "Showdown — MIA @ BUF",
            "season": 2026,
            "site": "draftkings",
            "site_name": "DraftKings",
            "contest_type": "showdown",
            "salary_cap": site["salary_cap"],
            "captain_multiplier": site.get(
                "captain_multiplier", 1.5
            ),
            "roster": site["roster"],
            "players": players,
            "player_count": len(players),
            "home_team": "BUF",
            "away_team": "MIA",
            "games": [
                {
                    "game_id": "g-buf-mia",
                    "home_team": "BUF",
                    "away_team": "MIA",
                }
            ],
            "freshness": {},
        }
        mock_scripts.return_value = {
            "home_team": "BUF",
            "away_team": "MIA",
            "favorite": "BUF",
            "underdog": "MIA",
            "market_spread": -6.5,
            "market_total": 48.5,
            "projected_home_score": 27.0,
            "projected_away_score": 20.0,
            "projected_total": 47.0,
            "scripts_raw": [],
            "allocations": [
                {
                    "script_id": "low_scoring",
                    "label": "Low scoring game",
                    "code": "D",
                    "weight": 0.55,
                    "lineup_count": 4,
                    "raw_probability": 0.48,
                    "implication": "RBs, DST",
                },
                {
                    "script_id": "favorite_controls",
                    "label": "Favorite controls game",
                    "code": "A",
                    "weight": 0.25,
                    "lineup_count": 1,
                    "raw_probability": 0.22,
                    "implication": "Favorite QB/RB",
                },
                {
                    "script_id": "shootout",
                    "label": "Shootout",
                    "code": "B",
                    "weight": 0.20,
                    "lineup_count": 1,
                    "raw_probability": 0.18,
                    "implication": "Both QBs",
                },
            ],
        }
        result = generate_portfolio(
            slate_id="nfl-2026-3-sd-MIA-BUF",
            contest_type="showdown",
            lineup_count=6,
            strategy="balanced",
            seed=9,
        )
        self.assertTrue(
            result["optimization_metadata"]["game_script_driven"]
        )
        self.assertIsNotNone(result.get("game_scripts"))
        counts = {}
        for lineup in result["lineups"]:
            sid = lineup.get("game_script_id")
            if sid:
                counts[sid] = counts.get(sid, 0) + 1
        # Highest-weight script must claim the most seats.
        self.assertGreaterEqual(
            counts.get("low_scoring", 0),
            counts.get("favorite_controls", 0),
        )
        self.assertGreaterEqual(
            counts.get("low_scoring", 0),
            counts.get("shootout", 0),
        )
        self.assertGreaterEqual(counts.get("low_scoring", 0), 3)
        mix = {
            row["script_id"]: row["lineup_count"]
            for row in (result.get("game_scripts") or {}).get(
                "allocations"
            )
            or []
        }
        self.assertEqual(
            mix.get("low_scoring"),
            counts.get("low_scoring", 0),
        )

    def test_select_portfolio_prefers_underfilled_script_quotas(self):
        from app.analysis.insights.dfs.portfolio import (
            _select_portfolio_by_script,
        )

        def _cand(script_id: str, points: float, suffix: str):
            players = [
                {
                    "player_id": f"{script_id}-{suffix}-{i}",
                    "slot": "CPT" if i == 0 else "FLEX",
                }
                for i in range(6)
            ]
            return {
                "game_script_id": script_id,
                "game_script_code": script_id[:1].upper(),
                "projected_points": points,
                "projected_ceiling": points + 5,
                "players": players,
                "player_ids": [
                    str(p["player_id"]) for p in players
                ],
                "lineup_id": f"pf-{script_id}-{suffix}",
            }

        # Shootout candidates score higher, but low_scoring owns
        # most of the quota — selection must honor that.
        candidates = [
            _cand("shootout", 120 - i, str(i)) for i in range(8)
        ] + [
            _cand("low_scoring", 90 - i, str(i)) for i in range(8)
        ]
        allocations = [
            {
                "script_id": "low_scoring",
                "weight": 0.7,
                "lineup_count": 5,
            },
            {
                "script_id": "shootout",
                "weight": 0.3,
                "lineup_count": 2,
            },
        ]
        selected, _ = _select_portfolio_by_script(
            candidates=candidates,
            allocations=allocations,
            lineup_count=7,
            max_similarity=1.0,
            default_max_exposure=1.0,
            default_max_captain_exposure=1.0,
            exposure_cfg={
                "lock": set(),
                "exclude": set(),
                "max": {},
                "min": {},
                "target": {},
                "captain_max": {},
                "captain_min": {},
            },
        )
        counts = Counter(
            lineup.get("game_script_id") for lineup in selected
        )
        self.assertEqual(counts.get("low_scoring"), 5)
        self.assertEqual(counts.get("shootout"), 2)
        self.assertEqual(
            allocations[0]["lineup_count"],
            5,
        )

    def test_jaccard_and_analyze_signals(self):
        self.assertAlmostEqual(
            _jaccard({"a", "b"}, {"a", "b"}), 1.0
        )
        self.assertAlmostEqual(
            _jaccard({"a", "b", "c"}, {"a", "b", "d"}),
            0.5,
        )
        lineups = []
        shared = ["qb1", "rb1", "rb2", "wr1", "wr2", "wr3", "te1"]
        for index in range(4):
            players = [
                {
                    "player_id": pid,
                    "name": pid,
                    "position": "WR",
                    "projection": 10,
                    "ceiling": 14,
                    "floor": 7,
                    "projected_ownership": 0.1,
                    "salary": 5000,
                }
                for pid in shared
            ]
            players.append(
                {
                    "player_id": f"flex{index}",
                    "name": f"Flex {index}",
                    "position": "RB",
                    "projection": 8,
                    "ceiling": 12,
                    "floor": 5,
                    "projected_ownership": 0.05,
                    "salary": 4000,
                }
            )
            players.append(
                {
                    "player_id": "dst1",
                    "name": "DST",
                    "position": "DEF",
                    "projection": 6,
                    "ceiling": 10,
                    "floor": 3,
                    "projected_ownership": 0.08,
                    "salary": 2500,
                }
            )
            lineups.append(
                {
                    "lineup_id": f"L{index}",
                    "portfolio_index": index + 1,
                    "players": players,
                    "player_ids": [
                        player["player_id"]
                        for player in players
                    ],
                    "projected_points": 100,
                    "projected_ceiling": 140,
                    "projected_floor": 70,
                    "projected_ownership": 90,
                    "salary_used": 45000,
                }
            )
        analysis = analyze_portfolio(lineups)
        self.assertGreater(
            analysis["summary"]["average_lineup_similarity"],
            0.7,
        )
        types = {item["type"] for item in analysis["signals"]}
        self.assertTrue(
            "HIGH_PLAYER_CONCENTRATION" in types
            or "STRONG_CORE" in types
            or "HIGH_LINEUP_SIMILARITY" in types
        )

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_min_exposure_force_includes_player(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=10,
            strategy="balanced",
            default_max_exposure=0.8,
            max_lineup_similarity=0.9,
            player_exposure={"min": {"wr5": 0.4}},
            seed=11,
        )
        exposure = {
            row["player_id"]: row
            for row in result["exposure"]["players"]
        }
        self.assertIn("wr5", exposure)
        self.assertGreaterEqual(exposure["wr5"]["exposure"], 0.4 - 1e-9)
        for lineup in result["lineups"]:
            # At least some lineups include wr5; rate checked above.
            pass
        appearances = sum(
            1
            for lineup in result["lineups"]
            if "wr5"
            in {
                player["player_id"]
                for player in lineup["players"]
            }
        )
        self.assertGreaterEqual(appearances, 4)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_excluded_players_remain_in_exposure(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=4,
            strategy="gpp",
            excluded_players=["qb1"],
            seed=3,
        )
        exposure = {
            row["player_id"]: row
            for row in result["exposure"]["players"]
        }
        self.assertIn("qb1", exposure)
        self.assertTrue(exposure["qb1"]["excluded"])
        self.assertEqual(exposure["qb1"]["lineups"], 0)


class PortfolioConstructionValidationTests(unittest.TestCase):
    """Catch soft-penalty / elite under-exposure regressions."""

    def test_select_score_does_not_penalize_existing_exposure(self):
        from app.analysis.insights.dfs.portfolio import (
            _candidate_select_score,
            _normalize_exposure_config,
        )

        cfg = _normalize_exposure_config(None)
        candidate = {
            "projected_points": 140.0,
            "projected_ceiling": 180.0,
            "projected_ownership": 40.0,
            "player_ids": ["elite"],
        }
        low = _candidate_select_score(
            candidate,
            counts=Counter(),
            selected_count=0,
            lineup_count=20,
            exposure_cfg=cfg,
            default_max_exposure=0.7,
        )
        high = _candidate_select_score(
            candidate,
            counts=Counter({"elite": 10}),
            selected_count=10,
            lineup_count=20,
            exposure_cfg=cfg,
            default_max_exposure=0.7,
        )
        # Soft exposure penalties used to subtract rate*8 (~4 pts).
        self.assertAlmostEqual(low, high, places=5)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_high_projection_player_not_systematically_excluded(
        self, _mock_slate
    ):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=20,
            strategy="balanced",
            default_max_exposure=0.7,
            min_unique_players=2,
            seed=11,
        )
        exposure = {
            row["player_id"]: row
            for row in result["exposure"]["players"]
        }
        # rb1 is the top classic skill projection in the fake slate.
        self.assertIn("rb1", exposure)
        self.assertGreaterEqual(exposure["rb1"]["exposure"], 0.35)
        self.assertGreater(
            exposure["rb1"]["remaining_capacity"], -1
        )

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_exposure_cap_hard_limit(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=20,
            strategy="balanced",
            default_max_exposure=0.5,
            player_exposure={"max": {"rb1": 0.5}},
            seed=12,
        )
        for row in result["exposure"]["players"]:
            if row["player_id"] == "rb1":
                self.assertLessEqual(row["lineups"], 10)
                self.assertLessEqual(row["exposure"], 0.5 + 1e-9)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_exposure_below_cap_remains_competitive(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=10,
            strategy="max_projection",
            default_max_exposure=0.9,
            min_unique_players=1,
            seed=13,
        )
        exposure = {
            row["player_id"]: row["exposure"]
            for row in result["exposure"]["players"]
        }
        self.assertGreaterEqual(exposure.get("rb1", 0.0), 0.5)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_uniqueness_allows_shared_elites(self, _mock_slate):
        from app.analysis.insights.dfs.portfolio import (
            _passes_uniqueness,
        )

        selected = [
            {"player_ids": ["A", "B", "C", "D", "E", "F"]},
        ]
        # Shares elite core A-D, swaps two players — allowed.
        candidate = {"player_ids": ["A", "B", "C", "D", "G", "H"]}
        self.assertTrue(
            _passes_uniqueness(
                candidate,
                selected=selected,
                min_unique_players=2,
                max_similarity=0.8,
            )
        )
        # Only one player different — blocked by uniqueness.
        near_dup = {"player_ids": ["A", "B", "C", "D", "E", "X"]}
        self.assertFalse(
            _passes_uniqueness(
                near_dup,
                selected=selected,
                min_unique_players=2,
                max_similarity=0.8,
            )
        )

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_projection_quality_vs_max_projection_baseline(
        self, _mock_slate
    ):
        diversified = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=10,
            strategy="balanced",
            default_max_exposure=0.7,
            min_unique_players=2,
            seed=21,
        )
        max_proj = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=10,
            strategy="max_projection",
            default_max_exposure=0.9,
            min_unique_players=1,
            seed=21,
        )
        div_avg = float(
            diversified["portfolio"]["average_projection"]
        )
        max_avg = float(max_proj["portfolio"]["average_projection"])
        # Diversified should not crater vs max-projection baseline.
        self.assertGreaterEqual(div_avg, max_avg * 0.92)

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_max_projection_mode_prioritizes_points(self, _mock_slate):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=8,
            strategy="max_projection",
            default_max_exposure=0.9,
            min_unique_players=1,
            seed=22,
        )
        self.assertEqual(
            result["optimization_metadata"]["portfolio_strategy"],
            "max_projection",
        )
        self.assertGreaterEqual(
            result["portfolio"]["average_projection"], 100.0
        )
        self.assertIn("player_diagnostics", result)
        self.assertIn("rejected", result["optimization_metadata"])

    @patch(
        "app.analysis.insights.dfs.portfolio.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_brute_force_top_candidates_are_high_projection(
        self, _mock_slate
    ):
        result = generate_portfolio(
            slate_id="nfl-test-main",
            lineup_count=5,
            strategy="max_projection",
            default_max_exposure=1.0,
            min_unique_players=0,
            seed=23,
        )
        projections = [
            float(item["projected_points"])
            for item in result["lineups"]
        ]
        self.assertEqual(projections, sorted(projections, reverse=True))
        meta = result["optimization_metadata"]
        self.assertGreaterEqual(
            int(meta["candidate_lineups_generated"]), 5
        )


if __name__ == "__main__":
    unittest.main()
