"""POST /api/search-flights — real Google Flights fares for the search box.

Duffel's test inventory is invented, so the site searched with fake prices while
the tracked routes carried real ones. This endpoint closes that gap: it runs the
same Google Flights client the collector uses, synchronously, for signed-in
travellers.

Kept in Python because the client is a Python library; the Node endpoints handle
everything else.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from typing import Any

MAX_OFFERS = 12
DATE_FORMAT = "%Y-%m-%d"


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    """Write one JSON response."""
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def verify_user(token: str) -> dict[str, Any] | None:
    """Resolve the Supabase user behind an access token."""
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY") or ""
    if not url or not anon or not token:
        return None

    request = urllib.request.Request(
        f"{url}/auth/v1/user",
        headers={"apikey": anon, "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            user = json.loads(response.read().decode("utf-8"))
            return user if user.get("id") else None
    except Exception:
        return None


def valid_date(value: str) -> bool:
    """Is this a usable YYYY-MM-DD date?"""
    try:
        datetime.strptime(value, DATE_FORMAT)
        return True
    except (TypeError, ValueError):
        return False


def google_flights_url(origin: str, destination: str, outbound: str, return_date: str | None) -> str:
    """The bookable link SkyBuddy shows for a Google Flights result."""
    query = f"Flights from {origin} to {destination} on {outbound}"
    if return_date:
        query += f" through {return_date}"
    return "https://www.google.com/travel/flights?q=" + urllib.parse.quote(query)


def leg_dict(leg: Any) -> dict[str, Any]:
    """Flatten one leg of an itinerary."""
    airline = getattr(leg, "airline", None)
    return {
        "airline_code": getattr(airline, "name", "") if airline is not None else "",
        "airline_name": getattr(airline, "value", None) or str(airline or ""),
        "flight_number": getattr(leg, "flight_number", "") or "",
        "aircraft": getattr(leg, "aircraft", "") or "",
        "duration": getattr(leg, "duration", 0) or 0,
        "departure": getattr(leg, "departure_datetime", None),
        "arrival": getattr(leg, "arrival_datetime", None),
    }


def summarise(result: Any, context: dict[str, str]) -> dict[str, Any]:
    """Reduce one itinerary to the shape the dashboard renders.

    Round trips arrive as a tuple of two results; only the outbound decides the
    times, duration and stops shown on the card, because that is the direction
    whose cabin the traveller is choosing.
    """
    outbound = result[0] if isinstance(result, tuple) else result
    every = list(result) if isinstance(result, tuple) else [result]

    legs: list[dict[str, Any]] = []
    for part in every:
        legs.extend(leg_dict(leg) for leg in (getattr(part, "legs", None) or []))

    outbound_legs = [leg_dict(leg) for leg in (getattr(outbound, "legs", None) or [])]
    longest = max(legs, key=lambda leg: leg["duration"], default={})

    carriers: list[str] = []
    numbers: list[str] = []
    for leg in sorted(legs, key=lambda leg: leg is not longest):
        name = leg["airline_name"]
        if name and name not in carriers:
            carriers.append(name)
        if leg["flight_number"]:
            numbers.append(f"{leg['airline_code']} {leg['flight_number']}".strip())

    first = outbound_legs[0] if outbound_legs else {}
    last = outbound_legs[-1] if outbound_legs else {}

    return {
        "offer_id": (getattr(outbound, "booking_token", "") or "")[:40]
        or f"{context['origin']}{context['destination']}{len(legs)}",
        "airline": " + ".join(carriers) or "Unknown",
        "airline_code": (longest.get("airline_code") or "")[:2],
        "flight_number": ", ".join(numbers),
        "aircraft": longest.get("aircraft") or "",
        "price": float(getattr(outbound, "price", 0) or 0),
        "currency": getattr(outbound, "currency", None) or context["currency"],
        "duration_minutes": int(getattr(outbound, "duration", 0) or 0),
        "stops": int(getattr(outbound, "stops", 0) or 0),
        "departure_time": first.get("departure").isoformat() if first.get("departure") else None,
        "arrival_time": last.get("arrival").isoformat() if last.get("arrival") else None,
        "origin": context["origin"],
        "destination": context["destination"],
        "booking_url": google_flights_url(
            context["origin"], context["destination"], context["outbound_date"], context["return_date"]
        ),
    }


def run_search(body: dict[str, Any]) -> dict[str, Any]:
    """Search Google Flights and return normalised offers."""
    # Imported here so a dependency problem surfaces as a clean 502 rather than
    # a cold-start crash with no explanation.
    from fli.core import build_flight_segments, parse_cabin_class, parse_max_stops, parse_sort_by, resolve_airport
    from fli.models import FlightSearchFilters, PassengerInfo
    from fli.search import SearchFlights

    origin = str(body.get("origin", "")).upper()
    destination = str(body.get("destination", "")).upper()
    outbound_date = str(body.get("outbound_date", ""))
    return_date = body.get("return_date") or None
    currency = str(body.get("currency") or "EUR").upper()
    cabin = str(body.get("cabin") or "economy")

    segments, trip_type = build_flight_segments(
        origin=resolve_airport(origin),
        destination=resolve_airport(destination),
        departure_date=outbound_date,
        return_date=return_date,
    )

    filters = FlightSearchFilters(
        trip_type=trip_type,
        passenger_info=PassengerInfo(adults=max(1, min(int(body.get("passengers") or 1), 9))),
        flight_segments=segments,
        stops=parse_max_stops("ANY"),
        seat_type=parse_cabin_class(cabin.upper().replace(" ", "_")),
        sort_by=parse_sort_by("CHEAPEST"),
    )

    results = SearchFlights().search(filters, currency=currency) or []
    context = {
        "origin": origin,
        "destination": destination,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "currency": currency,
    }

    offers = [summarise(result, context) for result in results]
    offers = [offer for offer in offers if offer["price"] > 0]
    offers.sort(key=lambda offer: offer["price"])

    return {
        "origin": origin,
        "destination": destination,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "source": "google_flights",
        "sandbox": False,
        "count": len(offers),
        "offers": offers[:MAX_OFFERS],
    }


class handler(BaseHTTPRequestHandler):
    """Vercel Python entry point."""

    def do_POST(self) -> None:  # noqa: N802 - name fixed by the runtime
        """Search Google Flights for a signed-in traveller."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, TypeError):
            return _json(self, 400, {"error": "Body must be JSON."})

        auth = self.headers.get("Authorization") or ""
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if not verify_user(token):
            return _json(self, 401, {"error": "Sign in to run a search."})

        origin = str(body.get("origin", "")).upper()
        destination = str(body.get("destination", "")).upper()
        if len(origin) != 3 or len(destination) != 3 or origin == destination:
            return _json(self, 400, {"error": "Origin and destination must be different IATA codes."})
        if not valid_date(str(body.get("outbound_date", ""))):
            return _json(self, 400, {"error": "outbound_date must be YYYY-MM-DD."})
        if body.get("return_date") and not valid_date(str(body["return_date"])):
            return _json(self, 400, {"error": "return_date must be YYYY-MM-DD."})

        try:
            return _json(self, 200, run_search(body))
        except Exception as error:  # the scraper is unofficial; fail legibly
            return _json(self, 502, {"error": f"Google Flights search failed: {error}"})
