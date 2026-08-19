#!/usr/bin/env python3
"""Feed the SkyBuddy website with real Google Flights prices.

Reads every active tracked flight from Supabase, prices it with the `fli`
Google Flights client, writes an observation per route, then asks the site to
run the alert rules over the new data.

Designed for a scheduled runner (GitHub Actions) rather than a serverless
function: a Google Flights query takes tens of seconds and the collector is
happier with a real Python environment.

Environment:
    SUPABASE_URL                 project URL
    SUPABASE_SERVICE_ROLE_KEY    service-role key (bypasses RLS)
    SKYBUDDY_SITE_URL            e.g. https://skybuddy-ochre.vercel.app
    CRON_SECRET                  shared secret for /api/evaluate
    FLI_BIN                      path to the fli executable (default: fli)
    COLLECTOR_CURRENCY           default EUR
    COLLECTOR_MAX_FLIGHTS        safety cap per run (default 25)

Usage::

    python scripts/web_price_collector.py            # every active route
    python scripts/web_price_collector.py --dry-run  # price, print, store nothing
    python scripts/web_price_collector.py --flight-id <uuid>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

QUERY_TIMEOUT_SECONDS = 240


def env(name: str, default: str = "") -> str:
    """Read an environment variable, trimmed."""
    return (os.environ.get(name) or default).strip()


def api_request(url: str, *, method: str = "GET", headers: dict[str, str], payload: Any = None) -> Any:
    """Small JSON HTTP helper so the collector needs no third-party packages."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{method} {url} failed ({error.code}): {detail}") from error


class Supabase:
    """The few PostgREST calls the collector needs."""

    def __init__(self, url: str, service_key: str):
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def active_flights(self, limit: int, flight_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Return the tracked flights to price."""
        query = f"id=eq.{flight_id}" if flight_id else "active=is.true"
        path = f"{self.url}/rest/v1/tracked_flights?{query}&select=*&limit={limit}"
        return api_request(path, headers=self.headers) or []

    def insert_observation(self, row: dict[str, Any]) -> None:
        """Store one observed price."""
        headers = dict(self.headers)
        headers["Prefer"] = "return=minimal"
        api_request(
            f"{self.url}/rest/v1/price_observations",
            method="POST",
            headers=headers,
            payload=row,
        )


def google_flights_url(origin: str, destination: str, outbound: str, return_date: Optional[str]) -> str:
    """The bookable link SkyBuddy shows for a Google Flights result."""
    query = f"Flights from {origin} to {destination} on {outbound}"
    if return_date:
        query += f" through {return_date}"
    return "https://www.google.com/travel/flights?q=" + urllib.parse.quote(query)


def run_fli(flight: dict[str, Any], currency: str, fli_bin: str) -> list[dict[str, Any]]:
    """Price one route with the Google Flights client."""
    command = [
        fli_bin,
        "flights",
        flight["origin"],
        flight["destination"],
        flight["outbound_date"],
        "--class",
        (flight.get("cabin") or "economy").upper().replace(" ", "_"),
        "--stops",
        "ANY",
        "--sort",
        "CHEAPEST",
        "--currency",
        currency,
        "--format",
        "json",
    ]
    if flight.get("return_date"):
        command += ["--return", flight["return_date"]]

    completed = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=QUERY_TIMEOUT_SECONDS
    )
    payload = json.loads(completed.stdout)
    return payload.get("flights") or []


def summarise(itinerary: dict[str, Any]) -> dict[str, Any]:
    """Reduce one Google Flights itinerary to what SkyBuddy stores and shows."""
    legs = itinerary.get("legs") or []
    carriers, numbers, aircraft = [], [], []

    for leg in legs:
        airline = (leg.get("airline") or {}).get("name")
        if airline and airline not in carriers:
            carriers.append(airline)
        code = (leg.get("airline") or {}).get("code") or ""
        number = leg.get("flight_number") or ""
        if number:
            numbers.append(f"{code} {number}".strip())
        if leg.get("aircraft"):
            aircraft.append(leg["aircraft"])

    longest = max(legs, key=lambda leg: leg.get("duration") or 0, default={})

    return {
        "price": float(itinerary.get("price") or 0),
        "currency": itinerary.get("currency") or "EUR",
        "airline": " + ".join(carriers) or "Unknown",
        "flight_numbers": ", ".join(numbers),
        "aircraft": (longest.get("aircraft") or (aircraft[0] if aircraft else "")),
        "duration_minutes": int(itinerary.get("duration") or 0),
        "stops": int(itinerary.get("stops") or 0),
    }


def collect(args: argparse.Namespace) -> int:
    """Price every tracked route and hand the results to the website."""
    supabase_url = env("SUPABASE_URL")
    service_key = env("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.", file=sys.stderr)
        return 2

    currency = env("COLLECTOR_CURRENCY", "EUR")
    fli_bin = env("FLI_BIN", "fli")
    limit = int(env("COLLECTOR_MAX_FLIGHTS", "25"))

    supabase = Supabase(supabase_url, service_key)
    flights = supabase.active_flights(limit, args.flight_id)
    if not flights:
        print("No active tracked flights.")
        return 0

    stored, failed = 0, 0
    for flight in flights:
        route = f"{flight['origin']}→{flight['destination']} {flight['outbound_date']}"
        try:
            itineraries = run_fli(flight, currency, fli_bin)
        except subprocess.TimeoutExpired:
            print(f"! {route}: Google Flights timed out", file=sys.stderr)
            failed += 1
            continue
        except subprocess.CalledProcessError as error:
            print(f"! {route}: query failed — {error.stderr[:200]}", file=sys.stderr)
            failed += 1
            continue

        priced = [item for item in itineraries if item.get("price")]
        if not priced:
            print(f"! {route}: no priced itineraries returned", file=sys.stderr)
            failed += 1
            continue

        best = summarise(min(priced, key=lambda item: item["price"]))
        print(
            f"✓ {route}: {best['price']:.2f} {best['currency']} "
            f"· {best['airline']} · {best['aircraft'] or 'aircraft n/a'} "
            f"· {best['duration_minutes']}min · {best['stops']} stop(s)"
        )

        if args.dry_run:
            continue

        supabase.insert_observation(
            {
                "tracked_flight_id": flight["id"],
                "user_id": flight["user_id"],
                "price": round(best["price"], 2),
                "currency": best["currency"],
                "airline": best["airline"],
                "booking_url": google_flights_url(
                    flight["origin"],
                    flight["destination"],
                    flight["outbound_date"],
                    flight.get("return_date"),
                ),
                "source": "google_flights",
            }
        )
        stored += 1

    print(f"\nStored {stored} observation(s), {failed} route(s) failed.")

    if stored and not args.dry_run:
        evaluate(args.flight_id)
    return 0


def evaluate(flight_id: Optional[str]) -> None:
    """Ask the website to run the alert rules over the new observations."""
    site = env("SKYBUDDY_SITE_URL").rstrip("/")
    secret = env("CRON_SECRET")
    if not site or not secret:
        print("SKYBUDDY_SITE_URL or CRON_SECRET not set — skipping alert evaluation.")
        return

    payload: dict[str, Any] = {}
    if flight_id:
        payload["tracked_flight_id"] = flight_id

    try:
        result = api_request(
            f"{site}/api/evaluate",
            method="POST",
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            payload=payload,
        )
        print(f"Alerts evaluated: {json.dumps(result.get('alerts', 0))} raised.")
    except Exception as error:  # pragma: no cover - network failure should not fail the run
        print(f"! alert evaluation failed: {error}", file=sys.stderr)


def main() -> int:
    """Parse arguments and run the collector."""
    parser = argparse.ArgumentParser(description="Collect Google Flights prices for the SkyBuddy website")
    parser.add_argument("--flight-id", help="Only price this tracked flight")
    parser.add_argument("--dry-run", action="store_true", help="Print prices without storing them")
    return collect(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
