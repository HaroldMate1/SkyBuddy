#!/usr/bin/env python3
"""User flight preferences and watched routes management."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
PREFS_FILE = ROOT / "config" / "preferences.json"


@dataclass
class FlightPreferences:
    """User flight preferences."""

    preferred_airlines: list[str] = field(default_factory=list)
    avoided_airlines: list[str] = field(default_factory=list)
    preferred_departure_time: str = "morning"  # morning, afternoon, evening
    max_flight_duration_hours: int = 15
    max_stops: int = 2
    preferred_cabin: str = "economy"
    price_alert_threshold_percent: int = 10  # Alert when X% below median
    preferred_currency: str = "EUR"


@dataclass
class WatchedRoute:
    """A route to monitor for price changes."""

    name: str
    origin: str
    destination: str
    outbound_date: str
    return_date: Optional[str] = None
    target_price: Optional[float] = None
    created_at: str = ""
    last_checked: Optional[str] = None
    lowest_price_found: Optional[float] = None
    price_history: dict[str, float] = field(default_factory=dict)


class PreferencesManager:
    """Manage user preferences and watched routes."""

    def __init__(self, prefs_file: Path = PREFS_FILE):
        """Initialize preferences manager."""
        self.prefs_file = prefs_file
        self.preferences = self._load_preferences()
        self.watched_routes = self._load_watched_routes()

    def _load_preferences(self) -> FlightPreferences:
        """Load preferences from file."""
        if not self.prefs_file.exists():
            return FlightPreferences()

        try:
            with open(self.prefs_file) as f:
                data = json.load(f)
                prefs_data = data.get("preferences", {})
                return FlightPreferences(**prefs_data)
        except Exception as e:
            print(f"Error loading preferences: {e}")
            return FlightPreferences()

    def _load_watched_routes(self) -> dict[str, WatchedRoute]:
        """Load watched routes from file."""
        if not self.prefs_file.exists():
            return {}

        try:
            with open(self.prefs_file) as f:
                data = json.load(f)
                routes_data = data.get("watched_routes", {})
                return {
                    name: WatchedRoute(**route_data) for name, route_data in routes_data.items()
                }
        except Exception as e:
            print(f"Error loading watched routes: {e}")
            return {}

    def save(self) -> None:
        """Save preferences and routes to file."""
        self.prefs_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "preferences": asdict(self.preferences),
            "watched_routes": {
                name: asdict(route) for name, route in self.watched_routes.items()
            },
        }

        with open(self.prefs_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_watched_route(
        self,
        name: str,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: Optional[str] = None,
        target_price: Optional[float] = None,
    ) -> WatchedRoute:
        """Add a route to watch."""
        from datetime import datetime

        route = WatchedRoute(
            name=name,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            target_price=target_price,
            created_at=datetime.now().isoformat(),
        )

        self.watched_routes[name] = route
        self.save()
        return route

    def remove_watched_route(self, name: str) -> bool:
        """Remove a watched route."""
        if name in self.watched_routes:
            del self.watched_routes[name]
            self.save()
            return True
        return False

    def update_price_history(self, route_name: str, price: float) -> None:
        """Update price history for a route."""
        from datetime import datetime

        if route_name not in self.watched_routes:
            return

        route = self.watched_routes[route_name]
        today = datetime.now().strftime("%Y-%m-%d")

        route.price_history[today] = price
        route.last_checked = datetime.now().isoformat()

        if route.lowest_price_found is None or price < route.lowest_price_found:
            route.lowest_price_found = price

        self.save()

    def should_alert(self, route_name: str, current_price: float) -> bool:
        """Check if should alert for price change."""
        if route_name not in self.watched_routes:
            return False

        route = self.watched_routes[route_name]

        # Alert if below target price
        if route.target_price and current_price <= route.target_price:
            return True

        # Alert if below historical median + threshold
        if len(route.price_history) > 1:
            import statistics

            prices = list(route.price_history.values())
            median = statistics.median(prices)
            threshold = median * (1 - self.preferences.price_alert_threshold_percent / 100)

            if current_price <= threshold:
                return True

        return False

    def get_all_watched_routes(self) -> dict[str, WatchedRoute]:
        """Get all watched routes."""
        return self.watched_routes

    def update_preferences(self, **kwargs) -> None:
        """Update preferences."""
        for key, value in kwargs.items():
            if hasattr(self.preferences, key):
                setattr(self.preferences, key, value)
        self.save()


def get_preferences_manager() -> PreferencesManager:
    """Get or create preferences manager singleton."""
    return PreferencesManager()
