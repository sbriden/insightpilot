"""Tests for admin password gate helpers."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.auth import (
    admin_auth_enabled,
    is_admin_only_path,
    is_public_path,
    issue_admin_token,
    password_matches,
    verify_admin_token,
)


class AdminAuthTests(unittest.TestCase):
    def test_auth_disabled_without_password(self):
        with patch.dict(os.environ, {"ADMIN_PASSWORD": ""}, clear=False):
            self.assertFalse(admin_auth_enabled())
            self.assertTrue(verify_admin_token(None))

    def test_token_round_trip(self):
        with patch.dict(
            os.environ,
            {
                "ADMIN_PASSWORD": "secret",
                "ADMIN_SESSION_SECRET": "signing",
            },
            clear=False,
        ):
            self.assertTrue(admin_auth_enabled())
            self.assertTrue(password_matches("secret"))
            self.assertFalse(password_matches("nope"))
            token = issue_admin_token()
            self.assertTrue(verify_admin_token(token))
            self.assertFalse(verify_admin_token(token + "x"))

    def test_path_classification(self):
        self.assertTrue(is_public_path("/api/public/applications/by-slug/x", "GET"))
        self.assertTrue(is_public_path("/api/admin/login", "POST"))
        self.assertTrue(is_public_path("/api/admin/status", "GET"))
        self.assertTrue(is_admin_only_path("/api/applications", "GET"))
        self.assertTrue(
            is_admin_only_path("/api/sources/nflverse/refresh", "POST")
        )
        self.assertFalse(
            is_admin_only_path("/api/sources/nflverse/analyze", "POST")
        )


if __name__ == "__main__":
    unittest.main()
