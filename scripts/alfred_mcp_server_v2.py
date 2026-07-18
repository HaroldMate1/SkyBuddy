#!/usr/bin/env python3
"""Enhanced MCP Server for Alfred with FlightClaw features integrated.

Includes: search, monitoring, alerts, recommendations, loyalty programs, passenger profiles.
"""
from __future__ import annotations

import json
from typing import Any

from alerts import get_alerts_manager
from flight_formatter import FlightFormatter, get_formatter
from flight_monitor import FlightMonitor
from flight_scraper import generate_search_urls, parse_args
from loyalty_cards import get_loyalty_manager
from passenger_profiles import get_passenger_manager
from preferences import get_preferences_manager
from recommendations import RecommendationEngine, get_recommendation_engine

formatter = get_formatter()


class AlfredFlightServerV2:
    """Enhanced flight tracking MCP server with FlightClaw features."""

    def __init__(self):
        """Initialize enhanced Alfred flight server."""
        self.monitor = FlightMonitor()
        self.prefs = get_preferences_manager()
        self.alerts = get_alerts_manager()
        self.loyalty = get_loyalty_manager()
        self.passengers = get_passenger_manager()
        self.recommendations = get_recommendation_engine()

    # ========== SEARCH & BOOKING ==========

    def search_flights(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str | None = None,
        passengers: int = 1,
        cabin_class: str = "economy",
    ) -> dict[str, Any]:
        """Search for flights on a route."""
        result = self.monitor.duffel.search_flights(
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            passengers=passengers,
            cabin_class=cabin_class,
        )

        if not result.flights:
            return {
                "origin": origin,
                "destination": destination,
                "status": "no_flights_found",
                "fallback_urls": generate_search_urls(
                    {
                        "origin": origin,
                        "destination": destination,
                        "outbound_target_date": outbound_date,
                        "return_target_date": return_date,
                    }
                ),
            }

        flights_data = [
            {
                "airline": f.airline,
                "price": f.price,
                "currency": f.currency,
                "duration": f.duration_minutes,
                "stops": f.stops,
                "departure_time": f.departure_time,
                "arrival_time": f.arrival_time,
                "booking_url": f.booking_url,
            }
            for f in sorted(result.flights, key=lambda f: f.price)[:10]
        ]

        # Get recommendations based on preferences
        recs = self.recommendations.recommend_flights(
            flights_data,
            price_median=sum(f["price"] for f in flights_data) / len(flights_data),
        )

        return {
            "origin": origin,
            "destination": destination,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "flights_found": len(result.flights),
            "best_price": min(f["price"] for f in flights_data),
            "currency": flights_data[0]["currency"] if flights_data else "EUR",
            "flights": flights_data,
            "recommendations": [
                {
                    "rank": i + 1,
                    "score": rec.score,
                    "airline": rec.airline,
                    "price": rec.price,
                    "currency": rec.currency,
                    "duration_hours": rec.duration_minutes / 60,
                    "stops": rec.stops,
                    "reasons": rec.reasons,
                    "booking_url": rec.booking_url,
                }
                for i, rec in enumerate(recs[:3])
            ],
        }

    # ========== MONITORING & ALERTS ==========

    def add_watched_route(
        self,
        name: str,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str | None = None,
        target_price: float | None = None,
    ) -> dict[str, Any]:
        """Add a route to watch for price changes."""
        return self.monitor.search_and_add_route(
            name=name,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            target_price=target_price,
        )

    def list_watched_routes(self) -> dict[str, Any]:
        """List all currently watched routes with stats."""
        routes = self.prefs.get_all_watched_routes()
        if not routes:
            return {"routes": [], "message": "No routes being monitored"}

        result = {"routes": [], "total": len(routes)}

        for route_name in routes:
            stats = self.monitor.get_route_stats(route_name)
            result["routes"].append(stats)

        return result

    def monitor_all(self) -> dict[str, Any]:
        """Check all watched routes for price changes."""
        alerts_triggered = self.monitor.monitor_all_routes()

        return {
            "routes_checked": len(self.prefs.get_all_watched_routes()),
            "alerts_triggered": len(alerts_triggered),
            "alerts": {
                route_name: [
                    {
                        "type": alert.alert_type,
                        "current_price": alert.current_price,
                        "currency": alert.currency,
                        "price_drop_percent": alert.price_drop_percent,
                        "booking_url": alert.booking_url,
                    }
                    for alert in alerts
                ]
                for route_name, alerts in alerts_triggered.items()
            },
        }

    def get_recent_alerts(self, hours: int = 24) -> dict[str, Any]:
        """Get recent price alerts."""
        recent = self.alerts.get_recent_alerts(hours=hours)
        return {
            "hours_lookback": hours,
            "alerts_found": len(recent),
            "alerts": [
                {
                    "route": alert.route_name,
                    "origin": alert.origin,
                    "destination": alert.destination,
                    "price": alert.current_price,
                    "currency": alert.currency,
                    "type": alert.alert_type,
                    "drop_percent": alert.price_drop_percent,
                    "time": alert.timestamp,
                    "booking_url": alert.booking_url,
                }
                for alert in recent
            ],
        }

    # ========== PREFERENCES ==========

    def get_preferences(self) -> dict[str, Any]:
        """Get current user preferences."""
        prefs = self.prefs.preferences
        return {
            "preferred_airlines": prefs.preferred_airlines,
            "avoided_airlines": prefs.avoided_airlines,
            "preferred_departure_time": prefs.preferred_departure_time,
            "max_flight_duration_hours": prefs.max_flight_duration_hours,
            "max_stops": prefs.max_stops,
            "preferred_cabin": prefs.preferred_cabin,
            "price_alert_threshold_percent": prefs.price_alert_threshold_percent,
            "preferred_currency": prefs.preferred_currency,
        }

    def update_preferences(self, **kwargs) -> dict[str, Any]:
        """Update user preferences."""
        self.prefs.update_preferences(**kwargs)
        return {"updated": True, "preferences": self.get_preferences()}

    # ========== LOYALTY & CARDS ==========

    def add_credit_card(
        self,
        card_id: str,
        issuer: str,
        product: str,
        network: str = "unknown",
        region: str = "US",
        points_per_dollar: float = 1.0,
        transfer_partners: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """Add a credit card."""
        card = self.loyalty.add_card(
            card_id=card_id,
            issuer=issuer,
            product=product,
            network=network,
            region=region,
            points_per_dollar=points_per_dollar,
            transfer_partners=transfer_partners or [],
            notes=notes,
        )

        return {
            "card_id": card.id,
            "issuer": card.issuer,
            "product": card.product,
            "total_cards": len(self.loyalty.list_cards()),
        }

    def list_cards(self) -> dict[str, Any]:
        """List all credit cards."""
        cards = self.loyalty.list_cards()
        return {
            "total": len(cards),
            "cards": [
                {
                    "id": c.id,
                    "issuer": c.issuer,
                    "product": c.product,
                    "network": c.network,
                    "region": c.region,
                    "points_per_dollar": c.points_per_dollar,
                }
                for c in cards
            ],
        }

    def add_loyalty_balance(
        self,
        program: str,
        balance: int,
        tier: str = "member",
    ) -> dict[str, Any]:
        """Add or update loyalty program balance."""
        prog = self.loyalty.add_loyalty_program(
            program=program,
            balance=balance,
            tier=tier,
        )

        return {
            "program": prog.program,
            "balance": prog.balance,
            "tier": prog.tier,
            "total_programs": len(self.loyalty.list_programs()),
        }

    def list_loyalty_programs(self) -> dict[str, Any]:
        """List loyalty program balances."""
        programs = self.loyalty.list_programs()
        total_value = sum(p.balance for p in programs)

        return {
            "total_programs": len(programs),
            "total_points": total_value,
            "programs": [
                {
                    "program": p.program,
                    "balance": p.balance,
                    "tier": p.tier,
                }
                for p in programs
            ],
        }

    def estimate_points_earnings(self, flight_cost: float) -> dict[str, Any]:
        """Estimate points earned from flight purchase."""
        earnings = self.loyalty.estimate_earnings(flight_cost)

        return {
            "flight_cost": flight_cost,
            "card_earnings": [
                {"card_id": card_id, "points": points}
                for card_id, points in earnings.items()
            ],
            "total_potential_points": sum(earnings.values()),
        }

    # ========== PASSENGERS ==========

    def add_passenger(
        self,
        name: str,
        given_name: str,
        family_name: str,
        born_on: str,
        gender: str,
        title: str = "mr",
        email: str = "",
        phone_number: str = "",
        passport: str = "",
        nationality: str = "",
    ) -> dict[str, Any]:
        """Add a passenger profile."""
        passenger = self.passengers.add_passenger(
            name=name,
            given_name=given_name,
            family_name=family_name,
            born_on=born_on,
            gender=gender,
            title=title,
            email=email,
            phone_number=phone_number,
            passport=passport,
            nationality=nationality,
        )

        return {
            "name": passenger.name,
            "full_name": f"{passenger.given_name} {passenger.family_name}",
            "total_passengers": len(self.passengers.list_passengers()),
        }

    def list_passengers(self) -> dict[str, Any]:
        """List all passenger profiles."""
        passengers = self.passengers.list_passengers()

        return {
            "total": len(passengers),
            "passengers": [
                {
                    "name": p.name,
                    "full_name": f"{p.given_name} {p.family_name}",
                    "born_on": p.born_on,
                    "gender": p.gender,
                    "title": p.title,
                    "email": p.email,
                }
                for p in passengers
            ],
        }

    # ========== UTILITY ==========

    def handle_request(self, method: str, params: dict) -> dict[str, Any]:
        """Handle MCP request from Alfred."""
        methods = {
            # Search & booking
            "search_flights": self.search_flights,
            # Monitoring
            "add_watched_route": self.add_watched_route,
            "list_watched_routes": self.list_watched_routes,
            "monitor_all": self.monitor_all,
            "get_recent_alerts": self.get_recent_alerts,
            # Preferences
            "get_preferences": self.get_preferences,
            "update_preferences": self.update_preferences,
            # Loyalty
            "add_credit_card": self.add_credit_card,
            "list_cards": self.list_cards,
            "add_loyalty_balance": self.add_loyalty_balance,
            "list_loyalty_programs": self.list_loyalty_programs,
            "estimate_points_earnings": self.estimate_points_earnings,
            # Passengers
            "add_passenger": self.add_passenger,
            "list_passengers": self.list_passengers,
        }

        if method not in methods:
            return {"error": f"Unknown method: {method}"}

        try:
            return methods[method](**params)
        except Exception as e:
            return {"error": str(e)}


def create_mcp_server() -> AlfredFlightServerV2:
    """Create enhanced MCP server instance."""
    return AlfredFlightServerV2()


if __name__ == "__main__":
    server = create_mcp_server()

    # Test search
    print("=== SEARCH FLIGHTS ===")
    result = server.search_flights(
        origin="BIO",
        destination="BOG",
        outbound_date="2026-12-04",
        return_date="2027-01-08",
    )
    print(json.dumps(result, indent=2, default=str)[:500])

    # Test preferences
    print("\n=== GET PREFERENCES ===")
    print(json.dumps(server.get_preferences(), indent=2))

    # Test loyalty
    print("\n=== ADD CARD ===")
    result = server.add_credit_card(
        card_id="amex-plat",
        issuer="American Express",
        product="Platinum",
        points_per_dollar=1.5,
    )
    print(json.dumps(result, indent=2))

    print("\nMCP Server ready for Alfred integration!")
