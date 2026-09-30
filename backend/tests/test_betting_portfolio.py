"""Tests for sports betting portfolio analytics."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting.portfolio import (
    analyze_betting_portfolio,
    create_position_from_market,
)


def _market(**overrides):
    base = {
        "market_id": "m1",
        "event_id": "e1",
        "event_label": "BUF @ MIA",
        "home_team": "MIA",
        "away_team": "BUF",
        "market_type": "spread",
        "selection": "BUF -3.5",
        "line": -3.5,
        "price": -110,
        "model_probability": 0.58,
        "market_probability": 0.524,
        "edge_probability": 5.6,
        "expected_value": 4.2,
        "confidence": "High",
        "sport": "NFL",
    }
    base.update(overrides)
    return base


class BettingPortfolioTests(unittest.TestCase):
    def test_create_position_from_market(self):
        position = create_position_from_market(
            _market(),
            exposure=40,
            notes="After injury update",
        )
        self.assertTrue(position["position_id"].startswith("pos-"))
        self.assertEqual(position["exposure"], 40.0)
        self.assertEqual(position["entry_price"], -110)
        self.assertEqual(position["status"], "open")
        self.assertEqual(position["notes"], "After injury update")

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_analyze_detects_game_concentration(self, mock_slate):
        markets = [
            _market(
                market_id="m-spread",
                selection="BUF -3.5",
                market_type="spread",
            ),
            _market(
                market_id="m-total",
                selection="Over 47.5",
                market_type="total",
                line=47.5,
            ),
            _market(
                market_id="m-ml",
                selection="BUF",
                market_type="moneyline",
                line=None,
                price=-150,
            ),
        ]
        mock_slate.return_value = {
            "season": 2026,
            "week": 3,
            "slate_id": "nfl-2026-w3",
            "markets": markets,
            "events": [
                {
                    "event_id": "e1",
                    "label": "BUF @ MIA",
                    "home_team": "MIA",
                    "away_team": "BUF",
                }
            ],
        }
        positions = [
            create_position_from_market(market, exposure=25)
            for market in markets
        ]
        result = analyze_betting_portfolio(
            positions,
            season=2026,
            week=3,
        )
        analytics = result["analytics"]
        self.assertEqual(analytics["summary"]["open_positions"], 3)
        self.assertGreaterEqual(
            analytics["summary"]["total_exposure"], 75
        )
        game = analytics["exposure"]["game"][0]
        self.assertEqual(game["positions"], 3)
        self.assertGreaterEqual(game["exposure_pct"], 99)
        assumptions = {
            row["assumption"] for row in analytics["assumptions"]
        }
        self.assertTrue(
            any("BUF" in name for name in assumptions)
            or any("High-scoring" in name for name in assumptions)
        )
        alert_ids = {
            row["signal_id"] for row in analytics["alerts"]
        }
        self.assertIn("HIGH_GAME_CONCENTRATION", alert_ids)
        self.assertGreaterEqual(len(analytics["correlations"]), 1)

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_generate_respects_total_and_risk_exposure(
        self, mock_slate
    ):
        from app.analysis.insights.betting.portfolio import (
            generate_betting_portfolio,
        )

        markets = []
        teams = [
            ("BUF", "MIA"),
            ("DET", "GB"),
            ("DAL", "PHI"),
            ("KC", "DEN"),
            ("SF", "SEA"),
            ("BAL", "CIN"),
        ]
        for index, (away, home) in enumerate(teams):
            event_id = f"e{index}"
            markets.append(
                _market(
                    market_id=f"m{index}-spread",
                    event_id=event_id,
                    event_label=f"{away} @ {home}",
                    home_team=home,
                    away_team=away,
                    selection=f"{away} -3.5",
                    market_type="spread",
                    edge_probability=7.5 - index * 0.4,
                    confidence="High",
                )
            )
            markets.append(
                _market(
                    market_id=f"m{index}-total",
                    event_id=event_id,
                    event_label=f"{away} @ {home}",
                    home_team=home,
                    away_team=away,
                    selection=f"Over {44 + index}",
                    market_type="total",
                    line=44 + index,
                    edge_probability=6.5 - index * 0.35,
                    confidence="High" if index < 4 else "Moderate",
                )
            )
        mock_slate.return_value = {
            "season": 2026,
            "week": 3,
            "slate_id": "nfl-2026-w3",
            "markets": markets,
            "events": [
                {
                    "event_id": f"e{i}",
                    "label": f"{away} @ {home}",
                    "home_team": home,
                    "away_team": away,
                }
                for i, (away, home) in enumerate(teams)
            ],
        }
        result = generate_betting_portfolio(
            total_exposure=300,
            risk_exposure=80,
            season=2026,
            week=3,
            risk="balanced",
        )
        positions = result["positions"]
        self.assertGreaterEqual(len(positions), 2)
        allocated = sum(float(p["exposure"]) for p in positions)
        self.assertLessEqual(allocated, 300.0 + 0.05)
        self.assertGreaterEqual(allocated, 100.0)
        by_game: dict[str, float] = {}
        for position in positions:
            for game in (
                position.get("legs")
                if position.get("bet_type") == "parlay"
                else [
                    {
                        "event_id": position.get("event_id"),
                    }
                ]
            ):
                key = str((game or {}).get("event_id") or "")
                # Risk accounting charges full stake per leg game
                # during generation; analytics split exposure.
                by_game[key] = by_game.get(key, 0.0) + float(
                    position["exposure"]
                ) / max(
                    1,
                    len(position.get("legs") or [1]),
                )
        generation = result["generation"]
        self.assertEqual(generation["total_exposure"], 300)
        self.assertEqual(generation["risk_exposure"], 80)
        self.assertGreaterEqual(generation["single_count"], 1)
        self.assertGreaterEqual(generation["parlay_count"], 1)
        self.assertEqual(generation["target_parlay_pct"], 0.45)

        aggressive = generate_betting_portfolio(
            total_exposure=300,
            risk_exposure=100,
            season=2026,
            week=3,
            risk="aggressive",
        )
        self.assertGreater(
            aggressive["generation"]["target_parlay_pct"],
            result["generation"]["target_parlay_pct"],
        )
        self.assertGreaterEqual(
            aggressive["generation"]["parlay_count"], 1
        )
        conservative = generate_betting_portfolio(
            total_exposure=300,
            risk_exposure=80,
            season=2026,
            week=3,
            risk="conservative",
        )
        self.assertGreaterEqual(
            conservative["generation"]["single_count"],
            conservative["generation"]["parlay_count"],
        )
        self.assertLessEqual(
            conservative["generation"]["target_parlay_pct"],
            0.25,
        )

    def test_results_summary_computes_pnl_and_breakdowns(self):
        from app.analysis.insights.betting.portfolio import (
            _build_results_summary,
        )

        settled = [
            {
                **create_position_from_market(
                    _market(market_id="a"), exposure=25
                ),
                "status": "won",
                "entry_price": -110,
                "edge": 4.5,
                "confidence": "High",
                "closing_price": -125,
            },
            {
                **create_position_from_market(
                    _market(
                        market_id="b",
                        market_type="total",
                        selection="Over 47.5",
                    ),
                    exposure=25,
                ),
                "status": "lost",
                "entry_price": -110,
                "edge": 2.0,
                "confidence": "Moderate",
                "model_probability": 0.57,
            },
            {
                **create_position_from_market(
                    _market(market_id="c"), exposure=20
                ),
                "status": "push",
                "entry_price": -110,
                "edge": 1.0,
                "confidence": "High",
            },
        ]
        settled[0]["model_probability"] = 0.62
        summary = _build_results_summary(settled)
        self.assertEqual(summary["won"], 1)
        self.assertEqual(summary["lost"], 1)
        self.assertEqual(summary["push"], 1)
        self.assertEqual(summary["win_rate"], 50.0)
        # +$22.73 on -110/$25 win, -$25 on loss, $0 push ≈ -$2.27
        self.assertAlmostEqual(summary["profit_loss"], -2.27, places=1)
        self.assertTrue(summary["by_market"])
        self.assertTrue(summary["by_confidence"])
        self.assertEqual(len(summary["settled_positions"]), 3)


if __name__ == "__main__":
    unittest.main()
