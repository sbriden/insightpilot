"""Regression tests for prediction-tape and probability semantics."""

from __future__ import annotations

import unittest

from app.analysis.insights.betting.clv import compute_clv
from app.analysis.insights.betting.dataset_eligibility import (
    eligibility_counts,
    filter_rows,
    qualification_status,
    row_eligible,
)
from app.analysis.insights.betting.market_movement import build_market_movement
from app.analysis.insights.betting.pricing import (
    REFERENCE_PROBABILITY,
    american_to_implied_prob,
    expected_value_american,
    market_edge_probability,
    market_probs_from_two_way_american,
    reference_edge_probability,
    remove_vig_two_way,
)
from app.analysis.insights.betting.results import (
    build_bet_tape_snapshot,
    filter_learning_rows,
    settle_event_markets,
)
from app.analysis.insights.betting.tape_provenance import (
    resolve_bet_market_lines,
)
from app.analysis.insights.betting.tape_quality_audit import (
    build_pricing_semantics_audit,
    build_tape_quality_report,
)


def _final_event(**overrides):
    base = {
        "event_id": "g1",
        "label": "ATL @ GB",
        "season": 2026,
        "week": 3,
        "status": "Final",
        "home_team": "GB",
        "away_team": "ATL",
        "home_score": 24,
        "away_score": 17,
        "projected_home_score": 23.0,
        "projected_away_score": 18.0,
        "projected_total": 41.0,
        "model_spread": -5.0,
        "market_spread": -3.5,
        "market_total": 45.5,
        "current_spread": -3.5,
        "current_total": 45.5,
    }
    base.update(overrides)
    return base


def _markets():
    return [
        {
            "market_id": "g1:spread",
            "market_type": "spread",
            "selection": "GB -3.5",
            "line": -3.5,
            "price": -110,
            "home_team": "GB",
            "away_team": "ATL",
            "model_probability": 0.58,
            "edge_probability": 5.6,
            "confidence": "High",
            "bet_status": "strong_bet",
            "bet_label": "Strong Bet",
            "market_probability": None,
            "reference_probability": 0.5,
            "market_probability_source": "unavailable",
        },
        {
            "market_id": "g1:total",
            "market_type": "total",
            "selection": "Under 45.5",
            "line": 45.5,
            "price": -110,
            "home_team": "GB",
            "away_team": "ATL",
            "model_probability": 0.55,
            "edge_probability": 2.6,
            "confidence": "Moderate",
            "bet_status": "lean",
            "bet_label": "Lean",
        },
        {
            "market_id": "g1:moneyline",
            "market_type": "moneyline",
            "selection": "GB",
            "line": None,
            "price": -220,
            "home_team": "GB",
            "away_team": "ATL",
            "model_probability": 0.7,
            "edge_probability": 4.0,
            "confidence": "High",
            "bet_status": "pass",
            "bet_label": "Pass",
        },
    ]


class TapeIntegrityTests(unittest.TestCase):
    def test_missing_opening_does_not_become_bet_line_from_close(self):
        resolved = resolve_bet_market_lines(
            snap_spread=None,
            snap_total=None,
            opening_spread=None,
            opening_total=None,
            tape_source="live",
        )
        self.assertIsNone(resolved["bet_market_spread"])
        self.assertIsNone(resolved["bet_market_total"])
        self.assertEqual(resolved["bet_spread_source"], "unavailable")

        event = _final_event(
            opening_spread=None,
            opening_total=None,
            current_spread=-7.0,
            current_total=50.0,
            market_spread=-7.0,
            market_total=50.0,
        )
        snap = {
            "projected_home_score": 23.0,
            "projected_away_score": 18.0,
            "projected_total": 41.0,
            "model_spread": -5.0,
            "market_spread": None,
            "market_total": None,
            "tape_source": "first_publish",
            "captured_at": "2026-09-20T12:00:00+00:00",
            "frozen": True,
        }
        settled = settle_event_markets(event, _markets(), snapshot=snap)
        by_id = {row["market_id"]: row for row in settled}
        self.assertIsNone(by_id["g1:spread"]["bet_line"])
        self.assertEqual(by_id["g1:spread"]["closing_line"], -7.0)
        self.assertNotEqual(
            by_id["g1:spread"]["bet_line"],
            by_id["g1:spread"]["closing_line"],
        )
        self.assertFalse(by_id["g1:spread"]["clv_available"])
        self.assertIsNone(by_id["g1:spread"]["clv"])

    def test_frozen_decision_quote_unchanged_when_close_arrives(self):
        event = _final_event(
            opening_spread=-2.0,
            opening_total=47.0,
            current_spread=-4.0,
            current_total=44.0,
            market_spread=-4.0,
            market_total=44.0,
        )
        snap = {
            "projected_home_score": 23.0,
            "projected_away_score": 18.0,
            "projected_total": 41.0,
            "model_spread": -5.0,
            "market_spread": -2.0,
            "market_total": 47.0,
            "tape_source": "first_publish",
            "captured_at": "2026-09-20T12:00:00+00:00",
            "frozen": True,
        }
        settled = settle_event_markets(event, _markets(), snapshot=snap)
        spread = next(r for r in settled if r["market_type"] == "spread")
        self.assertEqual(spread["bet_line"], -2.0)
        self.assertEqual(spread["closing_line"], -4.0)
        self.assertEqual(spread["bet_line_source"], "snapshot")
        self.assertEqual(spread["closing_line_source"], "closing")
        self.assertEqual(spread["clv"], 2.0)
        self.assertTrue(spread["clv_available"])

    def test_missing_quotes_yield_unavailable_clv_not_zero(self):
        out = compute_clv(
            market_type="spread",
            selection="GB -3",
            home_team="GB",
            away_team="ATL",
            bet_line=None,
            closing_line=-3.0,
            bet_source="unavailable",
            closing_source="closing",
        )
        self.assertIsNone(out["clv"])
        self.assertFalse(out["clv_available"])
        self.assertIsNone(out["beat_close"])

    def test_legacy_settled_row_without_provenance_not_clv_eligible(self):
        from app.analysis.insights.betting.clv import attach_clv_fields
        from app.analysis.insights.betting.dataset_eligibility import (
            clv_eligible,
        )

        row = {
            "market_id": "legacy:spread",
            "market_type": "spread",
            "selection": "GB -3",
            "home_team": "GB",
            "away_team": "ATL",
            "bet_line": -3.0,
            "closing_line": -3.0,
            "result": "won",
            "settled_at": "2026-09-20T12:00:00+00:00",
        }
        self.assertFalse(clv_eligible(row))
        attached = attach_clv_fields(row)
        self.assertFalse(attached["clv_available"])
        self.assertIsNone(attached["clv"])

    def test_provenance_retained_through_opening_fallback_settle(self):
        event = _final_event(
            opening_spread=-2.0,
            opening_total=47.0,
            current_spread=-3.5,
            current_total=45.5,
        )
        snap = build_bet_tape_snapshot(event, prefer_opening=True)
        self.assertEqual(snap["tape_source"], "opening_fallback")
        settled = settle_event_markets(event, _markets(), snapshot=snap)
        spread = next(r for r in settled if r["market_type"] == "spread")
        self.assertEqual(spread["tape_source"], "opening_fallback")
        self.assertEqual(spread["bet_line_source"], "opening")
        self.assertEqual(spread["bet_line"], -2.0)
        self.assertEqual(spread["closing_line"], -3.5)

    def test_opening_not_substituted_from_current_in_movement(self):
        move = build_market_movement(
            opening_spread=None,
            current_spread=-4.5,
            opening_total=None,
            current_total=48.5,
        )
        self.assertIsNone(move["opening_spread"])
        self.assertIsNone(move["opening_total"])
        self.assertIsNone(move["spread_move"])
        self.assertFalse(move["opening_available"])
        self.assertIsNone(move["opening_moneyline"])
        # No opening spread ⇒ no synthetic opening ML either.
        self.assertIsNone(move["opening_moneyline_display"])
        self.assertIsNotNone(move["current_moneyline_display"])


class PricingSemanticsTests(unittest.TestCase):
    def test_two_way_american_devig(self):
        probs = market_probs_from_two_way_american(-110, -110)
        self.assertEqual(probs["market_probability_source"], "two_way_american")
        self.assertAlmostEqual(probs["market_probability"], 0.5, places=5)
        fair_a, fair_b = remove_vig_two_way(
            american_to_implied_prob(-110),
            american_to_implied_prob(-110),
        )
        self.assertAlmostEqual(fair_a, 0.5, places=5)
        self.assertAlmostEqual(fair_b, 0.5, places=5)

    def test_missing_book_prices_no_synthetic_market_edge(self):
        self.assertIsNone(market_edge_probability(0.58, None))
        ref = reference_edge_probability(0.58)
        self.assertAlmostEqual(ref, 8.0, places=1)
        self.assertEqual(REFERENCE_PROBABILITY, 0.5)
        missing = market_probs_from_two_way_american(-110, None)
        self.assertEqual(missing["market_probability_source"], "unavailable")
        self.assertIsNone(missing["market_probability"])

    def test_american_odds_and_ev(self):
        self.assertIsNone(american_to_implied_prob(-50))
        self.assertAlmostEqual(
            american_to_implied_prob(-110) or 0, 0.5238, places=3
        )
        self.assertAlmostEqual(
            american_to_implied_prob(150) or 0, 0.4, places=3
        )
        ev_fav = expected_value_american(0.55, -110)
        ev_dog = expected_value_american(0.45, 150)
        self.assertIsNotNone(ev_fav)
        self.assertIsNotNone(ev_dog)
        self.assertIsNone(expected_value_american(0.55, None))

    def test_invalid_odds_and_push_ev(self):
        self.assertIsNone(american_to_implied_prob(0))
        self.assertIsNone(remove_vig_two_way(None, 0.5)[0])
        ev = expected_value_american(0.48, -110, p_push=0.04)
        self.assertIsNotNone(ev)

    def test_pricing_audit_flags_reference_vs_market(self):
        rows = [
            {
                "market_type": "spread",
                "market_probability": None,
                "reference_probability": 0.5,
                "market_probability_source": "unavailable",
                "expected_value_basis": "assumed_minus_110",
            },
            {
                "market_type": "moneyline",
                "market_probability": 0.65,
                "market_probability_source": "single_side_american",
                "expected_value_basis": "offered_price",
                "expected_value": 2.0,
                "market_edge_probability": 3.0,
            },
        ]
        audit = build_pricing_semantics_audit(rows)
        self.assertEqual(audit["missing_market_probability"], 1)
        self.assertEqual(audit["real_book_market_probability"], 1)
        self.assertEqual(audit["assumed_minus_110_ev"], 1)


class EligibilityTests(unittest.TestCase):
    def test_pass_unknown_qualified_separation(self):
        rows = [
            {
                "bet_status": "strong_bet",
                "result": "won",
                "model_probability": 0.6,
                "bet_line": -3.0,
                "bet_line_source": "snapshot",
                "market_type": "spread",
                "selection": "GB -3",
            },
            {
                "bet_status": "pass",
                "result": "lost",
                "model_probability": 0.55,
                "market_type": "spread",
                "selection": "ATL +3",
            },
            {
                "bet_status": None,
                "result": "won",
                "model_probability": 0.52,
                "market_type": "total",
                "selection": "Over 45",
            },
        ]
        self.assertEqual(qualification_status(rows[2]), "unknown")
        self.assertTrue(row_eligible(rows[0], "qualified_bet_roi"))
        self.assertFalse(row_eligible(rows[1], "qualified_bet_roi"))
        self.assertFalse(row_eligible(rows[2], "qualified_bet_roi"))
        self.assertTrue(row_eligible(rows[1], "forecast_quality"))
        self.assertTrue(row_eligible(rows[2], "forecast_quality"))
        learn = filter_rows(rows, "selection_learning")
        self.assertEqual(len(learn), 1)
        self.assertEqual(learn[0]["bet_status"], "strong_bet")
        cohort, label = filter_learning_rows(rows)
        self.assertEqual(label, "strong_lean_thin")
        self.assertEqual(len(cohort), 1)
        counts = eligibility_counts(rows)
        self.assertEqual(counts["qualified_bet_roi"], 1)
        self.assertEqual(counts["by_qualification"]["unknown"], 1)

    def test_learning_excludes_pass_corpus(self):
        rows = [
            {"bet_status": "pass", "result": "won"} for _ in range(20)
        ]
        cohort, label = filter_learning_rows(rows)
        self.assertEqual(label, "no_actionable")
        self.assertEqual(cohort, [])

    def test_tape_quality_report_counts(self):
        settled = settle_event_markets(
            _final_event(
                opening_spread=None,
                opening_total=None,
                current_spread=-3.5,
                current_total=45.5,
            ),
            _markets(),
            snapshot={
                "model_spread": -5.0,
                "projected_total": 41.0,
                "market_spread": None,
                "market_total": None,
                "tape_source": "first_publish",
                "captured_at": "2026-09-20T12:00:00+00:00",
            },
        )
        report = build_tape_quality_report(settled)
        self.assertGreaterEqual(report["clv_unavailable"], 1)
        self.assertGreaterEqual(report["missing_bet_line"], 1)


class SettlementEdgeCasesTests(unittest.TestCase):
    def test_push_and_reversed_spread_side(self):
        event = _final_event(home_score=24, away_score=21)  # margin 3
        markets = [
            {
                "market_id": "g1:spread",
                "market_type": "spread",
                "selection": "GB -3",
                "line": -3.0,
                "price": -110,
                "home_team": "GB",
                "away_team": "ATL",
                "model_probability": 0.55,
                "bet_status": "lean",
            }
        ]
        snap = {
            "market_spread": -3.0,
            "market_total": 45.0,
            "model_spread": -4.0,
            "projected_total": 44.0,
            "tape_source": "first_publish",
            "captured_at": "2026-09-20T12:00:00+00:00",
        }
        settled = settle_event_markets(
            event,
            markets,
            snapshot=snap,
        )
        self.assertEqual(settled[0]["result"], "push")

        away_mkt = [
            {
                "market_id": "g1:spread_away",
                "market_type": "spread",
                "selection": "ATL +3",
                "line": 3.0,
                "price": -110,
                "home_team": "GB",
                "away_team": "ATL",
                "model_probability": 0.55,
                "bet_status": "lean",
            }
        ]
        settled_away = settle_event_markets(
            event, away_mkt, snapshot=snap
        )
        self.assertEqual(settled_away[0]["result"], "push")
        self.assertEqual(settled_away[0]["bet_line"], 3.0)


if __name__ == "__main__":
    unittest.main()
