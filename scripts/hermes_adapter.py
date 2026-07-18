#!/usr/bin/env python3
"""SkyBuddy adapter for Hermes personal assistant.

Allows Hermes to access all SkyBuddy flight tracking capabilities
through natural language requests and workflow actions.
"""
from __future__ import annotations

from agent_integration import SkyBuddyAgent, AgentType


class HermesAdapter:
    """Adapter for Hermes agent to use SkyBuddy."""

    def __init__(self):
        """Initialize Hermes adapter."""
        self.skybuddy = SkyBuddyAgent(agent_type=AgentType.HERMES)
        self._register_hermes_actions()

    def _register_hermes_actions(self) -> None:
        """Register SkyBuddy actions with Hermes."""
        # These would be registered with Hermes' action system
        actions = {
            "search_flights": self.search_and_recommend,
            "monitor_flights": self.monitor_routes,
            "check_prices": self.check_prices,
            "book_flights": self.prepare_booking,
            "check_points": self.check_loyalty_points,
            "manage_trips": self.manage_trips,
        }

        for action_name, action_func in actions.items():
            self.register_action(action_name, action_func)

    def register_action(self, name: str, func) -> None:
        """Register an action with Hermes."""
        # This would integrate with Hermes' action registration
        # For now, store for reference
        pass

    # ========== FLIGHT SEARCH & RECOMMENDATIONS ==========

    def search_and_recommend(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str = None,
        **kwargs,
    ) -> str:
        """Search flights and get AI recommendations for Hermes."""
        result = self.skybuddy.search_flights(
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            **kwargs,
        )

        # Format for Hermes natural language output
        if result.get("status") == "success":
            output = f"Found {result['flights_found']} flights from {origin} to {destination}.\n\n"

            output += "Top Recommendations:\n"
            for rec in result.get("top_recommendations", [])[:3]:
                output += f"\n#{rec['rank']}: {rec['airline']} - {result['currency']} {rec['price']:.0f}\n"
                output += f"  Score: {rec['score']:.0f}/100\n"
                output += f"  Duration: {rec['duration_hours']:.1f} hours | Stops: {rec['stops']}\n"
                output += f"  Reasons: {', '.join(rec['reasons'][:2])}\n"
                output += f"  Book: {rec['booking_url']}\n"

            return output
        else:
            return f"No flights found for {origin} → {destination} on {outbound_date}"

    # ========== MONITORING ==========

    def monitor_routes(self, *routes: tuple[str, str, str, str]) -> str:
        """Monitor multiple routes with Hermes."""
        added = []

        for route_data in routes:
            if len(route_data) >= 4:
                name, origin, dest, date = route_data[:4]
                target = route_data[4] if len(route_data) > 4 else None

                result = self.skybuddy.add_route(
                    name=name,
                    origin=origin,
                    destination=dest,
                    outbound_date=date,
                    target_price=target,
                )

                if result.get("flights_found", 0) > 0:
                    added.append(
                        f"✓ {name}: Best price {result['best_price']:.0f} {result['currency']}"
                    )

        if added:
            return "Monitoring routes:\n" + "\n".join(added)
        else:
            return "No routes added to monitoring."

    def check_prices(self) -> str:
        """Check prices on all monitored routes for Hermes."""
        result = self.skybuddy.check_all_routes()

        if result["alerts_triggered"] > 0:
            output = f"🚨 {result['alerts_triggered']} deals found!\n\n"

            for route_name, alert_data in result.get("summary", {}).items():
                output += f"{route_name}:\n"
                for alert in alert_data["alerts"]:
                    output += f"  Price: {alert['currency']} {alert['price']:.0f} "
                    output += f"(↓ {alert['drop']})\n"

            return output
        else:
            return f"No price alerts. Monitoring {result['routes_checked']} route(s)."

    # ========== BOOKINGS ==========

    def prepare_booking(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: str = None,
        passengers: list[str] = None,
    ) -> str:
        """Prepare booking with passenger info for Hermes."""
        if not passengers:
            return "Please provide passenger names for booking."

        # Get passenger details
        pax_data = self.skybuddy.passengers.get_passengers_for_booking(passengers)

        if len(pax_data) != len(passengers):
            missing = set(passengers) - set(pax_data.keys())
            return f"Missing passenger profiles: {', '.join(missing)}. Please add them first."

        # Search flights
        result = self.skybuddy.search_flights(
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            passengers=len(pax_data),
        )

        if result.get("status") != "success":
            return "No flights available for booking."

        output = f"Booking preparation for {len(pax_data)} passenger(s):\n\n"

        for pax_name in passengers:
            pax = pax_data[pax_name]
            output += f"- {pax.given_name} {pax.family_name} (DOB: {pax.born_on})\n"

        output += f"\nTop flight options:\n"
        for i, rec in enumerate(result.get("top_recommendations", [])[:2], 1):
            output += f"\n{i}. {rec['airline']} - {result['currency']} {rec['price']:.0f}\n"
            output += f"   Duration: {rec['duration_hours']:.1f}h | Stops: {rec['stops']}\n"

        return output

    # ========== LOYALTY & POINTS ==========

    def check_loyalty_points(self) -> str:
        """Check loyalty points balance for Hermes."""
        programs = self.skybuddy.loyalty.list_programs()

        if not programs:
            return "No loyalty programs tracked. Add your programs first."

        output = "Your loyalty point balances:\n\n"

        total_points = 0
        for prog in programs:
            output += f"{prog.program}: {prog.balance:,} points ({prog.tier})\n"
            total_points += prog.balance

        output += f"\nTotal: {total_points:,} points"

        return output

    def estimate_earnings(self, flight_cost: float) -> str:
        """Estimate points earned on flight for Hermes."""
        cards = self.skybuddy.loyalty.list_cards()

        if not cards:
            return "No credit cards tracked. Add your cards first."

        earnings = self.skybuddy.loyalty.estimate_earnings(flight_cost)

        output = f"Points earned on EUR {flight_cost:,.0f} flight:\n\n"

        for card in cards:
            points = earnings.get(card.id, 0)
            output += f"{card.issuer} {card.product}: {points:,.0f} points\n"

        total = sum(earnings.values())
        output += f"\nTotal potential: {total:,.0f} points"

        return output

    # ========== TRIP MANAGEMENT ==========

    def manage_trips(self, action: str, trip_name: str = None) -> str:
        """Manage trips for Hermes."""
        if action == "list":
            routes = self.skybuddy.list_routes()
            if routes["total"] == 0:
                return "No trips being tracked."

            output = f"Your trips ({routes['total']}):\n\n"
            for route in routes.get("routes", []):
                output += f"• {route.get('route_name', 'N/A')}\n"
                output += f"  {route.get('origin', '?')} → {route.get('destination', '?')}\n"
                output += f"  Best price: {route.get('lowest_price', 'N/A')}\n\n"

            return output

        elif action == "remove":
            if not trip_name:
                return "Please provide trip name to remove."

            if self.skybuddy.prefs.remove_watched_route(trip_name):
                return f"✓ Removed trip '{trip_name}' from monitoring."
            else:
                return f"Trip '{trip_name}' not found."

        else:
            return "Unknown trip action. Use 'list' or 'remove'."


def create_hermes_adapter() -> HermesAdapter:
    """Factory function for Hermes adapter."""
    return HermesAdapter()
