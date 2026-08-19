#!/usr/bin/env python3
"""Universal MCP Server for SkyBuddy - Works with any agent.

Provides Model Context Protocol interface for:
- Hermes
- OpenClaw
- Claude
- Any MCP-compatible client
"""
from __future__ import annotations

import json
from typing import Any, Dict

from agent_integration import SkyBuddyAgent, AgentType


class SkyBuddyMCPServer:
    """Universal MCP server for SkyBuddy."""

    def __init__(self, agent_type: str = AgentType.GENERIC, user: str | None = None):
        """Initialize MCP server for a traveller workspace."""
        self.agent = SkyBuddyAgent(agent_type=agent_type, user=user)
        self.agent_type = agent_type

    def list_tools(self) -> list[Dict[str, Any]]:
        """Return list of available tools/methods."""
        return [
            {
                "name": "create_user",
                "description": (
                    "Create a traveller workspace with its own preferences, watched routes, "
                    "passengers, cards, bookings and price history."
                ),
                "parameters": {
                    "user": "Unique id (e.g. harold)",
                    "display_name": "Human-readable name",
                    "email": "Contact address for alerts (optional)",
                    "home_airport": "Default origin IATA code (optional)",
                    "currency": "Preferred currency (default EUR)",
                    "notes": "Free-text context (optional)",
                    "make_active": "Switch to this traveller immediately (default true)",
                },
            },
            {
                "name": "list_users",
                "description": "List every traveller workspace and which one is active",
                "parameters": {},
            },
            {
                "name": "get_current_user",
                "description": "Describe the active traveller and the files their data lives in",
                "parameters": {},
            },
            {
                "name": "switch_user",
                "description": "Make a traveller active; every later tool call uses their workspace",
                "parameters": {"user": "User id to switch to"},
            },
            {
                "name": "update_user",
                "description": "Update a traveller profile",
                "parameters": {
                    "user": "User id",
                    "display_name": "New display name (optional)",
                    "email": "New email (optional)",
                    "home_airport": "New home airport (optional)",
                    "currency": "New currency (optional)",
                    "notes": "New notes (optional)",
                },
            },
            {
                "name": "delete_user",
                "description": "Delete a traveller workspace",
                "parameters": {
                    "user": "User id",
                    "remove_data": "Also delete their stored files (default false)",
                },
            },
            {
                "name": "search_flights",
                "description": "Search for flights with AI recommendations",
                "parameters": {
                    "origin": "IATA code (e.g., BIO)",
                    "destination": "IATA code (e.g., BOG)",
                    "outbound_date": "YYYY-MM-DD",
                    "return_date": "YYYY-MM-DD (optional)",
                    "passengers": "Number of passengers (default 1)",
                    "cabin_class": "economy/business/first (default economy)",
                },
            },
            {
                "name": "add_route",
                "description": "Add a route to monitor for price changes",
                "parameters": {
                    "name": "Route name (e.g., Colombia Trip)",
                    "origin": "IATA code",
                    "destination": "IATA code",
                    "outbound_date": "YYYY-MM-DD",
                    "return_date": "YYYY-MM-DD (optional)",
                    "target_price": "Alert when below this price (optional)",
                },
            },
            {
                "name": "list_routes",
                "description": "List all monitored routes and their prices",
                "parameters": {},
            },
            {
                "name": "check_all_routes",
                "description": "Check all routes for price changes and trigger alerts",
                "parameters": {},
            },
            {
                "name": "get_alerts",
                "description": "Get recent price alerts",
                "parameters": {
                    "hours": "Look back this many hours (default 24)",
                },
            },
            {
                "name": "get_preferences",
                "description": "Get current user preferences",
                "parameters": {},
            },
            {
                "name": "set_preferences",
                "description": "Update user preferences",
                "parameters": {
                    "preferred_airlines": "List of airlines",
                    "avoided_airlines": "List of airlines to avoid",
                    "preferred_departure_time": "morning/afternoon/evening",
                    "max_flight_duration_hours": "Maximum acceptable flight length",
                    "max_stops": "Maximum number of stops",
                    "preferred_cabin": "economy/business/first",
                },
            },
            {
                "name": "add_card",
                "description": "Add a credit card for points tracking",
                "parameters": {
                    "card_id": "Unique ID (e.g., amex-plat)",
                    "issuer": "Card issuer (e.g., American Express)",
                    "product": "Product name (e.g., Platinum)",
                    "points_per_dollar": "Points earning rate",
                },
            },
            {
                "name": "list_cards",
                "description": "List all credit cards",
                "parameters": {},
            },
            {
                "name": "add_loyalty_program",
                "description": "Add loyalty program balance",
                "parameters": {
                    "program": "Program name (e.g., Amex Membership Rewards)",
                    "balance": "Current points balance",
                    "tier": "Membership tier",
                },
            },
            {
                "name": "estimate_earnings",
                "description": "Estimate points earned from a flight",
                "parameters": {
                    "flight_cost": "Flight cost in your preferred currency",
                },
            },
            {
                "name": "add_passenger",
                "description": "Add traveler profile for bookings",
                "parameters": {
                    "name": "Unique name (e.g., harold)",
                    "given_name": "First name",
                    "family_name": "Last name",
                    "born_on": "YYYY-MM-DD",
                    "gender": "M/F/X",
                    "title": "mr/ms/mrs/mx",
                    "passport": "Passport number (optional)",
                    "nationality": "Country code (optional)",
                },
            },
            {
                "name": "list_passengers",
                "description": "List all passenger profiles",
                "parameters": {},
            },
            {
                "name": "prepare_booking",
                "description": (
                    "Create a booking intent for a specific flight link. Executes nothing: "
                    "the intent must be confirmed by a human before the agent may act on it."
                ),
                "parameters": {
                    "booking_url": "Direct link to the flight/offer to book",
                    "airline": "Airline of the chosen offer",
                    "origin": "IATA code",
                    "destination": "IATA code",
                    "outbound_date": "YYYY-MM-DD",
                    "price": "Price agreed at search time",
                    "currency": "Currency of the price (default EUR)",
                    "return_date": "YYYY-MM-DD (optional)",
                    "cabin": "economy/business/first (default economy)",
                    "passengers": "List of passenger profile names",
                    "max_price": "Hard ceiling; booking is refused above it",
                    "allow_payment": "Grant payment authority for this intent (default false)",
                    "notes": "Free-text context stored with the intent",
                },
            },
            {
                "name": "confirm_booking",
                "description": (
                    "Approve a booking intent after a human OK. Re-checks the price ceiling "
                    "and returns the agent playbook for the booking link."
                ),
                "parameters": {
                    "intent_id": "Intent id returned by prepare_booking",
                    "approved_by": "Who approved the booking",
                    "current_price": "Live price to re-validate against the ceiling (optional)",
                    "allow_payment": "Override payment authority for this intent (optional)",
                },
            },
            {
                "name": "get_booking_playbook",
                "description": "Get the step-by-step instructions the agent executes on the booking link",
                "parameters": {"intent_id": "Intent id"},
            },
            {
                "name": "mark_booking_executed",
                "description": "Record the outcome of a booking the agent carried out",
                "parameters": {
                    "intent_id": "Intent id",
                    "confirmation_code": "Airline confirmation code",
                    "amount_paid": "Final amount paid",
                    "success": "True if the booking completed (default true)",
                    "detail": "Extra context for the audit trail",
                },
            },
            {
                "name": "cancel_booking",
                "description": "Cancel a booking intent before it is executed",
                "parameters": {
                    "intent_id": "Intent id",
                    "reason": "Why it was cancelled",
                },
            },
            {
                "name": "list_bookings",
                "description": "List booking intents and their audit trail",
                "parameters": {
                    "status": (
                        "Filter: awaiting_confirmation/ready_to_execute/in_progress/"
                        "booked/cancelled/failed (optional)"
                    ),
                },
            },
            {
                "name": "get_price_baseline",
                "description": (
                    "Scan the recorded price history for a route (365 days by default) and "
                    "return the baseline: min, percentiles, median, trend and buy thresholds."
                ),
                "parameters": {
                    "origin": "IATA code",
                    "destination": "IATA code",
                    "days": "Lookback window in days (default 365)",
                    "outbound_date": "Restrict to this departure date (optional)",
                },
            },
            {
                "name": "evaluate_price",
                "description": (
                    "Compare a live price against the historical baseline and return a verdict: "
                    "buy_now, good, fair, wait or high."
                ),
                "parameters": {
                    "origin": "IATA code",
                    "destination": "IATA code",
                    "price": "Live price to evaluate",
                    "days": "Lookback window in days (default 365)",
                    "target_price": "Your target price (optional)",
                    "outbound_date": "Departure date of the offer (optional)",
                },
            },
            {
                "name": "auto_book_if_deal",
                "description": (
                    "Evaluate a live offer against its 365-day baseline and, when the verdict is "
                    "buy-worthy, automatically create the booking intent for its link "
                    "(still pending human confirmation)."
                ),
                "parameters": {
                    "origin": "IATA code",
                    "destination": "IATA code",
                    "outbound_date": "YYYY-MM-DD",
                    "price": "Live price of the offer",
                    "booking_url": "Link to the offer",
                    "airline": "Airline of the offer",
                    "return_date": "YYYY-MM-DD (optional)",
                    "currency": "Currency (default EUR)",
                    "passengers": "List of passenger profile names",
                    "target_price": "Your target price (optional)",
                    "max_price": "Hard ceiling for the booking intent (optional)",
                    "days": "Lookback window in days (default 365)",
                },
            },
            {
                "name": "record_price_observation",
                "description": "Record one observed price so the historical baseline keeps growing",
                "parameters": {
                    "origin": "IATA code",
                    "destination": "IATA code",
                    "price": "Observed price",
                    "currency": "Currency (default EUR)",
                    "outbound_date": "YYYY-MM-DD (optional)",
                    "return_date": "YYYY-MM-DD (optional)",
                    "airline": "Airline of the observed fare (optional)",
                    "source": "Where the price came from (optional)",
                    "booking_url": "Link to the observed fare (optional)",
                },
            },
            {
                "name": "get_seat_advisory",
                "description": (
                    "Seat-selection workflow for a flight: FlightAware aircraft check, SeatMaps cabin "
                    "map, cross-check sites (SeatGuru, aeroLOPA, ExpertFlyer, Flightradar24) and the "
                    "actions that actually assign the seat."
                ),
                "parameters": {
                    "airline": "Operating or marketing airline",
                    "duration_minutes": "Itinerary duration in minutes",
                    "aircraft": "Aircraft type, e.g. Airbus A350-900 (optional)",
                    "flight_number": "Flight number, e.g. IB 6131 (optional)",
                    "cabin": "economy/business/first (default economy)",
                },
            },
        ]

    def call_tool(self, tool_name: str, **params) -> Dict[str, Any]:
        """Call a tool and return result."""
        methods = {
            "create_user": self.agent.create_user,
            "list_users": self.agent.list_users,
            "get_current_user": self.agent.get_current_user,
            "switch_user": self.agent.switch_user,
            "update_user": self.agent.update_user,
            "delete_user": self.agent.delete_user,
            "search_flights": self.agent.search_flights,
            "add_route": self.agent.add_route,
            "list_routes": self.agent.list_routes,
            "check_all_routes": self.agent.check_all_routes,
            "get_alerts": self.agent.get_alerts,
            "get_preferences": self.agent.get_preferences,
            "set_preferences": self.agent.set_preferences,
            "add_card": self.agent.add_card,
            "list_cards": self.agent.list_cards,
            "add_loyalty_program": self.agent.add_loyalty_program,
            "estimate_earnings": self.agent.estimate_earnings,
            "add_passenger": self.agent.add_passenger,
            "list_passengers": self.agent.list_passengers,
            "prepare_booking": self.agent.prepare_booking,
            "confirm_booking": self.agent.confirm_booking,
            "get_booking_playbook": self.agent.get_booking_playbook,
            "mark_booking_executed": self.agent.mark_booking_executed,
            "cancel_booking": self.agent.cancel_booking,
            "list_bookings": self.agent.list_bookings,
            "record_price_observation": self.agent.record_price_observation,
            "get_price_baseline": self.agent.get_price_baseline,
            "evaluate_price": self.agent.evaluate_price,
            "auto_book_if_deal": self.agent.auto_book_if_deal,
            "get_seat_advisory": self.agent.get_seat_advisory,
        }

        if tool_name not in methods:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            # Filter kwargs to only include parameters the method accepts
            import inspect

            sig = inspect.signature(methods[tool_name])
            takes_kwargs = any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in sig.parameters.values()
            )
            valid_params = (
                dict(params)
                if takes_kwargs
                else {k: v for k, v in params.items() if k in sig.parameters}
            )

            result = methods[tool_name](**valid_params)
            return result
        except Exception as e:
            return {"error": str(e), "tool": tool_name}

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol request."""
        if request.get("method") == "list_tools":
            return {
                "agent": self.agent_type,
                "tools": self.list_tools(),
            }
        elif request.get("method") == "call_tool":
            return self.call_tool(
                tool_name=request.get("tool"),
                **request.get("params", {}),
            )
        else:
            return {"error": "Unknown method"}

    def start(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        """Start MCP server (for local testing)."""
        print(f"\n{'='*80}")
        print(f"SkyBuddy MCP Server")
        print(f"Agent Type: {self.agent_type}")
        print(f"Host: {host}:{port}")
        print(f"{'='*80}\n")

        print("Available tools:")
        for tool in self.list_tools():
            print(f"  - {tool['name']}: {tool['description']}")

        print(f"\n{'='*80}")
        print("Server ready. Send MCP requests to test.")
        print(f"{'='*80}\n")

        # Example: Test search
        result = self.call_tool(
            "search_flights",
            origin="BIO",
            destination="BOG",
            outbound_date="2026-12-04",
            return_date="2027-01-08",
        )

        print("Example search result (first 500 chars):")
        print(json.dumps(result, indent=2, default=str)[:500])
        print("\nServer running. Ready for agent integration.\n")


if __name__ == "__main__":
    import sys

    agent_type = sys.argv[1] if len(sys.argv) > 1 else AgentType.GENERIC
    user = sys.argv[2] if len(sys.argv) > 2 else None

    server = SkyBuddyMCPServer(agent_type=agent_type, user=user)
    server.start()
