"""Tests for DFS salary CSV parse + fuzzy matching."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app.analysis.insights.dfs.salary_csv import (
    ingest_dfs_salary_csv,
    match_salary_row,
    parse_salary_csv,
)
from app.canonical.ids import make_player_id


class ParseSalaryCsvTests(unittest.TestCase):
    def test_parses_draftkings_style(self):
        csv_text = (
            "Name,TeamAbbrev,Roster Position,Salary\n"
            "Josh Allen,BUF,QB,7800\n"
            "James Cook,BUF,RB/FLEX,6200\n"
            "Buffalo Bills,BUF,DST,2900\n"
        )
        rows = parse_salary_csv(csv_text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["name"], "Josh Allen")
        self.assertEqual(rows[0]["team"], "BUF")
        self.assertEqual(rows[0]["position"], "QB")
        self.assertEqual(rows[0]["salary"], 7800)
        self.assertEqual(rows[1]["position"], "RB")
        self.assertEqual(rows[2]["position"], "DEF")

    def test_parses_fanduel_style(self):
        csv_text = (
            "Id,Position,First Name,Last Name,Salary,Team\n"
            "1,QB,Josh,Allen,8200,BUF\n"
            "2,D,Buffalo,Bills,3000,BUF\n"
        )
        rows = parse_salary_csv(csv_text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "Josh Allen")
        self.assertEqual(rows[0]["salary"], 8200)


class MatchSalaryRowTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {
                "player_id": "p-allen",
                "name": "Josh Allen",
                "name_key": "josh allen",
                "team": "BUF",
                "position": "QB",
            },
            {
                "player_id": "p-cook",
                "name": "James Cook",
                "name_key": "james cook",
                "team": "BUF",
                "position": "RB",
            },
            {
                "player_id": make_player_id("fantasy_dst:BUF"),
                "name": "Buffalo Bills D/ST",
                "name_key": "buffalo bills dst",
                "team": "BUF",
                "position": "DEF",
            },
        ]

    def test_exact_team_pos_name(self):
        result = match_salary_row(
            {
                "name": "Josh Allen",
                "team": "BUF",
                "position": "QB",
                "salary": 7800,
            },
            self.candidates,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["player_id"], "p-allen")
        self.assertGreaterEqual(result["score"], 0.99)

    def test_fuzzy_name_same_team_pos(self):
        result = match_salary_row(
            {
                "name": "J. Allen",
                "team": "BUF",
                "position": "QB",
                "salary": 7800,
            },
            self.candidates,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["player_id"], "p-allen")

    def test_defense_alias(self):
        result = match_salary_row(
            {
                "name": "Buffalo Bills",
                "team": "BUF",
                "position": "DST",
                "salary": 2900,
            },
            self.candidates,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(
            result["player_id"],
            make_player_id("fantasy_dst:BUF"),
        )

    def test_rejects_wrong_team(self):
        result = match_salary_row(
            {
                "name": "Josh Allen",
                "team": "MIA",
                "position": "QB",
                "salary": 7800,
            },
            self.candidates,
        )
        self.assertIsNone(result)


class IngestSalaryCsvTests(unittest.TestCase):
    @patch(
        "app.analysis.insights.dfs.salary_csv.upsert_fact_dfs_salary",
        return_value=2,
    )
    @patch("app.analysis.insights.dfs.salary_csv._load_match_candidates")
    def test_ingest_persists_matches(
        self,
        mock_candidates,
        mock_upsert,
    ):
        mock_candidates.return_value = [
            {
                "player_id": "p-allen",
                "name": "Josh Allen",
                "name_key": "josh allen",
                "team": "BUF",
                "position": "QB",
            },
            {
                "player_id": "p-cook",
                "name": "James Cook",
                "name_key": "james cook",
                "team": "BUF",
                "position": "RB",
            },
        ]
        csv_text = (
            "Name,TeamAbbrev,Position,Salary\n"
            "Josh Allen,BUF,QB,7800\n"
            "James Cook,BUF,RB,6200\n"
            "Unknown Guy,BUF,WR,4000\n"
        )
        result = ingest_dfs_salary_csv(
            csv_text,
            site="draftkings",
            contest_type="classic",
            season=2026,
            week=2,
            filename="dk.csv",
            persist=True,
        )
        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["unmatched"], 1)
        self.assertEqual(result["persisted"], 2)
        mock_upsert.assert_called_once()
        frame = mock_upsert.call_args.args[0]
        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(len(frame), 2)
        self.assertEqual(
            set(frame["player_id"]),
            {"p-allen", "p-cook"},
        )


if __name__ == "__main__":
    unittest.main()
