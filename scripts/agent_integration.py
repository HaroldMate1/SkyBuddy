#!/usr/bin/env python3
"""Universal agent integration layer for SkyBuddy.

Provides unified interface for all agent types: Hermes, OpenClaw, Claude, etc.
All agents communicate through this layer or via MCP server.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

from alerts import get_alerts_manager
from booking_agent import get_booking_agent
from flight_formatter import FlightFormatter
from flight_monitor import FlightMonitor
from loyalty_cards import get_loyalty_manager
from passenger_profiles import get_passenger_manager
from preferences import get_preferences_manager
from price_baseline import DEFAULT_LOOKBACK_DAYS, get_buy_engine, get_price_baseline
from recommendations import get_recommendation_engine
from seat_advisor import build_seat_advisory


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
        self.booking = get_booking_agent()
        self.baseline = get_price_baseline()
        self.buy_engine = get_buy_engine()
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

    # ========== BOOKING (AGENT TRIGGER) ==========

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
        passengers: Optional[List[str]] = None,
        max_price: Optional[float] = None,
        allow_payment: bool = False,
        notes: str = "",
        flight_number: str = "",
        aircraft: str = "",
        duration_minutes: int = 0,
    ) -> Dict[str, Any]:
        """Create a booking intent for a flight link. Nothing is executed yet."""
        return self.booking.prepare_booking(
            booking_url=booking_url,
            airline=airline,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            price=price,
            currency=currency,
            return_date=return_date,
            cabin=cabin,
            passengers=passengers,
            max_price=max_price,
            allow_payment=allow_payment,
            notes=notes,
            flight_number=flight_number,
            aircraft=aircraft,
            duration_minutes=duration_minutes,
        )

    def prepare_booking_from_recommendation(
        self,
        recommendation: Dict[str, Any],
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: Optional[str] = None,
        passengers: Optional[List[str]] = None,
        max_price: Optional[float] = None,
        allow_payment: bool = False,
    ) -> Dict[str, Any]:
        """Create a booking intent straight from a `search_flights` recommendation."""
        booking_url = recommendation.get("booking_url", "")
        if not booking_url:
            return {"status": "error", "error": "Recommendation has no booking_url."}

        return self.prepare_booking(
            booking_url=booking_url,
            airline=recommendation.get("airline", "Unknown"),
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            price=float(recommendation.get("price", 0.0)),
            currency=recommendation.get("currency", "EUR"),
            passengers=passengers,
            max_price=max_price,
            allow_payment=allow_payment,
            notes=f"Score {recommendation.get('score', 'n/a')}/100 from SkyBuddy search.",
        )

    def confirm_booking(
        self,
        intent_id: str,
        approved_by: str,
        current_price: Optional[float] = None,
        allow_payment: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Approve a booking intent and release the agent playbook."""
        return self.booking.confirm_booking(
            intent_id=intent_id,
            approved_by=approved_by,
            current_price=current_price,
            allow_payment=allow_payment,
        )

    def get_booking_playbook(self, intent_id: str) -> Dict[str, Any]:
        """Return the step-by-step booking instructions for a confirmed intent."""
        return self.booking.get_booking_playbook(intent_id)

    def mark_booking_executed(
        self,
        intent_id: str,
        confirmation_code: str = "",
        amount_paid: Optional[float] = None,
        success: bool = True,
        detail: str = "",
    ) -> Dict[str, Any]:
        """Record the outcome of a booking the agent carried out."""
        return self.booking.mark_executed(
            intent_id=intent_id,
            confirmation_code=confirmation_code,
            amount_paid=amount_paid,
            success=success,
            detail=detail,
        )

    def cancel_booking(self, intent_id: str, reason: str = "") -> Dict[str, Any]:
        """Cancel a booking intent before it is executed."""
        return self.booking.cancel_booking(intent_id, reason)

    def list_bookings(self, status: Optional[str] = None) -> Dict[str, Any]:
        """List booking intents, optionally filtered by status."""
        return self.booking.list_bookings(status)

    # ========== HISTORICAL BASELINE & BUY SIGNAL ==========

    def get_price_baseline(
        self,
        origin: str,
        destination: str,
        days: int = DEFAULT_LOOKBACK_DAYS,
        outbound_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scan the recorded price history for a route (a year by default)."""
        return asdict(
            self.baseline.build(origin, destination, days=days, outbound_date=outbound_date)
        )

    def record_price_observation(
        self,
        origin: str,
        destination: str,
        price: float,
        currency: str = "EUR",
        outbound_date: str = "",
        return_date: str = "",
        airline: str = "",
        source: str = "agent",
        booking_url: str = "",
    ) -> Dict[str, Any]:
        """Record one observed price so the baseline keeps growing."""
        return asdict(
            self.baseline.record_price(
                origin=origin,
                destination=destination,
                price=price,
                currency=currency,
                outbound_date=outbound_date,
                return_date=return_date,
                airline=airline,
                source=source,
                booking_url=booking_url,
            )
        )

    def evaluate_price(
        self,
        origin: str,
        destination: str,
        price: float,
        days: int = DEFAULT_LOOKBACK_DAYS,
        target_price: Optional[float] = None,
        outbound_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a buy verdict for a live price against its historical baseline."""
        return self.baseline.evaluate(
            origin=origin,
            destination=destination,
            price=price,
            days=days,
            target_price=target_price,
            outbound_date=outbound_date,
        )

    def auto_book_if_deal(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        price: float,
        booking_url: str,
        airline: str = "",
        return_date: Optional[str] = None,
        currency: str = "EUR",
        passengers: Optional[List[str]] = None,
        target_price: Optional[float] = None,
        max_price: Optional[float] = None,
        days: int = DEFAULT_LOOKBACK_DAYS,
        cabin: str = "economy",
    ) -> Dict[str, Any]:
        """Create the booking intent automatically when the price beats its history."""
        return self.buy_engine.auto_book_if_deal(
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            price=price,
            booking_url=booking_url,
            airline=airline,
            return_date=return_date,
            currency=currency,
            passengers=passengers,
            target_price=target_price,
            max_price=max_price,
            days=days,
            cabin=cabin,
        )

    # ========== SEAT SELECTION ==========

    def get_seat_advisory(
        self,
        airline: str,
        duration_minutes: int,
        aircraft: str = "",
        flight_number: str = "",
        cabin: str = "economy",
    ) -> Dict[str, Any]:
        """Return the seat-map workflow, cross-check sites and selection actions."""
        return build_seat_advisory(
            airline=airline,
            duration_minutes=duration_minutes,
            aircraft=aircraft,
            flight_number=flight_number,
            cabin=cabin,
        )

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
