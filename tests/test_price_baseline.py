from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import booking_agent
import price_baseline


class PriceBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.scanner = price_baseline.PriceBaseline(
            baseline_file=self.tmp / "baseline.csv",
            observations_file=self.tmp / "observations.csv",
        )
        self.now = datetime.now(timezone.utc)

    def _seed_year(self, prices: list[float], step_days: int = 3) -> None:
        """Record one price every `step_days` going backwards from today."""
        for index, price in enumerate(prices):
            observed = self.now - timedelta(days=index * step_days)
            self.scanner.record_price(
                origin="BIO",
                destination="BOG",
                price=price,
                outbound_date="2026-12-04",
                observed_at=observed.isoformat(timespec="seconds"),
                source="test",
            )

    def test_baseline_summarises_the_recorded_year(self) -> None:
        self._seed_year([600 + (index % 20) * 10 for index in range(100)])

        baseline = self.scanner.build("BIO", "BOG")

        self.assertEqual(baseline.days, price_baseline.DEFAULT_LOOKBACK_DAYS)
        self.assertEqual(baseline.samples, 100)
        self.assertEqual(baseline.minimum, 600.0)
        self.assertEqual(baseline.maximum, 790.0)
        self.assertIsNotNone(baseline.median)
        self.assertEqual(baseline.confidence, "high")
        self.assertEqual(baseline.buy_threshold, baseline.p10)

    def test_observations_outside_the_window_are_ignored(self) -> None:
        self.scanner.record_price(
            origin="BIO",
            destination="BOG",
            price=400.0,
            observed_at=(self.now - timedelta(days=400)).isoformat(timespec="seconds"),
        )
        self._seed_year([800.0, 810.0, 820.0])

        baseline = self.scanner.build("BIO", "BOG")

        self.assertEqual(baseline.samples, 3)
        self.assertEqual(baseline.minimum, 800.0)

    def test_other_routes_do_not_contaminate_the_baseline(self) -> None:
        self._seed_year([800.0, 820.0, 840.0])
        self.scanner.record_price(origin="MAD", destination="BOG", price=300.0)

        baseline = self.scanner.build("BIO", "BOG")

        self.assertEqual(baseline.samples, 3)

    def test_verdicts_track_the_position_in_the_distribution(self) -> None:
        self._seed_year([float(price) for price in range(600, 900, 3)])

        cheap = self.scanner.evaluate("BIO", "BOG", price=610.0)
        median_ish = self.scanner.evaluate("BIO", "BOG", price=745.0)
        expensive = self.scanner.evaluate("BIO", "BOG", price=890.0)

        self.assertEqual(cheap["verdict"], price_baseline.VERDICT_BUY)
        self.assertTrue(cheap["should_book"])
        self.assertEqual(median_ish["verdict"], price_baseline.VERDICT_FAIR)
        self.assertFalse(median_ish["should_book"])
        self.assertEqual(expensive["verdict"], price_baseline.VERDICT_HIGH)

    def test_target_price_always_wins(self) -> None:
        self._seed_year([float(price) for price in range(600, 900, 3)])

        verdict = self.scanner.evaluate("BIO", "BOG", price=800.0, target_price=820.0)

        self.assertEqual(verdict["verdict"], price_baseline.VERDICT_BUY)
        self.assertTrue(any("target" in reason for reason in verdict["reasons"]))

    def test_empty_history_is_reported_not_guessed(self) -> None:
        verdict = self.scanner.evaluate("BIO", "BOG", price=700.0)

        self.assertEqual(verdict["confidence"], "none")
        self.assertIsNone(verdict["percentile"])
        self.assertTrue(any("No price history" in reason for reason in verdict["reasons"]))


class BuyDecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.scanner = price_baseline.PriceBaseline(
            baseline_file=self.tmp / "baseline.csv",
            observations_file=self.tmp / "observations.csv",
        )
        self.engine = price_baseline.BuyDecisionEngine(self.scanner)
        self.engine.booking = booking_agent.BookingAgent(bookings_file=self.tmp / "bookings.json")

        now = datetime.now(timezone.utc)
        for index, price in enumerate(range(700, 1000, 3)):
            self.scanner.record_price(
                origin="BIO",
                destination="BOG",
                price=float(price),
                outbound_date="2026-12-04",
                observed_at=(now - timedelta(days=index)).isoformat(timespec="seconds"),
                source="test",
            )

    def _trigger(self, price: float):
        return self.engine.auto_book_if_deal(
            origin="BIO",
            destination="BOG",
            outbound_date="2026-12-04",
            price=price,
            booking_url="https://www.iberia.com/es/booking/offer",
            airline="Iberia",
            passengers=["harold"],
        )

    def test_cheap_offer_creates_a_booking_intent(self) -> None:
        result = self._trigger(705.0)

        self.assertTrue(result["triggered"])
        self.assertEqual(result["assessment"]["verdict"], price_baseline.VERDICT_BUY)
        intent_id = result["booking"]["intent_id"]
        self.assertEqual(
            self.engine.booking.intents[intent_id].status, booking_agent.AWAITING
        )

    def test_expensive_offer_creates_nothing(self) -> None:
        result = self._trigger(980.0)

        self.assertFalse(result["triggered"])
        self.assertNotIn("booking", result)
        self.assertEqual(self.engine.booking.intents, {})

    def test_triggered_intent_keeps_a_price_ceiling(self) -> None:
        result = self._trigger(705.0)
        intent = self.engine.booking.intents[result["booking"]["intent_id"]]

        self.assertIsNotNone(intent.max_price)
        self.assertGreaterEqual(intent.max_price, 705.0)
        self.assertLess(intent.max_price, 730.0)

    def test_live_offer_is_recorded_into_the_history(self) -> None:
        before = self.scanner.build("BIO", "BOG").samples
        self._trigger(705.0)

        self.assertEqual(self.scanner.build("BIO", "BOG").samples, before + 1)


if __name__ == "__main__":
    unittest.main()
