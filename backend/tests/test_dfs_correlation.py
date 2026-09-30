"""Tests for the DFS Player Correlation Engine."""

from __future__ import annotations

import unittest

from app.analysis.insights.dfs.correlation import (
    CorrelationConfig,
    build_correlation_context,
    score_lineup_correlation,
    summarize_portfolio_correlations,
)


def _player(
    *,
    player_id: str,
    name: str,
    position: str,
    team: str,
    opponent: str,
    depth_order: int | None = None,
) -> dict:
    row = {
        "player_id": player_id,
        "name": name,
        "position": position,
        "team": team,
        "opponent": opponent,
        "projection": 15.0,
        "salary": 5000,
    }
    if depth_order is not None:
        row["depth_order"] = depth_order
    return row


def _showdown_pool() -> list[dict]:
    """BUF @ MIA style single-game pool."""

    return [
        _player(
            player_id="qb_buf",
            name="Josh Allen",
            position="QB",
            team="BUF",
            opponent="MIA",
            depth_order=1,
        ),
        _player(
            player_id="wr1_buf",
            name="Stefon Diggs",
            position="WR",
            team="BUF",
            opponent="MIA",
            depth_order=1,
        ),
        _player(
            player_id="wr2_buf",
            name="Gabe Davis",
            position="WR",
            team="BUF",
            opponent="MIA",
            depth_order=2,
        ),
        _player(
            player_id="te_buf",
            name="Dawson Knox",
            position="TE",
            team="BUF",
            opponent="MIA",
            depth_order=1,
        ),
        _player(
            player_id="rb1_buf",
            name="James Cook",
            position="RB",
            team="BUF",
            opponent="MIA",
            depth_order=1,
        ),
        _player(
            player_id="rb2_buf",
            name="Latavius Murray",
            position="RB",
            team="BUF",
            opponent="MIA",
            depth_order=2,
        ),
        _player(
            player_id="dst_buf",
            name="Bills DST",
            position="DST",
            team="BUF",
            opponent="MIA",
        ),
        _player(
            player_id="k_buf",
            name="Tyler Bass",
            position="K",
            team="BUF",
            opponent="MIA",
        ),
        _player(
            player_id="qb_mia",
            name="Tua Tagovailoa",
            position="QB",
            team="MIA",
            opponent="BUF",
            depth_order=1,
        ),
        _player(
            player_id="wr1_mia",
            name="Tyreek Hill",
            position="WR",
            team="MIA",
            opponent="BUF",
            depth_order=1,
        ),
        _player(
            player_id="wr2_mia",
            name="Jaylen Waddle",
            position="WR",
            team="MIA",
            opponent="BUF",
            depth_order=2,
        ),
        _player(
            player_id="dst_mia",
            name="Dolphins DST",
            position="DST",
            team="MIA",
            opponent="BUF",
        ),
        _player(
            player_id="unrelated",
            name="Other League QB",
            position="QB",
            team="KC",
            opponent="LV",
            depth_order=1,
        ),
        _player(
            player_id="unrelated_wr",
            name="Other League WR",
            position="WR",
            team="LV",
            opponent="KC",
            depth_order=1,
        ),
    ]


class TestDfsCorrelationEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.players = _showdown_pool()
        self.ctx = build_correlation_context(
            self.players,
            sport="nfl",
            season=2024,
            week=1,
            game_id="2024_01_BUF_MIA",
        )

    def _edge(self, a: str, b: str):
        return self.ctx.get_edge(a, b)

    def test_qb_primary_wr_positive(self) -> None:
        edge = self._edge("qb_buf", "wr1_buf")
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertEqual(edge.correlation_type, "positive")
        self.assertGreater(edge.correlation_score, 0.5)
        self.assertEqual(edge.rule_id, "qb_own_wr1")
        self.assertIn("passing", edge.correlation_reason.lower())

    def test_qb_opposing_wr_positive(self) -> None:
        edge = self._edge("qb_buf", "wr1_mia")
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertEqual(edge.correlation_type, "positive")
        self.assertGreater(edge.correlation_score, 0.2)
        self.assertEqual(edge.rule_id, "qb_opp_pass_catcher")

    def test_qb_opposing_dst_negative(self) -> None:
        edge = self._edge("qb_buf", "dst_mia")
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertEqual(edge.correlation_type, "negative")
        self.assertLess(edge.correlation_score, -0.4)
        self.assertEqual(edge.rule_id, "qb_opp_dst")

    def test_rb_committee_negative(self) -> None:
        edge = self._edge("rb1_buf", "rb2_buf")
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertEqual(edge.correlation_type, "negative")
        self.assertLess(edge.correlation_score, -0.3)
        self.assertEqual(edge.rule_id, "rb_committee")
        self.assertIn("compete", edge.correlation_reason.lower())

    def test_qb_own_dst_context_dependent(self) -> None:
        base = self._edge("qb_buf", "dst_buf")
        self.assertIsNotNone(base)
        assert base is not None
        self.assertEqual(base.rule_id, "qb_own_dst")

        control = build_correlation_context(
            self.players,
            sport="nfl",
            game_script_id="favorite_controls",
        )
        shootout = build_correlation_context(
            self.players,
            sport="nfl",
            game_script_id="shootout",
        )
        control_edge = control.get_edge("qb_buf", "dst_buf")
        shoot_edge = shootout.get_edge("qb_buf", "dst_buf")
        self.assertIsNotNone(control_edge)
        self.assertIsNotNone(shoot_edge)
        assert control_edge is not None and shoot_edge is not None
        self.assertGreater(
            control_edge.correlation_score,
            shoot_edge.correlation_score,
        )

    def test_unrelated_players_neutral(self) -> None:
        # Cross-game pairs are not stored as edges (neutral).
        edge = self._edge("qb_buf", "unrelated_wr")
        self.assertIsNone(edge)

        # Explicit structural check for same-context neutrals:
        # players on different games stay out of the matrix.
        other_ctx = build_correlation_context(
            [
                _player(
                    player_id="a",
                    name="A",
                    position="RB",
                    team="BUF",
                    opponent="MIA",
                ),
                _player(
                    player_id="b",
                    name="B",
                    position="K",
                    team="MIA",
                    opponent="BUF",
                ),
            ]
        )
        # RB vs opposing K is not a defined rule → no edge.
        self.assertIsNone(other_ctx.get_edge("a", "b"))

    def test_shootout_multiple_positive(self) -> None:
        ctx = build_correlation_context(
            self.players,
            sport="nfl",
            game_script_id="shootout",
        )
        pairs = [
            ("qb_buf", "wr1_buf"),
            ("qb_buf", "wr1_mia"),
            ("wr1_buf", "wr1_mia"),
            ("qb_mia", "wr1_mia"),
        ]
        positives = 0
        for a, b in pairs:
            edge = ctx.get_edge(a, b)
            self.assertIsNotNone(edge, msg=f"{a}/{b}")
            assert edge is not None
            if edge.correlation_score > 0:
                positives += 1
        self.assertGreaterEqual(positives, 3)

        lineup = [
            p
            for p in self.players
            if p["player_id"]
            in {"qb_buf", "wr1_buf", "qb_mia", "wr1_mia", "wr2_mia"}
        ]
        scored = score_lineup_correlation(lineup, ctx)
        self.assertGreater(scored["positive_correlation"], 0.5)
        self.assertGreater(len(scored["positive_pairs"]), 2)

    def test_low_scoring_defensive_rb_relationships(self) -> None:
        ctx = build_correlation_context(
            self.players,
            sport="nfl",
            game_script_id="low_scoring",
        )
        rb_dst = ctx.get_edge("rb1_buf", "dst_buf")
        self.assertIsNotNone(rb_dst)
        assert rb_dst is not None
        self.assertEqual(rb_dst.correlation_type, "positive")
        self.assertGreater(rb_dst.correlation_score, 0.3)

        base = build_correlation_context(self.players, sport="nfl")
        base_edge = base.get_edge("rb1_buf", "dst_buf")
        assert base_edge is not None
        self.assertGreaterEqual(
            rb_dst.correlation_score,
            base_edge.correlation_score,
        )

    def test_small_historical_sample_reduces_confidence(self) -> None:
        empirics = [
            {
                "player_id": "qb_buf",
                "correlated_player_id": "wr1_buf",
                "correlation_score": 0.95,
                "games_together": 2,
                "correlation_reason": "Tiny sample co-movement.",
            }
        ]
        ctx = build_correlation_context(
            self.players,
            sport="nfl",
            empirical_rows=empirics,
            config=CorrelationConfig(min_empirical_games=6),
        )
        edge = ctx.get_edge("qb_buf", "wr1_buf")
        self.assertIsNotNone(edge)
        assert edge is not None
        # Tiny sample should not dominate structural High confidence.
        self.assertIn(edge.source, {"structural", "blended"})
        if edge.source == "blended":
            self.assertLess(edge.confidence_score, 0.95)

        # Explicit low-n empirical-only pair
        empirics_only = [
            {
                "player_id": "k_buf",
                "correlated_player_id": "wr1_mia",
                "correlation_score": 0.80,
                "games_together": 2,
            }
        ]
        ctx2 = build_correlation_context(
            self.players,
            sport="nfl",
            empirical_rows=empirics_only,
        )
        # games < min → may skip entirely (conf < 0.2 gate) or Low
        edge2 = ctx2.get_edge("k_buf", "wr1_mia")
        if edge2 is not None:
            self.assertIn(edge2.confidence, {"Low", "Very Low"})
            self.assertLess(edge2.confidence_score, 0.45)

    def test_team_change_invalidates_historical(self) -> None:
        empirics = [
            {
                "player_id": "qb_buf",
                "correlated_player_id": "wr1_buf",
                "correlation_score": 0.99,
                "games_together": 40,
                "invalidated": True,
                "correlation_reason": "Player changed teams.",
            }
        ]
        ctx = build_correlation_context(
            self.players,
            sport="nfl",
            empirical_rows=empirics,
        )
        edge = ctx.get_edge("qb_buf", "wr1_buf")
        self.assertIsNotNone(edge)
        assert edge is not None
        # Invalidated empirical must not override structural.
        self.assertEqual(edge.source, "structural")
        self.assertLess(edge.correlation_score, 0.99)

    def test_lineup_and_portfolio_summaries(self) -> None:
        lineup = [
            p
            for p in self.players
            if p["player_id"]
            in {"qb_buf", "wr1_buf", "wr1_mia", "dst_mia", "rb1_buf"}
        ]
        scored = score_lineup_correlation(lineup, self.ctx)
        self.assertIn("lineup_correlation_score", scored)
        self.assertTrue(scored["positive_pairs"])
        self.assertTrue(scored["negative_pairs"])

        summary = summarize_portfolio_correlations(
            [{"players": lineup}, {"players": lineup}],
            self.ctx,
        )
        self.assertTrue(
            summary["positive_correlation_exposure"]
        )
        self.assertIsNotNone(summary["narrative"])


if __name__ == "__main__":
    unittest.main()
