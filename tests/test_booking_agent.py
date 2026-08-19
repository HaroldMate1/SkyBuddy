from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import booking_agent


class BookingAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.agent = booking_agent.BookingAgent(bookings_file=self.tmp / "bookings.json")

    def _prepare(self, **overrides):
        payload = {
            "booking_url": "https://www.iberia.com/es/booking/offer",
            "airline": "Iberia",
            "origin": "bio",
            "destination": "bog",
            "outbound_date": "2026-12-04",
            "return_date": "2027-01-08",
            "price": 684.0,
            "currency": "EUR",
            "passengers": ["harold"],
            "max_price": 700.0,
        }
        payload.update(overrides)
        return self.agent.prepare_booking(**payload)

    def test_prepare_creates_intent_awaiting_confirmation(self) -> None:
        result = self._prepare()

        self.assertEqual(result["status"], booking_agent.AWAITING)
        self.assertTrue(result["intent_id"].startswith("bk_"))
        self.assertEqual(result["intent"]["origin"], "BIO")
        self.assertIn("confirm_booking", result["next_step"])

    def test_price_above_ceiling_is_refused(self) -> None:
        result = self._prepare(price=780.0, max_price=700.0)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("exceeds the ceiling", result["error"])

    def test_non_http_link_is_refused(self) -> None:
        result = self._prepare(booking_url="javascript:alert(1)")

        self.assertEqual(result["status"], "error")
        self.assertIn("http(s)", result["error"])

    def test_unknown_host_is_flagged_but_allowed(self) -> None:
        result = self._prepare(booking_url="https://cheap-tickets.example/offer")

        self.assertEqual(result["status"], booking_agent.AWAITING)
        self.assertTrue(any("not one of SkyBuddy" in warning for warning in result["warnings"]))

    def test_playbook_requires_confirmation_first(self) -> None:
        intent_id = self._prepare()["intent_id"]

        blocked = self.agent.get_booking_playbook(intent_id)
        self.assertEqual(blocked["status"], "error")

        self.agent.confirm_booking(intent_id, approved_by="harold")
        released = self.agent.get_booking_playbook(intent_id)
        self.assertEqual(released["status"], booking_agent.IN_PROGRESS)

    def test_confirmation_rechecks_live_price_against_ceiling(self) -> None:
        intent_id = self._prepare()["intent_id"]

        refused = self.agent.confirm_booking(intent_id, approved_by="harold", current_price=760.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.agent.intents[intent_id].status, booking_agent.AWAITING)

        accepted = self.agent.confirm_booking(intent_id, approved_by="harold", current_price=670.0)
        self.assertEqual(accepted["status"], booking_agent.READY)
        self.assertEqual(self.agent.intents[intent_id].price, 670.0)

    def test_playbook_stops_before_payment_without_authority(self) -> None:
        intent_id = self._prepare()["intent_id"]
        playbook = self.agent.confirm_booking(intent_id, approved_by="harold")["agent_playbook"]

        steps = [step["step"] for step in playbook["steps"]]
        self.assertIn("stop_before_payment", steps)
        self.assertNotIn("pay", steps)
        self.assertFalse(playbook["payment_authority"])

    def test_payment_authority_replaces_the_stop_step(self) -> None:
        intent_id = self._prepare(allow_payment=True)["intent_id"]
        playbook = self.agent.confirm_booking(intent_id, approved_by="harold")["agent_playbook"]

        steps = [step["step"] for step in playbook["steps"]]
        self.assertIn("pay", steps)
        self.assertNotIn("stop_before_payment", steps)

    def test_long_haul_intent_gets_seat_check_step(self) -> None:
        intent_id = self._prepare(
            flight_number="IB 6585", aircraft="Airbus A350-900", duration_minutes=620
        )["intent_id"]
        playbook = self.agent.confirm_booking(intent_id, approved_by="harold")["agent_playbook"]

        steps = [step["step"] for step in playbook["steps"]]
        self.assertIn("check_seats", steps)
        self.assertTrue(playbook["seat_advisory"]["is_long_haul"])
        names = [source["name"] for source in playbook["seat_advisory"]["cross_check_sources"]]
        self.assertIn("SeatGuru", names)
        self.assertIn("aeroLOPA", names)

    def test_short_haul_intent_has_no_seat_step(self) -> None:
        intent_id = self._prepare(duration_minutes=95)["intent_id"]
        playbook = self.agent.confirm_booking(intent_id, approved_by="harold")["agent_playbook"]

        self.assertNotIn("check_seats", [step["step"] for step in playbook["steps"]])

    def test_cancel_and_audit_trail(self) -> None:
        intent_id = self._prepare()["intent_id"]
        self.agent.cancel_booking(intent_id, reason="found cheaper")

        stored = self.agent.get_booking(intent_id)
        self.assertEqual(stored["status"], booking_agent.CANCELLED)
        events = [entry["event"] for entry in stored["intent"]["history"]]
        self.assertEqual(events[0], "prepared")
        self.assertIn("cancelled", events)

    def test_intents_persist_across_instances(self) -> None:
        intent_id = self._prepare()["intent_id"]

        reloaded = booking_agent.BookingAgent(bookings_file=self.tmp / "bookings.json")
        self.assertIn(intent_id, reloaded.intents)


if __name__ == "__main__":
    unittest.main()
