from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from google_flights_monitor import (  # noqa: E402
    airline_name,
    collect_google_flights,
    date_range,
)


class GoogleFlightsMonitorTests(unittest.TestCase):
    def test_date_range_is_inclusive_and_rejects_reverse_windows(self) -> None:
        self.assertEqual(
            date_range(date(2026, 12, 2), date(2026, 12, 4)),
            [date(2026, 12, 2), date(2026, 12, 3), date(2026, 12, 4)],
        )
        with self.assertRaisesRegex(ValueError, "start date must not be after end date"):
            date_range(date(2026, 12, 4), date(2026, 12, 2))

    def test_lufthansa_passenger_code_is_not_labelled_as_cargo(self) -> None:
        leg = {"airline": {"code": "LH", "name": "Lufthansa Cargo"}}
        self.assertEqual(airline_name(leg), "Lufthansa")

    def test_collects_every_carrier_combination_and_baggage_mode(self) -> None:
        calls: list[tuple[str, str, date, date, int]] = []

        def fake_query(origin: str, destination: str, outbound: date, return_date: date, bags: int):
            calls.append((origin, destination, outbound, return_date, bags))
            if bags == 0:
                return {
                    "flights": [
                        self.flight(1200, [("IB", "Iberia")], [("IB", "Iberia")]),
                        self.flight(1100, [("IB", "Iberia"), ("AA", "American Airlines")], [("AA", "American Airlines")]),
                    ]
                }
            return {
                "flights": [
                    self.flight(1250, [("UX", "Air Europa")], [("UX", "Air Europa")]),
                    self.flight(1300, [("LH", "Lufthansa Cargo"), ("AC", "Air Canada")], [("TP", "TAP Portugal")]),
                ]
            }

        result = collect_google_flights(
            origin="BIO",
            destination="BOG",
            outbound_start=date(2026, 12, 2),
            outbound_end=date(2026, 12, 3),
            return_start=date(2027, 1, 6),
            return_end=date(2027, 1, 7),
            query_runner=fake_query,
            observed_at="2026-07-18T14:43:03+00:00",
        )

        self.assertEqual(len(calls), 8)
        self.assertEqual(result["queries_attempted"], 8)
        self.assertEqual(result["query_failures"], [])
        carriers = {row["carrier"]: row for row in result["carriers"]}
        self.assertEqual(
            set(carriers),
            {
                "Iberia",
                "American Airlines + Iberia",
                "Air Europa",
                "Air Canada + Lufthansa + TAP Portugal",
            },
        )
        self.assertEqual(carriers["American Airlines + Iberia"]["cabin_only"]["price_eur"], 1100)
        self.assertIsNone(carriers["Air Europa"]["cabin_only"])
        self.assertEqual(carriers["Air Europa"]["one_checked_bag"]["price_eur"], 1250)

    def test_does_not_publish_partial_output_by_default(self) -> None:
        def failing_query(*_args):
            raise RuntimeError("upstream unavailable")

        with self.assertRaisesRegex(RuntimeError, "Google Flights sweep incomplete"):
            collect_google_flights(
                origin="BIO",
                destination="BOG",
                outbound_start=date(2026, 12, 2),
                outbound_end=date(2026, 12, 2),
                return_start=date(2027, 1, 6),
                return_end=date(2027, 1, 6),
                query_runner=failing_query,
                observed_at="2026-07-18T14:43:03+00:00",
            )

    @staticmethod
    def flight(price: float, outbound_airlines: list[tuple[str, str]], return_airlines: list[tuple[str, str]]) -> dict:
        def leg(code: str, name: str) -> dict:
            return {
                "airline": {"code": code, "name": name},
                "departure_airport": {"code": "AAA"},
                "arrival_airport": {"code": "BBB"},
                "flight_number": "1",
            }

        return {
            "price": price,
            "duration": 1500,
            "outbound": {"stops": max(0, len(outbound_airlines) - 1), "legs": [leg(*item) for item in outbound_airlines]},
            "return": {"stops": max(0, len(return_airlines) - 1), "legs": [leg(*item) for item in return_airlines]},
        }


if __name__ == "__main__":
    unittest.main()
