# Long-haul seat advisory

SkyBuddy includes a lightweight seat-intelligence workflow for flights or itineraries over **8 hours**. It is based on the practical workflow shown in the referenced travel reel:

1. **FlightAware** — confirm the exact operating flight and aircraft type/subtype.
2. **SeatMaps** — inspect the airline-specific aircraft cabin map before choosing seats.

This is deliberately a verification workflow, not a magic “best seat” oracle. The same aircraft model can have different layouts by airline, cabin refit, route, season or last-minute aircraft swap.

## CLI usage

```bash
python scripts/seat_advisor.py \
  --airline Iberia \
  --flight-number "IB 6131" \
  --aircraft "Airbus A350-900" \
  --duration-minutes 610 \
  --cabin economy
```

The command returns JSON with:

- whether the flight crosses the 8-hour threshold;
- a `FlightAware` link for aircraft confirmation;
- a `SeatMaps` search link for the airline/aircraft/cabin map;
- a configuration warning;
- seat-selection tips covering lavatories, galleys, exit rows, bulkheads, sleep and aisle access.

## Agent workflow

For long-haul options, an agent should:

1. Identify flight number, operating airline, duration and aircraft when available.
2. Run `scripts/seat_advisor.py`.
3. Open the FlightAware result and confirm the operating aircraft.
4. Use the confirmed airline + aircraft in SeatMaps.
5. Report seat advice only as verified or unverified; never infer the exact seat map from aircraft model alone.

## Caveats

- FlightAware aircraft details can change close to departure.
- SeatMaps may lag airline refits or aircraft swaps.
- Paid seat availability must still be checked in the airline or booking checkout.
- SeatGuru-style sources may be useful as legacy references, but they are not part of this implemented reel workflow and should not override current airline/SeatMaps evidence.
