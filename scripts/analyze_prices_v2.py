#!/usr/bin/env python3
"""Enhanced flight price analysis with monitoring and alerts."""
from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from alerts import get_alerts_manager
from flight_monitor import FlightMonitor
from preferences import get_preferences_manager

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "price_observations.csv"


@dataclass
class Observation:
    source: str
    origin: str
    destination: str
    outbound_date: str
    return_date: str
    airline: str
    currency: str
    total_price: float
    flight_summary: str
    booking_url: str
    observed_at: str


def load_observations(path: Path = DATA) -> list[Observation]:
    """Load price observations from CSV."""
    if not path.exists():
        return []
    rows: list[Observation] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            price = (row.get("total_price") or "").strip()
            if not price:
                continue
            try:
                total_price = float(price)
            except ValueError:
                continue
            rows.append(
                Observation(
                    source=row.get("source", ""),
                    origin=row.get("origin", ""),
                    destination=row.get("destination", ""),
                    outbound_date=row.get("outbound_date", ""),
                    return_date=row.get("return_date", ""),
                    airline=row.get("airline", ""),
                    currency=row.get("currency", ""),
                    total_price=total_price,
                    flight_summary=row.get("flight_summary", ""),
                    booking_url=row.get("booking_url", ""),
                    observed_at=row.get("observed_at", ""),
                )
            )
    return rows


def main() -> int:
    """Run enhanced price analysis."""
    obs = load_observations()
    if not obs:
        print("No price observations yet. Add rows to data/price_observations.csv first.")
        return 0

    prices = [o.total_price for o in obs]
    if not prices:
        print("No observations with valid prices. Check data/price_observations.csv for incomplete entries.")
        return 0

    median = statistics.median(prices)
    threshold_10 = median * 0.90
    threshold_15 = median * 0.85

    # Print header
    print("\n" + "=" * 140)
    print("FLIGHT PRICE TRACKER - Bilbao (BIO) to Bogota (BOG)")
    print("Target: Depart ~Dec 4, 2026 | Return ~Jan 8, 2027")
    print("=" * 140)
    print(f"Observations: {len(obs)} | Historical median: EUR {median:.2f}\n")

    sorted_obs = sorted(obs, key=lambda o: o.total_price)

    # Print price table
    print(f"{'Price':<12} {'Deal':<12} {'Airline':<20} {'Source':<20} {'Details':<35} {'Link':<50}")
    print("-" * 140)

    for o in sorted_obs:
        if o.total_price <= threshold_15:
            deal_label = "* GREAT"
        elif o.total_price <= threshold_10:
            deal_label = "* GOOD"
        else:
            deal_label = ""

        date_str = ""
        if o.outbound_date and o.return_date:
            date_str = f"{o.outbound_date} to {o.return_date}"
        if o.flight_summary:
            details = o.flight_summary[:33]
        else:
            details = date_str[:33] if date_str else ""

        url = o.booking_url[:47] if o.booking_url else "N/A"
        price_str = f"EUR {o.total_price:.0f}"
        print(f"{price_str:<12} {deal_label:<12} {o.airline:<20} {o.source:<20} {details:<35} {url:<50}")

    print("\n" + "=" * 140)

    best_overall = min(sorted_obs, key=lambda o: o.total_price)

    print(f"[***] BEST OPTION: EUR {best_overall.total_price:.0f} ROUND-TRIP")
    print(f"      {best_overall.airline} via {best_overall.source}")
    print(f"      {best_overall.flight_summary}")
    if best_overall.booking_url:
        print(f"      {best_overall.booking_url}\n")

    cheap = [o for o in obs if o.total_price <= threshold_10]
    if cheap:
        print(f"[*] {len(cheap)} DEAL(S) FOUND (at least 10% below median of EUR {median:.2f})")
        print("\nAll deals ranked:")
        for i, o in enumerate(sorted([c for c in cheap if c.total_price <= threshold_15], key=lambda x: x.total_price), 1):
            print(f"\n  #{i} EUR {o.total_price:.0f} - {o.airline} via {o.source}")
            print(f"     {o.flight_summary}")
            if o.booking_url:
                print(f"     {o.booking_url}")
    else:
        print(f"[INFO] No fares currently at least 10% below historical median (EUR {median:.2f})")

    print("=" * 140 + "\n")

    # Show monitoring status
    prefs = get_preferences_manager()
    if prefs.watched_routes:
        print("=" * 140)
        print("MONITORED ROUTES")
        print("=" * 140 + "\n")

        monitor = FlightMonitor()
        for route_name in prefs.watched_routes:
            stats = monitor.get_route_stats(route_name)
            print(f"[{route_name}]")
            if "observations" in stats:
                print(f"  Route: {stats['origin']} to {stats['destination']}")
                print(f"  Lowest: EUR {stats['lowest_price']:.2f} | Median: EUR {stats['median_price']:.2f}")
                print(f"  Observations: {stats['observations']}")
            else:
                print(f"  Status: {stats.get('status', 'Unknown')}")
            print()

        print("=" * 140 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
