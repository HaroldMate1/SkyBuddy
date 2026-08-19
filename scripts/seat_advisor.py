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


def seatguru_url() -> str:
    """Return the SeatGuru entry point for annotated seat maps."""
    return "https://www.seatguru.com/"


def aerolopa_url() -> str:
    """Return the aeroLOPA entry point for airline-specific cabin diagrams."""
    return "https://www.aerolopa.com/"


def expertflyer_url() -> str:
    """Return the ExpertFlyer entry point for seat-availability alerts."""
    return "https://www.expertflyer.com/"


def flightradar24_url(flight_number: str = "") -> str:
    """Return a Flightradar24 link for the flight, or its data home page."""
    slug = _flightaware_slug(flight_number).lower()
    if slug:
        return f"https://www.flightradar24.com/data/flights/{slug}"
    return "https://www.flightradar24.com/data/flights"


def cross_check_sources(airline: str, aircraft: str = "", flight_number: str = "", cabin: str = "") -> list[dict[str, str]]:
    """Return the secondary seat-research websites, with the query to run on each.

    These complement — never replace — the FlightAware → SeatMaps workflow. Each
    entry carries the site entry point and the exact search string to type there,
    so an agent never has to guess a URL scheme that may have changed.
    """
    airline = _clean(airline)
    aircraft = _clean(aircraft)
    cabin = _clean(cabin) or "economy"
    flight_number = _clean(flight_number)

    return [
        {
            "name": "SeatGuru",
            "url": seatguru_url(),
            "query": " ".join(part for part in (airline, aircraft, "seat map") if part),
            "role": "cross-check",
            "why": "Colour-coded good/bad seat annotations and traveller notes per aircraft version.",
        },
        {
            "name": "aeroLOPA",
            "url": aerolopa_url(),
            "query": " ".join(part for part in (airline, aircraft) if part),
            "role": "cross-check",
            "why": "High-accuracy, airline-specific cabin diagrams drawn from real layout-of-passenger-accommodation data.",
        },
        {
            "name": "ExpertFlyer",
            "url": expertflyer_url(),
            "query": " ".join(part for part in (flight_number or airline, aircraft, cabin) if part),
            "role": "availability",
            "why": "Live seat availability and alerts when a preferred seat opens up before departure.",
        },
        {
            "name": "Flightradar24",
            "url": flightradar24_url(flight_number),
            "query": flight_number or airline,
            "role": "verify",
            "why": "Second source for the registration and aircraft actually flying the route in recent days.",
        },
        {
            "name": "Airline seat selection",
            "url": "",
            "query": f"{airline} manage my booking seat selection".strip(),
            "role": "act",
            "why": "The only place the seat is actually assigned — apply the choice validated on the maps above.",
        },
    ]


def seat_selection_actions(cabin: str = "economy") -> list[dict[str, str]]:
    """Return the practical steps that turn seat research into an assigned seat."""
    cabin = _clean(cabin).lower() or "economy"
    actions = [
        {
            "when": "at_booking",
            "action": "Check whether seat selection is included in the fare before paying for it separately.",
            "note": "Basic/light fares often charge; some cards, status tiers or corporate fares waive the fee.",
        },
        {
            "when": "at_booking",
            "action": "Apply the seat validated on the cabin map through the airline's own seat-selection page.",
            "note": "Confirm the seat number appears on the itinerary before leaving the booking flow.",
        },
        {
            "when": "after_booking",
            "action": "Re-check the seat map a few days before departure for aircraft swaps.",
            "note": "A swap silently reassigns seats; the same number can be a different position on the new layout.",
        },
        {
            "when": "check_in",
            "action": "Re-open the map at the 24-48h check-in window when blocked seats are released.",
            "note": "Exit rows and bulkheads frequently free up at check-in at no cost.",
        },
    ]
    if "business" in cabin or "first" in cabin:
        actions.append(
            {
                "when": "at_booking",
                "action": "Verify direct aisle access, seat direction and privacy doors for the exact cabin version.",
                "note": "Premium cabins vary the most between sub-fleets of the same aircraft model.",
            }
        )
    return actions


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
            "cross_check_sources": [],
            "flightaware_query": "",
            "seatmaps_query": "",
            "selection_tips": [],
            "seat_selection_actions": seat_selection_actions(cabin),
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
        "cross_check_sources": cross_check_sources(airline, aircraft, flight_number, cabin),
        "flightaware_query": flightaware_query(airline, flight_number),
        "seatmaps_query": seatmaps_query(airline, aircraft, cabin),
        "selection_tips": selection_tips(cabin),
        "seat_selection_actions": seat_selection_actions(cabin),
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
