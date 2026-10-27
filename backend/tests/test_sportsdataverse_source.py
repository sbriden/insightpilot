"""Unit tests for sportsdataverse CFB source helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app.sources import sportsdataverse as sdv_source


class SportsdataverseSourceTests(unittest.TestCase):

    def test_catalog_includes_cfb_canonical_datasets(self):
        datasets = sdv_source.list_datasets()
        ids = {item["id"] for item in datasets}
        self.assertEqual(
            ids,
            {
                "dim_team",
                "dim_player",
                "dim_game",
                "fact_player_game",
                "fact_team_game",
                "fact_defensive_game",
                "fact_game_market",
            },
        )
        for item in datasets:
            self.assertEqual(item["domain"], "canonical")

    def test_get_dataset_definition_unknown(self):
        with self.assertRaises(ValueError):
            sdv_source.get_dataset_definition("pbp")

    @patch(
        "app.sources.sportsdataverse.get_current_season",
        return_value=2024,
    )
    def test_normalize_seasons_default(
        self,
        _mock_season,
    ):
        dataset = sdv_source.get_dataset_definition(
            "dim_game"
        )
        seasons = sdv_source.normalize_seasons(
            None,
            dataset=dataset,
        )
        self.assertEqual(
            seasons,
            [2021, 2022, 2023, 2024],
        )

    @patch(
        "app.sources.sportsdataverse.get_current_season",
        return_value=2024,
    )
    def test_normalize_seasons_rejects_pre_2003(
        self,
        _mock_season,
    ):
        dataset = sdv_source.get_dataset_definition(
            "dim_game"
        )
        with self.assertRaises(ValueError):
            sdv_source.normalize_seasons(
                [2000],
                dataset=dataset,
            )

    def test_dataframe_fields(self):
        df = pd.DataFrame(
            {
                "team_id": ["ip_team_000001"],
                "team_name": ["Alabama"],
            }
        )
        fields = sdv_source.dataframe_fields(df)
        self.assertEqual(
            [field["name"] for field in fields],
            ["team_id", "team_name"],
        )

    def test_source_label(self):
        dataset = sdv_source.get_dataset_definition(
            "dim_team"
        )
        label = sdv_source.source_label(
            dataset,
            [2024],
        )
        self.assertEqual(
            label,
            "sportsdataverse - dim_team (2024)",
        )


if __name__ == "__main__":
    unittest.main()
