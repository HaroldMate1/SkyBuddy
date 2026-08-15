from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import seat_advisor


class SeatAdvisorTests(unittest.TestCase):
    def test_long_haul_itinerary_uses_reel_workflow_flightaware_then_seatmaps(self) -> None:
        advisory = seat_advisor.build_seat_advisory(
            airline="Iberia",
            aircraft="Airbus A350-900",
            flight_number="IB 6131",
            duration_minutes=610,
            cabin="economy",
        )

        self.assertTrue(advisory["is_long_haul"])
        self.assertEqual(advisory["threshold_minutes"], 480)
        self.assertIn("FlightAware", advisory["workflow_steps"][0]["source"])
        self.assertIn("flightaware.com", advisory["workflow_steps"][0]["url"])
        self.assertIn("SeatMaps", advisory["workflow_steps"][1]["source"])
        self.assertIn("seatmaps.com", advisory["workflow_steps"][1]["url"])
        self.assertEqual([source["name"] for source in advisory["seat_map_sources"]], ["FlightAware", "SeatMaps"])
        self.assertIn("IB 6131", advisory["flightaware_query"])
        self.assertIn("Iberia Airbus A350-900 economy seat map", advisory["seatmaps_query"])
        self.assertIn("Verify the exact airline seat map", advisory["configuration_warning"])
        self.assertTrue(any("lavatory" in tip.lower() for tip in advisory["selection_tips"]))
        self.assertTrue(any("exit row" in tip.lower() for tip in advisory["selection_tips"]))

    def test_short_haul_itinerary_stays_lightweight(self) -> None:
        advisory = seat_advisor.build_seat_advisory(
            airline="Air Europa",
            aircraft="Boeing 737-800",
            duration_minutes=95,
        )

        self.assertFalse(advisory["is_long_haul"])
        self.assertEqual(advisory["priority"], "normal")
        self.assertEqual(advisory["workflow_steps"], [])
        self.assertEqual(advisory["seat_map_sources"], [])
        self.assertIn("under 8 hours", advisory["summary"])

    def test_missing_aircraft_fails_closed_without_guessing_layout(self) -> None:
        advisory = seat_advisor.build_seat_advisory(
            airline="Avianca",
            flight_number="AV 121",
            duration_minutes=670,
        )

        self.assertTrue(advisory["is_long_haul"])
        self.assertEqual(advisory["priority"], "high")
        self.assertIn("aircraft type is missing", advisory["configuration_warning"].lower())
        self.assertIn("AV 121", advisory["flightaware_query"])
        self.assertIn("Avianca", advisory["seatmaps_query"])
        self.assertFalse(any("best seat is" in tip.lower() for tip in advisory["selection_tips"]))

    def test_cli_outputs_json_for_agent_workflows(self) -> None:
        payload = seat_advisor.cli_payload(
            airline="KLM",
            aircraft="Boeing 787-10",
            flight_number="KL 741",
            duration_minutes=690,
            cabin="economy",
        )

        self.assertEqual(payload["airline"], "KLM")
        self.assertEqual(payload["aircraft"], "Boeing 787-10")
        self.assertTrue(payload["seat_advisory"]["is_long_haul"])
        sources = payload["seat_advisory"]["seat_map_sources"]
        self.assertEqual(sources[0]["name"], "FlightAware")
        self.assertIn("https://www.flightaware.com/live/flight/", sources[0]["url"])
        self.assertEqual(sources[1]["name"], "SeatMaps")
        self.assertIn("https://seatmaps.com/search/?q=", sources[1]["url"])


if __name__ == "__main__":
    unittest.main()
