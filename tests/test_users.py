from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import booking_agent
import price_baseline
import users


class UserWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        self.manager = users.UserManager(
            users_file=self.root / "config" / "users.json", root=self.root
        )

    def test_create_user_makes_it_active_with_its_own_workspace(self) -> None:
        result = self.manager.create_user("harold", display_name="Harold Mateo", home_airport="bio")

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["user"]["home_airport"], "BIO")
        self.assertEqual(self.manager.active, "harold")
        self.assertTrue((self.root / "config" / "users" / "harold").exists())
        self.assertTrue((self.root / "data" / "users" / "harold").exists())

    def test_user_ids_are_validated_and_unique(self) -> None:
        self.manager.create_user("harold")

        self.assertEqual(self.manager.create_user("harold")["status"], "error")
        self.assertEqual(self.manager.create_user("Not Valid!")["status"], "error")
        self.assertEqual(self.manager.create_user("")["status"], "error")

    def test_workspaces_never_share_files(self) -> None:
        self.manager.create_user("harold")
        self.manager.create_user("ana")

        harold = self.manager.workspace("harold")
        ana = self.manager.workspace("ana")

        for attribute in (
            "preferences_file",
            "passengers_file",
            "cards_file",
            "alerts_file",
            "bookings_file",
            "baseline_file",
            "observations_file",
        ):
            self.assertNotEqual(getattr(harold, attribute), getattr(ana, attribute))

    def test_default_workspace_keeps_the_legacy_paths(self) -> None:
        workspace = users.build_workspace(users.DEFAULT_USER, self.root)

        self.assertEqual(workspace.preferences_file, self.root / "config" / "preferences.json")
        self.assertEqual(workspace.alerts_file, self.root / "data" / "alerts.json")

    def test_switching_is_persisted(self) -> None:
        self.manager.create_user("harold")
        self.manager.create_user("ana")
        self.manager.switch_user("harold")

        reloaded = users.UserManager(
            users_file=self.root / "config" / "users.json", root=self.root
        )
        self.assertEqual(reloaded.active, "harold")
        self.assertEqual(reloaded.current()["user"]["user_id"], "harold")

    def test_switching_to_an_unknown_user_is_refused(self) -> None:
        self.assertEqual(self.manager.switch_user("nobody")["status"], "error")

    def test_update_user_only_applies_known_fields(self) -> None:
        self.manager.create_user("harold")
        result = self.manager.update_user("harold", home_airport="mad", nickname="ignored")

        self.assertEqual(result["user"]["home_airport"], "MAD")
        self.assertNotIn("nickname", result["applied"])

    def test_delete_user_can_remove_their_data(self) -> None:
        self.manager.create_user("ana")
        (self.root / "data" / "users" / "ana" / "bookings.json").write_text("{}", encoding="utf-8")

        result = self.manager.delete_user("ana", remove_data=True)

        self.assertEqual(result["status"], "deleted")
        self.assertFalse((self.root / "data" / "users" / "ana").exists())
        self.assertNotIn("ana", self.manager.users)

    def test_default_workspace_cannot_be_deleted(self) -> None:
        self.assertEqual(self.manager.delete_user("default")["status"], "error")

    def test_slugify_builds_usable_ids(self) -> None:
        self.assertEqual(users.slugify("Harold Mateo"), "harold-mateo")
        self.assertEqual(users.slugify("  Ana  "), "ana")


class PerUserDataTests(unittest.TestCase):
    """Two travellers must never see each other's flights."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        self.manager = users.UserManager(
            users_file=self.root / "config" / "users.json", root=self.root
        )
        self.manager.create_user("harold")
        self.manager.create_user("ana")

    def booking_for(self, user: str) -> booking_agent.BookingAgent:
        return booking_agent.BookingAgent(bookings_file=self.manager.workspace(user).bookings_file)

    def baseline_for(self, user: str) -> price_baseline.PriceBaseline:
        workspace = self.manager.workspace(user)
        return price_baseline.PriceBaseline(
            baseline_file=workspace.baseline_file,
            observations_file=workspace.observations_file,
        )

    def test_booking_intents_stay_inside_one_workspace(self) -> None:
        harold = self.booking_for("harold")
        created = harold.prepare_booking(
            booking_url="https://www.iberia.com/offer",
            airline="Iberia",
            origin="BIO",
            destination="BOG",
            outbound_date="2026-12-04",
            price=684.0,
        )

        self.assertEqual(created["status"], booking_agent.AWAITING)
        self.assertEqual(self.booking_for("harold").list_bookings()["count"], 1)
        self.assertEqual(self.booking_for("ana").list_bookings()["count"], 0)

    def test_price_history_stays_inside_one_workspace(self) -> None:
        self.baseline_for("harold").record_price("BIO", "BOG", 720.0)
        self.baseline_for("harold").record_price("BIO", "BOG", 690.0)
        self.baseline_for("ana").record_price("BIO", "BOG", 980.0)

        self.assertEqual(self.baseline_for("harold").build("BIO", "BOG").samples, 2)
        self.assertEqual(self.baseline_for("ana").build("BIO", "BOG").samples, 1)
        self.assertEqual(self.baseline_for("ana").build("BIO", "BOG").minimum, 980.0)


if __name__ == "__main__":
    unittest.main()
