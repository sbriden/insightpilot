"""Tests for historical / incremental / reprocess ingestion."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.sources import data_lifecycle
from app.sources import nflverse as nflverse_source


def _passed_report() -> MagicMock:
    report = MagicMock()
    report.passed = True
    report.to_dict.return_value = {
        "passed": True,
        "status": "passed",
        "message": (
            "The data loaded successfully "
            "and passed validation."
        ),
    }
    return report


def _failed_report() -> MagicMock:
    report = MagicMock()
    report.passed = False
    report.to_dict.return_value = {
        "passed": False,
        "status": "failed",
        "message": (
            "The data loaded but failed validation "
            "(1 error, 0 warnings)."
        ),
    }
    return report


class DataLifecycleTests(unittest.TestCase):

    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_historical_seasons_span_several_years(
        self,
        _mock_season,
    ):
        seasons = data_lifecycle.historical_seasons(
            current_season=2024,
        )
        self.assertEqual(
            seasons,
            [2021, 2022, 2023, 2024],
        )
        self.assertEqual(
            data_lifecycle.current_seasons(
                current_season=2024,
            ),
            [2024],
        )

    def test_resolve_scope_seasons(self):
        self.assertEqual(
            data_lifecycle.resolve_scope_seasons(
                "historical",
                current_season=2024,
            ),
            [2021, 2022, 2023, 2024],
        )
        self.assertEqual(
            data_lifecycle.resolve_scope_seasons(
                "incremental",
                current_season=2024,
            ),
            [2024],
        )
        self.assertEqual(
            data_lifecycle.resolve_scope_seasons(
                "seasons",
                seasons=[2022, 2023],
                current_season=2024,
            ),
            [2022, 2023],
        )

    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_season_aware_defaults_are_historical(
        self,
        _mock_season,
    ):
        dataset = nflverse_source.get_dataset_definition(
            "fact_player_game"
        )
        seasons = nflverse_source.normalize_seasons(
            None,
            dataset=dataset,
        )
        self.assertEqual(
            seasons,
            [2021, 2022, 2023, 2024],
        )
        analytics = nflverse_source.get_dataset_definition(
            "player_usage_trend"
        )
        self.assertGreaterEqual(
            analytics.history_lookback_seasons,
            1,
        )

    def test_ingest_modes_are_documented(self):
        modes = {
            item["id"]: item
            for item in data_lifecycle.list_ingest_modes()
        }
        self.assertIn("historical", modes)
        self.assertIn("incremental", modes)
        self.assertIn("reprocess", modes)
        self.assertEqual(
            modes["reprocess"]["layers"],
            ["analytics", "intelligence"],
        )
        self.assertNotIn(
            "facts",
            modes["reprocess"]["layers"],
        )

    def test_reprocess_rejects_fact_layers(self):
        with self.assertRaises(ValueError):
            data_lifecycle.layers_for_mode(
                "reprocess",
                layers=["facts", "analytics"],
            )

    @patch(
        "app.sources.data_lifecycle._record_ingestion_state",
    )
    @patch(
        "app.canonical.data_quality.validate_ingested_seasons",
    )
    @patch(
        "app.sources.data_lifecycle.refresh_dataset",
    )
    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_incremental_targets_live_season(
        self,
        _mock_season,
        mock_refresh,
        mock_validate,
        _mock_state,
    ):
        mock_validate.return_value = _passed_report()
        mock_refresh.side_effect = (
            lambda dataset_id, seasons, **kwargs: {
                "dataset_id": dataset_id,
                "seasons": list(seasons),
                "row_count": 1,
                "persisted": True,
                "force_refresh": True,
            }
        )
        result = data_lifecycle.run_ingest(
            mode="incremental",
            dataset_ids=[
                "fact_player_game",
                "player_fantasy_profile",
            ],
            persist=True,
        )
        self.assertEqual(result["mode"], "incremental")
        self.assertEqual(result["seasons"], [2024])
        self.assertEqual(result["status"], "succeeded")
        self.assertIn("passed validation", result["message"])
        self.assertEqual(result["datasets_refreshed"], 2)
        called_seasons = [
            call.args[1] for call in mock_refresh.call_args_list
        ]
        self.assertTrue(
            all(seasons == [2024] for seasons in called_seasons)
        )

    @patch(
        "app.sources.data_lifecycle._record_ingestion_state",
    )
    @patch(
        "app.canonical.data_quality.validate_ingested_seasons",
    )
    @patch(
        "app.sources.data_lifecycle.refresh_dataset",
    )
    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_reprocess_skips_facts(
        self,
        _mock_season,
        mock_refresh,
        mock_validate,
        _mock_state,
    ):
        mock_validate.return_value = _passed_report()
        mock_refresh.side_effect = (
            lambda dataset_id, seasons, **kwargs: {
                "dataset_id": dataset_id,
                "seasons": list(seasons),
                "row_count": 3,
                "persisted": True,
                "force_refresh": True,
            }
        )
        result = data_lifecycle.run_ingest(
            mode="reprocess",
            persist=True,
        )
        self.assertEqual(result["mode"], "reprocess")
        self.assertEqual(
            result["layers"],
            ["analytics", "intelligence"],
        )
        called_ids = [
            call.args[0] for call in mock_refresh.call_args_list
        ]
        self.assertTrue(
            all(
                dataset_id.startswith("player_")
                or dataset_id == "fantasy_signal"
                for dataset_id in called_ids
            )
        )
        self.assertFalse(
            any(
                dataset_id.startswith("fact_")
                for dataset_id in called_ids
            )
        )

    @patch(
        "app.sources.data_lifecycle._record_ingestion_state",
    )
    @patch(
        "app.canonical.data_quality.validate_ingested_seasons",
    )
    @patch(
        "app.sources.data_lifecycle.refresh_dataset",
    )
    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_failed_validation_blocks_derived(
        self,
        _mock_season,
        mock_refresh,
        mock_validate,
        _mock_state,
    ):
        mock_validate.return_value = _failed_report()
        mock_refresh.side_effect = (
            lambda dataset_id, seasons, **kwargs: {
                "dataset_id": dataset_id,
                "seasons": list(seasons),
                "row_count": 1,
                "persisted": True,
                "force_refresh": True,
            }
        )
        result = data_lifecycle.run_ingest(
            mode="incremental",
            persist=True,
        )
        self.assertEqual(result["status"], "failed_validation")
        self.assertTrue(result["validation_blocked_derived"])
        called_ids = [
            call.args[0] for call in mock_refresh.call_args_list
        ]
        self.assertFalse(
            any(
                dataset_id.startswith("player_")
                or dataset_id == "fantasy_signal"
                for dataset_id in called_ids
            )
        )

    @patch(
        "app.sources.data_lifecycle.run_ingest",
    )
    def test_refresh_pipeline_maps_current_to_incremental(
        self,
        mock_run,
    ):
        mock_run.return_value = {"mode": "incremental"}
        data_lifecycle.refresh_pipeline(scope="current")
        self.assertEqual(
            mock_run.call_args.kwargs["mode"],
            "incremental",
        )

    @patch(
        "app.canonical.data_quality.validate_ingested_seasons",
    )
    @patch(
        "app.sources.data_lifecycle.get_latest_ingestion_state",
        return_value=None,
    )
    @patch(
        "app.sources.nflverse.get_current_season",
        return_value=2024,
    )
    def test_fantasy_data_quality_live_report(
        self,
        _mock_season,
        _mock_latest,
        mock_validate,
    ):
        mock_validate.return_value = _passed_report()
        result = data_lifecycle.get_fantasy_data_quality(
            live=True,
        )
        self.assertEqual(
            result["product"],
            "fantasy_football",
        )
        self.assertEqual(
            result["report_source"],
            "live",
        )
        self.assertTrue(result["passed"])
        self.assertIn(
            "passed validation",
            result["message"],
        )


if __name__ == "__main__":
    unittest.main()
