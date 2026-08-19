# SkyBuddy Setup Instructions

## Initial GitHub Setup

SkyBuddy is ready to push to GitHub! Follow these steps:

### 1. Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: **SkyBuddy**
3. Description: "AI-powered flight tracking for any agent - Hermes, OpenClaw, Claude, or your own"
4. Make it **Public** (so others can use it)
5. Do NOT initialize with README (already exists)
6. Click "Create repository"

### 2. Push to GitHub

Run these commands from the SkyBuddy directory:

```bash
cd /path/to/SkyBuddy

# Add remote
git remote add origin https://github.com/HaroldMate1/SkyBuddy.git

# Rename branch to main
git branch -M main

# Push
git push -u origin main
```

### 3. Verify

Visit: https://github.com/HaroldMate1/SkyBuddy

You should see:
- README.md with full documentation
- CLAUDE.md with integration guide
- scripts/ folder with all modules
- config/ with example configuration
- This SETUP.md file

## Project Structure

```
SkyBuddy/
├── README.md                    # Main documentation
├── CLAUDE.md                    # Claude/LLM integration guide
├── SETUP.md                     # This file
├── requirements.txt             # Python dependencies
├── config/
│   ├── search_config.example.json   # Route config template
│   ├── search_config.json           # Your config (auto-created)
│   ├── preferences.json             # Preferences (auto-created)
│   ├── passengers.json              # Passengers (auto-created)
│   └── cards.json                   # Loyalty cards (auto-created)
├── data/
│   ├── price_observations.csv       # Manual price data
│   └── alerts.json                  # Alert history (auto-created)
├── scripts/
│   ├── __init__.py
│   ├── agent_integration.py         # Universal agent interface
│   ├── mcp_server.py                # MCP protocol server
│   ├── hermes_adapter.py            # Hermes integration
│   ├── openclaw_adapter.py          # OpenClaw integration
│   ├── flight_scraper.py            # URL generator (7 sources)
│   ├── flight_monitor.py            # Price monitoring
│   ├── duffel_client.py             # Real-time flight search
│   ├── preferences.py               # Preferences management
│   ├── alerts.py                    # Alert system
│   ├── recommendations.py           # AI flight scoring
│   ├── loyalty_cards.py             # Loyalty tracking
│   ├── passenger_profiles.py        # Traveler management
│   ├── flight_formatter.py          # Output formatting
│   ├── analyze_prices.py            # Price analysis
│   └── ... (legacy scripts)
└── docs/
    └── (future documentation)
```

## Installation

```bash
# Clone
git clone https://github.com/HaroldMate1/SkyBuddy.git
cd SkyBuddy

# Install dependencies
pip install -r requirements.txt

# Optional: Set Duffel API key
export DUFFEL_API_KEY="your_key_here"
```

## Usage

### Command Line

```bash
# Search flights
python scripts/flight_scraper.py BIO BOG 2026-12-04 2027-01-08

# Monitor routes
python scripts/flight_monitor.py

# Analyze prices
python scripts/analyze_prices.py

# Start MCP server
python scripts/mcp_server.py
```

### With Python

```python
from scripts.agent_integration import create_agent

sky = create_agent()

# Search
result = sky.search_flights("BIO", "BOG", "2026-12-04", "2027-01-08")

# Monitor
sky.add_route("Colombia", "BIO", "BOG", "2026-12-04", "2027-01-08", target_price=650)

# Check
alerts = sky.check_all_routes()
```

### With Agent

**Hermes:**
```python
from scripts.hermes_adapter import create_hermes_adapter

hermes = create_hermes_adapter()
# "Find flights from Bilbao to Bogota in December"
```

**OpenClaw:**
```python
from scripts.openclaw_adapter import OpenClawMCPServer

server = OpenClawMCPServer()
# Use via MCP interface
```

**Claude:**
```python
# Via MCP server or direct import
from scripts.mcp_server import SkyBuddyMCPServer

server = SkyBuddyMCPServer()
```

## Configuration

### Example: Colombia Trip

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

### Set Preferences

```python
from scripts.preferences import get_preferences_manager

prefs = get_preferences_manager()
prefs.update_preferences(
    preferred_airlines=["United", "Lufthansa"],
    preferred_departure_time="morning",
    max_stops=2,
    preferred_cabin="business"
)
```

## Features

### Flight Search
- Multi-source search (Google Flights, Avianca, Iberia, KLM, Air France, Kayak, Skyscanner)
- Real-time pricing via Duffel API
- AI-powered recommendations (scored 0-100)

### Price Monitoring
- Track unlimited routes
- Automatic price checking
- Price history tracking
- Trend analysis

### Alerts
- Target price alerts
- Below-median alerts
- Price drop alerts
- Email notifications

### AI Recommendations
Flights scored on:
- Price (40%)
- Duration (30%)
- Stops (20%)
- Preferences (10%)

### Loyalty Integration
- Credit card tracking
- Loyalty points balance
- Points earning estimation
- Tier management

### Traveler Profiles
- Passenger information
- Frequent flyer numbers
- Multi-passenger bookings

## Support

### Documentation
- **README.md** - Feature documentation
- **CLAUDE.md** - Claude Code integration
- **Docstrings** - In every module

### Issues & Questions
- GitHub Issues: https://github.com/HaroldMate1/SkyBuddy/issues
- GitHub Discussions: https://github.com/HaroldMate1/SkyBuddy/discussions

## Contributing

Contributions welcome! Areas for enhancement:
- [ ] Web interface
- [ ] Email digests
- [ ] Mobile notifications
- [ ] More flight APIs
- [ ] Dashboard
- [ ] Carbon tracking

## License

Open source - use freely for personal and commercial projects.

---

**SkyBuddy: Intelligent flight tracking for humans and agents.** ✈️

Built by HaroldMate1
