#!/usr/bin/env python3
"""Apply the latest consolidated Google Flights sweep to fare history."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote


def fare(value: dict[str, Any] | None) -> str:
    return "unavailable" if value is None else str(value["price_eur"])


def details(label: str, itinerary: dict[str, Any] | None) -> str:
    if itinerary is None:
        return f"{label}: not returned"
    return (
        f"{label}: €{itinerary['price_eur']:.2f}, {itinerary['outbound_date']} to "
        f"{itinerary['return_date']}, {itinerary['outbound_stops']} outbound stop(s), "
        f"{itinerary['return_stops']} return stop(s), {itinerary['total_duration_minutes']} total minutes"
    )


def google_url(origin: str, destination: str, outbound: str, return_date: str) -> str:
    query = quote(f"{origin} to {destination} {outbound} to {return_date}")
    return f"https://www.google.com/travel/flights?q={query}&curr=EUR&hl=es&gl=ES"


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--input", default="data/google_flights_latest.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    failures = payload.get("query_failures", [])
    if failures:
        raise SystemExit(f"Refusing to apply incomplete sweep: {len(failures)} query failure(s)")
    python = Path(sys.executable)
    history_script = Path(__file__).with_name("fare_history.py")
    base = [str(python), str(history_script), "--root", str(root)]
    observed_at = payload["observed_at"]
    source = payload["source"]

    cabin_candidates: list[tuple[dict[str, Any], str]] = []
    checked_candidates: list[tuple[dict[str, Any], str]] = []
    applied: list[str] = []
    for carrier_result in payload["carriers"]:
        carrier = carrier_result["carrier"]
        cabin = carrier_result["cabin_only"]
        checked = carrier_result["one_checked_bag"]
        primary = cabin or checked
        if primary is None:
            continue
        if cabin:
            cabin_candidates.append((cabin, carrier))
        if checked:
            checked_candidates.append((checked, carrier))
        url = google_url(payload["origin"], payload["destination"], primary["outbound_date"], primary["return_date"])
        date_pairs = payload["queries_attempted"] // 2
        notes = (
            f"Complete {date_pairs}-pair flexible-window Google sweep. {details('Cabin only', cabin)}. "
            f"{details('One checked bag filter', checked)}. Bag weight/fare family not exposed by fli."
        )
        command = base + [
            "record-airline",
            "--observed-at", observed_at,
            "--airline", carrier,
            "--no-bag", fare(cabin),
            "--checked-bag", fare(checked),
            "--source", source,
            "--url", url,
            "--outbound", primary["outbound_date"],
            "--return-date", primary["return_date"],
            "--notes", notes,
        ]
        run(command)
        applied.append(carrier)

    if not cabin_candidates:
        raise SystemExit("Sweep contained no cabin-only fare")
    cabin_winner, cabin_carrier = min(
        cabin_candidates,
        key=lambda item: (item[0]["price_eur"], item[0]["outbound_stops"] + item[0]["return_stops"], item[0]["total_duration_minutes"]),
    )
    checked_winner: dict[str, Any] | None = None
    checked_carrier = ""
    if checked_candidates:
        checked_winner, checked_carrier = min(
            checked_candidates,
            key=lambda item: (item[0]["price_eur"], item[0]["outbound_stops"] + item[0]["return_stops"], item[0]["total_duration_minutes"]),
        )
    winner_url = google_url(payload["origin"], payload["destination"], cabin_winner["outbound_date"], cabin_winner["return_date"])
    summary_notes = (
        f"Complete {payload['queries_attempted'] // 2}-pair flexible-window Google sweep; {payload['queries_attempted']} queries, "
        f"{payload['itineraries_returned']} itineraries, {len(applied)} carrier combinations. "
        f"Cabin winner {cabin_carrier}: {details('fare', cabin_winner)}. "
        f"Checked winner {checked_carrier or 'none'}: {details('fare', checked_winner)}. "
        "Checked result uses Google's one-bag filter; weight/fare family not exposed."
    )
    command = base + [
        "record",
        "--observed-at", observed_at,
        "--origin", payload["origin"],
        "--destination", payload["destination"],
        "--no-bag", str(cabin_winner["price_eur"]),
        "--checked-bag", fare(checked_winner),
        "--airline", cabin_carrier,
        "--checked-airline", checked_carrier or cabin_carrier,
        "--checked-outbound", checked_winner["outbound_date"] if checked_winner else cabin_winner["outbound_date"],
        "--checked-return", checked_winner["return_date"] if checked_winner else cabin_winner["return_date"],
        "--source", source,
        "--url", winner_url,
        "--outbound", cabin_winner["outbound_date"],
        "--return-date", cabin_winner["return_date"],
        "--notes", summary_notes,
    ]
    summary = run(command)
    print(json.dumps({
        "applied_carriers": applied,
        "cabin_winner": {**cabin_winner, "carrier": cabin_carrier},
        "checked_winner": ({**checked_winner, "carrier": checked_carrier} if checked_winner else None),
        "history_summary": summary,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
