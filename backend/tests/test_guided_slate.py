"""Tests for Guided Market Slate templates, selection, and workflow."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.analysis.insights.betting import guided_slate as guided
from app.analysis.insights.betting import slate_template as tmpl
from app.analysis.insights.betting import template_builder as builder
from app.analysis.insights.betting import template_selector as selector
from app.analysis.insights.betting.pricing import american_to_implied_prob


def _side(
    *,
    cid: str,
    sport: str = "NBA",
    event_id: str = "e1",
    market_type: str = "moneyline",
    selection: str = "HOME",
    price: float = -150.0,
    fair: float | None = None,
) -> dict:
    implied = american_to_implied_prob(price) or 0.5
    return {
        "candidate_id": cid,
        "sport": sport,
        "event_id": event_id,
        "event_label": f"AWAY @ {selection}",
        "market_type": market_type,
        "market_key": f"{sport}:{event_id}:{market_type}",
        "selection": selection,
        "line": None,
        "price": price,
        "home_team": "HOME",
        "away_team": "AWAY",
        "raw_implied_probability": implied,
        "fair_probability": fair if fair is not None else implied,
        "probability_source": "test",
        "source": "test",
    }


def _inventory_pool() -> list[dict]:
    """Diverse sides covering every odds bucket across many games."""

    specs = [
        ("sf1", "g1", "A", -180.0),
        ("sf2", "g2", "B", -200.0),
        ("sf3", "g3", "C", -160.0),
        ("mf1", "g4", "D", -130.0),
        ("mf2", "g5", "E", -120.0),
        ("mf3", "g6", "F", -140.0),
        ("ne1", "g7", "G", -105.0),
        ("ne2", "g8", "H", 100.0),
        ("ne3", "g9", "I", 105.0),
        ("mu1", "g10", "J", 130.0),
        ("mu2", "g11", "K", 150.0),
        ("mu3", "g12", "L", 160.0),
        ("lu1", "g13", "M", 200.0),
        ("lu2", "g14", "N", 220.0),
        ("sf4", "g15", "O", -170.0),
        ("mf4", "g16", "P", -115.0),
        ("ne4", "g17", "Q", -102.0),
        ("mu4", "g18", "R", 140.0),
    ]
    return [
        _side(
            cid=cid,
            event_id=eid,
            selection=sel,
            price=price,
        )
        for cid, eid, sel, price in specs
    ]


class OddsBucketTests(unittest.TestCase):
    def test_bucket_eligibility_positive_and_negative(self):
        self.assertTrue(tmpl.odds_in_bucket(-180, "strong_favorite"))
        self.assertTrue(tmpl.odds_in_bucket(-120, "moderate_favorite"))
        self.assertTrue(tmpl.odds_in_bucket(100, "near_even"))
        self.assertTrue(tmpl.odds_in_bucket(140, "moderate_underdog"))
        self.assertTrue(tmpl.odds_in_bucket(200, "larger_underdog"))
        self.assertFalse(tmpl.odds_in_bucket(-105, "strong_favorite"))
        self.assertIsNone(tmpl.bucket_for_odds(-90))

    def test_templates_validate_for_common_counts(self):
        for n in (3, 5, 8, 10):
            for factory in (
                tmpl.build_low_template,
                tmpl.build_medium_template,
                tmpl.build_high_template,
            ):
                factory(n).validate()

    def test_adaptive_buckets_cover_multiple_options(self):
        sides = _inventory_pool()
        adaptive = tmpl.build_adaptive_buckets(sides, min_options=4)
        for bucket_id in tmpl.BUCKET_ORDER:
            self.assertIn(bucket_id, adaptive)
            self.assertGreaterEqual(
                int(adaptive[bucket_id]["count"]),
                4,
            )
            self.assertTrue(adaptive[bucket_id]["adaptive"])
            bounds = tmpl.BUCKET_SEMANTIC_BOUNDS[bucket_id]
            self.assertGreaterEqual(
                float(adaptive[bucket_id]["min_odds"]),
                float(bounds["min_odds"]),
            )
            self.assertLessEqual(
                float(adaptive[bucket_id]["max_odds"]),
                float(bounds["max_odds"]),
            )

    def test_adaptive_buckets_keep_semantic_walls(self):
        # Outliers and thin inventory must not pull -110 into strong
        # favorites or into larger underdogs.
        sides = [
            _side(cid="sf0", event_id="e0", price=-9000.0),
            _side(cid="sf1", event_id="e1", price=-180.0),
            _side(cid="sf2", event_id="e2", price=-160.0),
            _side(cid="mf1", event_id="e3", price=-120.0),
            _side(cid="mf2", event_id="e4", price=-110.0),
            _side(cid="ne1", event_id="e5", price=100.0),
            _side(cid="mu1", event_id="e6", price=140.0),
            _side(cid="lu1", event_id="e7", price=200.0),
            _side(cid="lu2", event_id="e8", price=4500.0),
        ]
        adaptive = tmpl.build_adaptive_buckets(sides, min_options=4)
        strong = adaptive["strong_favorite"]
        self.assertLessEqual(float(strong["max_odds"]), -150.0)
        self.assertGreaterEqual(float(strong["min_odds"]), -1000.0)
        self.assertNotIn("-110", strong["odds_text"])

        larger = adaptive["larger_underdog"]
        self.assertGreaterEqual(float(larger["min_odds"]), 176.0)
        self.assertLessEqual(float(larger["max_odds"]), 1000.0)
        self.assertNotIn("-110", larger["odds_text"])


class TemplateSelectorBuilderTests(unittest.TestCase):
    def test_selects_matching_risk_family(self):
        sides = _inventory_pool()
        low = selector.select_template(
            risk="low",
            ticket_count=8,
            total_exposure=40,
            sides=sides,
        )
        high = selector.select_template(
            risk="high",
            ticket_count=8,
            total_exposure=40,
            sides=sides,
        )
        self.assertIn("low", low["template"].risk_levels)
        self.assertIn("high", high["template"].risk_levels)
        self.assertGreater(
            low["template"].single_pct,
            high["template"].single_pct,
        )
        self.assertGreater(
            sum(1 for r in high["template"].recipes if r.ticket_type == "parlay"),
            sum(1 for r in low["template"].recipes if r.ticket_type == "parlay"),
        )

    def test_inventory_shortfall_still_returns_template(self):
        # Only favorites available.
        sides = [
            _side(cid=f"c{i}", event_id=f"e{i}", price=-160.0)
            for i in range(10)
        ]
        result = selector.select_template(
            risk="high",
            ticket_count=6,
            total_exposure=30,
            sides=sides,
        )
        self.assertIsNotNone(result["template"])
        self.assertGreaterEqual(result["effective_tickets"], 1)

    def test_stakes_sum_to_exposure_and_distinguish_tickets(self):
        template = tmpl.build_medium_template(8)
        built = builder.build_requirements(
            template,
            total_exposure=40,
            inventory=selector.count_bucket_inventory(_inventory_pool()),
        )
        self.assertEqual(built["total_exposure"], 40)
        self.assertEqual(
            sum(int(t["stake"]) for t in built["tickets"]),
            40,
        )
        singles = [
            t for t in built["tickets"] if t["ticket_type"] == "single"
        ]
        parlays = [
            t for t in built["tickets"] if t["ticket_type"] == "parlay"
        ]
        self.assertEqual(built["ticket_count"], 8)
        self.assertEqual(
            built["ticket_count"],
            len(singles) + len(parlays),
        )
        pick_legs = sum(int(t["leg_count"]) for t in built["tickets"])
        self.assertEqual(pick_legs, len(built["steps"]))
        self.assertGreater(pick_legs, built["ticket_count"])

    def test_insufficient_budget_raises(self):
        with self.assertRaises(ValueError):
            selector.select_template(
                risk="medium",
                ticket_count=10,
                total_exposure=0,
                sides=_inventory_pool(),
                min_stake=1,
            )

    def test_budget_shrinks_ticket_count(self):
        result = selector.select_template(
            risk="medium",
            ticket_count=20,
            total_exposure=5,
            sides=_inventory_pool(),
            min_stake=1,
        )
        self.assertLessEqual(result["effective_tickets"], 5)
        self.assertIsNotNone(result["adjustment_message"])


class GuidedWorkflowTests(unittest.TestCase):
    def _start(self, **kwargs):
        sides = _inventory_pool()
        with patch.object(
            guided,
            "_load_pool",
            return_value=(
                sides,
                {
                    "date": "2026-10-30",
                    "sports": ["NBA"],
                    "candidate_count": len(sides),
                    "eligible_markets": len(sides) // 2,
                    "eligible_sides": len(sides),
                    "rejected_markets": 0,
                    "pool": {},
                },
            ),
        ):
            return guided.start_guided_slate(
                ticket_count=kwargs.get("ticket_count", 6),
                total_exposure=kwargs.get("total_exposure", 30),
                risk=kwargs.get("risk", "medium"),
                sports=["NBA"],
                slate_date="2026-10-30",
                seed=1,
            )

    def test_start_hides_template_name_and_returns_step(self):
        result = self._start()
        session = result["session"]
        self.assertEqual(session["label"], "Guided Market Slate")
        self.assertIn("template_id", session)
        self.assertNotIn("template_name", session)
        self.assertIsNotNone(result["current_step"])
        self.assertGreater(len(result["candidates"]), 0)
        self.assertEqual(
            session["summary"]["total_exposure"],
            30,
        )
        self.assertIn("adaptive_buckets", session)
        # Dynamic ranges should leave multiple choices on the first step.
        self.assertGreaterEqual(len(result["candidates"]), 4)

    def test_each_step_keeps_multiple_candidates(self):
        sides = _inventory_pool()
        with patch.object(
            guided,
            "_load_pool",
            return_value=(
                sides,
                {
                    "date": "2026-10-30",
                    "sports": ["NBA"],
                    "candidate_count": len(sides),
                    "eligible_markets": 8,
                    "eligible_sides": len(sides),
                    "rejected_markets": 0,
                    "pool": {},
                },
            ),
        ):
            session = guided.start_guided_slate(
                ticket_count=5,
                total_exposure=25,
                risk="medium",
                sports=["NBA"],
            )["session"]
            guard = 0
            while session.get("status") != "ready_for_review":
                guard += 1
                self.assertLess(guard, 40)
                candidates = guided.list_step_candidates(
                    session,
                    sides=sides,
                )
                remaining_steps = sum(
                    1
                    for s in (session.get("steps") or [])
                    if s.get("status") != "complete"
                )
                # While the board still has enough unlocked sides, keep
                # offering multiple choices.
                if remaining_steps <= len(sides):
                    self.assertGreaterEqual(
                        len(candidates),
                        min(4, max(1, len(sides) - guard + 1)),
                    )
                self.assertGreater(len(candidates), 0)
                session = guided.select_guided_pick(
                    session,
                    candidate_id=candidates[0]["candidate_id"],
                    sides=sides,
                )["session"]

    def test_select_replace_back_and_confirm_flow(self):
        sides = _inventory_pool()
        with patch.object(
            guided,
            "_load_pool",
            return_value=(
                sides,
                {
                    "date": "2026-10-30",
                    "sports": ["NBA"],
                    "candidate_count": len(sides),
                    "eligible_markets": 8,
                    "eligible_sides": len(sides),
                    "rejected_markets": 0,
                    "pool": {},
                },
            ),
        ):
            started = guided.start_guided_slate(
                ticket_count=4,
                total_exposure=20,
                risk="low",
                sports=["NBA"],
                slate_date="2026-10-30",
            )
            session = started["session"]
            # Fill every step.
            guard = 0
            while session.get("status") != "ready_for_review":
                guard += 1
                self.assertLess(guard, 40)
                candidates = guided.list_step_candidates(session, sides=sides)
                self.assertGreater(len(candidates), 0)
                pick = candidates[0]["candidate_id"]
                nxt = guided.select_guided_pick(
                    session,
                    candidate_id=pick,
                    sides=sides,
                )
                session = nxt["session"]

            self.assertEqual(
                session["summary"]["completed_steps"],
                session["summary"]["total_steps"],
            )
            # Replace first step then re-complete.
            replaced = guided.replace_guided_pick(session, step_index=0)
            session = replaced["session"]
            self.assertEqual(session["status"], "in_progress")
            candidates = replaced["candidates"]
            session = guided.select_guided_pick(
                session,
                candidate_id=candidates[0]["candidate_id"],
                sides=sides,
            )["session"]

            # Finish remaining if any.
            guard = 0
            while session.get("status") != "ready_for_review":
                guard += 1
                self.assertLess(guard, 40)
                candidates = guided.list_step_candidates(session, sides=sides)
                session = guided.select_guided_pick(
                    session,
                    candidate_id=candidates[0]["candidate_id"],
                    sides=sides,
                )["session"]

            reviewed = guided.review_guided_slate(session)
            session = reviewed["session"]
            confirmed = guided.confirm_guided_slate(session)
            self.assertTrue(confirmed["session"]["confirmed"])
            self.assertEqual(
                confirmed["session"]["status"],
                "confirmed",
            )

    def test_no_duplicate_candidate_across_steps(self):
        sides = _inventory_pool()
        with patch.object(
            guided,
            "_load_pool",
            return_value=(
                sides,
                {
                    "date": "2026-10-30",
                    "sports": ["NBA"],
                    "candidate_count": len(sides),
                    "eligible_markets": 8,
                    "eligible_sides": len(sides),
                    "rejected_markets": 0,
                    "pool": {},
                },
            ),
        ):
            session = guided.start_guided_slate(
                ticket_count=5,
                total_exposure=25,
                risk="medium",
                sports=["NBA"],
            )["session"]
            used: set[str] = set()
            guard = 0
            while session.get("status") != "ready_for_review":
                guard += 1
                self.assertLess(guard, 40)
                candidates = guided.list_step_candidates(session, sides=sides)
                for cand in candidates:
                    self.assertNotIn(cand["candidate_id"], used)
                pick = candidates[0]["candidate_id"]
                used.add(pick)
                session = guided.select_guided_pick(
                    session,
                    candidate_id=pick,
                    sides=sides,
                )["session"]

    def test_session_round_trip_resume(self):
        started = self._start(ticket_count=4, total_exposure=16, risk="low")
        session = started["session"]
        # Simulate localStorage round-trip.
        blob = dict(session)
        sides = _inventory_pool()
        with patch.object(
            guided,
            "_load_pool",
            return_value=(
                sides,
                {
                    "date": "2026-10-30",
                    "sports": ["NBA"],
                    "candidate_count": len(sides),
                    "eligible_markets": 8,
                    "eligible_sides": len(sides),
                    "rejected_markets": 0,
                    "pool": {},
                },
            ),
        ):
            candidates = guided.list_step_candidates(blob, sides=sides)
            resumed = guided.select_guided_pick(
                blob,
                candidate_id=candidates[0]["candidate_id"],
                sides=sides,
            )
        self.assertEqual(
            resumed["session"]["session_id"],
            session["session_id"],
        )
        self.assertEqual(
            resumed["session"]["summary"]["completed_steps"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
