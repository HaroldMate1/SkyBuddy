#!/usr/bin/env python3
"""Transactionally apply a consolidated Google Flights sweep to fare history."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fare_history import route_key


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


def history_base(root: Path, origin: str, destination: str) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).with_name("fare_history.py")),
        "--root",
        str(root),
        "--origin",
        origin,
        "--destination",
        destination,
    ]


def recover_interrupted_promotion(live_route: Path) -> None:
    backup = live_route.parent / f".{live_route.name}.previous"
    if not backup.exists():
        return
    if live_route.exists():
        shutil.rmtree(backup)
    else:
        os.replace(backup, live_route)


def promote_route(staged_route: Path, live_route: Path) -> None:
    """Replace one route tree, rolling back if the promotion itself fails."""
    live_route.parent.mkdir(parents=True, exist_ok=True)
    backup = live_route.parent / f".{live_route.name}.previous"
    if backup.exists():
        shutil.rmtree(backup)
    had_live = live_route.exists()
    if had_live:
        os.replace(live_route, backup)
    try:
        os.replace(staged_route, live_route)
    except Exception:
        if had_live and backup.exists():
            os.replace(backup, live_route)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def apply_payload(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    failures = payload.get("query_failures", [])
    if failures:
        raise SystemExit(f"Refusing to apply incomplete sweep: {len(failures)} query failure(s)")

    origin = str(payload["origin"]).upper()
    destination = str(payload["destination"]).upper()
    key = route_key(origin, destination)
    observed_at = str(payload["observed_at"])
    source = str(payload["source"])
    date_pairs = int(payload["queries_attempted"]) // 2

    cabin_candidates: list[tuple[dict[str, Any], str]] = []
    checked_candidates: list[tuple[dict[str, Any], str]] = []
    carrier_records: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = []
    for carrier_result in payload["carriers"]:
        carrier = str(carrier_result["carrier"])
        cabin = carrier_result["cabin_only"]
        checked = carrier_result["one_checked_bag"]
        if cabin is not None:
            cabin_candidates.append((cabin, carrier))
        if checked is not None:
            checked_candidates.append((checked, carrier))
        if cabin is not None or checked is not None:
            carrier_records.append((carrier, cabin, checked))

    if not cabin_candidates:
        raise SystemExit("Sweep contained no cabin-only fare")

    def ranking(item: tuple[dict[str, Any], str]) -> tuple[float, int, int]:
        itinerary = item[0]
        return (
            float(itinerary["price_eur"]),
            int(itinerary["outbound_stops"]) + int(itinerary["return_stops"]),
            int(itinerary["total_duration_minutes"]),
        )

    cabin_winner, cabin_carrier = min(cabin_candidates, key=ranking)
    checked_winner: dict[str, Any] | None = None
    checked_carrier = ""
    if checked_candidates:
        checked_winner, checked_carrier = min(checked_candidates, key=ranking)

    cabin_url = google_url(origin, destination, cabin_winner["outbound_date"], cabin_winner["return_date"])
    checked_url = (
        google_url(origin, destination, checked_winner["outbound_date"], checked_winner["return_date"])
        if checked_winner
        else cabin_url
    )
    summary_notes = (
        f"Complete {date_pairs}-pair flexible-window Google sweep; {payload['queries_attempted']} queries, "
        f"{payload['itineraries_returned']} itineraries, {len(carrier_records)} carrier combinations. "
        f"Cabin winner {cabin_carrier}: {details('fare', cabin_winner)}. "
        f"Checked winner {checked_carrier or 'none'}: {details('fare', checked_winner)}. "
        "Checked result uses Google's one-bag filter; weight/fare family not exposed."
    )

    root.mkdir(parents=True, exist_ok=True)
    live_route = root / "routes" / key
    live_route.parent.mkdir(parents=True, exist_ok=True)
    recover_interrupted_promotion(live_route)
    with tempfile.TemporaryDirectory(prefix=".skybuddy-apply-", dir=root) as tmp:
        staging_root = Path(tmp)
        staged_route = staging_root / "routes" / key
        if live_route.exists():
            staged_route.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(live_route, staged_route)
        base = history_base(staging_root, origin, destination)

        for carrier, cabin, checked in carrier_records:
            primary = cabin or checked
            if primary is None:
                raise RuntimeError(f"carrier record unexpectedly has no fare: {carrier}")
            url = google_url(origin, destination, primary["outbound_date"], primary["return_date"])
            notes = (
                f"Complete {date_pairs}-pair flexible-window Google sweep. {details('Cabin only', cabin)}. "
                f"{details('One checked bag filter', checked)}. Bag weight/fare family not exposed by fli."
            )
            run(base + [
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
            ])

        run(base + [
            "record",
            "--observed-at", observed_at,
            "--no-bag", str(cabin_winner["price_eur"]),
            "--checked-bag", fare(checked_winner),
            "--airline", cabin_carrier,
            "--checked-airline", checked_carrier or cabin_carrier,
            "--checked-outbound", checked_winner["outbound_date"] if checked_winner else cabin_winner["outbound_date"],
            "--checked-return", checked_winner["return_date"] if checked_winner else cabin_winner["return_date"],
            "--source", source,
            "--url", cabin_url,
            "--checked-url", checked_url,
            "--outbound", cabin_winner["outbound_date"],
            "--return-date", cabin_winner["return_date"],
            "--notes", summary_notes,
        ])
        promote_route(staged_route, live_route)

    summary = run(history_base(root, origin, destination) + ["status"])
    return {
        "applied_carriers": [carrier for carrier, _, _ in carrier_records],
        "cabin_winner": {**cabin_winner, "carrier": cabin_carrier},
        "checked_winner": ({**checked_winner, "carrier": checked_carrier} if checked_winner else None),
        "history_summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--input", default="data/google_flights_latest.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    print(json.dumps(apply_payload(payload, root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
