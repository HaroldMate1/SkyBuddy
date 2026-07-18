#!/usr/bin/env python3
"""Universal agent integration layer for SkyBuddy.

Provides unified interface for all agent types: Hermes, OpenClaw, Claude, etc.
All agents communicate through this layer or via MCP server.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from alerts import get_alerts_manager
from flight_formatter import FlightFormatter
from flight_monitor import FlightMonitor
from loyalty_cards import get_loyalty_manager
from passenger_profiles import get_passenger_manager
from preferences import get_preferences_manager
from recommendations import get_recommendation_engine


class AgentType:
    """Supported agent types."""

    HERMES = "hermes"
    OPENCLAW = "openclaw"
    CLAUDE = "claude"
    GENERIC = "generic"


class SkyBuddyAgent:
    """Universal SkyBuddy integration for any agent."""

    def __init__(self, agent_type: str = AgentType.GENERIC):
        """Initialize SkyBuddy agent integration.

        Args:
            agent_type: Type of agent (hermes, openclaw, claude, generic)
        """
        self.agent_type = agent_type
        self.monitor = FlightMonitor()
        self.prefs = get_preferences_manager()
        self.alerts = get_alerts_manager()
        self.loyalty = get_loyalty_manager()
        self.passengers = get_passenger_manager()
        self.recommendations = get_recommendation_engine()
        self.formatter = FlightFormatter()

        # Store agent-specific callbacks
        self.callbacks: Dict[str, Callable] = {}
        self._setup_agent_specific()

    def _setup_agent_specific(self) -> None:
        """Setup agent-specific behavior."""
        if self.agent_type == AgentType.HERMES:
            self._setup_hermes()
        elif self.agent_type == AgentType.OPENCLAW:
            self._setup_openclaw()
        elif self.agent_type == AgentType.CLAUDE:
            self._setup_claude()

    def _setup_hermes(self) -> None:
        """Setup Hermes agent callbacks."""
        # Hermes uses workflow-based actions
        pass

    def _setup_openclaw(self) -> None:
        """Setup OpenClaw agent callbacks."""
        # OpenClaw uses MCP protocol
        pass

    def _setup_claude(self) -> None:
        """Setup Claude callbacks."""
        # Claude uses direct API calls
        pass

    # ========== FLIGHT SEARCH ==========

    def search_flights(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy",
    ) -> Dict[str, Any]:
        """Search for flights and get AI recommendations."""
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
                "status": "no_flights",
                "origin": origin,
                "destination": destination,
                "message": "No flights found. Check search parameters.",
            }

        # Format flights for recommendation
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
            for f in sorted(result.flights, key=lambda f: f.price)[:15]
        ]

        # Get recommendations
        recs = self.recommendations.recommend_flights(
            flights_data,
            price_median=sum(f["price"] for f in flights_data) / len(flights_data),
        )

        return {
            "status": "success",
            "origin": origin,
            "destination": destination,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "flights_found": len(result.flights),
            "best_price": min(f["price"] for f in flights_data),
            "currency": flights_data[0]["currency"],
            "flights": flights_data[:5],
            "top_recommendations": [
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

    # ========== MONITORING ==========

    def add_route(
        self,
        name: str,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: Optional[str] = None,
        target_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Add a route to monitor."""
        return self.monitor.search_and_add_route(
            name=name,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            target_price=target_price,
        )

    def list_routes(self) -> Dict[str, Any]:
        """List all monitored routes."""
        routes = self.prefs.get_all_watched_routes()
        if not routes:
            return {"routes": [], "total": 0, "message": "No routes monitored"}

        return {
            "routes": [self.monitor.get_route_stats(name) for name in routes],
            "total": len(routes),
        }

    def check_all_routes(self) -> Dict[str, Any]:
        """Check all routes for price changes."""
        alerts_triggered = self.monitor.monitor_all_routes()
        return {
            "routes_checked": len(self.prefs.get_all_watched_routes()),
            "alerts_triggered": len(alerts_triggered),
            "summary": {
                route_name: {
                    "count": len(alerts),
                    "alerts": [
                        {
                            "price": alert.current_price,
                            "currency": alert.currency,
                            "drop": f"{alert.price_drop_percent:.1f}%",
                        }
                        for alert in alerts
                    ],
                }
                for route_name, alerts in alerts_triggered.items()
            },
        }

    # ========== ALERTS ==========

    def get_alerts(self, hours: int = 24) -> Dict[str, Any]:
        """Get recent price alerts."""
        recent = self.alerts.get_recent_alerts(hours=hours)
        if not recent:
            return {"alerts": [], "total": 0}

        return {
            "total": len(recent),
            "hours": hours,
            "alerts": [
                {
                    "route": alert.route_name,
                    "origin": alert.origin,
                    "destination": alert.destination,
                    "price": alert.current_price,
                    "currency": alert.currency,
                    "type": alert.alert_type,
                    "savings": f"{alert.price_drop_percent:.1f}%",
                    "time": alert.timestamp,
                    "booking_url": alert.booking_url,
                }
                for alert in recent
            ],
        }

    # ========== PREFERENCES ==========

    def get_preferences(self) -> Dict[str, Any]:
        """Get user preferences."""
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

    def set_preferences(self, **kwargs) -> Dict[str, Any]:
        """Update preferences."""
        self.prefs.update_preferences(**kwargs)
        return {"updated": True, "preferences": self.get_preferences()}

    # ========== LOYALTY ==========

    def add_card(
        self,
        card_id: str,
        issuer: str,
        product: str,
        points_per_dollar: float = 1.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Add credit card."""
        self.loyalty.add_card(
            card_id=card_id,
            issuer=issuer,
            product=product,
            points_per_dollar=points_per_dollar,
            **kwargs,
        )
        return {
            "status": "added",
            "card_id": card_id,
            "total_cards": len(self.loyalty.list_cards()),
        }

    def list_cards(self) -> Dict[str, Any]:
        """List credit cards."""
        cards = self.loyalty.list_cards()
        return {
            "total": len(cards),
            "cards": [
                {
                    "id": c.id,
                    "issuer": c.issuer,
                    "product": c.product,
                    "points_per_dollar": c.points_per_dollar,
                }
                for c in cards
            ],
        }

    def add_loyalty_program(
        self,
        program: str,
        balance: int,
        tier: str = "member",
    ) -> Dict[str, Any]:
        """Add loyalty program balance."""
        self.loyalty.add_loyalty_program(program=program, balance=balance, tier=tier)
        return {
            "status": "added",
            "program": program,
            "balance": balance,
            "total_programs": len(self.loyalty.list_programs()),
        }

    def estimate_earnings(self, flight_cost: float) -> Dict[str, Any]:
        """Estimate points earned on flight."""
        earnings = self.loyalty.estimate_earnings(flight_cost)
        return {
            "flight_cost": flight_cost,
            "earnings": [
                {"card": card_id, "points": int(points)}
                for card_id, points in earnings.items()
            ],
            "total_points": int(sum(earnings.values())),
        }

    # ========== PASSENGERS ==========

    def add_passenger(
        self,
        name: str,
        given_name: str,
        family_name: str,
        born_on: str,
        gender: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Add passenger profile."""
        self.passengers.add_passenger(
            name=name,
            given_name=given_name,
            family_name=family_name,
            born_on=born_on,
            gender=gender,
            **kwargs,
        )
        return {
            "status": "added",
            "name": name,
            "total_passengers": len(self.passengers.list_passengers()),
        }

    def list_passengers(self) -> Dict[str, Any]:
        """List passengers."""
        passengers = self.passengers.list_passengers()
        return {
            "total": len(passengers),
            "passengers": [
                {
                    "name": p.name,
                    "full_name": f"{p.given_name} {p.family_name}",
                    "dob": p.born_on,
                }
                for p in passengers
            ],
        }

    # ========== HELPER METHODS ==========

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register agent-specific callback."""
        self.callbacks[event] = callback

    def trigger_callback(self, event: str, data: Any) -> None:
        """Trigger agent-specific callback."""
        if event in self.callbacks:
            self.callbacks[event](data)

    def to_json(self, data: Any) -> str:
        """Convert to JSON for agent response."""
        return json.dumps(data, indent=2, default=str)


def create_agent(agent_type: str = AgentType.GENERIC) -> SkyBuddyAgent:
    """Factory function to create agent."""
    return SkyBuddyAgent(agent_type=agent_type)
