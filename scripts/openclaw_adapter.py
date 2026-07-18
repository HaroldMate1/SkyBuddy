#!/usr/bin/env python3
"""SkyBuddy adapter for OpenClaw MCP framework.

Allows OpenClaw to access all SkyBuddy flight tracking capabilities
through the Model Context Protocol (MCP).
"""
from __future__ import annotations

import json
from typing import Any, Dict

from agent_integration import SkyBuddyAgent, AgentType


class OpenClawAdapter:
    """Adapter for OpenClaw to use SkyBuddy via MCP."""

    def __init__(self):
        """Initialize OpenClaw adapter."""
        self.skybuddy = SkyBuddyAgent(agent_type=AgentType.OPENCLAW)
        self.name = "SkyBuddy Flight Tracker"
        self.version = "1.0.0"

    def get_schema(self) -> Dict[str, Any]:
        """Get MCP schema for OpenClaw."""
        return {
            "name": self.name,
            "version": self.version,
            "description": "AI-powered flight tracking, monitoring, and recommendations",
            "tools": self._get_tools_schema(),
        }

    def _get_tools_schema(self) -> list[Dict[str, Any]]:
        """Get tool definitions for OpenClaw."""
        return [
            {
                "name": "search_flights",
                "description": "Search for flights and get AI-scored recommendations",
                "category": "search",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "description": "Airport code (e.g., BIO)"},
                        "destination": {"type": "string", "description": "Airport code (e.g., BOG)"},
                        "outbound_date": {
                            "type": "string",
                            "description": "Departure date (YYYY-MM-DD)",
                        },
                        "return_date": {
                            "type": "string",
                            "description": "Return date (YYYY-MM-DD, optional)",
                        },
                        "passengers": {
                            "type": "integer",
                            "description": "Number of passengers (default 1)",
                        },
                        "cabin_class": {
                            "type": "string",
                            "enum": ["economy", "business", "first"],
                            "description": "Cabin class",
                        },
                    },
                    "required": ["origin", "destination", "outbound_date"],
                },
            },
            {
                "name": "add_monitored_route",
                "description": "Add a route to monitor for price changes",
                "category": "monitoring",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                        "outbound_date": {"type": "string"},
                        "return_date": {"type": "string"},
                        "target_price": {"type": "number"},
                    },
                    "required": ["name", "origin", "destination", "outbound_date"],
                },
            },
            {
                "name": "check_monitored_routes",
                "description": "Check all monitored routes for price changes",
                "category": "monitoring",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_price_alerts",
                "description": "Get recent price alerts",
                "category": "alerts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hours": {"type": "integer", "description": "Hours lookback (default 24)"}
                    },
                },
            },
            {
                "name": "add_credit_card",
                "description": "Add credit card for points tracking",
                "category": "loyalty",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "card_id": {"type": "string"},
                        "issuer": {"type": "string"},
                        "product": {"type": "string"},
                        "points_per_dollar": {"type": "number"},
                    },
                    "required": ["card_id", "issuer", "product"],
                },
            },
            {
                "name": "estimate_points_earnings",
                "description": "Estimate points earned on flight",
                "category": "loyalty",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "flight_cost": {"type": "number", "description": "Flight cost in preferred currency"}
                    },
                    "required": ["flight_cost"],
                },
            },
            {
                "name": "add_passenger_profile",
                "description": "Add traveler profile for bookings",
                "category": "passengers",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "given_name": {"type": "string"},
                        "family_name": {"type": "string"},
                        "born_on": {"type": "string"},
                        "gender": {"type": "string", "enum": ["M", "F", "X"]},
                        "passport": {"type": "string"},
                    },
                    "required": ["name", "given_name", "family_name", "born_on", "gender"],
                },
            },
            {
                "name": "get_travel_preferences",
                "description": "Get current travel preferences",
                "category": "preferences",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "update_travel_preferences",
                "description": "Update travel preferences",
                "category": "preferences",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "preferred_airlines": {"type": "array", "items": {"type": "string"}},
                        "avoided_airlines": {"type": "array", "items": {"type": "string"}},
                        "preferred_departure_time": {
                            "type": "string",
                            "enum": ["morning", "afternoon", "evening"],
                        },
                        "max_flight_duration_hours": {"type": "integer"},
                        "max_stops": {"type": "integer"},
                        "preferred_cabin": {"type": "string"},
                    },
                },
            },
        ]

    def process_tool_call(self, tool_name: str, **params) -> Dict[str, Any]:
        """Process OpenClaw tool call."""
        handlers = {
            "search_flights": self.skybuddy.search_flights,
            "add_monitored_route": self.skybuddy.add_route,
            "check_monitored_routes": self.skybuddy.check_all_routes,
            "get_price_alerts": lambda hours=24: self.skybuddy.get_alerts(hours),
            "add_credit_card": self.skybuddy.add_card,
            "estimate_points_earnings": self.skybuddy.estimate_earnings,
            "add_passenger_profile": self.skybuddy.add_passenger,
            "get_travel_preferences": lambda: self.skybuddy.get_preferences(),
            "update_travel_preferences": lambda **kw: self.skybuddy.set_preferences(**kw),
        }

        if tool_name not in handlers:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = handlers[tool_name](**params)
            return result
        except TypeError as e:
            # Handle parameter mismatch
            return {"error": f"Invalid parameters: {str(e)}", "tool": tool_name}
        except Exception as e:
            return {"error": str(e), "tool": tool_name}

    def to_mcp_response(self, result: Dict[str, Any]) -> str:
        """Convert result to MCP response format."""
        return json.dumps(result, indent=2, default=str)

    def validate_input(self, tool_name: str, params: Dict[str, Any]) -> tuple[bool, str]:
        """Validate input parameters for a tool."""
        schema = {tool["name"]: tool["inputSchema"] for tool in self._get_tools_schema()}

        if tool_name not in schema:
            return False, f"Unknown tool: {tool_name}"

        tool_schema = schema[tool_name]
        required = tool_schema.get("required", [])

        for field in required:
            if field not in params:
                return False, f"Missing required parameter: {field}"

        return True, "Valid"


class OpenClawMCPServer:
    """OpenClaw MCP server wrapper."""

    def __init__(self):
        """Initialize OpenClaw MCP server."""
        self.adapter = OpenClawAdapter()

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OpenClaw MCP request."""
        if request.get("method") == "get_schema":
            return self.adapter.get_schema()

        elif request.get("method") == "call_tool":
            tool_name = request.get("tool")
            params = request.get("params", {})

            # Validate
            valid, msg = self.adapter.validate_input(tool_name, params)
            if not valid:
                return {"error": msg}

            # Process
            return self.adapter.process_tool_call(tool_name, **params)

        else:
            return {"error": "Unknown method"}


def create_openclaw_adapter() -> OpenClawAdapter:
    """Factory function for OpenClaw adapter."""
    return OpenClawAdapter()


if __name__ == "__main__":
    # Test
    server = OpenClawMCPServer()

    # Get schema
    schema = server.handle_request({"method": "get_schema"})
    print("OpenClaw MCP Schema:")
    print(json.dumps(schema, indent=2)[:500])

    # Test search
    result = server.handle_request(
        {
            "method": "call_tool",
            "tool": "search_flights",
            "params": {
                "origin": "BIO",
                "destination": "BOG",
                "outbound_date": "2026-12-04",
            },
        }
    )
    print("\n\nExample search result (first 300 chars):")
    print(json.dumps(result, indent=2, default=str)[:300])
