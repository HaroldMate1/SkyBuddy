#!/usr/bin/env python3
"""MCP Server for Alfred - Flight tracking capabilities via Model Context Protocol."""
from __future__ import annotations

import json
from typing import Any

from alerts import get_alerts_manager
from flight_monitor import FlightMonitor
from flight_scraper import generate_search_urls, parse_args
from preferences import get_preferences_manager


class AlfredFlightServer:
    """Flight tracking MCP server for Alfred integration."""

    def __init__(self):
        """Initialize Alfred flight server."""
        self.monitor = FlightMonitor()
        self.prefs = get_preferences_manager()
        self.alerts = get_alerts_manager()

    def search_flights(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str | None = None,
        passengers: int = 1,
        cabin_class: str = "economy",
    ) -> dict[str, Any]:
        """Search for flights on a route.

        Args:
            origin: IATA code (e.g., 'BIO')
            destination: IATA code (e.g., 'BOG')
            outbound_date: Date in YYYY-MM-DD format
            return_date: Optional return date
            passengers: Number of passengers
            cabin_class: Cabin class preference

        Returns:
            Search results with flights and booking URLs
        """
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
                "search_urls": generate_search_urls(
                    {
                        "origin": origin,
                        "destination": destination,
                        "outbound_target_date": outbound_date,
                        "return_target_date": return_date,
                    }
                ),
            }

        return {
            "origin": origin,
            "destination": destination,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "flights_found": len(result.flights),
            "best_price": min(f.price for f in result.flights),
            "currency": result.flights[0].currency,
            "flights": [
                {
                    "airline": f.airline,
                    "departure": f.departure_time,
                    "arrival": f.arrival_time,
                    "duration_hours": f.duration_minutes / 60,
                    "stops": f.stops,
                    "price": f.price,
                    "currency": f.currency,
                    "booking_url": f.booking_url,
                }
                for f in sorted(result.flights, key=lambda f: f.price)[:5]
            ],
        }

    def add_watched_route(
        self,
        name: str,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str | None = None,
        target_price: float | None = None,
    ) -> dict[str, Any]:
        """Add a route to watch for price changes.

        Args:
            name: Friendly name for the route
            origin: IATA code
            destination: IATA code
            outbound_date: Departure date
            return_date: Return date (optional)
            target_price: Alert when price drops below this

        Returns:
            Confirmation and current price info
        """
        return self.monitor.search_and_add_route(
            name=name,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            target_price=target_price,
        )

    def list_watched_routes(self) -> dict[str, Any]:
        """List all currently watched routes.

        Returns:
            Dictionary of route names and their current status
        """
        routes = self.prefs.get_all_watched_routes()
        if not routes:
            return {"routes": [], "message": "No routes being monitored"}

        result = {
            "routes": [],
            "total": len(routes),
        }

        for route_name in routes:
            stats = self.monitor.get_route_stats(route_name)
            result["routes"].append(stats)

        return result

    def remove_watched_route(self, route_name: str) -> dict[str, Any]:
        """Stop watching a route.

        Args:
            route_name: Name of the route to remove

        Returns:
            Confirmation of removal
        """
        success = self.prefs.remove_watched_route(route_name)
        return {
            "route_name": route_name,
            "removed": success,
            "message": f"Route '{route_name}' removed" if success else f"Route '{route_name}' not found",
        }

    def monitor_all(self) -> dict[str, Any]:
        """Check all watched routes for price changes and trigger alerts.

        Returns:
            Summary of alerts triggered
        """
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

    def get_preferences(self) -> dict[str, Any]:
        """Get current user preferences.

        Returns:
            Current flight preferences
        """
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
        """Update user preferences.

        Args:
            **kwargs: Preferences to update

        Returns:
            Updated preferences
        """
        self.prefs.update_preferences(**kwargs)
        return {
            "updated": True,
            "preferences": self.get_preferences(),
        }

    def get_recent_alerts(self, hours: int = 24) -> dict[str, Any]:
        """Get recent price alerts.

        Args:
            hours: Look back this many hours

        Returns:
            List of recent alerts
        """
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

    def handle_request(self, method: str, params: dict) -> dict[str, Any]:
        """Handle MCP request from Alfred.

        Args:
            method: MCP method name
            params: Method parameters

        Returns:
            Method result
        """
        methods = {
            "search_flights": self.search_flights,
            "add_watched_route": self.add_watched_route,
            "list_watched_routes": self.list_watched_routes,
            "remove_watched_route": self.remove_watched_route,
            "monitor_all": self.monitor_all,
            "get_preferences": self.get_preferences,
            "update_preferences": self.update_preferences,
            "get_recent_alerts": self.get_recent_alerts,
        }

        if method not in methods:
            return {"error": f"Unknown method: {method}"}

        try:
            return methods[method](**params)
        except Exception as e:
            return {"error": str(e)}


def create_mcp_server() -> AlfredFlightServer:
    """Create an MCP server instance."""
    return AlfredFlightServer()


if __name__ == "__main__":
    # Test the server
    server = create_mcp_server()

    # Example: Search flights
    print("=== Search Flights ===")
    result = server.search_flights(
        origin="BIO",
        destination="BOG",
        outbound_date="2026-12-04",
        return_date="2027-01-08",
    )
    print(json.dumps(result, indent=2, default=str))

    # Example: Add watched route
    print("\n=== Add Watched Route ===")
    result = server.add_watched_route(
        name="Colombia Trip",
        origin="BIO",
        destination="BOG",
        outbound_date="2026-12-04",
        return_date="2027-01-08",
        target_price=650.0,
    )
    print(json.dumps(result, indent=2, default=str))

    # Example: List routes
    print("\n=== List Watched Routes ===")
    result = server.list_watched_routes()
    print(json.dumps(result, indent=2, default=str))
