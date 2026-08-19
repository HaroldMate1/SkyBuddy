#!/usr/bin/env python3
"""Agent booking trigger for SkyBuddy.

Turns a chosen flight (and its booking link) into a *booking intent*: a stored,
auditable object that an agent can execute step by step.

Design rules:

1. Nothing is executed on creation. An intent starts as ``awaiting_confirmation``.
2. A human (or an explicitly authorised caller) must confirm the intent by id.
3. The agreed price ceiling is re-checked at confirmation time.
4. The playbook always stops before payment unless payment authority was granted
   explicitly for that single intent.

Usage (CLI)::

    python scripts/booking_agent.py prepare --booking-url "https://..." \
        --airline Iberia --origin BIO --destination BOG \
        --outbound-date 2026-12-04 --return-date 2027-01-08 \
        --price 684 --currency EUR --passenger harold --max-price 700
    python scripts/booking_agent.py confirm --intent-id bk_7f3a1c --approved-by harold
    python scripts/booking_agent.py playbook --intent-id bk_7f3a1c
    python scripts/booking_agent.py list
    python scripts/booking_agent.py cancel --intent-id bk_7f3a1c --reason "found cheaper"
"""
from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from passenger_profiles import PassengerManager, get_passenger_manager
from seat_advisor import build_seat_advisory
from users import get_workspace

ROOT = Path(__file__).resolve().parents[1]
BOOKINGS_FILE = ROOT / "data" / "bookings.json"

# Status lifecycle
AWAITING = "awaiting_confirmation"
READY = "ready_to_execute"
IN_PROGRESS = "in_progress"
BOOKED = "booked"
CANCELLED = "cancelled"
FAILED = "failed"

# Domains SkyBuddy itself generates links for. Anything else is allowed but
# flagged, so the agent (and the human) can see it is unverified.
KNOWN_BOOKING_DOMAINS = (
    "google.com",
    "avianca.com",
    "iberia.com",
    "klm.com",
    "airfrance.com",
    "airfrance.es",
    "kayak.com",
    "skyscanner.net",
    "skyscanner.com",
    "duffel.com",
)


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class BookingIntent:
    """A booking an agent is authorised to carry out on a specific link."""

    intent_id: str
    booking_url: str
    airline: str
    origin: str
    destination: str
    outbound_date: str
    price: float
    currency: str = "EUR"
    return_date: Optional[str] = None
    cabin: str = "economy"
    flight_number: str = ""
    aircraft: str = ""
    duration_minutes: int = 0
    passengers: list[str] = field(default_factory=list)
    max_price: Optional[float] = None
    allow_payment: bool = False
    status: str = AWAITING
    created_at: str = ""
    approved_by: str = ""
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    confirmation_code: str = ""
    amount_paid: Optional[float] = None
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)

    def log(self, event: str, detail: str = "") -> None:
        """Append an audit entry to the intent history."""
        self.history.append({"at": _now(), "event": event, "detail": detail})


class BookingAgent:
    """Create, confirm and hand out booking intents for any agent."""

    def __init__(
        self,
        bookings_file: Path = BOOKINGS_FILE,
        passengers: Optional[PassengerManager] = None,
    ):
        """Initialise the booking agent and load stored intents."""
        self.bookings_file = bookings_file
        self.passengers = passengers or get_passenger_manager()
        self.intents: dict[str, BookingIntent] = self._load()

    # ---------- persistence ----------

    def _load(self) -> dict[str, BookingIntent]:
        """Load stored intents from disk."""
        if not self.bookings_file.exists():
            return {}
        try:
            with open(self.bookings_file, encoding="utf-8") as handle:
                data = json.load(handle)
            return {
                intent_id: BookingIntent(**payload)
                for intent_id, payload in data.get("bookings", {}).items()
            }
        except Exception as error:  # pragma: no cover - defensive
            print(f"Error loading bookings: {error}")
            return {}

    def save(self) -> None:
        """Persist all intents to disk."""
        self.bookings_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _now(),
            "bookings": {
                intent_id: asdict(intent) for intent_id, intent in self.intents.items()
            },
        }
        with open(self.bookings_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    # ---------- validation ----------

    @staticmethod
    def _validate_url(booking_url: str) -> tuple[bool, str, list[str]]:
        """Validate a booking URL and report any warnings."""
        warnings: list[str] = []
        parsed = urlparse(booking_url)

        if parsed.scheme not in ("http", "https"):
            return False, "Booking URL must be an http(s) link.", warnings
        if not parsed.netloc:
            return False, "Booking URL has no host.", warnings
        if parsed.scheme == "http":
            warnings.append("Link is not HTTPS — do not enter payment details on it.")

        host = parsed.netloc.lower().split(":")[0]
        if not any(host == domain or host.endswith("." + domain) for domain in KNOWN_BOOKING_DOMAINS):
            warnings.append(
                f"Host '{host}' is not one of SkyBuddy's known booking sources — verify it manually."
            )
        return True, "", warnings

    def _check_passengers(self, names: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        """Resolve passenger profiles and report missing details."""
        resolved: list[dict[str, Any]] = []
        warnings: list[str] = []

        for name in names:
            profile = self.passengers.get_passenger(name)
            if profile is None:
                warnings.append(
                    f"No passenger profile named '{name}' — the agent will have to ask for their details."
                )
                resolved.append({"name": name, "profile_found": False})
                continue

            missing = [
                field_name
                for field_name in ("given_name", "family_name", "born_on", "passport")
                if not getattr(profile, field_name, "")
            ]
            if missing:
                warnings.append(f"Passenger '{name}' is missing: {', '.join(missing)}.")
            resolved.append(
                {
                    "name": name,
                    "profile_found": True,
                    "given_name": profile.given_name,
                    "family_name": profile.family_name,
                    "born_on": profile.born_on,
                    "passport": profile.passport,
                    "nationality": profile.nationality,
                    "frequent_flyer": profile.frequent_flyer,
                    "missing_fields": missing,
                }
            )
        return resolved, warnings

    # ---------- lifecycle ----------

    def prepare_booking(
        self,
        booking_url: str,
        airline: str,
        origin: str,
        destination: str,
        outbound_date: str,
        price: float,
        currency: str = "EUR",
        return_date: Optional[str] = None,
        cabin: str = "economy",
        passengers: Optional[list[str]] = None,
        max_price: Optional[float] = None,
        allow_payment: bool = False,
        notes: str = "",
        flight_number: str = "",
        aircraft: str = "",
        duration_minutes: int = 0,
    ) -> dict[str, Any]:
        """Create a booking intent for a flight link. Executes nothing.

        Args:
            booking_url: Direct link to the flight/offer to book.
            airline: Operating or marketing airline of the chosen offer.
            origin: Origin IATA code.
            destination: Destination IATA code.
            outbound_date: Outbound date, YYYY-MM-DD.
            price: Price agreed at search time.
            currency: Currency of ``price``.
            return_date: Return date for round trips.
            cabin: Cabin class of the offer.
            passengers: Passenger profile names to travel.
            max_price: Hard ceiling; the intent is refused above it.
            allow_payment: Grant payment authority for this single intent.
            notes: Free-text context stored with the intent.
            flight_number: Marketing flight number, used for the seat advisory.
            aircraft: Aircraft type, used for the seat advisory.
            duration_minutes: Itinerary duration; over 8 hours triggers the
                long-haul seat-map workflow inside the playbook.

        Returns:
            The stored intent, its warnings, and the confirmation instructions.
        """
        valid, error, warnings = self._validate_url(booking_url)
        if not valid:
            return {"status": "error", "error": error}

        if price <= 0:
            return {"status": "error", "error": "Price must be greater than zero."}

        ceiling = max_price if max_price is not None else price
        if price > ceiling:
            return {
                "status": "rejected",
                "error": f"Price {price} {currency} exceeds the ceiling {ceiling} {currency}.",
            }

        passenger_names = passengers or []
        resolved, passenger_warnings = self._check_passengers(passenger_names)
        warnings.extend(passenger_warnings)
        if not passenger_names:
            warnings.append("No passengers attached — the agent cannot fill traveller details.")

        intent = BookingIntent(
            intent_id=f"bk_{uuid.uuid4().hex[:6]}",
            booking_url=booking_url,
            airline=airline,
            origin=origin.upper(),
            destination=destination.upper(),
            outbound_date=outbound_date,
            return_date=return_date,
            price=float(price),
            currency=currency,
            cabin=cabin,
            flight_number=flight_number,
            aircraft=aircraft,
            duration_minutes=int(duration_minutes or 0),
            passengers=passenger_names,
            max_price=float(ceiling),
            allow_payment=bool(allow_payment),
            created_at=_now(),
            notes=notes,
            warnings=warnings,
        )
        intent.log("prepared", f"{origin}->{destination} at {price} {currency}")

        self.intents[intent.intent_id] = intent
        self.save()

        return {
            "status": AWAITING,
            "intent_id": intent.intent_id,
            "intent": asdict(intent),
            "passengers": resolved,
            "warnings": warnings,
            "next_step": (
                f"Ask the traveller to approve, then call "
                f"confirm_booking('{intent.intent_id}', approved_by='<who>')."
            ),
        }

    def confirm_booking(
        self,
        intent_id: str,
        approved_by: str,
        current_price: Optional[float] = None,
        allow_payment: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Approve an intent and release the agent playbook.

        Args:
            intent_id: Intent to approve.
            approved_by: Who approved it — stored in the audit trail.
            current_price: Live price re-checked against the ceiling, if known.
            allow_payment: Override the payment authority for this intent.

        Returns:
            The approved intent plus its execution playbook, or an error.
        """
        intent = self.intents.get(intent_id)
        if intent is None:
            return {"status": "error", "error": f"Unknown intent: {intent_id}"}
        if intent.status not in (AWAITING, READY):
            return {"status": "error", "error": f"Intent {intent_id} is '{intent.status}'."}
        if not approved_by:
            return {"status": "error", "error": "approved_by is required — bookings need an owner."}

        if current_price is not None:
            if intent.max_price is not None and current_price > intent.max_price:
                intent.status = AWAITING
                intent.log("price_check_failed", f"{current_price} > ceiling {intent.max_price}")
                self.save()
                return {
                    "status": "rejected",
                    "error": (
                        f"Live price {current_price} {intent.currency} is above the ceiling "
                        f"{intent.max_price} {intent.currency}. Confirmation refused."
                    ),
                    "intent_id": intent_id,
                }
            intent.price = float(current_price)
            intent.log("price_rechecked", f"{current_price} {intent.currency}")

        if allow_payment is not None:
            intent.allow_payment = bool(allow_payment)

        intent.status = READY
        intent.approved_by = approved_by
        intent.approved_at = _now()
        intent.log("confirmed", f"approved by {approved_by}")
        self.save()

        return {
            "status": READY,
            "intent_id": intent_id,
            "intent": asdict(intent),
            "agent_playbook": self.build_playbook(intent),
        }

    def build_playbook(self, intent: BookingIntent) -> dict[str, Any]:
        """Build the ordered instructions an agent follows on the booking link."""
        resolved, _ = self._check_passengers(intent.passengers)
        trip = f"{intent.origin} → {intent.destination}"
        dates = intent.outbound_date + (f" / {intent.return_date}" if intent.return_date else "")

        steps: list[dict[str, str]] = [
            {
                "step": "open_link",
                "action": f"Open the booking URL: {intent.booking_url}",
                "check": "The page loads on the airline or aggregator site, not a redirect elsewhere.",
            },
            {
                "step": "verify_itinerary",
                "action": f"Confirm the offer shows {trip} on {dates}, {intent.cabin} class, {intent.airline}.",
                "check": "Abort if route, dates, cabin or carrier differ from the intent.",
            },
            {
                "step": "verify_price",
                "action": (
                    f"Confirm the total is at or below {intent.max_price} {intent.currency} "
                    f"(agreed {intent.price} {intent.currency}), including taxes and baggage."
                ),
                "check": "Abort and report back if the total is above the ceiling.",
            },
            {
                "step": "fill_passengers",
                "action": (
                    "Fill traveller details from the stored profiles: "
                    + (", ".join(p["name"] for p in resolved) if resolved else "none attached")
                ),
                "check": "Names must match passports exactly; ask the human for anything missing.",
            },
            {
                "step": "select_extras",
                "action": "Apply the agreed baggage and seat choices only; decline upsells not in the intent.",
                "check": "Any added cost must keep the total under the ceiling.",
            },
        ]

        seat_advisory = build_seat_advisory(
            airline=intent.airline,
            aircraft=intent.aircraft,
            flight_number=intent.flight_number,
            duration_minutes=intent.duration_minutes,
            cabin=intent.cabin,
        )
        if seat_advisory.get("is_long_haul"):
            sources = seat_advisory["seat_map_sources"] + seat_advisory["cross_check_sources"]
            steps.insert(
                len(steps) - 1,
                {
                    "step": "check_seats",
                    "action": (
                        "Long-haul itinerary: confirm the aircraft on FlightAware, then inspect the "
                        "cabin map before picking seats — "
                        + "; ".join(
                            f"{source['name']}: {source['url'] or source.get('query', '')}"
                            for source in sources
                        )
                    ),
                    "check": seat_advisory["configuration_warning"],
                },
            )

        if intent.allow_payment:
            steps.append(
                {
                    "step": "pay",
                    "action": "Payment authority was granted for this intent — complete the purchase.",
                    "check": "Stop immediately if the final total differs from the verified one.",
                }
            )
        else:
            steps.append(
                {
                    "step": "stop_before_payment",
                    "action": (
                        "STOP at the payment page. Report the final total and hand control back "
                        "to the human to enter payment details."
                    ),
                    "check": "Never enter card details without explicit payment authority.",
                }
            )

        steps.append(
            {
                "step": "record_result",
                "action": (
                    f"After booking, call mark_executed('{intent.intent_id}', "
                    "confirmation_code=..., amount_paid=...)."
                ),
                "check": "Store the airline confirmation code in the audit trail.",
            }
        )

        return {
            "intent_id": intent.intent_id,
            "status": intent.status,
            "booking_url": intent.booking_url,
            "summary": f"{intent.airline} · {trip} · {dates} · {intent.price} {intent.currency}",
            "payment_authority": intent.allow_payment,
            "passengers": resolved,
            "warnings": intent.warnings,
            "seat_advisory": seat_advisory,
            "steps": steps,
            "abort_conditions": [
                "Route, dates, cabin or airline do not match the intent.",
                f"Total above {intent.max_price} {intent.currency}.",
                "The site asks for data no profile covers and no human is available.",
                "The page is not HTTPS or the domain looks unrelated to the airline.",
            ],
        }

    def get_booking_playbook(self, intent_id: str) -> dict[str, Any]:
        """Return the playbook for a confirmed intent."""
        intent = self.intents.get(intent_id)
        if intent is None:
            return {"status": "error", "error": f"Unknown intent: {intent_id}"}
        if intent.status not in (READY, IN_PROGRESS):
            return {
                "status": "error",
                "error": (
                    f"Intent {intent_id} is '{intent.status}'. Confirm it first with "
                    "confirm_booking()."
                ),
            }
        intent.status = IN_PROGRESS
        intent.log("playbook_issued")
        self.save()
        return {"status": IN_PROGRESS, "agent_playbook": self.build_playbook(intent)}

    def mark_executed(
        self,
        intent_id: str,
        confirmation_code: str = "",
        amount_paid: Optional[float] = None,
        success: bool = True,
        detail: str = "",
    ) -> dict[str, Any]:
        """Record the outcome of an executed booking."""
        intent = self.intents.get(intent_id)
        if intent is None:
            return {"status": "error", "error": f"Unknown intent: {intent_id}"}

        intent.status = BOOKED if success else FAILED
        intent.executed_at = _now()
        intent.confirmation_code = confirmation_code
        intent.amount_paid = amount_paid
        intent.log("executed" if success else "failed", detail or confirmation_code)
        self.save()
        return {"status": intent.status, "intent": asdict(intent)}

    def cancel_booking(self, intent_id: str, reason: str = "") -> dict[str, Any]:
        """Cancel an intent before it is executed."""
        intent = self.intents.get(intent_id)
        if intent is None:
            return {"status": "error", "error": f"Unknown intent: {intent_id}"}
        if intent.status == BOOKED:
            return {
                "status": "error",
                "error": "Intent is already booked — cancel with the airline, not with SkyBuddy.",
            }
        intent.status = CANCELLED
        intent.log("cancelled", reason)
        self.save()
        return {"status": CANCELLED, "intent_id": intent_id, "reason": reason}

    def list_bookings(self, status: Optional[str] = None) -> dict[str, Any]:
        """List stored intents, optionally filtered by status."""
        items = [
            asdict(intent)
            for intent in self.intents.values()
            if status is None or intent.status == status
        ]
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"count": len(items), "bookings": items}

    def get_booking(self, intent_id: str) -> dict[str, Any]:
        """Return a single intent by id."""
        intent = self.intents.get(intent_id)
        if intent is None:
            return {"status": "error", "error": f"Unknown intent: {intent_id}"}
        return {"status": intent.status, "intent": asdict(intent)}


def get_booking_agent(user: Optional[str] = None) -> BookingAgent:
    """Return a booking agent bound to a traveller workspace."""
    workspace = get_workspace(user)
    return BookingAgent(
        bookings_file=workspace.bookings_file,
        passengers=PassengerManager(profiles_file=workspace.passengers_file),
    )


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="SkyBuddy agent booking trigger")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", help="Traveller workspace to use (default: the active one)")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser(
        "prepare", parents=[common], help="Create a booking intent from a flight link"
    )
    prepare.add_argument("--booking-url", required=True)
    prepare.add_argument("--airline", required=True)
    prepare.add_argument("--origin", required=True)
    prepare.add_argument("--destination", required=True)
    prepare.add_argument("--outbound-date", required=True)
    prepare.add_argument("--return-date")
    prepare.add_argument("--price", type=float, required=True)
    prepare.add_argument("--currency", default="EUR")
    prepare.add_argument("--cabin", default="economy")
    prepare.add_argument("--passenger", action="append", default=[], dest="passengers")
    prepare.add_argument("--max-price", type=float)
    prepare.add_argument(
        "--allow-payment",
        action="store_true",
        help="Grant payment authority for this intent (off by default)",
    )
    prepare.add_argument("--notes", default="")
    prepare.add_argument("--flight-number", default="")
    prepare.add_argument("--aircraft", default="")
    prepare.add_argument(
        "--duration-minutes",
        type=int,
        default=0,
        help="Itinerary duration; over 480 adds the long-haul seat workflow to the playbook",
    )

    confirm = sub.add_parser("confirm", parents=[common], help="Approve an intent and release the playbook")
    confirm.add_argument("--intent-id", required=True)
    confirm.add_argument("--approved-by", required=True)
    confirm.add_argument("--current-price", type=float)
    confirm.add_argument("--allow-payment", dest="allow_payment", action="store_true", default=None)

    playbook = sub.add_parser("playbook", parents=[common], help="Print the agent playbook for a confirmed intent")
    playbook.add_argument("--intent-id", required=True)

    executed = sub.add_parser("executed", parents=[common], help="Record the outcome of a booking")
    executed.add_argument("--intent-id", required=True)
    executed.add_argument("--confirmation-code", default="")
    executed.add_argument("--amount-paid", type=float)
    executed.add_argument("--failed", action="store_true")
    executed.add_argument("--detail", default="")

    cancel = sub.add_parser("cancel", parents=[common], help="Cancel an intent before execution")
    cancel.add_argument("--intent-id", required=True)
    cancel.add_argument("--reason", default="")

    listing = sub.add_parser("list", parents=[common], help="List stored booking intents")
    listing.add_argument("--status")

    show = sub.add_parser("show", parents=[common], help="Show a single intent")
    show.add_argument("--intent-id", required=True)

    return parser


def main() -> int:
    """Run the booking CLI."""
    args = build_parser().parse_args()
    agent = get_booking_agent(getattr(args, "user", None))

    if args.command == "prepare":
        result = agent.prepare_booking(
            booking_url=args.booking_url,
            airline=args.airline,
            origin=args.origin,
            destination=args.destination,
            outbound_date=args.outbound_date,
            return_date=args.return_date,
            price=args.price,
            currency=args.currency,
            cabin=args.cabin,
            passengers=args.passengers,
            max_price=args.max_price,
            allow_payment=args.allow_payment,
            notes=args.notes,
            flight_number=args.flight_number,
            aircraft=args.aircraft,
            duration_minutes=args.duration_minutes,
        )
    elif args.command == "confirm":
        result = agent.confirm_booking(
            intent_id=args.intent_id,
            approved_by=args.approved_by,
            current_price=args.current_price,
            allow_payment=args.allow_payment,
        )
    elif args.command == "playbook":
        result = agent.get_booking_playbook(args.intent_id)
    elif args.command == "executed":
        result = agent.mark_executed(
            intent_id=args.intent_id,
            confirmation_code=args.confirmation_code,
            amount_paid=args.amount_paid,
            success=not args.failed,
            detail=args.detail,
        )
    elif args.command == "cancel":
        result = agent.cancel_booking(args.intent_id, args.reason)
    elif args.command == "list":
        result = agent.list_bookings(args.status)
    else:
        result = agent.get_booking(args.intent_id)

    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
