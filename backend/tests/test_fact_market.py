"""Tests for canonical fact_market."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import pandas as pd

from app.canonical.ids import (
    is_player_id,
    make_player_id,
    player_resolution_key,
)
from app.canonical.fact_market import (
    build_fact_market,
)


class FactMarketTests(unittest.TestCase):

    def test_build_fact_market_separates_weekly_and_draft(self):
        gsis_id = "00-0037001"
        fp_id = "19196"
        player_id = make_player_id(
            player_resolution_key(gsis_id=gsis_id)
        )

        weekly = pd.DataFrame(
            [
                {
                    "page": "qb",
                    "fantasypros_id": fp_id,
                    "rank": 1,
                    "ecr": 2.1,
                    "r2p_pts": 21.4,
                    "player_owned_avg": 99.1,
                }
            ]
        )
        draft = pd.DataFrame(
            [
                {
                    "page_type": "redraft-overall",
                    "id": fp_id,
                    "ecr": 12.5,
                    "player_owned_avg": 98.0,
                }
            ]
        )
        ff_ids = pd.DataFrame(
            [
                {
                    "fantasypros_id": fp_id,
                    "gsis_id": gsis_id,
                }
            ]
        )

        with (
            patch(
                "app.canonical.fact_market.upsert_fact_market"
            ),
            patch(
                "nflreadpy.get_current_season",
                return_value=2026,
            ),
            patch(
                "nflreadpy.get_current_week",
                return_value=2,
            ),
        ):
            fact = build_fact_market(
                [2026],
                persist=True,
                source_frames={
                    "weekly_rankings": weekly,
                    "draft_rankings": draft,
                    "ff_playerids": ff_ids,
                },
                player_id_lookup={gsis_id: player_id},
            )

        self.assertEqual(len(fact), 2)

        weekly_row = fact[
            fact["source"] == "fantasypros_weekly"
        ].iloc[0]
        self.assertTrue(is_player_id(weekly_row["player_id"]))
        self.assertEqual(weekly_row["season"], 2026)
        self.assertEqual(weekly_row["week"], 2)
        self.assertEqual(weekly_row["rank"], 1)
        self.assertAlmostEqual(weekly_row["projection"], 21.4)
        self.assertIsNone(weekly_row["adp"])
        self.assertAlmostEqual(weekly_row["ownership"], 99.1)

        draft_row = fact[
            fact["source"] == "fantasypros_draft"
        ].iloc[0]
        self.assertIsNone(draft_row["week"])
        self.assertAlmostEqual(draft_row["adp"], 12.5)
        self.assertAlmostEqual(draft_row["rank"], 12.5)
        self.assertIsNone(draft_row["projection"])

        source_ids = json.loads(weekly_row["source_ids"])
        self.assertEqual(source_ids["fantasypros_id"], fp_id)
        self.assertEqual(source_ids["gsis_id"], gsis_id)

        # No performance columns leaked into market.
        self.assertNotIn("pass_yards", fact.columns)
        self.assertNotIn("targets", fact.columns)


if __name__ == "__main__":
    unittest.main()
