#!/usr/bin/env python3
"""Flight and booking formatters for beautiful output (FlightClaw-style)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class FlightLeg:
    """Single flight leg."""

    airline_code: str
    airline_name: str
    flight_number: str
    aircraft: str = ""
    origin_code: str = ""
    origin_name: str = ""
    departure_time: str = ""
    destination_code: str = ""
    destination_name: str = ""
    arrival_time: str = ""
    duration_minutes: int = 0
    distance_km: int = 0


@dataclass
class BookingItinerary:
    """Complete booking itinerary."""

    booking_reference: str
    confirmation_number: str
    total_price: float
    currency: str = "EUR"
    outbound_legs: list[FlightLeg] = None
    return_legs: list[FlightLeg] = None
    passengers: list[str] = None
    booking_status: str = "confirmed"
    booking_date: str = ""

    def __post_init__(self):
        if self.outbound_legs is None:
            self.outbound_legs = []
        if self.return_legs is None:
            self.return_legs = []
        if self.passengers is None:
            self.passengers = []


class FlightFormatter:
    """Format flight information for display."""

    @staticmethod
    def format_time(iso_datetime: str) -> str:
        """Format ISO datetime to readable format."""
        if not iso_datetime:
            return "N/A"
        try:
            return iso_datetime[:16].replace("T", " ")
        except (ValueError, IndexError):
            return iso_datetime

    @staticmethod
    def format_duration(minutes: int) -> str:
        """Format duration in minutes to readable format."""
        if minutes <= 0:
            return "N/A"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"

    @staticmethod
    def format_leg(leg: FlightLeg) -> str:
        """Format a single flight leg."""
        lines = []

        # Main flight line
        carrier = f"{leg.airline_code}{leg.flight_number}" if leg.flight_number else leg.airline_code
        origin = f"{leg.origin_code}" if leg.origin_code else "?"
        dest = f"{leg.destination_code}" if leg.destination_code else "?"

        dep_time = FlightFormatter.format_time(leg.departure_time)
        arr_time = FlightFormatter.format_time(leg.arrival_time)
        duration = FlightFormatter.format_duration(leg.duration_minutes)

        lines.append(f"  {carrier} | {origin} {dep_time} -> {dest} {arr_time} ({duration})")

        if leg.aircraft:
            lines.append(f"    Aircraft: {leg.aircraft}")

        if leg.distance_km:
            lines.append(f"    Distance: {leg.distance_km:,} km")

        return "\n".join(lines)

    @staticmethod
    def format_itinerary(itinerary: BookingItinerary) -> str:
        """Format complete itinerary."""
        lines = []

        # Header
        lines.append("=" * 100)
        lines.append("FLIGHT BOOKING CONFIRMATION")
        lines.append("=" * 100)
        lines.append("")

        # Booking info
        lines.append("Booking Details:")
        lines.append(f"  Reference: {itinerary.booking_reference}")
        lines.append(f"  Confirmation: {itinerary.confirmation_number}")
        lines.append(f"  Total: {itinerary.currency} {itinerary.total_price:,.2f}")
        lines.append(f"  Status: {itinerary.booking_status.upper()}")
        if itinerary.booking_date:
            lines.append(f"  Booked: {itinerary.booking_date}")
        lines.append("")

        # Passengers
        if itinerary.passengers:
            lines.append("Passengers:")
            for pax in itinerary.passengers:
                lines.append(f"  - {pax}")
            lines.append("")

        # Outbound flights
        if itinerary.outbound_legs:
            lines.append("Outbound Journey:")
            for leg in itinerary.outbound_legs:
                lines.append(FlightFormatter.format_leg(leg))
            lines.append("")

        # Return flights
        if itinerary.return_legs:
            lines.append("Return Journey:")
            for leg in itinerary.return_legs:
                lines.append(FlightFormatter.format_leg(leg))
            lines.append("")

        lines.append("=" * 100)
        return "\n".join(lines)

    @staticmethod
    def format_flight_option(
        airline: str,
        price: float,
        currency: str,
        duration_minutes: int,
        stops: int,
        departure_time: str,
        arrival_time: str,
        origin: str,
        destination: str,
        departure_date: str = "",
    ) -> str:
        """Format a flight search result option."""
        lines = []

        # Price and airline
        lines.append(f"{currency} {price:,.0f} | {airline}")

        # Route and times
        dep_time = FlightFormatter.format_time(departure_time)
        arr_time = FlightFormatter.format_time(arrival_time)
        duration = FlightFormatter.format_duration(duration_minutes)

        lines.append(f"{origin} {dep_time} → {destination} {arr_time}")
        lines.append(f"Duration: {duration} | Stops: {stops}")

        if departure_date:
            lines.append(f"Date: {departure_date}")

        return " | ".join(lines)

    @staticmethod
    def format_search_results(
        results: list[dict],
        origin: str,
        destination: str,
        currency: str = "EUR",
        max_results: int = 10,
    ) -> str:
        """Format flight search results as a table."""
        if not results:
            return "No flights found."

        lines = []
        lines.append("=" * 130)
        lines.append(f"FLIGHT SEARCH RESULTS - {origin} to {destination}")
        lines.append("=" * 130)
        lines.append("")
        lines.append(
            f"{'Price':<12} {'Airline':<20} {'Duration':<15} {'Stops':<8} "
            f"{'Departure':<20} {'Arrival':<20}"
        )
        lines.append("-" * 130)

        for i, flight in enumerate(results[:max_results], 1):
            price_str = f"{currency} {flight.get('price', 0):,.0f}"
            airline = flight.get("airline", "N/A")[:18]
            duration = FlightFormatter.format_duration(flight.get("duration", 0))
            stops = str(flight.get("stops", 0))

            dep_time = FlightFormatter.format_time(flight.get("departure_time", ""))
            arr_time = FlightFormatter.format_time(flight.get("arrival_time", ""))

            lines.append(
                f"{price_str:<12} {airline:<20} {duration:<15} {stops:<8} "
                f"{dep_time:<20} {arr_time:<20}"
            )

        lines.append("=" * 130)
        return "\n".join(lines)

    @staticmethod
    def print_flight_deals(
        flights: list[dict],
        median_price: float,
        currency: str = "EUR",
    ) -> None:
        """Print flight deals comparison."""
        if not flights:
            print("No flights to display.")
            return

        print("\n" + "=" * 120)
        print("FLIGHT DEALS & ANALYSIS")
        print(f"Historical Median: {currency} {median_price:,.0f}")
        print("=" * 120)
        print("")

        # Calculate thresholds
        threshold_10 = median_price * 0.90
        threshold_15 = median_price * 0.85

        deals_found = False

        for flight in sorted(flights, key=lambda f: f.get("price", 0)):
            price = flight.get("price", 0)

            # Determine deal level
            if price <= threshold_15:
                label = "*** GREAT DEAL"
                deals_found = True
            elif price <= threshold_10:
                label = "** GOOD DEAL"
                deals_found = True
            else:
                label = "   Regular"

            discount = ((median_price - price) / median_price * 100) if median_price > 0 else 0

            airline = flight.get("airline", "N/A")
            duration = FlightFormatter.format_duration(flight.get("duration", 0))
            stops = flight.get("stops", 0)

            print(
                f"{label} | {currency} {price:>7,.0f} ({discount:>+5.0f}%) "
                f"| {airline:<20} | {duration} | {stops} stops"
            )

        print("=" * 120)

        if not deals_found:
            print(
                f"No deals currently available (10%+ below median of {currency} {median_price:,.0f})"
            )

        print("")


def get_formatter() -> FlightFormatter:
    """Get formatter singleton."""
    return FlightFormatter()
