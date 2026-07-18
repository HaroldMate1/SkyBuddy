from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fare_history.py"
PYTHON = sys.executable


class FareHistoryTests(unittest.TestCase):
    def run_cli(
        self,
        root: Path,
        *args: str,
        origin: str = "BIO",
        destination: str = "BOG",
        check: bool = True,
    ) -> dict:
        result = subprocess.run(
            [
                PYTHON,
                str(SCRIPT),
                "--root",
                str(root),
                "--origin",
                origin,
                "--destination",
                destination,
                *args,
            ],
            check=check,
            capture_output=True,
            text=True,
        )
        if not check:
            return {"returncode": result.returncode, "stderr": result.stderr}
        return json.loads(result.stdout)

    def test_record_summary_graph_and_alert_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.run_cli(
                root,
                "record",
                "--observed-at", "2026-07-18T07:00:00+02:00",
                "--no-bag", "1120",
                "--checked-bag", "1180",
                "--airline", "Example Air",
                "--checked-airline", "Different Bag Air",
                "--checked-outbound", "2026-12-03",
                "--checked-return", "2027-01-09",
                "--source", "Test",
                "--url", "https://example.com/one",
                "--checked-url", "https://example.com/checked-one",
            )
            self.assertEqual(first["latest"]["checked_airline"], "Different Bag Air")
            self.assertEqual(first["latest"]["checked_outbound_date"], "2026-12-03")
            self.assertEqual(first["latest"]["checked_url"], "https://example.com/checked-one")
            self.assertEqual(first["observations"], 1)
            self.assertTrue(Path(first["graph_path"]).exists())
            with Image.open(first["graph_path"]) as dashboard:
                self.assertEqual(dashboard.size, (1200, 1500))
                self.assertEqual(dashboard.mode, "RGBA")
            self.assertFalse(self.run_cli(root, "should-alert")["alert_required"])

            second = self.run_cli(
                root,
                "record",
                "--observed-at", "2026-07-19T07:00:00+02:00",
                "--no-bag", "1030",
                "--checked-bag", "1090",
                "--airline", "Example Air",
                "--source", "Test",
                "--url", "https://example.com/two",
            )
            self.assertEqual(second["change_from_previous_eur"]["checked_bag"], -90)
            self.assertTrue(self.run_cli(root, "should-alert")["alert_required"])
            self.run_cli(root, "mark-alert-sent", "--sent-at", "2026-07-19T07:05:00+02:00")
            self.assertFalse(self.run_cli(root, "should-alert")["alert_required"])

            self.run_cli(
                root,
                "record",
                "--observed-at", "2026-07-20T07:00:00+02:00",
                "--no-bag", "990",
                "--checked-bag", "1050",
                "--airline", "Example Air",
                "--source", "Test",
                "--url", "https://example.com/three",
            )
            alert = self.run_cli(root, "should-alert")
            self.assertTrue(alert["alert_required"])
            self.assertEqual(alert["reason"], "materially better fare")

    def test_records_per_airline_quotes_including_unverified_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            verified = self.run_cli(
                root,
                "record-airline",
                "--observed-at", "2026-07-18T07:00:00+02:00",
                "--airline", "Air Europa",
                "--no-bag", "1705.29",
                "--checked-bag", "unavailable",
                "--source", "Kayak",
                "--url", "https://example.com/air-europa",
            )
            self.assertEqual(verified["airline_observations"], 1)
            self.assertEqual(verified["latest_airlines"]["Air Europa"]["no_checked_bag_eur"], 1705.29)

            unavailable = self.run_cli(
                root,
                "record-airline",
                "--observed-at", "2026-07-18T07:00:00+02:00",
                "--airline", "Iberia",
                "--no-bag", "unavailable",
                "--checked-bag", "unavailable",
                "--source", "Iberia direct",
                "--url", "https://example.com/iberia",
                "--notes", "No usable live fare captured",
            )
            self.assertEqual(unavailable["airline_observations"], 2)
            self.assertIsNone(unavailable["latest_airlines"]["Iberia"]["no_checked_bag_eur"])
            self.assertEqual(unavailable["latest_airlines"]["Iberia"]["status"], "not_verified")
            history = root / "routes" / "BIO-BOG" / "data" / "airline_history.csv"
            self.assertTrue(history.exists())
            status = self.run_cli(root, "status")
            self.assertEqual(set(status["latest_airlines"]), {"Air Europa", "Iberia"})
            self.assertEqual(status["latest_airlines"]["Iberia"]["status"], "not_verified")

    def test_rejects_nonpositive_price(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [PYTHON, str(SCRIPT), "--root", tmp, "--origin", "BIO", "--destination", "BOG", "record", "--observed-at", "2026-07-18T07:00:00+02:00", "--no-bag", "0", "--checked-bag", "1000", "--airline", "X", "--source", "Y", "--url", "https://example.com"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_unavailable_checked_bag_is_not_alertable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_cli(
                root,
                "record",
                "--observed-at", "2026-07-18T07:00:00+02:00",
                "--no-bag", "1250",
                "--checked-bag", "unavailable",
                "--airline", "Example Air",
                "--source", "Test",
                "--url", "https://example.com/unavailable",
            )
            self.assertIsNone(result["latest"]["checked_bag_eur"])
            alert = self.run_cli(root, "should-alert")
            self.assertFalse(alert["alert_required"])
            self.assertEqual(alert["reason"], "checked-bag fare unavailable")

            mark = self.run_cli(
                root,
                "mark-alert-sent",
                "--sent-at",
                "2026-07-18T07:05:00+02:00",
                check=False,
            )
            self.assertNotEqual(mark["returncode"], 0)
            self.assertIn("checked-bag fare unavailable", mark["stderr"])

    def test_routes_have_independent_history_dashboard_and_alert_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            common = (
                "record",
                "--observed-at", "2026-07-18T07:00:00+02:00",
                "--no-bag", "950",
                "--checked-bag", "1000",
                "--airline", "Example Air",
                "--source", "Test",
                "--url", "https://example.com",
            )
            bio = self.run_cli(root, *common, origin="BIO", destination="BOG")
            mad = self.run_cli(root, *common, origin="MAD", destination="JFK")

            self.assertNotEqual(bio["history_path"], mad["history_path"])
            self.assertEqual(self.run_cli(root, "status", origin="BIO", destination="BOG")["observations"], 1)
            self.assertEqual(self.run_cli(root, "status", origin="MAD", destination="JFK")["observations"], 1)
            self.assertTrue((root / "routes" / "BIO-BOG" / "reports" / "fare_history.png").exists())
            self.assertTrue((root / "routes" / "MAD-JFK" / "reports" / "fare_history.png").exists())

            self.run_cli(
                root,
                "mark-alert-sent",
                "--sent-at", "2026-07-18T07:05:00+02:00",
                origin="BIO",
                destination="BOG",
            )
            self.assertFalse(self.run_cli(root, "should-alert", origin="BIO", destination="BOG")["alert_required"])
            self.assertTrue(self.run_cli(root, "should-alert", origin="MAD", destination="JFK")["alert_required"])


if __name__ == "__main__":
    unittest.main()
