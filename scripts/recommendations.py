#!/usr/bin/env python3
"""AI-powered flight recommendations based on user preferences."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional

from preferences import PreferencesManager, get_preferences_manager


@dataclass
class FlightRecommendation:
    """A recommended flight with scoring."""

    airline: str
    price: float
    currency: str
    duration_minutes: int
    stops: int
    departure_time: str
    arrival_time: str
    booking_url: str
    score: float
    reasons: list[str]


class RecommendationEngine:
    """Score and rank flights based on preferences."""

    def __init__(self, preferences: Optional[PreferencesManager] = None):
        """Initialize recommendation engine."""
        self.prefs = preferences or get_preferences_manager()

    def score_flight(
        self,
        airline: str,
        price: float,
        duration_minutes: int,
        stops: int,
        departure_hour: int,
        price_median: float,
    ) -> tuple[float, list[str]]:
        """Score a flight and return (score, reasons).

        Score factors:
        - Budget sensitivity (price)
        - Duration preferences
        - Stop preferences
        - Departure time preferences
        - Airline preferences
        """
        score = 0.0
        reasons = []

        prefs = self.prefs.preferences

        # Price scoring (normalized against median)
        price_ratio = price / max(price_median, 1)
        if price_ratio < 0.85:
            price_score = 1.0
            reasons.append(f"Excellent price ({price_ratio*100:.0f}% of median)")
        elif price_ratio < 0.95:
            price_score = 0.8
            reasons.append(f"Good price ({price_ratio*100:.0f}% of median)")
        elif price_ratio < 1.05:
            price_score = 0.6
            reasons.append("Fair price")
        else:
            price_score = max(0.1, 1.0 - (price_ratio - 1.0))
            reasons.append(f"Above market price ({price_ratio*100:.0f}% of median)")

        score += price_score * 0.4  # 40% weight

        # Duration scoring
        duration_hours = duration_minutes / 60
        if duration_hours < 8:
            duration_score = 1.0
            reasons.append(f"Short flight ({duration_hours:.1f}h)")
        elif duration_hours < 12:
            duration_score = 0.8
            reasons.append(f"Reasonable duration ({duration_hours:.1f}h)")
        elif duration_hours < 16:
            duration_score = 0.6
            reasons.append(f"Long flight ({duration_hours:.1f}h)")
        else:
            duration_score = 0.3
            reasons.append(f"Very long flight ({duration_hours:.1f}h)")

        if duration_hours > prefs.max_flight_duration_hours:
            duration_score *= 0.5
            reasons.append(f"Exceeds preferred max ({prefs.max_flight_duration_hours}h)")

        score += duration_score * 0.3  # 30% weight

        # Stops scoring
        if stops == 0:
            stops_score = 1.0
            reasons.append("Non-stop")
        elif stops == 1:
            stops_score = 0.8
            reasons.append("1 stop")
        elif stops <= prefs.max_stops:
            stops_score = 0.6 - (stops - 2) * 0.1
            reasons.append(f"{stops} stops")
        else:
            stops_score = 0.2
            reasons.append(f"{stops} stops (exceeds preference)")

        score += stops_score * 0.2  # 20% weight

        # Departure time preferences
        preferred_time = prefs.preferred_departure_time.lower()
        if preferred_time == "morning" and 5 <= departure_hour < 12:
            score += 0.1
            reasons.append("Preferred morning departure")
        elif preferred_time == "afternoon" and 12 <= departure_hour < 18:
            score += 0.1
            reasons.append("Preferred afternoon departure")
        elif preferred_time == "evening" and 17 <= departure_hour <= 23:
            score += 0.1
            reasons.append("Preferred evening departure")

        # Airline preferences
        if prefs.preferences.preferred_airlines and airline.upper() in [a.upper() for a in prefs.preferences.preferred_airlines]:
            score += 0.15
            reasons.append(f"Preferred airline ({airline})")

        if prefs.preferences.avoided_airlines and airline.upper() in [a.upper() for a in prefs.preferences.avoided_airlines]:
            score *= 0.5
            reasons.append(f"Avoided airline ({airline})")

        # Normalize score to 0-100
        final_score = min(100, max(0, score * 100))

        return final_score, reasons

    def recommend_flights(
        self,
        flights: list[dict],
        price_median: Optional[float] = None,
    ) -> list[FlightRecommendation]:
        """Score and rank flights, return top recommendations.

        Args:
            flights: List of flight dicts with price, duration, stops, etc.
            price_median: Median price for normalization (calculated if not provided)

        Returns:
            Sorted list of FlightRecommendation objects
        """
        if not flights:
            return []

        # Calculate median if not provided
        if price_median is None:
            prices = [f.get("price", 0) for f in flights if f.get("price")]
            price_median = statistics.median(prices) if prices else 1000

        recommendations = []

        for flight in flights:
            # Skip incomplete flights
            if not all(
                flight.get(key)
                for key in ["airline", "price", "duration", "stops", "departure_time", "booking_url"]
            ):
                continue

            # Extract departure hour
            try:
                dep_hour = int(flight["departure_time"].split("T")[1].split(":")[0])
            except (ValueError, IndexError):
                dep_hour = 12

            # Score flight
            score, reasons = self.score_flight(
                airline=flight["airline"],
                price=float(flight["price"]),
                duration_minutes=int(flight["duration"]),
                stops=int(flight["stops"]),
                departure_hour=dep_hour,
                price_median=price_median,
            )

            recommendation = FlightRecommendation(
                airline=flight["airline"],
                price=float(flight["price"]),
                currency=flight.get("currency", "EUR"),
                duration_minutes=int(flight["duration"]),
                stops=int(flight["stops"]),
                departure_time=flight["departure_time"],
                arrival_time=flight.get("arrival_time", ""),
                booking_url=flight["booking_url"],
                score=score,
                reasons=reasons,
            )

            recommendations.append(recommendation)

        # Sort by score (highest first)
        return sorted(recommendations, key=lambda x: x.score, reverse=True)

    def format_recommendation(self, rec: FlightRecommendation) -> str:
        """Format a recommendation for display."""
        lines = [
            f"Score: {rec.score:.0f}/100 | {rec.airline}",
            f"Price: {rec.currency} {rec.price:.0f} | Duration: {rec.duration_minutes // 60}h {rec.duration_minutes % 60}m | Stops: {rec.stops}",
            f"Departure: {rec.departure_time} | Arrival: {rec.arrival_time}",
            f"Reasons: {'; '.join(rec.reasons)}",
            f"Book: {rec.booking_url}",
        ]
        return "\n".join(lines)

    def print_recommendations(self, recommendations: list[FlightRecommendation], top_n: int = 5) -> None:
        """Print top N recommendations."""
        if not recommendations:
            print("No recommendations available.")
            return

        print("\n" + "=" * 120)
        print("RECOMMENDED FLIGHTS")
        print("=" * 120 + "\n")

        for i, rec in enumerate(recommendations[:top_n], 1):
            print(f"{i}. {self.format_recommendation(rec)}\n")

        print("=" * 120 + "\n")


def get_recommendation_engine() -> RecommendationEngine:
    """Get or create recommendation engine singleton."""
    return RecommendationEngine()
