#!/usr/bin/env python3
"""Collect Google Flights results across an outbound/return date window via fli."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def date_range(start: date, end: date) -> list[date]:
    if start > end:
        raise ValueError("start date must not be after end date")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


AIRLINE_NAME_FIXES = {"LH": "Lufthansa"}


def airline_name(leg: dict[str, Any]) -> str:
    code = str(leg["airline"]["code"])
    return AIRLINE_NAME_FIXES.get(code, str(leg["airline"]["name"]))


def carrier_name(flight: dict[str, Any]) -> str:
    names = {
        airline_name(leg)
        for direction in ("outbound", "return")
        for leg in flight[direction]["legs"]
    }
    return " + ".join(sorted(names))


def itinerary_summary(flight: dict[str, Any], outbound: date, return_date: date, bags: int) -> dict[str, Any]:
    return {
        "carrier": carrier_name(flight),
        "price_eur": float(flight["price"]),
        "bags": bags,
        "outbound_date": outbound.isoformat(),
        "return_date": return_date.isoformat(),
        "outbound_stops": int(flight["outbound"]["stops"]),
        "return_stops": int(flight["return"]["stops"]),
        "total_duration_minutes": int(flight["duration"]),
        "outbound_airlines": [airline_name(leg) for leg in flight["outbound"]["legs"]],
        "return_airlines": [airline_name(leg) for leg in flight["return"]["legs"]],
    }


def run_query(fli: Path, origin: str, destination: str, outbound: date, return_date: date, bags: int) -> dict[str, Any]:
    command = [
        str(fli),
        "flights",
        origin,
        destination,
        outbound.isoformat(),
        "--return",
        return_date.isoformat(),
        "--class",
        "ECONOMY",
        "--stops",
        "ANY",
        "--sort",
        "CHEAPEST",
        "--bags",
        str(bags),
        "--currency",
        "EUR",
        "--language",
        "es-ES",
        "--country",
        "ES",
        "--format",
        "json",
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
    return json.loads(completed.stdout)


def collect_google_flights(
    *,
    origin: str,
    destination: str,
    outbound_start: date,
    outbound_end: date,
    return_start: date,
    return_end: date,
    query_runner,
    observed_at: str | None = None,
    allow_partial: bool = False,
) -> dict[str, Any]:
    """Collect and reduce every date pair and both checked-bag modes."""
    outbound_dates = date_range(outbound_start, outbound_end)
    return_dates = date_range(return_start, return_end)
    itineraries: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    total = len(outbound_dates) * len(return_dates) * 2
    completed_count = 0

    for outbound in outbound_dates:
        for return_date in return_dates:
            for bags in (0, 1):
                completed_count += 1
                print(
                    f"[{completed_count:02d}/{total}] {outbound} -> {return_date}, bags={bags}",
                    file=sys.stderr,
                    flush=True,
                )
                try:
                    payload = query_runner(origin, destination, outbound, return_date, bags)
                    for flight in payload.get("flights", []):
                        itineraries.append(itinerary_summary(flight, outbound, return_date, bags))
                except Exception as exc:
                    failures.append(
                        {
                            "outbound_date": outbound.isoformat(),
                            "return_date": return_date.isoformat(),
                            "bags": str(bags),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )

    if failures and not allow_partial:
        raise RuntimeError(f"Google Flights sweep incomplete: {len(failures)} of {total} queries failed")

    cheapest: dict[tuple[str, int], dict[str, Any]] = {}
    for itinerary in itineraries:
        key = (itinerary["carrier"], itinerary["bags"])
        ranking = (
            itinerary["price_eur"],
            itinerary["outbound_stops"] + itinerary["return_stops"],
            itinerary["total_duration_minutes"],
        )
        current = cheapest.get(key)
        if current is None:
            cheapest[key] = itinerary
            continue
        current_ranking = (
            current["price_eur"],
            current["outbound_stops"] + current["return_stops"],
            current["total_duration_minutes"],
        )
        if ranking < current_ranking:
            cheapest[key] = itinerary

    carriers = sorted({carrier for carrier, _ in cheapest})
    return {
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Google Flights via fli 0.9.0",
        "origin": origin.upper(),
        "destination": destination.upper(),
        "outbound_window": [outbound_start.isoformat(), outbound_end.isoformat()],
        "return_window": [return_start.isoformat(), return_end.isoformat()],
        "queries_attempted": total,
        "query_failures": failures,
        "itineraries_returned": len(itineraries),
        "carriers": [
            {
                "carrier": carrier,
                "cabin_only": cheapest.get((carrier, 0)),
                "one_checked_bag": cheapest.get((carrier, 1)),
            }
            for carrier in carriers
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--outbound-start", required=True)
    parser.add_argument("--outbound-end", required=True)
    parser.add_argument("--return-start", required=True)
    parser.add_argument("--return-end", required=True)
    parser.add_argument("--fli", help="Path to the fli executable; defaults to PATH or ROOT/.fli-venv/bin/fli")
    parser.add_argument("--output", help="Output JSON path; defaults to ROOT/data/google_flights_latest.json")
    parser.add_argument("--allow-partial", action="store_true", help="Publish results even if one or more queries fail")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    discovered = shutil.which("fli")
    fli = Path(args.fli).expanduser() if args.fli else Path(discovered) if discovered else root / ".fli-venv" / "bin" / "fli"
    if not fli.exists():
        raise SystemExit(f"Missing fli executable: {fli}")

    result = collect_google_flights(
        origin=args.origin,
        destination=args.destination,
        outbound_start=date.fromisoformat(args.outbound_start),
        outbound_end=date.fromisoformat(args.outbound_end),
        return_start=date.fromisoformat(args.return_start),
        return_end=date.fromisoformat(args.return_end),
        query_runner=lambda origin, destination, outbound, return_date, bags: run_query(
            fli, origin, destination, outbound, return_date, bags
        ),
        allow_partial=args.allow_partial,
    )
    output_path = Path(args.output).expanduser() if args.output else root / "data" / "google_flights_latest.json"
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "queries_attempted": result["queries_attempted"],
                "failures": len(result["query_failures"]),
                "itineraries_returned": result["itineraries_returned"],
                "carriers": [row["carrier"] for row in result["carriers"]],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
