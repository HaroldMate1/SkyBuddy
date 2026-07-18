from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_google_flights_results.py"


class ApplyGoogleFlightsResultsTests(unittest.TestCase):
    def test_applies_every_carrier_and_keeps_separate_winners(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            payload = {
                "observed_at": "2026-07-18T14:43:03+00:00",
                "source": "Google Flights via fli 0.9.0",
                "origin": "BIO",
                "destination": "BOG",
                "queries_attempted": 2,
                "query_failures": [],
                "itineraries_returned": 3,
                "carriers": [
                    {
                        "carrier": "American Airlines + Iberia",
                        "cabin_only": self.itinerary(1339, 0, "2026-12-02", "2027-01-10"),
                        "one_checked_bag": self.itinerary(1639, 1, "2026-12-05", "2027-01-07"),
                    },
                    {
                        "carrier": "Air Europa",
                        "cabin_only": self.itinerary(1548, 0, "2026-12-02", "2027-01-10"),
                        "one_checked_bag": self.itinerary(1578, 1, "2026-12-04", "2027-01-10"),
                    },
                    {
                        "carrier": "Air Canada + Lufthansa + TAP Portugal",
                        "cabin_only": None,
                        "one_checked_bag": self.itinerary(1614, 2, "2026-12-06", "2027-01-07"),
                    },
                ],
            }
            (data / "google_flights_latest.json").write_text(json.dumps(payload), encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["cabin_winner"]["carrier"], "American Airlines + Iberia")
            self.assertEqual(result["checked_winner"]["carrier"], "Air Europa")

            # Scheduler retries must not duplicate the same observation.
            subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
            )

            with (data / "fare_history.csv").open(newline="", encoding="utf-8") as handle:
                fare_rows = list(csv.DictReader(handle))
            self.assertEqual(len(fare_rows), 1)
            latest = fare_rows[-1]
            self.assertEqual(latest["airline"], "American Airlines + Iberia")
            self.assertEqual(latest["checked_airline"], "Air Europa")
            self.assertEqual(latest["checked_bag_eur"], "1578.0")

            with (data / "airline_history.csv").open(newline="", encoding="utf-8") as handle:
                airline_rows = list(csv.DictReader(handle))
            self.assertEqual(len(airline_rows), 3)
            bag_only = next(row for row in airline_rows if row["airline"] == "Air Canada + Lufthansa + TAP Portugal")
            self.assertEqual(bag_only["no_checked_bag_eur"], "")
            self.assertEqual(bag_only["checked_bag_eur"], "1614.0")
            self.assertTrue((root / "reports" / "fare_history.png").exists())

    @staticmethod
    def itinerary(price: float, stops: int, outbound: str, return_date: str) -> dict:
        return {
            "carrier": "fixture",
            "price_eur": price,
            "bags": 0,
            "outbound_date": outbound,
            "return_date": return_date,
            "outbound_stops": stops,
            "return_stops": stops,
            "total_duration_minutes": 1500,
            "outbound_airlines": ["Fixture"],
            "return_airlines": ["Fixture"],
        }


if __name__ == "__main__":
    unittest.main()
