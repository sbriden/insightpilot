"""Unit tests for market-probability daily bet slate generation."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from app.analysis.insights.betting import daily_slate as mod
from app.analysis.insights.betting.pricing import (
    american_to_implied_prob,
    remove_vig_two_way,
)


def _side(
    *,
    cid: str,
    sport: str = "NFL",
    event_id: str = "e1",
    market_type: str = "spread",
    selection: str = "HOME -3",
    price: float = -110.0,
    home_team: str = "HOME",
    away_team: str = "AWAY",
    line: float | None = -3.0,
) -> dict:
    implied = american_to_implied_prob(price)
    return {
        "candidate_id": cid,
        "sport": sport,
        "event_id": event_id,
        "event_label": f"{away_team} @ {home_team}",
        "market_type": market_type,
        "selection": selection,
        "line": line,
        "price": price,
        "home_team": home_team,
        "away_team": away_team,
        "home_logo_url": "https://example.test/home.png",
        "away_logo_url": "https://example.test/away.png",
        "start_time": "2026-10-23T20:00:00+00:00",
        "raw_implied_probability": implied,
        "probability_source": "american_implied",
        "source": "test",
    }


def _two_way_pool(
    n_markets: int = 8,
    *,
    fav_price: float = -300.0,
    dog_price: float = 240.0,
) -> list[dict]:
    """Build n complete two-sided moneyline markets."""

    rows: list[dict] = []
    for i in range(n_markets):
        eid = f"e{i}"
        home = f"H{i}"
        away = f"A{i}"
        rows.append(
            _side(
                cid=f"{eid}-home",
                event_id=eid,
                market_type="moneyline",
                selection=home,
                price=fav_price,
                home_team=home,
                away_team=away,
                line=None,
            )
        )
        rows.append(
            _side(
                cid=f"{eid}-away",
                event_id=eid,
                market_type="moneyline",
                selection=away,
                price=dog_price,
                home_team=home,
                away_team=away,
                line=None,
            )
        )
    return rows


class DailySlateTests(unittest.TestCase):
    def test_american_odds_convert_positive_and_negative(self):
        self.assertAlmostEqual(
            american_to_implied_prob(100),
            0.5,
            places=6,
        )
        self.assertAlmostEqual(
            american_to_implied_prob(-300),
            0.75,
            places=6,
        )
        self.assertAlmostEqual(
            american_to_implied_prob(300),
            0.25,
            places=6,
        )
        self.assertIsNone(american_to_implied_prob(-50))
        self.assertIsNone(american_to_implied_prob(None))

    def test_vig_adjusted_probabilities_sum_to_one(self):
        raw_a = american_to_implied_prob(-110)
        raw_b = american_to_implied_prob(-110)
        fair_a, fair_b = remove_vig_two_way(raw_a, raw_b)
        self.assertIsNotNone(fair_a)
        self.assertIsNotNone(fair_b)
        self.assertAlmostEqual(fair_a + fair_b, 1.0, places=9)

        raw_fav = american_to_implied_prob(-300)
        raw_dog = american_to_implied_prob(240)
        fair_fav, fair_dog = remove_vig_two_way(raw_fav, raw_dog)
        self.assertAlmostEqual(fair_fav + fair_dog, 1.0, places=9)

    def test_side_selection_matches_75_25_over_simulation(self):
        fair_fav, fair_dog = 0.75, 0.25
        market = {
            "market_key": "NFL:e1:moneyline",
            "sides": [
                {
                    "candidate_id": "fav",
                    "fair_probability": fair_fav,
                    "selection": "FAV",
                },
                {
                    "candidate_id": "dog",
                    "fair_probability": fair_dog,
                    "selection": "DOG",
                },
            ],
        }
        rng = __import__("random").Random(12345)
        n = 5000
        fav_hits = 0
        for _ in range(n):
            chosen = mod._sample_market_side(market, rng)
            if chosen["candidate_id"] == "fav":
                fav_hits += 1
        rate = fav_hits / n
        self.assertAlmostEqual(rate, 0.75, delta=0.025)

    def test_fixed_seed_repeatable_selections(self):
        pool = _two_way_pool(10)
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            a = mod.generate_daily_betting_slate(
                total_units=12,
                risk="balanced",
                slate_date="2026-10-23",
                sports=["NFL"],
                seed=99,
            )
            b = mod.generate_daily_betting_slate(
                total_units=12,
                risk="balanced",
                slate_date="2026-10-23",
                sports=["NFL"],
                seed=99,
            )
        self.assertEqual(
            [(p["selection"], p["units"]) for p in a["picks"]],
            [(p["selection"], p["units"]) for p in b["picks"]],
        )
        self.assertEqual(a["meta"]["seed"], 99)

    def test_low_risk_more_concentrated_than_medium_than_high(self):
        # Same selected probs: 0.80, 0.55, 0.30
        selected = [
            {"fair_probability": 0.80},
            {"fair_probability": 0.55},
            {"fair_probability": 0.30},
        ]
        low, _, _ = mod._allocate_by_probability(
            selected,
            total_units=100,
            exponent=3.0,
            min_stake=1,
            max_stake=80,
        )
        med, _, _ = mod._allocate_by_probability(
            selected,
            total_units=100,
            exponent=1.5,
            min_stake=1,
            max_stake=80,
        )
        high, _, _ = mod._allocate_by_probability(
            selected,
            total_units=100,
            exponent=0.75,
            min_stake=1,
            max_stake=80,
        )
        # Herfindahl concentration: sum(share^2)
        def hhi(stakes: list[int]) -> float:
            total = sum(stakes)
            return sum((s / total) ** 2 for s in stakes)

        self.assertGreater(hhi(low), hhi(med))
        self.assertGreater(hhi(med), hhi(high))
        self.assertEqual(low[0], max(low))
        self.assertEqual(sum(low), 100)
        self.assertEqual(sum(med), 100)
        self.assertEqual(sum(high), 100)

    def test_stakes_respect_min_max_and_budget(self):
        selected = [
            {"fair_probability": 0.7},
            {"fair_probability": 0.5},
            {"fair_probability": 0.3},
        ]
        stakes, unallocated, reason = mod._allocate_by_probability(
            selected,
            total_units=20,
            exponent=1.5,
            min_stake=2,
            max_stake=8,
        )
        self.assertTrue(all(2 <= s <= 8 for s in stakes))
        self.assertEqual(sum(stakes) + unallocated, 20)
        self.assertLessEqual(sum(stakes), 20)
        self.assertIsNone(reason)
        self.assertEqual(unallocated, 0)

    def test_redistribute_when_capacity_remains(self):
        selected = [
            {"fair_probability": 0.9},
            {"fair_probability": 0.1},
        ]
        stakes, unallocated, reason = mod._allocate_by_probability(
            selected,
            total_units=10,
            exponent=3.0,
            min_stake=1,
            max_stake=6,
        )
        self.assertEqual(stakes[0], 6)
        self.assertEqual(stakes[1], 4)
        self.assertEqual(unallocated, 0)
        self.assertIsNone(reason)

    def test_infeasible_min_stakes_reported(self):
        selected = [
            {"fair_probability": 0.5},
            {"fair_probability": 0.5},
            {"fair_probability": 0.5},
        ]
        stakes, unallocated, reason = mod._allocate_by_probability(
            selected,
            total_units=5,
            exponent=1.5,
            min_stake=2,
            max_stake=5,
        )
        self.assertEqual(reason, "min_stakes_exceed_budget")
        self.assertEqual(unallocated, 5)
        self.assertEqual(sum(stakes), 0)

    def test_no_duplicate_event_market_selections(self):
        pool = _two_way_pool(20)
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            result = mod.generate_daily_betting_slate(
                total_units=10,
                risk="aggressive",
                slate_date="2026-10-23",
                sports=["NFL"],
                seed=7,
            )
        single_keys = [
            (p["event_id"], p["market_type"])
            for p in result["picks"]
            if p["kind"] == "single"
        ]
        self.assertEqual(len(single_keys), len(set(single_keys)))
        # Parlay legs should not reuse the same market_key twice
        # within a ticket.
        for pick in result["picks"]:
            if pick["kind"] != "parlay":
                continue
            keys = [
                leg.get("market_key") or (leg.get("event_id"), leg.get("market_type"))
                for leg in (pick.get("legs") or [])
            ]
            self.assertEqual(len(keys), len(set(keys)))

    def test_generate_includes_parlays_when_pool_allows(self):
        pool = _two_way_pool(24)
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            result = mod.generate_daily_betting_slate(
                total_units=20,
                risk="balanced",
                slate_date="2026-10-23",
                sports=["NFL"],
                seed=11,
            )
        kinds = {p["kind"] for p in result["picks"]}
        self.assertIn("single", kinds)
        self.assertIn("parlay", kinds)
        self.assertGreater(result["meta"]["parlays"], 0)
        for pick in result["picks"]:
            if pick["kind"] != "parlay":
                continue
            self.assertGreaterEqual(len(pick["legs"]), 2)
            self.assertEqual(
                pick["probability_source"],
                "product_of_leg_market_probs",
            )
            self.assertIsNotNone(pick.get("offered_odds") or pick.get("price"))
            # Joint fair prob is product of leg fair probs.
            joint = 1.0
            for leg in pick["legs"]:
                joint *= float(leg["fair_probability"])
            self.assertAlmostEqual(
                pick["fair_probability"],
                joint,
                places=5,
            )

    def test_missing_odds_never_fabricate_probabilities(self):
        rows = [
            _side(cid="a", price=-110, selection="HOME -3"),
            {
                **_side(cid="b", price=-110, selection="AWAY +3"),
                "price": None,
                "raw_implied_probability": None,
            },
        ]
        markets, rejected = mod._build_eligible_markets(rows)
        self.assertEqual(markets, [])
        self.assertTrue(
            any(
                r["reason"]
                in {
                    "missing_or_invalid_odds",
                    "incomplete_two_way_market",
                }
                for r in rejected
            )
        )

    def test_moneyline_probabilities_from_moneyline_odds(self):
        rows = [
            _side(
                cid="h",
                market_type="moneyline",
                selection="HOME",
                price=-200,
                line=None,
            ),
            _side(
                cid="a",
                market_type="moneyline",
                selection="AWAY",
                price=170,
                line=None,
            ),
        ]
        markets, rejected = mod._build_eligible_markets(rows)
        self.assertEqual(rejected, [])
        self.assertEqual(len(markets), 1)
        sides = {
            s["selection"]: s["fair_probability"]
            for s in markets[0]["sides"]
        }
        raw_h = american_to_implied_prob(-200)
        raw_a = american_to_implied_prob(170)
        fair_h, fair_a = remove_vig_two_way(raw_h, raw_a)
        self.assertAlmostEqual(sides["HOME"], fair_h, places=6)
        self.assertAlmostEqual(sides["AWAY"], fair_a, places=6)

    def test_payout_uses_offered_odds_not_fair_prob(self):
        side = {
            **_side(
                cid="dog",
                market_type="moneyline",
                selection="AWAY",
                price=200,
                line=None,
            ),
            "fair_probability": 0.25,
            "raw_implied_probability": 0.333333,
            "selection_probability": 0.25,
            "market_key": "NFL:e1:moneyline",
        }
        pick = mod._pick_from_selected(
            side,
            units=2,
            risk_label="Medium",
            exponent=1.5,
            generated_at="2026-10-23T12:00:00+00:00",
        )
        # +200 pays 2u profit on 2u stake, payout 4
        self.assertEqual(pick["potential_profit"], 4.0)
        self.assertEqual(pick["potential_payout"], 6.0)
        self.assertEqual(pick["offered_odds"], 200)
        self.assertEqual(pick["fair_probability"], 0.25)

    def test_market_only_ignores_model_probability_fields(self):
        rows = [
            {
                **_side(
                    cid="h",
                    market_type="moneyline",
                    selection="HOME",
                    price=-150,
                    line=None,
                ),
                "model_probability": 0.99,
                "edge": 0.40,
                "qualification": "Strong Bet",
            },
            {
                **_side(
                    cid="a",
                    market_type="moneyline",
                    selection="AWAY",
                    price=130,
                    line=None,
                ),
                "model_probability": 0.01,
                "edge": -0.40,
                "qualification": "Pass",
            },
        ]
        markets, _ = mod._build_eligible_markets(rows)
        self.assertEqual(len(markets), 1)
        fair = {
            s["selection"]: s["fair_probability"]
            for s in markets[0]["sides"]
        }
        raw_h = american_to_implied_prob(-150)
        raw_a = american_to_implied_prob(130)
        expected_h, expected_a = remove_vig_two_way(raw_h, raw_a)
        self.assertAlmostEqual(fair["HOME"], expected_h, places=6)
        self.assertAlmostEqual(fair["AWAY"], expected_a, places=6)
        self.assertNotAlmostEqual(fair["HOME"], 0.99, places=2)

    def test_event_on_date_uses_et_calendar(self):
        late = {
            "start_time": "2026-10-23T03:00:00+00:00",  # 11pm ET Oct 22
        }
        early = {
            "start_time": "2026-10-23T05:00:00+00:00",  # 1am ET Oct 23
        }
        self.assertFalse(
            mod._event_on_date(late, date(2026, 10, 23))
        )
        self.assertTrue(
            mod._event_on_date(early, date(2026, 10, 23))
        )

    def test_date_only_start_not_started_until_next_et_day(self):
        from datetime import datetime as real_datetime

        today = real_datetime.now(mod._ET).date()
        today_event = {
            "start_time": today.isoformat(),
            "status": "False",
        }
        self.assertTrue(mod._event_on_date(today_event, today))
        self.assertFalse(mod._event_started(today_event))

        past = date.fromordinal(today.toordinal() - 1)
        past_event = {
            "start_time": past.isoformat(),
            "status": "scheduled",
        }
        self.assertTrue(mod._event_started(past_event))

    def test_attach_model_logos_uses_adjacent_day_and_abbr(self):
        rows = [
            {
                "candidate_id": "c1",
                "home_team": "MOST",
                "away_team": "SHSU",
                "home_logo_url": None,
                "away_logo_url": None,
            }
        ]

        def fake_model(*, sport, target_date):
            if target_date == date(2026, 10, 28):
                return (
                    [
                        {
                            "home_team": "MOST",
                            "away_team": "SHSU",
                            "home_logo_url": (
                                "https://a.espncdn.com/i/teamlogos/"
                                "ncaa/500/2623.png"
                            ),
                            "away_logo_url": (
                                "https://a.espncdn.com/i/teamlogos/"
                                "ncaa/500/2534.png"
                            ),
                        }
                    ],
                    {},
                )
            return ([], {})

        with patch.object(
            mod,
            "_candidates_from_model_slate",
            side_effect=fake_model,
        ), patch.object(
            mod,
            "_team_logo_urls_by_abbreviation",
            return_value={},
        ):
            enriched = mod._attach_model_logos_to_sao_rows(
                rows,
                public_sport="NCAAF",
                target_date=date(2026, 10, 27),
            )
        self.assertEqual(
            enriched[0]["home_logo_url"],
            "https://a.espncdn.com/i/teamlogos/ncaa/500/2623.png",
        )
        self.assertEqual(
            enriched[0]["away_logo_url"],
            "https://a.espncdn.com/i/teamlogos/ncaa/500/2534.png",
        )

        with patch.object(
            mod,
            "_candidates_from_model_slate",
            return_value=([], {}),
        ), patch.object(
            mod,
            "_team_logo_urls_by_abbreviation",
            return_value={
                "MOST": "https://example.test/most.png",
                "SHSU": "https://example.test/shsu.png",
            },
        ):
            enriched = mod._attach_model_logos_to_sao_rows(
                rows,
                public_sport="NCAAF",
                target_date=date(2026, 10, 27),
            )
        self.assertEqual(
            enriched[0]["home_logo_url"],
            "https://example.test/most.png",
        )
        self.assertEqual(
            enriched[0]["away_logo_url"],
            "https://example.test/shsu.png",
        )

    def test_expand_sao_game_candidates(self):
        game = {
            "provider_game_id": "g1",
            "home_abbr": "DET",
            "away_abbr": "CHI",
            "start_time": "2026-10-23T20:00:00Z",
            "spread": -1.5,
            "over_under": 240.5,
            "home_moneyline": -120,
            "away_moneyline": 100,
        }
        rows = mod._expand_sao_game_candidates(
            game,
            sport="NBA",
            league="nba",
        )
        types = {row["market_type"] for row in rows}
        self.assertEqual(types, {"spread", "total", "moneyline"})
        self.assertEqual(len(rows), 6)
        self.assertTrue(
            all(
                0 < row["raw_implied_probability"] < 1
                for row in rows
            )
        )
        markets, rejected = mod._build_eligible_markets(rows)
        self.assertEqual(len(rejected), 0)
        self.assertEqual(len(markets), 3)

    def test_candidates_from_sao_prefers_live_over_partial_db(self):
        target = date(2026, 10, 27)
        live_rows = [
            {
                "provider_game_id": "295329",
                "home_abbr": "BOS",
                "away_abbr": "BKN",
                "start_time": "2026-10-27T23:30:00.000Z",
                "status": "scheduled",
                "spread": -11.5,
                "over_under": 221.5,
                "home_moneyline": -550,
                "away_moneyline": 400,
            },
            {
                "provider_game_id": "295330",
                "home_abbr": "SAS",
                "away_abbr": "SAC",
                # UTC next-day tip that is still ET calendar 10/27.
                "start_time": "2026-10-28T00:00:00.000Z",
                "status": "scheduled",
                "spread": -3.5,
                "over_under": 230.5,
                "home_moneyline": -160,
                "away_moneyline": 140,
            },
            {
                "provider_game_id": "295331",
                "home_abbr": "NYK",
                "away_abbr": "DET",
                "start_time": "2026-10-28T00:00:00.000Z",
                "status": "scheduled",
                "spread": -6.5,
                "over_under": 225.5,
                "home_moneyline": -250,
                "away_moneyline": 200,
            },
            {
                "provider_game_id": "295332",
                "home_abbr": "LAL",
                "away_abbr": "POR",
                "start_time": "2026-10-28T03:00:00.000Z",
                "status": "scheduled",
                "spread": -9.5,
                "over_under": 228.5,
                "home_moneyline": -400,
                "away_moneyline": 320,
            },
        ]
        with patch.object(
            mod,
            "_load_sao_games_for_date",
            return_value=[live_rows[0]],
        ):
            with patch(
                "app.sources.scoresandodds.fetch_odds_rows",
                return_value=(live_rows, {"mocked": True}),
            ):
                rows, meta = mod._candidates_from_sao(
                    league="nba",
                    target_date=target,
                )

        self.assertEqual(meta["source"], "scoresandodds_live")
        self.assertEqual(meta["games"], 4)
        event_ids = {row["event_id"] for row in rows}
        self.assertEqual(len(event_ids), 4)

    def test_load_sao_games_uses_et_start_time_not_utc_game_date(self):
        import pandas as pd

        frame = pd.DataFrame(
            [
                {
                    "game_id": "sao:nba:late",
                    "game_date": date(2026, 10, 28),
                    "start_time": "2026-10-28T00:00:00+00:00",
                    "home_abbr": "SAS",
                    "away_abbr": "SAC",
                    "home_name": "Spurs",
                    "away_name": "Kings",
                    "spread": -3.5,
                    "over_under": 230.5,
                    "home_moneyline": -160,
                    "away_moneyline": 140,
                    "status": "scheduled",
                }
            ]
        )
        with patch(
            "app.canonical.sports_odds.fact_game_market"
            ".load_fact_game_market_from_db",
            return_value=frame,
        ):
            rows = mod._load_sao_games_for_date(
                "nba",
                date(2026, 10, 27),
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["away_abbr"], "SAC")

    def test_generate_daily_slate_with_mocked_pool(self):
        pool = _two_way_pool(12)
        # Mix sports
        for row in pool[6:]:
            row["sport"] = "NBA"
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            result = mod.generate_daily_betting_slate(
                total_units=10,
                risk="balanced",
                slate_date="2026-10-23",
                sports=["NFL", "NBA"],
                seed=42,
            )

        self.assertEqual(result["date"], "2026-10-23")
        self.assertEqual(result["risk"], "balanced")
        self.assertEqual(result["slate_mode_label"], "Market-Probability Randomized")
        self.assertEqual(result["total_units"], 10)
        self.assertIsNone(result["max_picks"])
        self.assertEqual(result["sports_requested"], ["NBA", "NFL"])
        self.assertGreater(result["allocated_units"], 0)
        self.assertLessEqual(
            result["allocated_units"],
            result["total_units"],
        )
        self.assertGreater(len(result["picks"]), 0)
        self.assertEqual(result["meta"]["eligible_markets"], 12)
        self.assertEqual(result["meta"]["sampled_markets"], 12)
        self.assertIn(
            "full_slate_uniform_markets",
            result["meta"]["selection"],
        )
        kinds = {pick["kind"] for pick in result["picks"]}
        self.assertTrue("single" in kinds or "parlay" in kinds)
        for pick in result["picks"]:
            self.assertIsInstance(pick["units"], int)
            self.assertGreaterEqual(pick["units"], 1)
            if pick["kind"] == "single":
                self.assertEqual(
                    pick.get("probability_source"),
                    "vig_adjusted_two_way_american",
                )
                self.assertEqual(
                    pick.get("home_logo_url"),
                    "https://example.test/home.png",
                )
            else:
                self.assertEqual(
                    pick.get("probability_source"),
                    "product_of_leg_market_probs",
                )

    def test_full_slate_sampling_varies_games_across_seeds(self):
        pool = _two_way_pool(24)
        for row in pool[12:]:
            row["sport"] = "NBA"

        event_ids: set[str] = set()
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            for seed in range(12):
                result = mod.generate_daily_betting_slate(
                    total_units=12,
                    risk="balanced",
                    slate_date="2026-10-23",
                    sports=["NFL", "NBA"],
                    seed=seed,
                )
                self.assertEqual(
                    result["meta"]["sampled_markets"],
                    result["meta"]["eligible_markets"],
                )
                for pick in result["picks"]:
                    if pick["kind"] == "single":
                        eid = str(pick.get("event_id") or "")
                        if eid:
                            event_ids.add(eid)
                    else:
                        for leg in pick.get("legs") or []:
                            eid = str(leg.get("event_id") or "")
                            if eid:
                                event_ids.add(eid)

        # Across seeds, far more than a fixed ~5-game pocket should
        # appear when 24 distinct games are eligible.
        self.assertGreaterEqual(len(event_ids), 10)

    def test_side_selection_remains_probability_weighted(self):
        # Heavy favorite should win most side draws; market choice
        # itself stays uniform over the full slate.
        pool = _two_way_pool(
            8,
            fav_price=-400.0,
            dog_price=300.0,
        )
        fav_hits = 0
        trials = 200
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            for seed in range(trials):
                result = mod.generate_daily_betting_slate(
                    total_units=8,
                    max_picks=1,
                    risk="conservative",
                    slate_date="2026-10-23",
                    sports=["NFL"],
                    seed=seed,
                )
                self.assertEqual(len(result["picks"]), 1)
                pick = result["picks"][0]
                if pick["kind"] != "single":
                    continue
                # Home sides are built as favorites in _two_way_pool.
                if str(pick.get("selection") or "").startswith("H"):
                    fav_hits += 1

        self.assertGreater(fav_hits / trials, 0.65)

    def test_rejects_non_positive_units(self):
        with self.assertRaises(ValueError):
            mod.generate_daily_betting_slate(total_units=0)

    def test_rejects_non_positive_max_picks(self):
        with self.assertRaises(ValueError):
            mod.generate_daily_betting_slate(
                total_units=5,
                max_picks=0,
            )

    def test_max_picks_caps_total_positions(self):
        pool = _two_way_pool(16)
        for row in pool[8:]:
            row["sport"] = "NBA"
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(pool, {"mocked": True}),
        ):
            result = mod.generate_daily_betting_slate(
                total_units=10,
                max_picks=5,
                risk="aggressive",
                slate_date="2026-10-23",
                sports=["NFL", "NBA"],
                seed=7,
            )

        self.assertEqual(result["max_picks"], 5)
        self.assertLessEqual(len(result["picks"]), 5)
        self.assertEqual(result["meta"]["max_picks"], 5)
        self.assertEqual(
            result["meta"]["selected_bets"],
            len(result["picks"]),
        )

    def test_apply_max_picks_preserves_single_share(self):
        profile = dict(mod._RISK_PROFILES["balanced"])
        capped = mod._apply_max_picks_to_profile(profile, 5)
        self.assertEqual(
            capped["target_singles"] + capped["max_parlays"],
            5,
        )
        self.assertEqual(capped["target_singles"], 3)
        self.assertEqual(capped["max_parlays"], 2)

        singles_only = mod._apply_max_picks_to_profile(profile, 1)
        self.assertEqual(singles_only["target_singles"], 1)
        self.assertEqual(singles_only["max_parlays"], 0)
        self.assertEqual(singles_only["single_pct"], 1.0)

    def test_rejects_empty_sports(self):
        with self.assertRaises(ValueError):
            mod.generate_daily_betting_slate(
                total_units=5,
                sports=["xyz"],
            )

    def test_insufficient_eligible_markets_raises(self):
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=([], {"mocked": True}),
        ):
            with self.assertRaises(ValueError) as ctx:
                mod.generate_daily_betting_slate(
                    total_units=5,
                    slate_date="2026-10-23",
                    sports=["NFL"],
                    seed=1,
                )
        self.assertIn("No eligible", str(ctx.exception))

    def test_enrich_model_candidates_applies_sao_moneyline(self):
        rows = [
            {
                "candidate_id": "cfb:ore-ml",
                "sport": "NCAAF",
                "event_id": "e1",
                "event_label": "ORE @ ILL",
                "market_type": "moneyline",
                "selection": "ORE",
                "line": None,
                "price": None,
                "home_team": "ILL",
                "away_team": "ORE",
                "raw_implied_probability": None,
                "probability_source": "pending_sao",
                "source": "model_slate",
            },
            {
                "candidate_id": "cfb:ill-spread",
                "sport": "NCAAF",
                "event_id": "e1",
                "event_label": "ORE @ ILL",
                "market_type": "spread",
                "selection": "ILL +10",
                "line": 10.0,
                "price": -110.0,
                "home_team": "ILL",
                "away_team": "ORE",
                "raw_implied_probability": american_to_implied_prob(
                    -110
                ),
                "probability_source": "american_implied",
                "source": "model_slate",
            },
        ]
        sao_game = {
            "away_abbr": "ORE",
            "home_abbr": "ILL",
            "home_moneyline": 310.0,
            "away_moneyline": -400.0,
            "spread_price": -105.0,
            "start_time": "2026-10-24T19:00:00.000Z",
        }
        with patch(
            "app.sources.scoresandodds.fetch_odds_rows",
            return_value=([sao_game], {"row_count": 1}),
        ):
            enriched, meta = mod._enrich_model_candidates_with_sao(
                rows,
                league="ncaaf",
                target_date=date(2026, 10, 24),
            )
        by_id = {row["candidate_id"]: row for row in enriched}
        self.assertEqual(by_id["cfb:ore-ml"]["price"], -400.0)
        self.assertEqual(by_id["cfb:ill-spread"]["price"], -105.0)
        self.assertEqual(meta["priced"], 2)
        self.assertEqual(meta["matched"], 2)

    def test_sport_availability_requires_two_sided_markets(self):
        # One-sided model-style rows must NOT mark a sport available.
        one_sided = [
            _side(
                cid="ncaaf-one",
                sport="NCAAF",
                event_id="cfb1",
                market_type="spread",
                selection="HOME -3",
            ),
        ]
        # Complete two-way NFL moneyline should be available.
        nfl = [
            _side(
                cid="nfl-h",
                sport="NFL",
                event_id="e1",
                market_type="moneyline",
                selection="HOME",
                price=-150,
                line=None,
            ),
            _side(
                cid="nfl-a",
                sport="NFL",
                event_id="e1",
                market_type="moneyline",
                selection="AWAY",
                price=130,
                line=None,
            ),
        ]
        meta = {
            "sao_sports": {
                "NFL": {"games": 1},
                "NCAAF": {"games": 0},
                "NBA": {"games": 0},
                "NHL": {"games": 0},
            },
        }
        with patch.object(
            mod,
            "_collect_candidates",
            return_value=(one_sided + nfl, meta),
        ):
            result = mod.list_daily_sport_availability(
                slate_date="2026-10-24",
            )
        self.assertEqual(result["available_sports"], ["NFL"])
        self.assertIn("NCAAF", result["unavailable_sports"])
        by_sport = {
            row["sport"]: row for row in result["sports"]
        }
        self.assertTrue(by_sport["NFL"]["available"])
        self.assertFalse(by_sport["NCAAF"]["available"])
        self.assertFalse(by_sport["NBA"]["available"])


if __name__ == "__main__":
    unittest.main()
