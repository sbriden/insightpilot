"""Tests for Analytical Applications persistence."""

from __future__ import annotations

import unittest
import uuid

from app.applications.repository import (
    create_application,
    delete_application,
    get_application,
    update_application,
)


class AnalyticalApplicationsTests(unittest.TestCase):
    def test_create_update_delete_application(self):
        app_id = f"test-app-{uuid.uuid4()}"
        created = create_application(
            {
                "id": app_id,
                "name": "NFL Player Decision Center",
                "description": "Player research workspace",
                "analyses": [
                    {
                        "analysis_key": "fantasy.player_overview",
                        "display_order": 0,
                    },
                    {
                        "analysis_key": "fantasy.player_usage",
                        "display_order": 1,
                    },
                ],
            }
        )
        self.assertEqual(created["id"], app_id)
        self.assertEqual(len(created["analyses"]), 2)

        loaded = get_application(app_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["name"], "NFL Player Decision Center")

        updated = update_application(
            app_id,
            {
                "name": "Sunday Decision Center",
                "analyses": [
                    {
                        "analysis_key": "betting.games",
                        "display_order": 0,
                    }
                ],
            },
        )
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["name"], "Sunday Decision Center")
        self.assertEqual(len(updated["analyses"]), 1)

        self.assertTrue(delete_application(app_id))
        self.assertIsNone(get_application(app_id))


if __name__ == "__main__":
    unittest.main()
