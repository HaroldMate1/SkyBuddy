# Flexible Google Flights monitoring

SkyBuddy can sweep every outbound/return date pair in two baggage modes, preserve every pure or mixed carrier combination returned by Google Flights, and render a fare-history dashboard.

## What is collected

For each date pair the collector runs two searches:

1. Cabin fare with no checked bag selected
2. Fare with Google's one-checked-bag filter

The reduced JSON retains the cheapest sensible result for every carrier combination in each mode. Cabin-only and checked-bag winners are stored separately because they may use different airlines and dates.

> Google's filter confirms one checked bag but does not expose the weight allowance or fare-family rules. SkyBuddy therefore does not claim a 23 kg allowance without direct airline confirmation.

## Installation

Use a virtual environment. The monitoring dependencies are optional and do not alter SkyBuddy's core Duffel installation.

```bash
python -m venv .monitor-venv
.monitor-venv/bin/pip install -r requirements-monitor.txt
```

The `flights` package installs the `fli` executable used for structured Google Flights results.

## Run a complete flexible-date sweep

The example below searches a five-day outbound window and a five-day return window. That produces 25 date pairs and 50 Google queries because both baggage modes are checked.

```bash
.monitor-venv/bin/python scripts/google_flights_monitor.py --root /path/to/private-monitor --origin BIO --destination BOG --outbound-start 2026-12-02 --outbound-end 2026-12-06 --return-start 2027-01-06 --return-end 2027-01-10 --fli .monitor-venv/bin/fli
```

By default the collector fails closed: if any query fails, it does not replace the last complete JSON result. `--allow-partial` is available for diagnostics, but should not be used for an automated price alert.

The complete result is written atomically to:

```text
/path/to/private-monitor/data/google_flights_latest.json
```

## Apply the sweep to history and dashboard

```bash
.monitor-venv/bin/python scripts/apply_google_flights_results.py --root /path/to/private-monitor
```

This records:

- Every carrier and mixed-carrier combination returned by Google
- Bag-only combinations when no cabin-only result was returned
- The overall cabin-only winner
- The separate checked-bag winner
- Per-carrier daily history
- Alert state and a PNG dashboard

Generated files remain private and are ignored by Git:

```text
data/google_flights_latest.json
data/fare_history.csv
data/airline_history.csv
data/alert_state.json
reports/fare_history.png
```

## Alert checks

An alert is eligible only when a checked-bag fare is available and at or below the threshold.

```bash
.monitor-venv/bin/python scripts/fare_history.py --root /path/to/private-monitor should-alert --threshold 1100 --improvement 25
```

After delivering an alert, mark it as sent to prevent duplicate notifications:

```bash
.monitor-venv/bin/python scripts/fare_history.py --root /path/to/private-monitor mark-alert-sent --sent-at 2026-07-18T15:00:00+00:00
```

## Automation guidance

Run the collector first and the applier only after a successful collector exit. A scheduler should never promote partial results or infer missing airlines from an older run. Carrier coverage is dynamic; there is deliberately no fixed airline shortlist.

## Data-source caveats

- `fli` is an unofficial Google Flights client and upstream response shapes may change.
- Search prices are observations, not booking guarantees.
- Verify baggage weight, fare family and ticketing terms on the airline or booking page before purchase.
- Airline code `LH` is normalized to `Lufthansa` because `fli` 0.9.0 can label ordinary Lufthansa passenger segments as “Lufthansa Cargo.”
