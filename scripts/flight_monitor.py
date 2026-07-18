#!/usr/bin/env python3
"""Flight price monitoring engine - tracks multiple routes and triggers alerts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from alerts import AlertsManager, PriceAlert, get_alerts_manager
from duffel_client import DuffelClient, get_duffel_client
from preferences import PreferencesManager, get_preferences_manager

ROOT = Path(__file__).resolve().parents[1]


class FlightMonitor:
    """Monitor multiple routes and manage price tracking."""

    def __init__(
        self,
        duffel_client: DuffelClient | None = None,
        preferences_manager: PreferencesManager | None = None,
        alerts_manager: AlertsManager | None = None,
    ):
        """Initialize flight monitor."""
        self.duffel = duffel_client or get_duffel_client()
        self.prefs = preferences_manager or get_preferences_manager()
        self.alerts = alerts_manager or get_alerts_manager()

    def monitor_all_routes(self) -> dict[str, list[PriceAlert]]:
        """Monitor all watched routes and return alerts triggered."""
        all_alerts = {}

        for route_name, route in self.prefs.get_all_watched_routes().items():
            alerts = self.monitor_route(route_name)
            if alerts:
                all_alerts[route_name] = alerts

        return all_alerts

    def monitor_route(self, route_name: str) -> list[PriceAlert]:
        """Monitor a single route and return alerts if triggered."""
        route = self.prefs.watched_routes.get(route_name)
        if not route:
            return []

        # Search for flights
        result = self.duffel.search_flights(
            origin=route.origin,
            destination=route.destination,
            outbound_date=route.outbound_date,
            return_date=route.return_date,
            cabin_class=self.prefs.preferences.preferred_cabin,
        )

        if not result.flights:
            return []

        # Get best price
        best_flight = min(result.flights, key=lambda f: f.price)
        current_price = best_flight.price
        currency = best_flight.currency

        # Update history
        self.prefs.update_price_history(route_name, current_price)

        # Check if should alert
        alerts_triggered = []
        if self.prefs.should_alert(route_name, current_price):
            alert = self.alerts.create_alert(
                route_name=route_name,
                origin=route.origin,
                destination=route.destination,
                current_price=current_price,
                currency=currency,
                previous_price=route.lowest_price_found,
                alert_type="price_drop",
                booking_url=best_flight.booking_url,
            )
            alerts_triggered.append(alert)

        return alerts_triggered

    def search_and_add_route(
        self,
        name: str,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str | None = None,
        target_price: float | None = None,
    ) -> dict:
        """Search for flights and add route to watched list."""
        # Search for flights
        result = self.duffel.search_flights(
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            cabin_class=self.prefs.preferences.preferred_cabin,
        )

        # Add to watched routes
        route = self.prefs.add_watched_route(
            name=name,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            target_price=target_price,
        )

        # Update with current price if available
        if result.flights:
            best_flight = min(result.flights, key=lambda f: f.price)
            self.prefs.update_price_history(name, best_flight.price)

            return {
                "route_name": name,
                "flights_found": len(result.flights),
                "best_price": best_flight.price,
                "currency": best_flight.currency,
                "booking_url": best_flight.booking_url,
                "flights": [
                    {
                        "airline": f.airline,
                        "departure": f.departure_time,
                        "arrival": f.arrival_time,
                        "stops": f.stops,
                        "price": f.price,
                        "currency": f.currency,
                    }
                    for f in sorted(result.flights, key=lambda f: f.price)[:5]
                ],
            }

        return {
            "route_name": name,
            "flights_found": 0,
            "message": "No flights found for this route",
        }

    def get_route_stats(self, route_name: str) -> dict:
        """Get statistics for a watched route."""
        route = self.prefs.watched_routes.get(route_name)
        if not route:
            return {"error": f"Route '{route_name}' not found"}

        if not route.price_history:
            return {
                "route_name": route_name,
                "origin": route.origin,
                "destination": route.destination,
                "status": "No price history yet",
            }

        import statistics

        prices = list(route.price_history.values())
        stats = {
            "route_name": route_name,
            "origin": route.origin,
            "destination": route.destination,
            "outbound_date": route.outbound_date,
            "return_date": route.return_date,
            "lowest_price": route.lowest_price_found,
            "highest_price": max(prices),
            "average_price": statistics.mean(prices),
            "median_price": statistics.median(prices),
            "std_dev": statistics.stdev(prices) if len(prices) > 1 else 0,
            "observations": len(prices),
            "target_price": route.target_price,
            "last_checked": route.last_checked,
        }

        if route.target_price:
            stats["percent_to_target"] = (
                (route.target_price - route.lowest_price_found) / route.lowest_price_found
            ) * 100

        return stats

    def print_monitoring_report(self) -> None:
        """Print monitoring report for all routes."""
        routes = self.prefs.get_all_watched_routes()
        if not routes:
            print("No routes being monitored. Add a route first with search_and_add_route().")
            return

        print("\n" + "=" * 120)
        print("FLIGHT MONITORING REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 120 + "\n")

        for route_name in routes:
            stats = self.get_route_stats(route_name)
            print(f"Route: {stats.get('route_name', 'N/A')}")
            print(f"  {stats.get('origin', 'N/A')} → {stats.get('destination', 'N/A')}")
            print(f"  Dates: {stats.get('outbound_date', 'N/A')} to {stats.get('return_date', 'N/A')}")

            if "observations" in stats:
                print(f"  Price Range: {stats.get('lowest_price', 'N/A')} - {stats.get('highest_price', 'N/A')}")
                print(f"  Average: {stats.get('average_price', 'N/A'):.2f}")
                print(f"  Median: {stats.get('median_price', 'N/A'):.2f}")
                print(f"  Observations: {stats.get('observations', 'N/A')}")

                if stats.get("target_price"):
                    print(f"  Target: {stats['target_price']:.2f} ({stats.get('percent_to_target', 0):.1f}% away)")

            print()

        print("=" * 120 + "\n")


def main() -> None:
    """Example usage of flight monitor."""
    monitor = FlightMonitor()

    # Example: Search and add route
    result = monitor.search_and_add_route(
        name="Colombia Trip",
        origin="BIO",
        destination="BOG",
        outbound_date="2026-12-04",
        return_date="2027-01-08",
        target_price=650.0,
    )

    print("\nSearch Result:")
    print(result)

    # Print stats
    stats = monitor.get_route_stats("Colombia Trip")
    print("\nRoute Stats:")
    print(stats)

    # Print monitoring report
    monitor.print_monitoring_report()


if __name__ == "__main__":
    main()
