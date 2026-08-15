#!/usr/bin/env python3
"""Long-haul seat intelligence helpers for SkyBuddy.

Workflow extracted from the referenced reel:
1. Use FlightAware to confirm the exact operating flight and aircraft type.
2. Use SeatMaps to inspect the airline-specific aircraft cabin map.

The module deliberately does not claim a best seat from aircraft type alone.
Airlines can operate several cabin configurations on the same aircraft model,
so every advisory preserves a fail-closed warning about configuration matching.
"""
from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.parse import quote_plus

LONG_HAUL_THRESHOLD_MINUTES = 8 * 60


def _clean(value: str | None) -> str:
    return " ".join(value.split()) if value else ""


def _flightaware_slug(flight_number: str) -> str:
    return "".join(ch for ch in _clean(flight_number).upper() if ch.isalnum())


def flightaware_query(airline: str, flight_number: str = "") -> str:
    flight_number = _clean(flight_number)
    airline = _clean(airline)
    if flight_number:
        return f"{flight_number} {airline} FlightAware aircraft details".strip()
    return f"{airline} FlightAware aircraft details".strip()


def seatmaps_query(airline: str, aircraft: str = "", cabin: str = "") -> str:
    parts = [_clean(airline), _clean(aircraft), _clean(cabin), "seat map"]
    return " ".join(part for part in parts if part)


def flightaware_url(airline: str, flight_number: str = "") -> str:
    slug = _flightaware_slug(flight_number)
    if slug:
        return f"https://www.flightaware.com/live/flight/{slug}"
    return f"https://www.flightaware.com/live/findflight?query={quote_plus(_clean(airline))}"


def seatmaps_url(airline: str, aircraft: str = "", cabin: str = "") -> str:
    return f"https://seatmaps.com/search/?q={quote_plus(seatmaps_query(airline, aircraft, cabin))}"


def seat_map_sources(airline: str, aircraft: str = "", flight_number: str = "", cabin: str = "") -> list[dict[str, str]]:
    """Return the two websites shown in the reel, in workflow order."""
    return [
        {
            "name": "FlightAware",
            "url": flightaware_url(airline, flight_number),
            "why": "Confirm the exact operating flight, aircraft type/subtype, route and timing before looking up a seat map.",
        },
        {
            "name": "SeatMaps",
            "url": seatmaps_url(airline, aircraft, cabin),
            "why": "Inspect the airline-specific aircraft cabin map for seat pitch, width, recline, lavatories, galleys and exit rows.",
        },
    ]


def workflow_steps(airline: str, aircraft: str = "", flight_number: str = "", cabin: str = "") -> list[dict[str, str]]:
    return [
        {
            "step": "confirm_aircraft",
            "source": "FlightAware",
            "url": flightaware_url(airline, flight_number),
            "query": flightaware_query(airline, flight_number),
            "instruction": "Open the flight page and confirm aircraft details for the exact operating flight.",
        },
        {
            "step": "inspect_seat_map",
            "source": "SeatMaps",
            "url": seatmaps_url(airline, aircraft, cabin),
            "query": seatmaps_query(airline, aircraft, cabin),
            "instruction": "Search the confirmed airline and aircraft, then inspect the cabin map before choosing seats.",
        },
    ]


def selection_tips(cabin: str = "economy") -> list[str]:
    cabin = _clean(cabin).lower() or "economy"
    tips = [
        "Verify the exact operating airline, aircraft subtype and cabin layout before choosing; the same aircraft model can have different configurations.",
        "Prefer seats away from lavatory and galley clusters for overnight sectors unless quick aisle access matters more than quiet.",
        "Check exit row restrictions and trade-offs: more legroom can mean narrower seats, fixed armrests, no under-seat bag, or colder cabin areas.",
        "Treat bulkhead rows carefully: extra knee room may come with bassinet positions, fixed screens, or no floor storage during taxi, take-off and landing.",
        "For sleep, window seats reduce interruptions; for hydration and movement, aisle seats are usually kinder on flights over 8 hours.",
    ]
    if "business" in cabin or "first" in cabin:
        tips.append("Confirm whether the advertised premium cabin has direct aisle access, door/privacy differences, and paired honeymoon seats.")
    else:
        tips.append("In economy, compare seat pitch, width, recline limitations and missing-window rows before accepting the cheapest assigned seat.")
    return tips


def build_seat_advisory(
    *,
    airline: str,
    duration_minutes: int | float,
    aircraft: str | None = None,
    flight_number: str | None = None,
    cabin: str | None = None,
) -> dict[str, Any]:
    airline = _clean(airline) or "Unknown airline"
    aircraft = _clean(aircraft)
    flight_number = _clean(flight_number)
    cabin = _clean(cabin) or "economy"
    duration = int(duration_minutes)
    is_long_haul = duration >= LONG_HAUL_THRESHOLD_MINUTES

    if not is_long_haul:
        return {
            "is_long_haul": False,
            "priority": "normal",
            "threshold_minutes": LONG_HAUL_THRESHOLD_MINUTES,
            "summary": f"Seat-map advisory is lightweight because this itinerary is under 8 hours ({duration} minutes).",
            "configuration_warning": "Still verify unusual aircraft swaps or tight personal preferences before paying for a seat.",
            "workflow_steps": [],
            "seat_map_sources": [],
            "flightaware_query": "",
            "seatmaps_query": "",
            "selection_tips": [],
        }

    if aircraft:
        warning = (
            "Verify the exact airline seat map and operating configuration before choosing a seat; "
            "aircraft model alone is not enough."
        )
    else:
        warning = (
            "The aircraft type is missing, so SkyBuddy cannot infer cabin layout. Use FlightAware to verify the aircraft type before selecting seats."
        )

    return {
        "is_long_haul": True,
        "priority": "high",
        "threshold_minutes": LONG_HAUL_THRESHOLD_MINUTES,
        "summary": f"Long-haul seat check recommended for a {duration}-minute itinerary.",
        "configuration_warning": warning,
        "workflow_steps": workflow_steps(airline, aircraft, flight_number, cabin),
        "seat_map_sources": seat_map_sources(airline, aircraft, flight_number, cabin),
        "flightaware_query": flightaware_query(airline, flight_number),
        "seatmaps_query": seatmaps_query(airline, aircraft, cabin),
        "selection_tips": selection_tips(cabin),
    }


def cli_payload(
    *,
    airline: str,
    duration_minutes: int,
    aircraft: str | None = None,
    flight_number: str | None = None,
    cabin: str | None = None,
) -> dict[str, Any]:
    return {
        "airline": _clean(airline) or "Unknown airline",
        "aircraft": _clean(aircraft) or None,
        "flight_number": _clean(flight_number) or None,
        "duration_minutes": int(duration_minutes),
        "cabin": _clean(cabin) or "economy",
        "seat_advisory": build_seat_advisory(
            airline=airline,
            aircraft=aircraft,
            flight_number=flight_number,
            duration_minutes=duration_minutes,
            cabin=cabin,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a FlightAware → SeatMaps advisory for a long-haul SkyBuddy itinerary.")
    parser.add_argument("--airline", required=True)
    parser.add_argument("--duration-minutes", type=int, required=True)
    parser.add_argument("--aircraft")
    parser.add_argument("--flight-number")
    parser.add_argument("--cabin", default="economy")
    args = parser.parse_args()
    print(json.dumps(cli_payload(**vars(args)), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
