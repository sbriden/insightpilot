"""Tests for sports betting portfolio analytics."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting.portfolio import (
    _position_clv,
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
        # With enough games and markets, generation should spend
        # essentially the full total exposure budget.
        self.assertGreaterEqual(allocated, 300.0 * 0.95)
        generation = result["generation"]
        self.assertEqual(generation["total_exposure"], 300)
        self.assertEqual(generation["risk_exposure"], 80)
        self.assertLessEqual(
            float(generation.get("unallocated_exposure") or 0.0),
            15.0,
        )
        self.assertGreaterEqual(generation["single_count"], 1)
        self.assertGreaterEqual(generation["parlay_count"], 1)
        self.assertEqual(generation["target_parlay_pct"], 0.45)
        self.assertEqual(generation["risk"], "balanced")

        # Risk exposure is a hard per-game ceiling during generation.
        game_risk: dict[str, float] = {}
        for position in positions:
            stake = float(position["exposure"])
            if position.get("bet_type") == "parlay":
                for leg in position.get("legs") or []:
                    key = str(leg.get("event_id") or "")
                    game_risk[key] = game_risk.get(key, 0.0) + stake
            else:
                key = str(position.get("event_id") or "")
                game_risk[key] = game_risk.get(key, 0.0) + stake
        for total in game_risk.values():
            self.assertLessEqual(total, 80.0 + 0.05)

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
        self.assertGreaterEqual(
            sum(
                float(p["exposure"])
                for p in aggressive["positions"]
            ),
            300.0 * 0.95,
        )
        conservative = generate_betting_portfolio(
            total_exposure=300,
            risk_exposure=80,
            season=2026,
            week=3,
            risk="conservative",
        )
        self.assertEqual(
            conservative["generation"]["risk"], "conservative"
        )
        self.assertGreaterEqual(
            conservative["generation"]["single_count"],
            conservative["generation"]["parlay_count"],
        )
        self.assertLessEqual(
            conservative["generation"]["target_parlay_pct"],
            0.25,
        )
        self.assertGreaterEqual(
            sum(
                float(p["exposure"])
                for p in conservative["positions"]
            ),
            300.0 * 0.95,
        )

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_generate_skips_games_that_already_started(
        self, mock_slate
    ):
        from app.analysis.insights.betting.portfolio import (
            generate_betting_portfolio,
        )

        played = "2026-10-15T20:15:00"
        future = "2026-10-18T17:00:00"
        markets = [
            _market(
                market_id="den-spread",
                event_id="den",
                event_label="SEA @ DEN",
                home_team="DEN",
                away_team="SEA",
                selection="DEN -2.5",
                edge_probability=9.0,
                start_time=played,
            ),
            _market(
                market_id="buf-spread",
                event_id="buf",
                event_label="BUF @ MIA",
                home_team="MIA",
                away_team="BUF",
                selection="BUF -3.5",
                edge_probability=6.0,
                start_time=future,
            ),
        ]
        mock_slate.return_value = {
            "season": 2026,
            "week": 6,
            "slate_id": "nfl-2026-w6",
            "markets": markets,
            "events": [
                {
                    "event_id": "den",
                    "label": "SEA @ DEN",
                    "home_team": "DEN",
                    "away_team": "SEA",
                    "status": "Final",
                    "start_time": played,
                    "home_score": 17,
                    "away_score": 14,
                },
                {
                    "event_id": "buf",
                    "label": "BUF @ MIA",
                    "home_team": "MIA",
                    "away_team": "BUF",
                    "status": "scheduled",
                    "start_time": future,
                },
            ],
        }
        result = generate_betting_portfolio(
            total_exposure=100,
            risk_exposure=100,
            season=2026,
            week=6,
            risk="balanced",
        )
        teams = {
            str(row.get("home_team") or "")
            for row in result["positions"]
        }
        self.assertNotIn("DEN", teams)
        self.assertIn("MIA", teams)
        self.assertIn(
            "SEA @ DEN",
            result["generation"]["excluded_started_games"],
        )

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_generate_falls_back_when_slate_is_all_pass(
        self, mock_slate
    ):
        """
        When every market is Pass / No Bet, generation should still
        allocate from ranked model edges instead of erroring out.
        """
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
                    edge_probability=2.6 - index * 0.2,
                    expected_value=0.4 - index * 0.1,
                    confidence="Moderate" if index < 2 else "Low",
                    bet_qualified=False,
                    bet_status="pass",
                    no_bet=True,
                )
            )
            markets.append(
                _market(
                    market_id=f"m{index}-total",
                    event_id=event_id,
                    event_label=f"{away} @ {home}",
                    home_team=home,
                    away_team=away,
                    selection=f"Under {44 + index}",
                    market_type="total",
                    line=44 + index,
                    edge_probability=2.1 - index * 0.15,
                    expected_value=-0.5,
                    confidence="Low",
                    bet_qualified=False,
                    bet_status="pass",
                    no_bet=True,
                )
            )
        mock_slate.return_value = {
            "season": 2026,
            "week": 5,
            "slate_id": "nfl-2026-w5",
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
            total_exposure=250,
            risk_exposure=75,
            season=2026,
            week=5,
            risk="balanced",
        )
        self.assertEqual(
            result["generation"]["candidate_source"],
            "progressive",
        )
        self.assertEqual(
            result["generation"]["deployment_status"],
            "fully_deployed",
        )
        allocated = sum(
            float(p["exposure"]) for p in result["positions"]
        )
        self.assertGreaterEqual(allocated, 250.0 * 0.95)
        self.assertGreaterEqual(
            result["generation"]["position_count"], 4
        )
        # Pass labels may still enter Tier 3 when EV is non-negative.
        self.assertGreaterEqual(
            result["generation"]["selected_by_tier"]["remainder"],
            1,
        )

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_progressive_tiers_prefer_strong_then_fill(
        self, mock_slate
    ):
        from app.analysis.insights.betting.portfolio import (
            generate_betting_portfolio,
        )

        markets = [
            _market(
                market_id="strong-1",
                event_id="e0",
                event_label="BUF @ MIA",
                home_team="MIA",
                away_team="BUF",
                selection="BUF -3.5",
                edge_probability=5.5,
                expected_value=4.2,
                confidence="High",
                bet_qualified=True,
                bet_status="strong_bet",
                data_quality={"label": "High"},
            ),
            _market(
                market_id="lean-1",
                event_id="e1",
                event_label="DET @ GB",
                home_team="GB",
                away_team="DET",
                selection="DET -2.5",
                edge_probability=2.2,
                expected_value=1.8,
                confidence="Moderate",
                bet_qualified=True,
                bet_status="lean",
            ),
            _market(
                market_id="pass-ok",
                event_id="e2",
                event_label="DAL @ PHI",
                home_team="PHI",
                away_team="DAL",
                selection="Over 47.5",
                market_type="total",
                line=47.5,
                edge_probability=1.0,
                expected_value=0.4,
                confidence="Low",
                bet_qualified=False,
                bet_status="pass",
                no_bet=True,
            ),
            _market(
                market_id="pass-neg",
                event_id="e3",
                event_label="KC @ DEN",
                home_team="DEN",
                away_team="KC",
                selection="KC -3",
                edge_probability=1.2,
                expected_value=-1.5,
                confidence="Low",
                bet_qualified=False,
                bet_status="pass",
                no_bet=True,
            ),
            _market(
                market_id="strong-2",
                event_id="e4",
                event_label="SF @ SEA",
                home_team="SEA",
                away_team="SF",
                selection="SF -3.5",
                edge_probability=4.5,
                expected_value=3.5,
                confidence="High",
                bet_qualified=True,
                bet_status="strong_bet",
            ),
            _market(
                market_id="lean-2",
                event_id="e5",
                event_label="BAL @ CIN",
                home_team="CIN",
                away_team="BAL",
                selection="BAL -1.5",
                edge_probability=1.8,
                expected_value=1.2,
                confidence="Moderate",
                bet_qualified=True,
                bet_status="lean",
            ),
        ]
        mock_slate.return_value = {
            "season": 2026,
            "week": 6,
            "slate_id": "nfl-2026-w6",
            "markets": markets,
            "events": [
                {
                    "event_id": f"e{i}",
                    "label": m["event_label"],
                    "home_team": m["home_team"],
                    "away_team": m["away_team"],
                }
                for i, m in enumerate(markets)
            ],
        }
        result = generate_betting_portfolio(
            total_exposure=200,
            risk_exposure=80,
            season=2026,
            week=6,
            risk="balanced",
        )
        gen = result["generation"]
        self.assertEqual(gen["candidate_source"], "progressive")
        self.assertIn(
            gen["deployment_status"],
            {"fully_deployed", "partially_deployed"},
        )
        market_ids = {
            str(row.get("market_id") or "")
            for row in result["positions"]
            if str(row.get("bet_type") or "single") == "single"
        }
        self.assertNotIn("pass-neg", market_ids)
        self.assertGreaterEqual(gen["selected_by_tier"]["preferred"], 1)
        self.assertIsNotNone(gen.get("deployment_pct"))
        # At least one selected single carries tier / qualification metadata.
        single = next(
            row
            for row in result["positions"]
            if str(row.get("bet_type") or "single") == "single"
        )
        self.assertIn(
            single.get("allocation_tier"),
            {"preferred", "secondary", "remainder"},
        )
        self.assertTrue(single.get("selection_rationale"))

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_generate_uses_leans_to_fill_tight_risk_cap(
        self, mock_slate
    ):
        """
        Tight risk vs total must not collapse to a few strong bets.
        Generation should keep selecting across the slate, including
        moderate-edge leans, until the budget is filled.
        """
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
            ("LAR", "ARI"),
            ("MIN", "CHI"),
        ]
        for index, (away, home) in enumerate(teams):
            event_id = f"e{index}"
            # First two games are Strong-Bet quality; the rest are
            # Lean-quality moderate edges that must still be used.
            strong = index < 2
            markets.append(
                _market(
                    market_id=f"m{index}-spread",
                    event_id=event_id,
                    event_label=f"{away} @ {home}",
                    home_team=home,
                    away_team=away,
                    selection=f"{away} -3.5",
                    market_type="spread",
                    edge_probability=6.5 if strong else 2.2,
                    expected_value=4.5 if strong else 1.4,
                    confidence="High" if strong else "Moderate",
                    bet_qualified=True,
                    bet_status="strong_bet" if strong else "lean",
                    no_bet=False,
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
                    edge_probability=5.8 if strong else 1.8,
                    expected_value=3.8 if strong else 1.2,
                    confidence="High" if strong else "Moderate",
                    bet_qualified=True,
                    bet_status="strong_bet" if strong else "lean",
                    no_bet=False,
                )
            )
        mock_slate.return_value = {
            "season": 2026,
            "week": 4,
            "slate_id": "nfl-2026-w4",
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
            total_exposure=500,
            risk_exposure=90,
            season=2026,
            week=4,
            risk="balanced",
        )
        allocated = sum(
            float(p["exposure"]) for p in result["positions"]
        )
        self.assertGreaterEqual(allocated, 500.0 * 0.95)
        self.assertGreaterEqual(
            result["generation"]["position_count"], 6
        )
        # Must reach beyond the two strong-bet games.
        event_ids = set()
        for position in result["positions"]:
            if position.get("bet_type") == "parlay":
                for leg in position.get("legs") or []:
                    event_ids.add(str(leg.get("event_id") or ""))
            else:
                event_ids.add(str(position.get("event_id") or ""))
        self.assertGreaterEqual(len(event_ids - {""}), 5)

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



    def test_position_clv_uses_side_aware_compute(self):
        # Favorite gets a better number: -2 -> -3.5 => +1.5 CLV.
        clv = _position_clv(
            {
                "market_type": "spread",
                "selection": "GB -2",
                "home_team": "GB",
                "away_team": "ATL",
                "entry_line": -2.0,
                "closing_line": -3.5,
            }
        )
        self.assertEqual(clv, 1.5)
        under = _position_clv(
            {
                "market_type": "total",
                "selection": "Under 47",
                "entry_line": 47.0,
                "closing_line": 45.5,
            }
        )
        self.assertEqual(under, 1.5)

    def test_rank_prefers_validated_ev_over_edge_overlap(self):
        from app.analysis.insights.betting.portfolio import (
            _RISK_PROFILES,
            _rank_market_candidates,
        )

        profile = {
            **_RISK_PROFILES["balanced"],
            "min_ev_pct": 0.0,
            "min_edge": 1.0,
        }
        high_edge_low_ev = _market(
            market_id="edgey",
            event_id="e1",
            edge_probability=8.0,
            expected_value=1.2,
            confidence="High",
            bet_qualified=True,
            bet_status="lean",
            no_bet=False,
            model_agreement=0.8,
            data_quality={"label": "High"},
        )
        lower_edge_high_ev = _market(
            market_id="evy",
            event_id="e2",
            event_label="DET @ GB",
            home_team="GB",
            away_team="DET",
            selection="DET -3.5",
            edge_probability=3.5,
            expected_value=7.5,
            confidence="High",
            bet_qualified=True,
            bet_status="strong_bet",
            no_bet=False,
            model_agreement=0.8,
            data_quality={"label": "High"},
        )
        ranked = _rank_market_candidates(
            [high_edge_low_ev, lower_edge_high_ev],
            profile=profile,
            allowed_types={"spread", "total", "moneyline"},
        )
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["market"]["market_id"], "evy")
        self.assertGreater(ranked[0]["ev_pct"], ranked[1]["ev_pct"])

    def test_uncertainty_discounts_allocation_weight(self):
        from app.analysis.insights.betting.portfolio import (
            _RISK_PROFILES,
            _uncertainty_multiplier,
        )

        clean = _market(
            model_agreement=0.85,
            probability_calibrated=True,
            data_quality={"label": "High"},
            uncertainty={
                "data_quality": "High",
                "model_agreement": 0.85,
                "probability_calibrated": True,
            },
        )
        noisy = _market(
            market_id="noisy",
            model_agreement=0.2,
            probability_calibrated=False,
            data_quality={"label": "Low"},
            uncertainty={
                "data_quality": "Low",
                "model_agreement": 0.2,
                "probability_calibrated": False,
                "sigma_margin": 18.0,
            },
        )
        profile = _RISK_PROFILES["balanced"]
        self.assertGreater(
            _uncertainty_multiplier(clean, profile),
            _uncertainty_multiplier(noisy, profile),
        )

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_same_game_correlation_discount_and_caps(
        self, mock_slate
    ):
        from app.analysis.insights.betting.portfolio import (
            generate_betting_portfolio,
        )

        markets = [
            _market(
                market_id="e0-spread",
                event_id="e0",
                selection="BUF -3.5",
                market_type="spread",
                edge_probability=6.0,
                expected_value=6.0,
                confidence="High",
                bet_qualified=True,
                bet_status="strong_bet",
                no_bet=False,
                model_agreement=0.8,
            ),
            _market(
                market_id="e0-total",
                event_id="e0",
                selection="Over 47.5",
                market_type="total",
                line=47.5,
                edge_probability=5.5,
                expected_value=5.5,
                confidence="High",
                bet_qualified=True,
                bet_status="strong_bet",
                no_bet=False,
                model_agreement=0.8,
            ),
            _market(
                market_id="e0-ml",
                event_id="e0",
                selection="BUF",
                market_type="moneyline",
                line=None,
                price=-150,
                edge_probability=5.0,
                expected_value=5.0,
                confidence="High",
                bet_qualified=True,
                bet_status="lean",
                no_bet=False,
                model_agreement=0.8,
            ),
        ]
        for index, (away, home) in enumerate(
            [("DET", "GB"), ("DAL", "PHI"), ("KC", "DEN"), ("SF", "SEA")]
        ):
            markets.append(
                _market(
                    market_id=f"e{index + 1}-spread",
                    event_id=f"e{index + 1}",
                    event_label=f"{away} @ {home}",
                    home_team=home,
                    away_team=away,
                    selection=f"{away} -3.5",
                    edge_probability=4.0 - index * 0.2,
                    expected_value=3.5 - index * 0.2,
                    confidence="High",
                    bet_qualified=True,
                    bet_status="lean",
                    no_bet=False,
                    model_agreement=0.7,
                )
            )
        mock_slate.return_value = {
            "season": 2026,
            "week": 6,
            "slate_id": "nfl-2026-w6",
            "markets": markets,
            "events": [
                {"event_id": "e0", "label": "BUF @ MIA"},
                {"event_id": "e1", "label": "DET @ GB"},
                {"event_id": "e2", "label": "DAL @ PHI"},
                {"event_id": "e3", "label": "KC @ DEN"},
                {"event_id": "e4", "label": "SF @ SEA"},
            ],
            "probability_calibration": {"active": False},
            "qualification_thresholds": {"active": False},
        }
        result = generate_betting_portfolio(
            total_exposure=200,
            risk_exposure=60,
            season=2026,
            week=6,
            risk="conservative",
        )
        self.assertEqual(
            result["generation"]["optimizer"],
            "progressive_tiered_ev",
        )
        # Conservative max_per_game=2 — at most two singles on e0.
        e0_singles = [
            p
            for p in result["positions"]
            if p.get("bet_type") != "parlay"
            and str(p.get("event_id")) == "e0"
        ]
        self.assertLessEqual(len(e0_singles), 2)
        game_risk = 0.0
        for position in result["positions"]:
            if position.get("bet_type") == "parlay":
                for leg in position.get("legs") or []:
                    if str(leg.get("event_id")) == "e0":
                        game_risk += float(position["exposure"])
            elif str(position.get("event_id")) == "e0":
                game_risk += float(position["exposure"])
        self.assertLessEqual(game_risk, 60.0 + 0.05)

    @patch(
        "app.analysis.insights.betting.portfolio.build_betting_slate"
    )
    def test_fractional_kelly_gated_until_validated(
        self, mock_slate
    ):
        from app.analysis.insights.betting.portfolio import (
            generate_betting_portfolio,
        )

        markets = []
        for index, (away, home) in enumerate(
            [
                ("BUF", "MIA"),
                ("DET", "GB"),
                ("DAL", "PHI"),
                ("KC", "DEN"),
                ("SF", "SEA"),
                ("BAL", "CIN"),
            ]
        ):
            markets.append(
                _market(
                    market_id=f"m{index}",
                    event_id=f"e{index}",
                    event_label=f"{away} @ {home}",
                    home_team=home,
                    away_team=away,
                    selection=f"{away} -3.5",
                    edge_probability=5.0,
                    expected_value=4.0,
                    confidence="High",
                    bet_qualified=True,
                    bet_status="strong_bet",
                    no_bet=False,
                    model_agreement=0.8,
                    probability_calibrated=True,
                )
            )
        mock_slate.return_value = {
            "season": 2026,
            "week": 7,
            "markets": markets,
            "events": [
                {"event_id": f"e{i}", "label": f"g{i}"}
                for i in range(6)
            ],
            "probability_calibration": {"active": False},
            "qualification_thresholds": {"active": False},
        }
        result = generate_betting_portfolio(
            total_exposure=300,
            risk_exposure=80,
            risk="balanced",
            bankroll=1000,
            sizing_mode="fractional_kelly",
        )
        sizing = result["generation"]["sizing"]
        self.assertEqual(sizing["mode"], "budget")
        self.assertEqual(sizing["requested"], "fractional_kelly")
        self.assertFalse(sizing["validated"])
        self.assertIn(
            "probability_calibration_inactive", sizing["reasons"]
        )

        mock_slate.return_value["probability_calibration"] = {
            "active": True
        }
        mock_slate.return_value["qualification_thresholds"] = {
            "active": True
        }
        unlocked = generate_betting_portfolio(
            total_exposure=300,
            risk_exposure=80,
            risk="balanced",
            bankroll=1000,
            sizing_mode="fractional_kelly",
        )
        self.assertEqual(
            unlocked["generation"]["sizing"]["mode"],
            "fractional_kelly",
        )
        self.assertTrue(unlocked["generation"]["sizing"]["validated"])

    def test_parlay_marks_independent_product_not_validated_ev(self):
        from app.analysis.insights.betting.portfolio import (
            create_parlay_position,
        )

        parlay = create_parlay_position(
            [
                _market(market_id="a", event_id="e1"),
                _market(
                    market_id="b",
                    event_id="e1",
                    market_type="total",
                    selection="Over 47.5",
                    line=47.5,
                ),
            ],
            exposure=20,
            parlay_size="small",
        )
        self.assertEqual(parlay["bet_type"], "parlay")
        self.assertIsNone(parlay["expected_value"])
        self.assertTrue(parlay["same_game_correlated"])
        self.assertEqual(
            parlay["joint_probability_model"],
            "independent_product_illustrative",
        )


if __name__ == "__main__":
    unittest.main()
