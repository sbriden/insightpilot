"""Tests for DFS site config and optimizer legality."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.dfs.optimize import (
    _fits_slot,
    optimize_lineup,
)
from app.analysis.insights.dfs.sites import (
    get_site_config,
    list_sites,
)
from app.analysis.insights.dfs.slate import _eligible_slots


def _fake_player(
    *,
    player_id: str,
    name: str,
    position: str,
    salary: int,
    projection: float,
    ownership: float = 0.1,
    team: str = "KC",
) -> dict:
    return {
        "dfs_player_id": f"draftkings:{player_id}",
        "player_id": player_id,
        "name": name,
        "position": position,
        "eligible_positions": (
            [position, "FLEX"]
            if position in {"RB", "WR", "TE"}
            else [position if position != "DEF" else "DST"]
        ),
        "team": team,
        "opponent": None,
        "salary": salary,
        "projection": projection,
        "floor": round(projection * 0.7, 1),
        "ceiling": round(projection * 1.4, 1),
        "projected_ownership": ownership,
        "value": round(projection / (salary / 1000.0), 2),
        "matchup_label": "Favorable",
        "primary_signal": {
            "id": "stable",
            "label": "→ Stable Role",
        },
        "signals": [],
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
            salary=6200,
            projection=15.0,
            team="SF",
        ),
        _fake_player(
            player_id="rb3",
            name="RB Three",
            position="RB",
            salary=5000,
            projection=12.0,
            team="CHI",
        ),
        _fake_player(
            player_id="wr1",
            name="WR One",
            position="WR",
            salary=7800,
            projection=19.0,
            team="BUF",
            ownership=0.22,
        ),
        _fake_player(
            player_id="wr2",
            name="WR Two",
            position="WR",
            salary=7000,
            projection=16.5,
            team="DAL",
        ),
        _fake_player(
            player_id="wr3",
            name="WR Three",
            position="WR",
            salary=5600,
            projection=13.5,
            team="MIN",
            ownership=0.05,
        ),
        _fake_player(
            player_id="wr4",
            name="WR Four",
            position="WR",
            salary=4800,
            projection=11.0,
            team="TB",
        ),
        _fake_player(
            player_id="te1",
            name="TE One",
            position="TE",
            salary=5400,
            projection=12.0,
            team="KC",
        ),
        _fake_player(
            player_id="te2",
            name="TE Two",
            position="TE",
            salary=4200,
            projection=9.0,
            team="BAL",
        ),
        _fake_player(
            player_id="dst1",
            name="DST One",
            position="DEF",
            salary=3000,
            projection=8.0,
            team="PIT",
        ),
        _fake_player(
            player_id="dst2",
            name="DST Two",
            position="DEF",
            salary=2600,
            projection=6.5,
            team="CLE",
        ),
    ]
    site = get_site_config("draftkings")
    return {
        "slate_id": "nfl-2026-main",
        "label": "Main Slate — 2026",
        "site": "draftkings",
        "site_name": "DraftKings",
        "salary_cap": site["salary_cap"],
        "roster": site["roster"],
        "players": players,
        "freshness": {},
    }


class DfsSiteTests(unittest.TestCase):
    def test_list_sites(self):
        sites = list_sites()
        ids = {site["id"] for site in sites}
        self.assertIn("draftkings", ids)
        self.assertIn("fanduel", ids)

    def test_draftkings_roster(self):
        site = get_site_config("draftkings")
        self.assertEqual(site["salary_cap"], 50000)
        self.assertEqual(len(site["roster"]), 9)
        slots = [item["slot"] for item in site["roster"]]
        self.assertEqual(
            slots,
            ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"],
        )

    def test_showdown_roster(self):
        site = get_site_config(
            "draftkings",
            contest_type="showdown",
        )
        self.assertEqual(site["contest_type"], "showdown")
        self.assertEqual(site["captain_multiplier"], 1.5)
        slots = [item["slot"] for item in site["roster"]]
        self.assertEqual(slots[0], "CPT")
        self.assertEqual(len(slots), 6)
        self.assertEqual(slots.count("FLEX"), 5)


class DfsOptimizeTests(unittest.TestCase):
    @patch(
        "app.analysis.insights.dfs.optimize.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_fills_legal_lineup(self, _mock_slate):
        result = optimize_lineup(
            slate_id="nfl-2026-main",
            site="draftkings",
            contest_type="gpp",
            risk="balanced",
        )
        lineup = result["lineup"]
        self.assertTrue(lineup["valid"])
        self.assertEqual(lineup["roster_filled"], 9)
        self.assertLessEqual(
            lineup["salary_used"],
            lineup["salary_cap"],
        )
        slots = [player["slot"] for player in lineup["players"]]
        self.assertEqual(len(slots), 9)
        self.assertEqual(slots.count("RB"), 2)
        self.assertEqual(slots.count("WR"), 3)

    @patch(
        "app.analysis.insights.dfs.optimize.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_locked_player_included(self, _mock_slate):
        result = optimize_lineup(
            slate_id="nfl-2026-main",
            site="draftkings",
            contest_type="cash",
            locked_players=["te2"],
        )
        ids = {
            player["player_id"]
            for player in result["lineup"]["players"]
        }
        self.assertIn("te2", ids)

    @patch(
        "app.analysis.insights.dfs.optimize.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_excluded_player_absent(self, _mock_slate):
        result = optimize_lineup(
            slate_id="nfl-2026-main",
            site="draftkings",
            contest_type="gpp",
            excluded_players=["wr1", "rb1"],
        )
        ids = {
            player["player_id"]
            for player in result["lineup"]["players"]
        }
        self.assertNotIn("wr1", ids)
        self.assertNotIn("rb1", ids)

    @patch(
        "app.analysis.insights.dfs.optimize.build_dfs_slate",
        return_value=_fake_slate(),
    )
    def test_contest_weights_differ(self, _mock_slate):
        cash = optimize_lineup(
            slate_id="nfl-2026-main",
            site="draftkings",
            contest_type="cash",
            risk="conservative",
        )
        gpp = optimize_lineup(
            slate_id="nfl-2026-main",
            site="draftkings",
            contest_type="gpp",
            risk="aggressive",
        )
        # Legacy cash/gpp contest labels map to classic format
        # and become the strategy key.
        self.assertEqual(
            cash["optimization_metadata"]["contest_type"],
            "classic",
        )
        self.assertEqual(
            cash["optimization_metadata"]["strategy"],
            "cash",
        )
        self.assertEqual(
            gpp["optimization_metadata"]["strategy"],
            "gpp",
        )
        self.assertGreater(
            cash["optimization_metadata"]["weights"]["floor"],
            gpp["optimization_metadata"]["weights"]["floor"],
        )

    @patch("app.analysis.insights.dfs.optimize.build_dfs_slate")
    def test_showdown_captain_is_double(self, mock_slate):
        mock_slate.return_value = _fake_showdown_slate()
        result = optimize_lineup(
            slate_id="nfl-2026-2-sd-BUF-DET",
            site="draftkings",
            contest_type="showdown",
            risk="balanced",
        )
        lineup = result["lineup"]
        self.assertTrue(lineup["valid"])
        self.assertEqual(lineup["roster_filled"], 6)
        self.assertEqual(lineup["contest_type"], "showdown")
        slots = [player["slot"] for player in lineup["players"]]
        self.assertEqual(slots.count("CPT"), 1)
        self.assertEqual(slots.count("FLEX"), 5)
        captain = next(
            player
            for player in lineup["players"]
            if player["slot"] == "CPT"
        )
        self.assertTrue(captain.get("is_captain"))
        self.assertEqual(captain.get("captain_multiplier"), 1.5)
        self.assertEqual(
            captain["salary"],
            int(round(int(captain["base_salary"]) * 1.5)),
        )
        self.assertAlmostEqual(
            float(captain["projection"]),
            float(captain["base_projection"]) * 1.5,
            places=1,
        )
        ids = [player["player_id"] for player in lineup["players"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertLessEqual(
            lineup["salary_used"],
            lineup["salary_cap"],
        )

    def test_defense_flex_rules(self):
        classic_flex = {
            "slot": "FLEX",
            "positions": ["RB", "WR", "TE"],
        }
        showdown_flex = {
            "slot": "FLEX",
            "positions": [
                "QB",
                "RB",
                "WR",
                "TE",
                "DEF",
                "DST",
                "K",
                "FLEX",
                "CPT",
            ],
        }
        showdown_cpt = {
            "slot": "CPT",
            "positions": [
                "QB",
                "RB",
                "WR",
                "TE",
                "DEF",
                "DST",
                "K",
                "FLEX",
                "CPT",
            ],
        }
        defense = {
            "position": "DEF",
            "is_team_defense": True,
        }
        skill = {"position": "RB"}
        self.assertFalse(
            _fits_slot(
                defense,
                classic_flex,
                contest_type="classic",
            )
        )
        self.assertTrue(
            _fits_slot(
                defense,
                showdown_flex,
                contest_type="showdown",
            )
        )
        self.assertTrue(
            _fits_slot(
                defense,
                showdown_cpt,
                contest_type="showdown",
            )
        )
        self.assertTrue(_fits_slot(skill, classic_flex))
        self.assertEqual(
            _eligible_slots("DEF", contest_type="classic"),
            ["DST", "DEF"],
        )
        self.assertEqual(
            _eligible_slots("DEF", contest_type="showdown"),
            ["CPT", "FLEX"],
        )

    @patch("app.analysis.insights.dfs.optimize.build_dfs_slate")
    def test_showdown_can_place_defense_in_flex(
        self, mock_slate
    ):
        slate = _fake_showdown_slate()
        # Make DST the highest-scoring non-captain so it lands
        # in FLEX when not chosen as CPT.
        for player in slate["players"]:
            if player["position"] == "DEF":
                player["projection"] = 40.0
                player["salary"] = 2500
            if player["player_id"] == "qb1":
                player["projection"] = 50.0
        mock_slate.return_value = slate
        result = optimize_lineup(
            slate_id="nfl-2026-2-sd-BUF-DET",
            site="draftkings",
            contest_type="showdown",
            risk="balanced",
        )
        lineup = result["lineup"]
        self.assertTrue(lineup["valid"])
        defense_slots = [
            player["slot"]
            for player in lineup["players"]
            if player["position"] in {"DEF", "DST"}
        ]
        self.assertTrue(defense_slots)
        self.assertTrue(
            all(slot in {"CPT", "FLEX"} for slot in defense_slots)
        )


def _fake_showdown_slate() -> dict:
    """Single-game pool with enough players for CPT + 5 FLEX."""

    players = [
        _fake_player(
            player_id="qb1",
            name="Josh Allen",
            position="QB",
            salary=7500,
            projection=24.0,
            team="BUF",
        ),
        _fake_player(
            player_id="rb1",
            name="James Cook",
            position="RB",
            salary=6800,
            projection=16.0,
            team="BUF",
        ),
        _fake_player(
            player_id="wr1",
            name="Khalil Shakir",
            position="WR",
            salary=5500,
            projection=13.0,
            team="BUF",
        ),
        _fake_player(
            player_id="te1",
            name="Dalton Kincaid",
            position="TE",
            salary=4200,
            projection=9.5,
            team="BUF",
        ),
        _fake_player(
            player_id="dst1",
            name="BUF DST",
            position="DEF",
            salary=3000,
            projection=7.0,
            team="BUF",
        ),
        _fake_player(
            player_id="rb2",
            name="Jahmyr Gibbs",
            position="RB",
            salary=8000,
            projection=21.0,
            team="DET",
        ),
        _fake_player(
            player_id="wr2",
            name="Amon-Ra St. Brown",
            position="WR",
            salary=7800,
            projection=19.5,
            team="DET",
        ),
        _fake_player(
            player_id="wr3",
            name="Jameson Williams",
            position="WR",
            salary=5200,
            projection=12.0,
            team="DET",
        ),
        _fake_player(
            player_id="qb2",
            name="Jared Goff",
            position="QB",
            salary=6400,
            projection=18.0,
            team="DET",
        ),
        _fake_player(
            player_id="te2",
            name="Sam LaPorta",
            position="TE",
            salary=5000,
            projection=11.0,
            team="DET",
        ),
    ]
    for player in players:
        player["eligible_positions"] = ["CPT", "FLEX"]
        if player["position"] == "DEF":
            player["is_team_defense"] = True
        player["opponent"] = (
            "DET" if player["team"] == "BUF" else "BUF"
        )
    site = get_site_config("draftkings", contest_type="showdown")
    return {
        "slate_id": "nfl-2026-2-sd-BUF-DET",
        "label": "Showdown — BUF @ DET",
        "site": "draftkings",
        "site_name": "DraftKings",
        "contest_type": "showdown",
        "salary_cap": site["salary_cap"],
        "roster": site["roster"],
        "captain_multiplier": 1.5,
        "players": players,
        "freshness": {},
    }