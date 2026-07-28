from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from dashboard import continuous_fare_series


class ContinuousFareSeriesTests(unittest.TestCase):
    def test_omits_unavailable_days_without_breaking_the_series(self) -> None:
        quotes = [
            {"observed_at": "2026-07-18T07:00:00+02:00", "no_checked_bag_eur": 1200.0},
            {"observed_at": "2026-07-19T07:00:00+02:00", "no_checked_bag_eur": None},
            {"observed_at": "2026-07-20T07:00:00+02:00", "no_checked_bag_eur": 1080.0},
        ]

        dates, fares = continuous_fare_series(quotes)

        self.assertEqual(
            dates,
            [
                datetime.fromisoformat("2026-07-18T12:00:00+02:00"),
                datetime.fromisoformat("2026-07-20T12:00:00+02:00"),
            ],
        )
        self.assertEqual(fares, [1200.0, 1080.0])

    def test_uses_the_latest_observation_for_each_day(self) -> None:
        quotes = [
            {"observed_at": "2026-07-18T07:00:00+02:00", "no_checked_bag_eur": 1200.0},
            {"observed_at": "2026-07-18T18:00:00+02:00", "no_checked_bag_eur": 1150.0},
        ]

        dates, fares = continuous_fare_series(quotes)

        self.assertEqual(dates, [datetime.fromisoformat("2026-07-18T12:00:00+02:00")])
        self.assertEqual(fares, [1150.0])


if __name__ == "__main__":
    unittest.main()
