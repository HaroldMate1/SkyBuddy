<p align="center">
  <img src="assets/skybuddy-logo.jpg" alt="SkyBuddy" width="220">
</p>

<h1 align="center">SkyBuddy</h1>

<p align="center">
  <strong>Flight tracking your agent can actually act on.</strong><br>
  Search fares, watch routes, compare every price against a year of history —
  then hand any MCP agent an auditable booking intent for the exact flight link.
</p>

<p align="center">
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HaroldMate1.SkyBuddy&title=repo%20visits&color=4ea1ff" alt="Repository visits">
  <img src="https://img.shields.io/github/stars/HaroldMate1/SkyBuddy?style=flat&color=4ea1ff" alt="Stars">
  <img src="https://img.shields.io/github/forks/HaroldMate1/SkyBuddy?style=flat&color=7c5cff" alt="Forks">
  <img src="https://img.shields.io/github/last-commit/HaroldMate1/SkyBuddy?color=35e0a1" alt="Last commit">
  <img src="https://github.com/HaroldMate1/SkyBuddy/actions/workflows/tests.yml/badge.svg" alt="Tests">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/protocol-MCP-black" alt="MCP">
</p>

---

## Table of contents

- [What SkyBuddy does](#what-skybuddy-does)
- [The website](#the-website)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Features in depth](#features-in-depth)
  - [1. Flight search](#1-flight-search)
  - [2. Price monitoring and alerts](#2-price-monitoring-and-alerts)
  - [3. Recommendation engine](#3-recommendation-engine)
  - [4. 365-day price baseline and buy signal](#4-365-day-price-baseline-and-buy-signal)
  - [5. Agent booking trigger](#5-agent-booking-trigger)
  - [6. Seat selection](#6-seat-selection)
  - [7. Loyalty, points and passengers](#7-loyalty-points-and-passengers)
  - [8. Flexible-date Google Flights sweeps](#8-flexible-date-google-flights-sweeps)
- [MCP tool reference](#mcp-tool-reference)
- [Python API reference](#python-api-reference)
- [Deploying the website to Vercel](#deploying-the-website-to-vercel)
- [Measuring usage](#measuring-usage)
- [Files and data](#files-and-data)
- [Environment variables](#environment-variables)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing, license, support](#contributing-license-support)

---

## What SkyBuddy does

SkyBuddy is a production-grade flight toolkit written in plain Python. Every capability is an
independent module you can call from the CLI, from Python, or through the bundled MCP server —
so Claude, Hermes, OpenClaw or your own agent all get the same 24 tools.

| | Capability | Module |
|---|---|---|
| 🔎 | Real-time search across Duffel plus 7 booking sources | `flight_scraper.py`, `duffel_client.py` |
| 📈 | Unlimited watched routes with full price history | `flight_monitor.py`, `preferences.py` |
| 🔔 | Target-price, below-median and price-drop alerts | `alerts.py` |
| 🧠 | Transparent 0–100 flight scoring with written reasons | `recommendations.py` |
| 📉 | **365-day price baseline and buy/wait verdict** | `price_baseline.py` |
| 🎫 | **Booking intents an agent can execute on the flight link** | `booking_agent.py` |
| 💺 | Seat-map workflow across FlightAware, SeatMaps and 4 more sites | `seat_advisor.py` |
| 📅 | Flexible-date Google Flights sweeps, both baggage modes | `google_flights_monitor.py` |
| 💳 | Credit cards, loyalty balances and points estimation | `loyalty_cards.py` |
| 🧳 | Traveller profiles ready for checkout | `passenger_profiles.py` |
| 📊 | Fare history store and rendered dashboard | `fare_history.py`, `dashboard.py` |
| 🤖 | One MCP surface for every agent | `mcp_server.py`, `agent_integration.py` |

---

## The website

A ready-to-deploy landing page lives in [`web/`](web) and ships with a `vercel.json`, so the
repository deploys to Vercel as-is. See [Deploying the website to Vercel](#deploying-the-website-to-vercel).

<p align="center">
  <img src="assets/screenshots/site-hero.jpg" alt="SkyBuddy landing page hero: an agent session that searches, evaluates the price against a year of history and creates a booking intent" width="900">
</p>

<p align="center"><em>Hero — the full loop, from search to a booking intent awaiting confirmation.</em></p>

<p align="center">
  <img src="assets/screenshots/site-features.jpg" alt="Feature grid showing flight search, monitoring, alerts, recommendations, flexible-date sweeps and the 365-day baseline" width="900">
</p>

<p align="center"><em>Features — every capability, mapped to the module that implements it.</em></p>

<p align="center">
  <img src="assets/screenshots/site-agent-booking.jpg" alt="Agent booking section explaining booking intents, human confirmation and the price ceiling" width="900">
</p>

<p align="center"><em>Agent booking — how the purchase trigger works, and what stops it.</em></p>

<p align="center">
  <img src="assets/screenshots/site-quickstart.jpg" alt="Quick start section with tabbed CLI, Python, MCP and booking commands" width="900">
</p>

<p align="center"><em>Quick start — CLI, Python, MCP and booking commands side by side.</em></p>

<p align="center">
  <img src="assets/screenshots/site-mcp-tools.jpg" alt="Table of MCP tools any agent can call" width="900">
</p>

<p align="center"><em>MCP surface — the tools any agent can call.</em></p>

---

## Quick start

```bash
git clone https://github.com/HaroldMate1/SkyBuddy.git
cd SkyBuddy
pip install -r requirements.txt

# optional: live fares through Duffel
export DUFFEL_API_KEY="your_key_here"
```

```bash
# 1 · search a route (uses config/search_config.json, or pass arguments)
python scripts/flight_scraper.py BIO BOG 2026-12-04 2027-01-08 EUR

# 2 · analyse the fares you have collected
python scripts/analyze_prices.py

# 3 · monitor every watched route and raise alerts
python scripts/flight_monitor.py

# 4 · ask what a good price actually is (365 days of history by default)
python scripts/price_baseline.py scan --origin BIO --destination BOG
python scripts/price_baseline.py evaluate --origin BIO --destination BOG --price 684

# 5 · let the history decide and create the purchase trigger
python scripts/price_baseline.py trigger \
  --origin BIO --destination BOG --outbound-date 2026-12-04 \
  --price 684 --airline Iberia --passenger harold \
  --booking-url "https://www.iberia.com/…"
```

From Python:

```python
import sys; sys.path.insert(0, "scripts")
from agent_integration import create_agent

sky = create_agent()

result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")
for rec in result["top_recommendations"]:
    print(rec["score"], rec["airline"], rec["price"], rec["booking_url"])
```

As an MCP server:

```bash
python scripts/mcp_server.py claude
```

```json
{
  "mcpServers": {
    "skybuddy": {
      "command": "python",
      "args": ["scripts/mcp_server.py", "claude"],
      "cwd": "/path/to/SkyBuddy"
    }
  }
}
```

---

## Configuration

Copy the example and edit it:

```bash
cp config/search_config.example.json config/search_config.json
```

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

Travel preferences live in `config/preferences.json` and feed the recommendation engine:

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

---

## Features in depth

### 1. Flight search

`flight_scraper.py` builds direct search URLs for **Google Flights, Avianca, Iberia, KLM, Air France,
Kayak and Skyscanner**. `duffel_client.py` adds live pricing when `DUFFEL_API_KEY` is set, returning
`Flight` objects with airline, price, duration, stops and a booking URL.

```bash
python scripts/flight_scraper.py               # uses the config file
python scripts/flight_scraper.py JFK LHR 2026-08-15 2026-08-25 GBP
```

### 2. Price monitoring and alerts

Watch as many routes as you like. Every check writes to the route's own history **and** to the
long-term baseline, so each run makes the next buy decision better informed.

```python
from flight_monitor import FlightMonitor

monitor = FlightMonitor()
monitor.search_and_add_route("Colombia Trip", "BIO", "BOG",
                             "2026-12-04", "2027-01-08", target_price=650)
alerts = monitor.monitor_all_routes()
```

Alert triggers:

| Trigger | Condition |
|---|---|
| Great deal | 15%+ below the historical median |
| Good deal | 10%+ below the historical median |
| Target reached | At or below your target price |
| Price drop | Significant fall from the previous observation |

### 3. Recommendation engine

Every fare is scored 0–100 and comes with its reasons:

```
Score = 40% price + 30% duration + 20% stops + 10% your preferences
```

### 4. 365-day price baseline and buy signal

`price_baseline.py` answers the only question that matters before buying: **is this price actually
good for this route?** It scans everything SkyBuddy has recorded — its own observation store, the
manual `price_observations.csv`, and the price history of watched routes — over a lookback window
that defaults to a **full year**, then turns a live fare into a verdict.

```bash
python scripts/price_baseline.py scan     --origin BIO --destination BOG            # baseline
python scripts/price_baseline.py record   --origin BIO --destination BOG --price 812 --airline Iberia
python scripts/price_baseline.py evaluate --origin BIO --destination BOG --price 684
```

```jsonc
// scan → the statistical baseline
{
  "days": 365, "samples": 121, "currency": "EUR",
  "minimum": 681.15, "p10": 700.28, "p25": 745.10,
  "median": 809.27, "p75": 872.40, "maximum": 958.80,
  "days_covered": 363, "recent_median_30d": 792.5,
  "trend": "falling", "trend_percent": -2.4,
  "confidence": "high",
  "buy_threshold": 700.28, "good_threshold": 745.10
}
```

| Verdict | Meaning | Books? |
|---|---|---|
| `buy_now` | At/below your target, or in the cheapest 10% of the window | ✅ |
| `good` | In the cheapest 25% of the window | ✅ |
| `fair` | At or below the median, but no standout | ❌ |
| `wait` | Above the median; history says better is likely | ❌ |
| `high` | In the most expensive quarter of the year | ❌ |

Confidence is reported honestly: with fewer than 12 observations or under 30 days of coverage the
verdict is labelled `medium`/`low`, and with no history at all SkyBuddy says so instead of guessing.

### 5. Agent booking trigger

This is the part that lets an agent **buy the ticket on the flight link** — without SkyBuddy ever
scraping a checkout behind your back.

`booking_agent.py` creates a **booking intent**: a stored, auditable object carrying the exact flight
URL, the passengers, the price you agreed to, a hard ceiling, and the checks that must pass before
money moves.

```
prepare_booking → awaiting_confirmation
       ↓ (human approves by intent id)
confirm_booking → ready_to_execute   ← price ceiling re-checked here
       ↓
get_booking_playbook → in_progress   ← ordered steps for the agent
       ↓
mark_booking_executed → booked | failed
```

```bash
# 1 · create the intent from a flight link
python scripts/booking_agent.py prepare \
  --booking-url "https://www.iberia.com/…" \
  --airline Iberia --origin BIO --destination BOG \
  --outbound-date 2026-12-04 --return-date 2027-01-08 \
  --price 684 --currency EUR --passenger harold --max-price 700 \
  --flight-number "IB 6585" --aircraft "Airbus A350-900" --duration-minutes 620

# 2 · approve it explicitly
python scripts/booking_agent.py confirm --intent-id bk_7f3a1c --approved-by harold

# 3 · hand the playbook to your agent
python scripts/booking_agent.py playbook --intent-id bk_7f3a1c
```

From an agent:

```python
sky = create_agent()

search = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")
intent = sky.prepare_booking_from_recommendation(
    search["top_recommendations"][0],
    origin="BIO", destination="BOG",
    outbound_date="2026-12-04", return_date="2027-01-08",
    passengers=["harold"], max_price=700,
)

sky.confirm_booking(intent["intent_id"], approved_by="harold", current_price=684.0)
playbook = sky.get_booking_playbook(intent["intent_id"])
```

Or fully automatic, driven by the year of history:

```python
sky.auto_book_if_deal(
    origin="BIO", destination="BOG",
    outbound_date="2026-12-04", return_date="2027-01-08",
    price=684.0, airline="Iberia",
    booking_url="https://www.iberia.com/…",
    passengers=["harold"], target_price=700,
)
# verdict buy_now → intent created, still awaiting your confirmation
```

**The playbook** the agent receives:

| Step | What the agent does | Abort condition |
|---|---|---|
| `open_link` | Opens the exact booking URL | Page redirects somewhere unrelated |
| `verify_itinerary` | Confirms route, dates, cabin, carrier | Anything differs from the intent |
| `verify_price` | Confirms the total is at or below the ceiling | Total above the ceiling |
| `fill_passengers` | Fills traveller data from stored profiles | Names cannot be matched to passports |
| `check_seats` | *(over 8 h)* aircraft check + cabin map before choosing seats | Configuration cannot be verified |
| `select_extras` | Applies agreed baggage/seats, declines upsells | Extras push the total over the ceiling |
| `stop_before_payment` | **Stops at payment and hands control back** | — |
| `record_result` | Stores the confirmation code in the audit trail | — |

**Safety rules, enforced in code:**

- An intent starts in `awaiting_confirmation`; nothing runs until a human approves it by id.
- `confirm_booking` re-validates the live price against the ceiling and refuses on breach.
- The playbook **stops before payment** unless payment authority was granted for that single intent.
- Non-HTTPS links and hosts outside the known booking sources are flagged in `warnings`.
- Every transition is appended to the intent's `history` for a complete audit trail.

### 6. Seat selection

`seat_advisor.py` implements a verification workflow rather than guessing a "best seat", because the
same aircraft model flies in different configurations.

**Primary workflow** (in order): **FlightAware** → confirm the operating aircraft, then **SeatMaps** →
inspect the airline-specific cabin map.

**Cross-check sources**, returned with the exact query to run on each site:

| Site | Role | Why |
|---|---|---|
| SeatGuru | cross-check | Colour-coded good/bad seat annotations per aircraft version |
| aeroLOPA | cross-check | High-accuracy airline-specific cabin diagrams |
| ExpertFlyer | availability | Live seat availability and alerts when a seat opens up |
| Flightradar24 | verify | Second source for the aircraft actually flying the route |
| Airline "manage my booking" | act | Where the seat is actually assigned |

Plus `seat_selection_actions()`: what to do at booking, after booking, and in the 24–48 h check-in
window when blocked exit rows and bulkheads are released.

```bash
python scripts/seat_advisor.py --airline Iberia --flight-number "IB 6131" \
  --aircraft "Airbus A350-900" --duration-minutes 610 --cabin economy
```

When a booking intent carries `duration_minutes` over 480, the seat check is inserted into the
booking playbook automatically. Full caveats: [docs/seat-advisory.md](docs/seat-advisory.md).

### 7. Loyalty, points and passengers

```python
from loyalty_cards import get_loyalty_manager

loyalty = get_loyalty_manager()
loyalty.add_card("amex-plat", "American Express", "Platinum", points_per_dollar=1.5)
loyalty.estimate_earnings(5000)     # → {"amex-plat": 7500.0}
```

```python
from passenger_profiles import get_passenger_manager

passengers = get_passenger_manager()
passengers.add_passenger("harold", "Harold", "Mateo", "1990-05-15", "M",
                         passport="AB123456", nationality="CO")
```

### 8. Flexible-date Google Flights sweeps

```bash
pip install -r requirements-monitor.txt
python scripts/google_flights_monitor.py --root /path/to/private-monitor \
  --origin BIO --destination BOG \
  --outbound-start 2026-12-02 --outbound-end 2026-12-06 \
  --return-start 2027-01-06 --return-end 2027-01-10
python scripts/apply_google_flights_results.py --root /path/to/private-monitor
```

Every date pair is queried in both baggage modes, and every pure or mixed carrier combination Google
returns is kept — no fixed airline list. Details: [docs/google-flights-monitor.md](docs/google-flights-monitor.md).

---

## MCP tool reference

All 24 tools are exposed by `scripts/mcp_server.py` to every agent type.

| Tool | Parameters | Returns |
|---|---|---|
| `search_flights` | `origin`, `destination`, `outbound_date`, `return_date?`, `passengers?`, `cabin_class?` | Fares plus top-3 scored recommendations |
| `add_route` | `name`, `origin`, `destination`, `outbound_date`, `return_date?`, `target_price?` | Watched route confirmation |
| `list_routes` | — | Watched routes with stats |
| `check_all_routes` | — | Routes checked and alerts triggered |
| `get_alerts` | `hours?` | Recent alerts |
| `get_preferences` | — | Current preferences |
| `set_preferences` | any preference field | Updated preferences |
| `add_card` | `card_id`, `issuer`, `product`, `points_per_dollar` | Card added |
| `list_cards` | — | All cards |
| `add_loyalty_program` | `program`, `balance`, `tier?` | Program added |
| `estimate_earnings` | `flight_cost` | Points per card |
| `add_passenger` | `name`, `given_name`, `family_name`, `born_on`, `gender`, … | Profile added |
| `list_passengers` | — | All profiles |
| `prepare_booking` | `booking_url`, `airline`, `origin`, `destination`, `outbound_date`, `price`, `passengers?`, `max_price?`, `allow_payment?`, `flight_number?`, `aircraft?`, `duration_minutes?` | Intent `awaiting_confirmation` |
| `confirm_booking` | `intent_id`, `approved_by`, `current_price?`, `allow_payment?` | Intent `ready_to_execute` + playbook |
| `get_booking_playbook` | `intent_id` | Ordered agent steps + seat advisory |
| `mark_booking_executed` | `intent_id`, `confirmation_code?`, `amount_paid?`, `success?` | Final intent state |
| `cancel_booking` | `intent_id`, `reason?` | Cancelled intent |
| `list_bookings` | `status?` | Intents and audit trail |
| `get_price_baseline` | `origin`, `destination`, `days?`, `outbound_date?` | Min, percentiles, median, trend, confidence |
| `evaluate_price` | `origin`, `destination`, `price`, `days?`, `target_price?` | Verdict, percentile, reasons |
| `auto_book_if_deal` | `origin`, `destination`, `outbound_date`, `price`, `booking_url`, `airline?`, `passengers?`, `target_price?`, `max_price?` | Assessment, and the intent if it wins |
| `record_price_observation` | `origin`, `destination`, `price`, `currency?`, `airline?`, … | Stored observation |
| `get_seat_advisory` | `airline`, `duration_minutes`, `aircraft?`, `flight_number?`, `cabin?` | Workflow, sources, tips, actions |

---

## Python API reference

Every public function, grouped by module. Add `scripts/` to `sys.path` (or run from `scripts/`).

<details open>
<summary><strong>agent_integration.py</strong> — the unified agent surface</summary>

`create_agent(agent_type)` → `SkyBuddyAgent`; `AgentType.HERMES | OPENCLAW | CLAUDE | GENERIC`

`SkyBuddyAgent`: `search_flights`, `add_route`, `list_routes`, `check_all_routes`, `get_alerts`,
`get_preferences`, `set_preferences`, `add_card`, `list_cards`, `add_loyalty_program`,
`estimate_earnings`, `add_passenger`, `list_passengers`, `prepare_booking`,
`prepare_booking_from_recommendation`, `confirm_booking`, `get_booking_playbook`,
`mark_booking_executed`, `cancel_booking`, `list_bookings`, `get_price_baseline`,
`record_price_observation`, `evaluate_price`, `auto_book_if_deal`, `get_seat_advisory`,
`register_callback`, `trigger_callback`, `to_json`
</details>

<details>
<summary><strong>booking_agent.py</strong> — the purchase trigger</summary>

`get_booking_agent()` → `BookingAgent` · `BookingIntent` dataclass (with `log()`)

`BookingAgent`: `prepare_booking`, `confirm_booking`, `build_playbook`, `get_booking_playbook`,
`mark_executed`, `cancel_booking`, `list_bookings`, `get_booking`, `save`

Constants: `AWAITING`, `READY`, `IN_PROGRESS`, `BOOKED`, `CANCELLED`, `FAILED`, `KNOWN_BOOKING_DOMAINS`

CLI: `prepare · confirm · playbook · executed · cancel · list · show`
</details>

<details>
<summary><strong>price_baseline.py</strong> — history and buy signal</summary>

`get_price_baseline()` → `PriceBaseline` · `get_buy_engine()` → `BuyDecisionEngine`

`PriceBaseline`: `record_price`, `record_many`, `collect`, `build`, `evaluate`

`BuyDecisionEngine`: `auto_book_if_deal`

Dataclasses: `PriceObservation`, `Baseline`.
Constants: `DEFAULT_LOOKBACK_DAYS` (365), `MIN_CONFIDENT_SAMPLES`, `VERDICT_BUY`, `VERDICT_GOOD`,
`VERDICT_FAIR`, `VERDICT_WAIT`, `VERDICT_HIGH`, `BUY_WORTHY`

CLI: `scan · record · evaluate · trigger`
</details>

<details>
<summary><strong>seat_advisor.py</strong> — seat intelligence</summary>

`build_seat_advisory(...)`, `cli_payload(...)`, `workflow_steps`, `seat_map_sources`,
`cross_check_sources`, `seat_selection_actions`, `selection_tips`,
`flightaware_url`, `flightaware_query`, `seatmaps_url`, `seatmaps_query`,
`seatguru_url`, `aerolopa_url`, `expertflyer_url`, `flightradar24_url`

Constant: `LONG_HAUL_THRESHOLD_MINUTES` (480)
</details>

<details>
<summary><strong>flight_monitor.py · flight_scraper.py · duffel_client.py</strong> — search and watching</summary>

`FlightMonitor`: `monitor_all_routes`, `monitor_route`, `search_and_add_route`, `get_route_stats`,
`print_monitoring_report`

`flight_scraper`: `load_config`, `parse_args`, `generate_search_urls`, and one generator per source —
`generate_google_flights_url`, `generate_avianca_url`, `generate_iberia_url`, `generate_klm_url`,
`generate_air_france_url`, `generate_kayak_url`, `generate_skyscanner_url`

`duffel_client`: `get_duffel_client()` → `DuffelClient.search_flights`; dataclasses `Flight`,
`FlightSearchResult`
</details>

<details>
<summary><strong>preferences.py · alerts.py · recommendations.py</strong> — state and scoring</summary>

`get_preferences_manager()` → `PreferencesManager`: `add_watched_route`, `remove_watched_route`,
`update_price_history`, `should_alert`, `get_all_watched_routes`, `update_preferences`, `save`
— dataclasses `FlightPreferences`, `WatchedRoute`

`get_alerts_manager()` → `AlertsManager`: `create_alert`, `get_recent_alerts`, `get_alerts_by_route`,
`format_alert_message`, `send_email_alert`, `print_alert`, `save_alerts` — dataclass `PriceAlert`

`get_recommendation_engine()` → `RecommendationEngine`: `score_flight`, `recommend_flights`,
`format_recommendation`, `print_recommendations` — dataclass `FlightRecommendation`
</details>

<details>
<summary><strong>loyalty_cards.py · passenger_profiles.py</strong> — traveller data</summary>

`get_loyalty_manager()` → `LoyaltyManager`: `add_card`, `remove_card`, `list_cards`,
`add_loyalty_program`, `update_balance`, `list_programs`, `get_total_points`, `can_book_with_points`,
`estimate_earnings`, `print_summary` — dataclasses `CreditCard`, `LoyaltyProgram`

`get_passenger_manager()` → `PassengerManager`: `add_passenger`, `get_passenger`, `list_passengers`,
`remove_passenger`, `add_frequent_flyer`, `get_passengers_for_booking` — dataclass `PassengerProfile`
</details>

<details>
<summary><strong>Analysis, history and presentation</strong></summary>

`analyze_prices.py` / `analyze_prices_v2.py`: `load_observations`, `main` — dataclass `Observation`

`fare_history.py`: `command_record`, `command_record_airline`, `command_status`, `command_should_alert`,
`command_mark_sent`, `summary`, `render_graph`, `load_rows`, `write_rows`, `load_state`, `write_state`

`dashboard.py`: `render_dashboard`, `parse_iso`, `eur`, `short_date`

`google_flights_monitor.py`: `collect_google_flights`, `run_query`, `itinerary_summary`, `date_range`,
`carrier_name`, `airline_name`

`apply_google_flights_results.py`: `run`, `google_url`, `details`, `fare`

`flight_formatter.py`: `get_formatter()` → `FlightFormatter`: `format_time`, `format_duration`,
`format_leg`, `format_itinerary`, `format_flight_option`, `format_search_results`, `print_flight_deals`
— dataclasses `FlightLeg`, `BookingItinerary`
</details>

<details>
<summary><strong>Agent adapters</strong></summary>

`mcp_server.py`: `SkyBuddyMCPServer`: `list_tools`, `call_tool`, `handle_request`, `start`

`hermes_adapter.py`: `create_hermes_adapter()` → `HermesAdapter`: `search_and_recommend`,
`monitor_routes`, `check_prices`, `prepare_booking`, `check_loyalty_points`, `estimate_earnings`,
`manage_trips`, `register_action`

`openclaw_adapter.py`: `create_openclaw_adapter()` → `OpenClawAdapter`: `get_schema`,
`process_tool_call`, `to_mcp_response`, `validate_input`; plus `OpenClawMCPServer.handle_request`

`legacy_mcp_server.py` / `legacy_mcp_server_v2.py`: `create_mcp_server()` — legacy legacy servers
</details>

---

## Deploying the website to Vercel

The site is static — no build step, no dependencies.

1. Push this repository to GitHub.
2. In Vercel: **Add New → Project → Import** `HaroldMate1/SkyBuddy`.
3. Leave every field at its default. `vercel.json` already sets framework *none*, no build command and
   `outputDirectory: "web"`.
4. **Deploy.**

Or from the CLI:

```bash
npm i -g vercel
vercel          # preview deployment
vercel --prod   # production
```

Local preview:

```bash
python -m http.server 8899 --directory web
# → http://localhost:8899
```

Editing: `web/index.html` (content), `web/styles.css` (design tokens at the top), `web/app.js`
(quick-start tabs and the live GitHub star/fork counter).

---

## Measuring usage

| Signal | Where | Notes |
|---|---|---|
| **Repo visits** | The visits badge at the top of this README | Counts README/badge loads, per `page_id=HaroldMate1.SkyBuddy` |
| **Stars / forks** | Badges above, and live on the website hero | Fetched from the GitHub API by `web/app.js` |
| **Clones & unique visitors** | GitHub → **Insights → Traffic** | Owner-only; 14-day rolling window |
| **Website traffic** | Vercel → Project → **Analytics** | Enable in the Vercel dashboard; no code change needed |
| **Release downloads** | GitHub → Releases | Per-asset counters |

> The visits badge is a third-party image service. If it ever fails to load, the badge simply does not
> render — nothing else in the README is affected.

---

## Files and data

```
SkyBuddy/
├── web/                       # Vercel landing page (index.html, styles.css, app.js, logo)
├── vercel.json                # static deploy config
├── scripts/                   # all Python modules (see the API reference)
├── tests/                     # unittest suite, run in CI
├── docs/                      # seat advisory + Google Flights monitoring guides
├── config/
│   ├── search_config.json     # route configuration
│   ├── preferences.json       # preferences and watched routes
│   ├── passengers.json        # traveller profiles
│   └── cards.json             # cards and loyalty programs
├── data/
│   ├── price_baseline.csv     # long-term observation store (365-day scans)
│   ├── price_observations.csv # manual/collector observations
│   ├── bookings.json          # booking intents and audit trail
│   └── alerts.json            # alert history
└── assets/                    # logo and website screenshots
```

Everything under `config/` and `data/` is git-ignored — your travel data stays local.

---

## Environment variables

```bash
DUFFEL_API_KEY=your_api_key          # live flight search

ALERT_EMAIL_FROM=you@gmail.com       # optional email alerts
ALERT_EMAIL_PASSWORD=app_password
ALERT_EMAIL_TO=recipient@example.com
```

---

## Testing

```bash
python -m unittest discover -s tests -v
```

The suite covers the seat advisory, fare history, Google Flights collection, the booking-intent
lifecycle (ceilings, confirmation, payment stops, audit trail) and the price baseline (windowing,
verdicts, auto-trigger). CI runs it on every push via `.github/workflows/tests.yml`.

---

## Roadmap

- [ ] Web dashboard backed by the baseline store
- [ ] Email digest of the week's verdicts
- [ ] Native Kayak / Skyscanner APIs
- [ ] Carbon footprint per itinerary
- [ ] Award-flight calculator

---

## Contributing, license, support

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
Issues and ideas: [GitHub Issues](https://github.com/HaroldMate1/SkyBuddy/issues).

Open source, free to use for personal travel planning.
Built by [Harold Mateo](https://github.com/HaroldMate1).

---

<p align="center"><strong>SkyBuddy — track it, score it, book it.</strong> ✈️</p>
