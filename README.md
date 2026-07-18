# SkyBuddy — AI-Powered Flight Tracking for Everyone

Production-grade flight price tracking with real-time search, smart monitoring, price alerts, and multi-agent integration. Works with any agent: Hermes, OpenClaw, Claude, or your own.

## Features

### Core Flight Tracking
- **Real-time Flight Search** — Multiple booking sources for any route
- **Intelligent Price Monitoring** — Track unlimited routes simultaneously
- **Smart Alerts** — Notifications when prices drop below targets
- **Historical Analysis** — Price trends and statistical insights
- **Flexible Google Flights Sweeps** — Every date pair, carrier combination, and baggage mode
- **Best Fares Highlighted** — Automatic deal detection

### Advanced Features
- **AI Recommendations** — Flights scored based on your preferences
- **Loyalty Integration** — Track credit cards and points programs
- **Passenger Profiles** — Store traveler information for quick bookings
- **Multi-Agent Support** — Works with Hermes, OpenClaw, Claude, or any MCP-compatible agent
- **Beautiful Formatting** — Professional itinerary displays
- **Preference Engine** — Airline preferences, time preferences, cabin classes

### Multi-Agent Compatible
- ✅ **Hermes Agent** — Personal assistant workflows
- ✅ **OpenClaw Agent** — Flight claw MCP integration
- ✅ **Claude** — Direct API usage
- ✅ **Any MCP Server** — Model Context Protocol support
- ✅ **Standalone** — CLI and programmatic APIs

## Quick Start

### Installation

```bash
git clone https://github.com/HaroldMate1/SkyBuddy.git
cd SkyBuddy
pip install -r requirements.txt

# Optional: Set up Duffel API for real-time search
export DUFFEL_API_KEY="your_key_here"
```

### Configuration

Edit `config/search_config.json`:

```json
{
  "origin": "BIO",
  "destination": "BOG",
  "outbound_target_date": "2026-12-04",
  "return_target_date": "2027-01-08",
  "passengers": 1,
  "cabin": "economy",
  "currency": "EUR",
  "sources": ["Google Flights", "Avianca", "Iberia", "KLM", "Air France"]
}
```

### Usage

#### 1. Search Flights (Any Route)

```bash
# Uses config
python scripts/flight_scraper.py

# Custom route
python scripts/flight_scraper.py JFK LHR 2026-08-15 2026-08-25 GBP
```

#### 2. Analyze Prices

```bash
python scripts/analyze_prices.py
```

Shows formatted table with:
- All fares sorted by price
- Deal indicators (10-15% below median)
- Best option highlighted
- Direct booking links

#### 3. Monitor Routes

```bash
python scripts/flight_monitor.py
```

Tracks multiple routes with:
- Automatic price checking
- Price history & trends
- Smart alert triggers
- Target price notifications

#### 4. Sweep Flexible Google Flights Dates

Install the optional monitor dependencies, run every date pair in both baggage modes, then apply the complete result:

```bash
pip install -r requirements-monitor.txt
python scripts/google_flights_monitor.py --root /path/to/private-monitor --origin BIO --destination BOG --outbound-start 2026-12-02 --outbound-end 2026-12-06 --return-start 2027-01-06 --return-end 2027-01-10
python scripts/apply_google_flights_results.py --root /path/to/private-monitor
```

This includes every pure or mixed carrier combination Google returns; it does not rely on a fixed airline list. See [Flexible Google Flights monitoring](docs/google-flights-monitor.md) for setup, alerting and data-source caveats.

#### 5. Use With Your Agent

**For Hermes:**
```python
from skybuddy.agent_integration import HermesIntegration

hermes = HermesIntegration()
hermes.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")
```

**For OpenClaw:**
```python
from skybuddy.agent_integration import OpenClawIntegration

openclaw = OpenClawIntegration()
openclaw.monitor_routes()
```

**For Claude/MCP:**
```bash
python scripts/mcp_server.py
```

Then use via Claude's tools.

## Architecture

### Core Modules

- **`flight_scraper.py`** — Generate booking URLs (7 sources)
- **`flight_monitor.py`** — Track price changes across routes
- **`google_flights_monitor.py`** — Flexible-date Google Flights collection across baggage modes
- **`apply_google_flights_results.py`** — Persist every returned carrier and both winners
- **`fare_history.py` / `dashboard.py`** — Alert-safe history and generated fare dashboard
- **`duffel_client.py`** — Real-time Duffel API integration
- **`preferences.py`** — User preferences & watched routes
- **`alerts.py`** — Price alert management
- **`recommendations.py`** — AI flight scoring engine
- **`loyalty_cards.py`** — Credit card & points tracking
- **`passenger_profiles.py`** — Traveler information storage
- **`flight_formatter.py`** — Beautiful output formatting

### Agent Integration

- **`mcp_server.py`** — MCP Protocol server (all agents)
- **`agent_integration.py`** — Unified agent interface
- **`hermes_adapter.py`** — Hermes agent integration
- **`openclaw_adapter.py`** — OpenClaw agent integration

### Data Storage

- `config/search_config.json` — Route configuration
- `config/preferences.json` — User preferences & watched routes
- `config/passengers.json` — Traveler profiles
- `config/cards.json` — Credit cards & loyalty programs
- `data/price_observations.csv` — Manual price data
- `data/alerts.json` — Alert history

## MCP Server Methods (All Agents)

```python
# Search & Booking
search_flights(origin, destination, outbound_date, return_date)

# Monitoring
add_watched_route(name, origin, destination, dates, target_price)
list_watched_routes()
monitor_all()
get_recent_alerts(hours)

# Preferences
get_preferences()
update_preferences(**kwargs)

# Loyalty
add_credit_card(id, issuer, product, points_per_dollar, ...)
list_cards()
add_loyalty_balance(program, balance, tier)
list_loyalty_programs()
estimate_points_earnings(flight_cost)

# Passengers
add_passenger(name, given_name, family_name, born_on, gender, ...)
list_passengers()
```

## Example Workflows

### Search & Get Recommendations

```bash
python scripts/flight_scraper.py BIO BOG 2026-12-04 2027-01-08
# Results include top 3 AI-scored recommendations with reasons
```

### Monitor Multiple Routes

```python
from skybuddy.flight_monitor import FlightMonitor

monitor = FlightMonitor()

# Add routes to watch
monitor.search_and_add_route("Colombia Trip", "BIO", "BOG", "2026-12-04", "2027-01-08", target_price=650)
monitor.search_and_add_route("Europe Trip", "BIO", "LHR", "2026-08-01", "2026-08-15", target_price=500)

# Check all routes
alerts = monitor.monitor_all_routes()
```

### Estimate Points Earnings

```python
from skybuddy.loyalty_cards import get_loyalty_manager

loyalty = get_loyalty_manager()

# Add cards
loyalty.add_card("amex-plat", "American Express", "Platinum", points_per_dollar=1.5)
loyalty.add_card("chase-sapphire", "Chase", "Sapphire Preferred", points_per_dollar=2.0)

# Estimate earnings on $5,000 flight
earnings = loyalty.estimate_earnings(5000)
# Returns: amex-plat: 7,500 points, chase-sapphire: 10,000 points
```

## Multi-Agent Integration

### Hermes Agent

```python
from skybuddy.hermes_adapter import HermesAdapter

adapter = HermesAdapter()

# Hermes can now:
# - Ask: "Find flights from Bilbao to Bogota in December"
# - Ask: "Monitor these flights and alert me when below €700"
# - Ask: "How many points will I earn on this flight?"
```

### OpenClaw Agent

```python
from skybuddy.openclaw_adapter import OpenClawAdapter

adapter = OpenClawAdapter()

# OpenClaw can now:
# - Search flights
# - Track prices
# - Get recommendations
# - Manage loyalty programs
```

### Claude/MCP

```bash
# Start MCP server
python scripts/mcp_server.py

# Claude can now call all SkyBuddy methods directly
```

## Configuration Examples

### Set Travel Preferences

```json
{
  "preferred_airlines": ["Avianca", "Iberia"],
  "avoided_airlines": ["Frontier"],
  "preferred_departure_time": "morning",
  "max_flight_duration_hours": 18,
  "max_stops": 2,
  "preferred_cabin": "economy",
  "price_alert_threshold_percent": 10,
  "preferred_currency": "EUR"
}
```

### Add Credit Cards

```python
loyalty.add_card(
    card_id="amex-plat",
    issuer="American Express",
    product="Platinum",
    network="amex",
    region="US",
    points_per_dollar=1.5,
    transfer_partners=["AirFrance", "United", "Virgin"],
    notes="Great for flights to Europe"
)
```

### Add Passenger

```python
passengers.add_passenger(
    name="harold",
    given_name="Harold",
    family_name="Mateo",
    born_on="1990-05-15",
    gender="M",
    title="mr",
    passport="AB123456",
    nationality="CO"
)
```

## Price Deal Logic

- **Great Deal:** 15%+ below historical median
- **Good Deal:** 10%+ below historical median
- **Target Alert:** Reaches your target price
- **Price Drop:** Significant change from previous observation

## Recommendation Scoring

Flights are scored 0-100 based on:
- **40%** Price (normalized vs. median)
- **30%** Duration
- **20%** Number of stops
- **10%** Your preferences (time, airline, cabin)

## Environment Variables

```bash
# Duffel API (for real-time search)
DUFFEL_API_KEY=your_api_key

# Email alerts (optional)
ALERT_EMAIL_FROM=your_email@gmail.com
ALERT_EMAIL_PASSWORD=your_app_password
ALERT_EMAIL_TO=recipient@example.com
```

## Support

Works with:
- **Personal Agents:** Hermes, Hermes
- **Multi-Agent Platforms:** OpenClaw
- **LLMs:** Claude (via MCP)
- **Frameworks:** Custom agents via MCP protocol

## License

Open source. Use freely for personal travel planning.

## Contributing

Contributions welcome! Areas for enhancement:
- Additional flight APIs (Kayak, Skyscanner native)
- More loyalty program integrations
- Mobile app
- Web dashboard
- Email digests

## Roadmap

- [ ] Web interface for price tracking
- [ ] Email price digest reports
- [ ] Mobile push notifications
- [ ] Group booking discounts
- [ ] Carbon footprint tracking
- [ ] Airline-specific perks tracker
- [ ] Award flight calculator

---

**SkyBuddy: Your intelligent flight companion for any agent.** ✈️
