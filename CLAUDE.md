# SkyBuddy - Claude Code Integration Guide

## Overview

SkyBuddy is a complete flight tracking and monitoring system that works with any agent or LLM. This guide explains how to use it with Claude Code and Claude AI.

## Quick Start with Claude

### 1. Use via MCP Server

```bash
# Start the MCP server
cd scripts
python mcp_server.py

# Claude can now call all SkyBuddy methods directly
```

### 2. Use Directly in Claude Code

```python
from agent_integration import create_agent

# Create agent
sky = create_agent()

# Search flights
result = sky.search_flights(
    origin="BIO",
    destination="BOG",
    outbound_date="2026-12-04",
    return_date="2027-01-08"
)

# Add route to monitor
sky.add_route(
    name="Colombia Trip",
    origin="BIO",
    destination="BOG",
    outbound_date="2026-12-04",
    return_date="2027-01-08",
    target_price=650
)

# Check for alerts
alerts = sky.get_alerts(hours=24)

# Manage loyalty
sky.add_card("amex-plat", "American Express", "Platinum", points_per_dollar=1.5)
earnings = sky.estimate_earnings(5000)  # Flight cost in EUR
```

## Available Methods

### Search & Recommendations

**`search_flights(origin, destination, outbound_date, return_date=None, passengers=1, cabin_class="economy")`**

Returns flights with AI-scored recommendations.

```python
result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")
# Returns:
# {
#   "flights_found": 15,
#   "best_price": 677,
#   "currency": "EUR",
#   "flights": [...],
#   "top_recommendations": [
#     {
#       "rank": 1,
#       "score": 95,
#       "airline": "Avianca",
#       "price": 677,
#       "reasons": ["Excellent price", "Non-stop", ...]
#     },
#     ...
#   ]
# }
```

### Monitoring

**`add_route(name, origin, destination, outbound_date, return_date=None, target_price=None)`**

Add a route to monitor for price changes.

```python
sky.add_route(
    name="Work Trip",
    origin="JFK",
    destination="LHR",
    outbound_date="2026-08-01",
    return_date="2026-08-15",
    target_price=500  # Alert when below $500
)
```

**`list_routes()`**

Get all monitored routes with current stats.

```python
routes = sky.list_routes()
# Returns stats for each route: lowest price, median, trend
```

**`check_all_routes()`**

Check all routes and trigger alerts.

```python
alerts = sky.check_all_routes()
# Returns alerts triggered, with prices and savings
```

### Alerts

**`get_alerts(hours=24)`**

Get recent price alerts.

```python
recent_alerts = sky.get_alerts(hours=24)
# Returns: time, route, price, savings %, booking URL
```

### Preferences

**`get_preferences()`**

Get current travel preferences.

```python
prefs = sky.get_preferences()
# Returns: preferred airlines, times, max duration, cabin, etc.
```

**`set_preferences(**kwargs)`**

Update preferences.

```python
sky.set_preferences(
    preferred_airlines=["United", "Lufthansa"],
    preferred_departure_time="morning",
    max_stops=2,
    preferred_cabin="business"
)
```

### Loyalty & Points

**`add_card(card_id, issuer, product, points_per_dollar=1.0, **kwargs)`**

Add credit card.

```python
sky.add_card(
    card_id="amex-plat",
    issuer="American Express",
    product="Platinum",
    points_per_dollar=1.5,
    transfer_partners=["AirFrance", "United", "Virgin"]
)
```

**`list_cards()`**

Get all credit cards.

**`add_loyalty_program(program, balance, tier="member")`**

Add loyalty program.

```python
sky.add_loyalty_program(
    program="Amex Membership Rewards",
    balance=150000,
    tier="platinum"
)
```

**`estimate_earnings(flight_cost)`**

Estimate points earned on flight.

```python
earnings = sky.estimate_earnings(5000)  # EUR 5,000 flight
# Returns: points per card + total potential
```

### Passengers

**`add_passenger(name, given_name, family_name, born_on, gender, **kwargs)`**

Add traveler profile.

```python
sky.add_passenger(
    name="harold",
    given_name="Harold",
    family_name="Mateo",
    born_on="1990-05-15",
    gender="M",
    passport="AB123456",
    nationality="CO"
)
```

**`list_passengers()`**

Get all passenger profiles.

## Workflows

### Find Cheap Flights

```python
# Search with recommendations
result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")

# Get top recommendation
best = result["top_recommendations"][0]
print(f"Recommended: {best['airline']} for {best['currency']} {best['price']}")
print(f"Score: {best['score']}/100")
print(f"Book: {best['booking_url']}")
```

### Monitor Multiple Trips

```python
trips = [
    ("Colombia", "BIO", "BOG", "2026-12-04", "2027-01-08", 650),
    ("Europe", "BIO", "LHR", "2026-08-01", "2026-08-15", 500),
    ("USA", "BIO", "JFK", "2026-07-01", "2026-07-15", 700),
]

for name, orig, dest, out, ret, target in trips:
    sky.add_route(name, orig, dest, out, ret, target)

# Check all
alerts = sky.check_all_routes()
if alerts["alerts_triggered"] > 0:
    print(f"🚨 Found {alerts['alerts_triggered']} deals!")
```

### Estimate Trip Cost

```python
# Search flights
result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08", passengers=2)

best_price = result["best_price"]
num_passengers = 2
total_cost = best_price * num_passengers

# Estimate earnings
earnings = sky.estimate_earnings(total_cost)

print(f"Trip cost: EUR {total_cost:,.0f} for {num_passengers} passengers")
print(f"Potential points: {earnings['total_points']:,}")
```

## Data Files

- `config/search_config.json` — Route configuration
- `config/preferences.json` — Auto-created with preferences & watched routes
- `config/passengers.json` — Auto-created with passenger profiles
- `config/cards.json` — Auto-created with loyalty cards & programs
- `data/price_observations.csv` — Manual price data entry
- `data/alerts.json` — Alert history

## Using with Agents

### Hermes

```python
from hermes_adapter import create_hermes_adapter

hermes = create_hermes_adapter()

# Hermes can now use:
# "Find cheap flights from Bilbao to Bogota in December"
# "Monitor these flights and alert me when below €650"
# "How many Amex points will I earn on this flight?"
```

### OpenClaw

```python
from openclaw_adapter import OpenClawMCPServer

server = OpenClawMCPServer()

# OpenClaw receives full MCP schema and can:
# - Search flights
# - Monitor routes
# - Check prices
# - Manage loyalty programs
```

### Direct API (Claude)

```python
from agent_integration import create_agent

sky = create_agent()

# Full programmatic access to all methods
```

## Environment Variables

```bash
# Optional: Real-time flight search
export DUFFEL_API_KEY="your_duffel_key"

# Optional: Email alerts
export ALERT_EMAIL_FROM="your_email@gmail.com"
export ALERT_EMAIL_PASSWORD="your_app_password"
export ALERT_EMAIL_TO="recipient@example.com"
```

## Common Patterns

### Pattern 1: Find & Monitor

```python
# Search
result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")
best = result["top_recommendations"][0]

# If good, monitor
sky.add_route(
    name="Booked Flight",
    origin="BIO",
    destination="BOG",
    outbound_date="2026-12-04",
    return_date="2027-01-08",
    target_price=best["price"] - 50  # Alert if drops further
)
```

### Pattern 2: Loyalty Optimization

```python
# Check points available
progs = sky.skybuddy.loyalty.list_programs()

# Estimate earnings on flight
result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")
earnings = sky.estimate_earnings(result["best_price"])

# Choose card with highest points
best_card = max(earnings["earnings"], key=lambda x: x["points"])
print(f"Use {best_card['card']} for {best_card['points']} points")
```

### Pattern 3: Multi-Passenger Booking

```python
# Add all passengers
passengers = ["Harold", "Jane", "John"]
for pax_name in passengers:
    # Add profile (assuming details available)
    pass

# Search for group
result = sky.search_flights(
    "BIO", "BOG", "2026-12-04",
    return_date="2027-01-08",
    passengers=len(passengers)
)

# Prepare booking with all details
booking = sky.skybuddy.passengers.get_passengers_for_booking(passengers)
```

## Tips & Best Practices

1. **Set Preferences First** — Configure airlines, times, cabin before searching
2. **Monitor Multiple Routes** — Track variation over time for better deals
3. **Set Realistic Targets** — Target prices below median, not arbitrary values
4. **Check Loyalty** — Estimate earnings to maximize rewards
5. **Use Recommendations** — AI scoring accounts for multiple factors
6. **Save Passengers** — Pre-create profiles for quick multi-passenger bookings

## Troubleshooting

**No flights found?**
- Check date format (YYYY-MM-DD)
- Try flexible dates (add route monitoring to catch deals)
- Check airport codes (verify IATA codes)

**Preferences not saving?**
- Check config folder permissions
- Ensure JSON is valid in config/preferences.json

**Alerts not triggering?**
- Verify target_price is set when adding route
- Check price_alert_threshold_percent in preferences
- Review get_alerts() to confirm alerts created

## Support

- **GitHub:** https://github.com/HaroldMate1/SkyBuddy
- **Issues:** https://github.com/HaroldMate1/SkyBuddy/issues
- **Docs:** This file + README.md

## Contributing

Feel free to extend SkyBuddy with:
- New flight APIs (Kayak, Skyscanner native)
- Additional loyalty programs
- Better recommendation scoring
- Email/SMS notifications
- Web dashboard

---

**SkyBuddy: Intelligent flight tracking for humans and agents.** ✈️
