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

    def __init__(self, agent_type: str = AgentType.GENERIC):
        """Initialize MCP server."""
        self.agent = SkyBuddyAgent(agent_type=agent_type)
        self.agent_type = agent_type

    def list_tools(self) -> list[Dict[str, Any]]:
        """Return list of available tools/methods."""
        return [
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
        ]

    def call_tool(self, tool_name: str, **params) -> Dict[str, Any]:
        """Call a tool and return result."""
        methods = {
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
        }

        if tool_name not in methods:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            # Filter kwargs to only include parameters the method accepts
            import inspect

            sig = inspect.signature(methods[tool_name])
            valid_params = {k: v for k, v in params.items() if k in sig.parameters}

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

    server = SkyBuddyMCPServer(agent_type=agent_type)
    server.start()
