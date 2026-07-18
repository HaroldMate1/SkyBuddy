#!/usr/bin/env python3
"""Persist route fare observations, render history, and deduplicate alerts."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "observed_at",
    "origin",
    "destination",
    "outbound_date",
    "return_date",
    "no_checked_bag_eur",
    "checked_bag_eur",
    "airline",
    "checked_airline",
    "checked_outbound_date",
    "checked_return_date",
    "source",
    "url",
    "checked_url",
    "notes",
]
AIRLINE_FIELDS = [
    "observed_at",
    "airline",
    "outbound_date",
    "return_date",
    "no_checked_bag_eur",
    "checked_bag_eur",
    "status",
    "source",
    "url",
    "notes",
]


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def positive_price(value: str | float) -> float:
    price = float(value)
    if not math.isfinite(price) or price <= 0:
        raise argparse.ArgumentTypeError("fare must be a positive finite number")
    return round(price, 2)


def optional_price(value: str | float | None) -> float | None:
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "na", "n/a", "unavailable", "none"}):
        return None
    return positive_price(value)


def route_key(origin: str, destination: str) -> str:
    normalized = f"{origin.upper()}-{destination.upper()}"
    if not re.fullmatch(r"[A-Z0-9]{3,5}-[A-Z0-9]{3,5}", normalized):
        raise SystemExit("origin and destination must be 3-5 character IATA-style codes")
    return normalized


def route_root(root: Path, origin: str, destination: str) -> Path:
    return root / "routes" / route_key(origin, destination)


def paths(root: Path) -> tuple[Path, Path, Path]:
    return root / "data" / "fare_history.csv", root / "data" / "alert_state.json", root / "reports" / "fare_history.png"


def airline_history_path(root: Path) -> Path:
    return root / "data" / "airline_history.csv"


def load_airline_rows(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    with history_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["no_checked_bag_eur"] = optional_price(row["no_checked_bag_eur"])
        row["checked_bag_eur"] = optional_price(row["checked_bag_eur"])
    rows.sort(key=lambda row: parse_iso(str(row["observed_at"])))
    return rows


def write_airline_rows(history_path: Path, rows: list[dict[str, Any]]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = history_path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AIRLINE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(history_path)


def latest_airlines(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[str(row["airline"])] = row
    return latest


def load_rows(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    with history_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["no_checked_bag_eur"] = float(row["no_checked_bag_eur"])
        row["checked_bag_eur"] = optional_price(row["checked_bag_eur"])
    rows.sort(key=lambda row: parse_iso(str(row["observed_at"])))
    return rows


def write_rows(history_path: Path, rows: list[dict[str, Any]]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = history_path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(history_path)


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"alert_active": False, "last_alert_price_eur": None, "last_alert_at": None}
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def render_graph(
    rows: list[dict[str, Any]],
    graph_path: Path,
    threshold: float = 1100.0,
    airline_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Render the Telegram dashboard while preserving the public CLI contract."""
    from dashboard import render_dashboard

    render_dashboard(rows, graph_path, threshold, airline_rows or [])


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"observations": 0, "latest": None}
    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    checked_values = [float(row["checked_bag_eur"]) for row in rows if row["checked_bag_eur"] is not None]
    return {
        "observations": len(rows),
        "latest": latest,
        "change_from_previous_eur": {
            "no_checked_bag": round(latest["no_checked_bag_eur"] - previous["no_checked_bag_eur"], 2) if previous else None,
            "checked_bag": round(latest["checked_bag_eur"] - previous["checked_bag_eur"], 2) if previous and latest["checked_bag_eur"] is not None and previous["checked_bag_eur"] is not None else None,
        },
        "historical_min_eur": {
            "no_checked_bag": min(row["no_checked_bag_eur"] for row in rows),
            "checked_bag": min(checked_values) if checked_values else None,
        },
        "historical_average_eur": {
            "no_checked_bag": round(sum(row["no_checked_bag_eur"] for row in rows) / len(rows), 2),
            "checked_bag": round(sum(checked_values) / len(checked_values), 2) if checked_values else None,
        },
    }


def command_record_airline(args: argparse.Namespace) -> dict[str, Any]:
    root = route_root(Path(args.root), args.origin, args.destination)
    history_path = airline_history_path(root)
    parse_iso(args.observed_at)
    rows = load_airline_rows(history_path)
    rows = [
        row
        for row in rows
        if not (str(row.get("observed_at")) == args.observed_at and str(row.get("airline")) == args.airline)
    ]
    no_bag = optional_price(args.no_bag)
    checked_bag = optional_price(args.checked_bag)
    row = {
        "observed_at": args.observed_at,
        "airline": args.airline,
        "outbound_date": args.outbound,
        "return_date": args.return_date,
        "no_checked_bag_eur": no_bag,
        "checked_bag_eur": checked_bag,
        "status": "verified" if no_bag is not None or checked_bag is not None else "not_verified",
        "source": args.source,
        "url": args.url,
        "notes": args.notes,
    }
    rows.append(row)
    rows.sort(key=lambda item: parse_iso(str(item["observed_at"])))
    write_airline_rows(history_path, rows)
    fare_path, _, graph_path = paths(root)
    fare_rows = load_rows(fare_path)
    if fare_rows:
        render_graph(fare_rows, graph_path, airline_rows=rows)
    return {
        "airline_observations": len(rows),
        "latest_airlines": latest_airlines(rows),
        "airline_history_path": str(history_path),
    }


def command_record(args: argparse.Namespace) -> dict[str, Any]:
    root = route_root(Path(args.root), args.origin, args.destination)
    history_path, state_path, graph_path = paths(root)
    parse_iso(args.observed_at)
    rows = load_rows(history_path)
    origin = args.origin.upper()
    destination = args.destination.upper()
    rows = [
        row
        for row in rows
        if not (
            str(row.get("observed_at")) == args.observed_at
            and str(row.get("origin")) == origin
            and str(row.get("destination")) == destination
        )
    ]
    row = {
        "observed_at": args.observed_at,
        "origin": origin,
        "destination": destination,
        "outbound_date": args.outbound,
        "return_date": args.return_date,
        "no_checked_bag_eur": positive_price(args.no_bag),
        "checked_bag_eur": optional_price(args.checked_bag),
        "airline": args.airline,
        "checked_airline": args.checked_airline or args.airline,
        "checked_outbound_date": args.checked_outbound or args.outbound,
        "checked_return_date": args.checked_return or args.return_date,
        "source": args.source,
        "url": args.url,
        "checked_url": args.checked_url or args.url,
        "notes": args.notes,
    }
    rows.append(row)
    rows.sort(key=lambda item: parse_iso(str(item["observed_at"])))
    write_rows(history_path, rows)
    state = load_state(state_path)
    if row["checked_bag_eur"] is not None and row["checked_bag_eur"] > args.threshold and state.get("alert_active"):
        state["alert_active"] = False
        write_state(state_path, state)
    render_graph(rows, graph_path, args.threshold, load_airline_rows(airline_history_path(root)))
    result = summary(rows)
    result.update({"history_path": str(history_path), "graph_path": str(graph_path)})
    return result


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = route_root(Path(args.root), args.origin, args.destination)
    history_path, _, graph_path = paths(root)
    rows = load_rows(history_path)
    airline_rows = load_airline_rows(airline_history_path(root))
    result = summary(rows)
    result.update(
        {
            "history_path": str(history_path),
            "airline_history_path": str(airline_history_path(root)),
            "graph_path": str(graph_path),
            "latest_airlines": latest_airlines(airline_rows),
        }
    )
    return result


def command_should_alert(args: argparse.Namespace) -> dict[str, Any]:
    root = route_root(Path(args.root), args.origin, args.destination)
    history_path, state_path, _ = paths(root)
    rows = load_rows(history_path)
    if not rows:
        return {"alert_required": False, "reason": "no observations"}
    latest = rows[-1]
    if latest["checked_bag_eur"] is None:
        return {"alert_required": False, "reason": "checked-bag fare unavailable", "latest": latest}
    price = float(latest["checked_bag_eur"])
    state = load_state(state_path)
    last_price = state.get("last_alert_price_eur")
    below = price <= args.threshold
    first_crossing = below and not state.get("alert_active", False)
    materially_better = below and last_price is not None and price <= float(last_price) - args.improvement
    return {
        "alert_required": bool(first_crossing or materially_better),
        "checked_bag_price_eur": price,
        "threshold_eur": args.threshold,
        "reason": "threshold crossing" if first_crossing else "materially better fare" if materially_better else "no new threshold event",
        "latest": latest,
    }


def command_mark_sent(args: argparse.Namespace) -> dict[str, Any]:
    root = route_root(Path(args.root), args.origin, args.destination)
    history_path, state_path, _ = paths(root)
    rows = load_rows(history_path)
    if not rows:
        raise SystemExit("cannot mark alert sent without an observation")
    latest = rows[-1]
    if latest["checked_bag_eur"] is None:
        raise SystemExit("cannot mark alert sent: checked-bag fare unavailable")
    state = {
        "alert_active": True,
        "last_alert_price_eur": float(latest["checked_bag_eur"]),
        "last_alert_at": args.sent_at,
    }
    parse_iso(args.sent_at)
    write_state(state_path, state)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--origin", default="BIO")
    parser.add_argument("--destination", default="BOG")
    sub = parser.add_subparsers(dest="command", required=True)

    airline = sub.add_parser("record-airline")
    airline.add_argument("--observed-at", required=True)
    airline.add_argument("--airline", required=True)
    airline.add_argument("--no-bag", default="unavailable")
    airline.add_argument("--checked-bag", default="unavailable")
    airline.add_argument("--source", required=True)
    airline.add_argument("--url", required=True)
    airline.add_argument("--outbound", default="2026-12-04")
    airline.add_argument("--return-date", default="2027-01-08")
    airline.add_argument("--notes", default="")
    airline.set_defaults(func=command_record_airline)

    record = sub.add_parser("record")
    record.add_argument("--observed-at", required=True)
    record.add_argument("--no-bag", type=positive_price, required=True)
    record.add_argument("--checked-bag", default="unavailable")
    record.add_argument("--airline", required=True)
    record.add_argument("--checked-airline")
    record.add_argument("--checked-outbound")
    record.add_argument("--checked-return")
    record.add_argument("--source", required=True)
    record.add_argument("--url", required=True)
    record.add_argument("--checked-url")
    record.add_argument("--outbound", default="2026-12-04")
    record.add_argument("--return-date", default="2027-01-08")
    record.add_argument("--notes", default="")
    record.add_argument("--threshold", type=positive_price, default=1100.0)
    record.set_defaults(func=command_record)

    status = sub.add_parser("status")
    status.set_defaults(func=command_status)

    alert = sub.add_parser("should-alert")
    alert.add_argument("--threshold", type=positive_price, default=1100.0)
    alert.add_argument("--improvement", type=positive_price, default=25.0)
    alert.set_defaults(func=command_should_alert)

    mark = sub.add_parser("mark-alert-sent")
    mark.add_argument("--sent-at", required=True)
    mark.set_defaults(func=command_mark_sent)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(args.func(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
