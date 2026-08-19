#!/usr/bin/env python3
"""Historical price baseline and buy-signal engine for SkyBuddy.

Answers the only question that matters before buying: *is this price actually
good for this route?* It scans everything SkyBuddy has recorded for the route
over a lookback window — **365 days by default** — builds a statistical
baseline, and turns a live fare into a verdict:

    buy_now · good · fair · wait · high

When the verdict is buy-worthy, :meth:`BuyDecisionEngine.auto_book_if_deal`
creates the booking intent for that flight link automatically, so the purchase
trigger is one human confirmation away.

Data sources scanned (all optional, whatever exists is used):

* ``data/price_baseline.csv``  — observations recorded by this module
* ``data/price_observations.csv`` — manual/collector observations
* ``config/preferences.json`` — price history of watched routes

Usage (CLI)::

    python scripts/price_baseline.py scan --origin BIO --destination BOG
    python scripts/price_baseline.py record --origin BIO --destination BOG \
        --outbound-date 2026-12-04 --price 684 --airline Iberia
    python scripts/price_baseline.py evaluate --origin BIO --destination BOG --price 684
    python scripts/price_baseline.py trigger --origin BIO --destination BOG \
        --outbound-date 2026-12-04 --price 684 --airline Iberia \
        --booking-url "https://..." --passenger harold
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from booking_agent import get_booking_agent
from preferences import PreferencesManager, get_preferences_manager
from users import get_workspace

ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = ROOT / "data" / "price_baseline.csv"
OBSERVATIONS_FILE = ROOT / "data" / "price_observations.csv"

#: Default lookback window. A full year captures every seasonal swing.
DEFAULT_LOOKBACK_DAYS = 365

#: Minimum observations before a baseline is considered trustworthy.
MIN_CONFIDENT_SAMPLES = 12

FIELDNAMES = [
    "observed_at",
    "origin",
    "destination",
    "outbound_date",
    "return_date",
    "airline",
    "currency",
    "price",
    "source",
    "booking_url",
]

VERDICT_BUY = "buy_now"
VERDICT_GOOD = "good"
VERDICT_FAIR = "fair"
VERDICT_WAIT = "wait"
VERDICT_HIGH = "high"

#: Verdicts that justify creating a booking intent automatically.
BUY_WORTHY = (VERDICT_BUY, VERDICT_GOOD)


def _now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def _parse_when(value: str) -> Optional[datetime]:
    """Parse an ISO timestamp or date into an aware datetime."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    for parser in (datetime.fromisoformat,):
        try:
            parsed = parser(text)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def verdict_for(
    price: float, baseline: "Baseline", target_price: Optional[float] = None
) -> str:
    """Classify a price against an already-built baseline.

    Shared by :meth:`PriceBaseline.evaluate` and by any caller that has the
    baseline in hand already and does not want to re-scan the history.
    """
    if target_price is not None and price <= target_price:
        return VERDICT_BUY
    if baseline.buy_threshold is not None and price <= baseline.buy_threshold:
        return VERDICT_BUY
    if baseline.good_threshold is not None and price <= baseline.good_threshold:
        return VERDICT_GOOD
    if baseline.median is not None and price <= baseline.median:
        return VERDICT_FAIR
    if baseline.p75 is not None and price <= baseline.p75:
        return VERDICT_WAIT
    return VERDICT_HIGH


def price_range(baseline: "Baseline") -> dict[str, Any]:
    """Return the lowest, median and highest price recorded in the window."""
    return {
        "days": baseline.days,
        "samples": baseline.samples,
        "currency": baseline.currency,
        "lowest": baseline.minimum,
        "median": baseline.median,
        "highest": baseline.maximum,
        "p10": baseline.p10,
        "p25": baseline.p25,
        "p75": baseline.p75,
        "trend": baseline.trend,
        "confidence": baseline.confidence,
    }


def _percentile(values: list[float], fraction: float) -> float:
    """Return the linear-interpolated percentile of a sorted-able sample."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


@dataclass
class PriceObservation:
    """One recorded price for a route."""

    observed_at: str
    origin: str
    destination: str
    price: float
    currency: str = "EUR"
    outbound_date: str = ""
    return_date: str = ""
    airline: str = ""
    source: str = "skybuddy"
    booking_url: str = ""


@dataclass
class Baseline:
    """Statistical summary of a route's recorded prices."""

    origin: str
    destination: str
    days: int
    samples: int
    currency: str = "EUR"
    minimum: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    median: Optional[float] = None
    p75: Optional[float] = None
    maximum: Optional[float] = None
    mean: Optional[float] = None
    first_observed: str = ""
    last_observed: str = ""
    days_covered: int = 0
    recent_median_30d: Optional[float] = None
    previous_median: Optional[float] = None
    trend: str = "unknown"
    trend_percent: Optional[float] = None
    confidence: str = "none"
    buy_threshold: Optional[float] = None
    good_threshold: Optional[float] = None
    sources: list[str] = field(default_factory=list)


class PriceBaseline:
    """Scan recorded history for a route and describe what a good price looks like."""

    def __init__(
        self,
        baseline_file: Path = BASELINE_FILE,
        observations_file: Path = OBSERVATIONS_FILE,
        preferences: Optional[PreferencesManager] = None,
    ):
        """Initialise the scanner over the local price stores."""
        self.baseline_file = baseline_file
        self.observations_file = observations_file
        self.preferences = preferences

    # ---------- recording ----------

    def record_price(
        self,
        origin: str,
        destination: str,
        price: float,
        currency: str = "EUR",
        outbound_date: str = "",
        return_date: str = "",
        airline: str = "",
        source: str = "skybuddy",
        booking_url: str = "",
        observed_at: str = "",
    ) -> PriceObservation:
        """Append one observation so tomorrow's baseline is richer than today's."""
        observation = PriceObservation(
            observed_at=observed_at or _now().isoformat(timespec="seconds"),
            origin=origin.upper(),
            destination=destination.upper(),
            price=float(price),
            currency=currency,
            outbound_date=outbound_date,
            return_date=return_date,
            airline=airline,
            source=source,
            booking_url=booking_url,
        )

        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.baseline_file.exists()
        with open(self.baseline_file, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            if is_new:
                writer.writeheader()
            writer.writerow(asdict(observation))
        return observation

    def record_many(self, observations: Iterable[dict[str, Any]]) -> int:
        """Record a batch of observations; returns how many were stored."""
        stored = 0
        for item in observations:
            if not item.get("price"):
                continue
            self.record_price(**item)
            stored += 1
        return stored

    # ---------- collection ----------

    def _from_baseline_file(self) -> list[PriceObservation]:
        """Read observations recorded by this module."""
        if not self.baseline_file.exists():
            return []
        rows: list[PriceObservation] = []
        with open(self.baseline_file, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    price = float(row.get("price") or 0)
                except ValueError:
                    continue
                if price <= 0:
                    continue
                rows.append(
                    PriceObservation(
                        observed_at=row.get("observed_at", ""),
                        origin=(row.get("origin") or "").upper(),
                        destination=(row.get("destination") or "").upper(),
                        price=price,
                        currency=row.get("currency") or "EUR",
                        outbound_date=row.get("outbound_date", ""),
                        return_date=row.get("return_date", ""),
                        airline=row.get("airline", ""),
                        source=row.get("source") or "skybuddy",
                        booking_url=row.get("booking_url", ""),
                    )
                )
        return rows

    def _from_observations_file(self) -> list[PriceObservation]:
        """Read the manual/collector observations CSV."""
        if not self.observations_file.exists():
            return []
        rows: list[PriceObservation] = []
        with open(self.observations_file, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    price = float(row.get("total_price") or 0)
                except ValueError:
                    continue
                if price <= 0:
                    continue
                rows.append(
                    PriceObservation(
                        observed_at=row.get("observed_at", ""),
                        origin=(row.get("origin") or "").upper(),
                        destination=(row.get("destination") or "").upper(),
                        price=price,
                        currency=row.get("currency") or "EUR",
                        outbound_date=row.get("outbound_date", ""),
                        return_date=row.get("return_date", ""),
                        airline=row.get("airline", ""),
                        source=row.get("source") or "observations",
                        booking_url=row.get("booking_url", ""),
                    )
                )
        return rows

    def _from_watched_routes(self) -> list[PriceObservation]:
        """Read the price history stored on watched routes."""
        rows: list[PriceObservation] = []
        try:
            manager = self.preferences or get_preferences_manager()
            routes = manager.get_all_watched_routes()
        except Exception:  # pragma: no cover - defensive
            return rows

        for route in routes.values():
            for stamp, price in (route.price_history or {}).items():
                try:
                    value = float(price)
                except (TypeError, ValueError):
                    continue
                if value <= 0:
                    continue
                rows.append(
                    PriceObservation(
                        observed_at=stamp,
                        origin=(route.origin or "").upper(),
                        destination=(route.destination or "").upper(),
                        price=value,
                        outbound_date=route.outbound_date or "",
                        return_date=route.return_date or "",
                        source="watched_route",
                    )
                )
        return rows

    def collect(
        self,
        origin: str,
        destination: str,
        days: int = DEFAULT_LOOKBACK_DAYS,
        outbound_date: Optional[str] = None,
    ) -> list[PriceObservation]:
        """Scan every store for this route inside the lookback window.

        Args:
            origin: Origin IATA code.
            destination: Destination IATA code.
            days: How far back to scan; defaults to a full year.
            outbound_date: Restrict to observations for this departure date.

        Returns:
            Observations sorted oldest first.
        """
        cutoff = _now() - timedelta(days=max(1, days))
        origin, destination = origin.upper(), destination.upper()

        pooled = (
            self._from_baseline_file()
            + self._from_observations_file()
            + self._from_watched_routes()
        )

        selected: list[tuple[datetime, PriceObservation]] = []
        seen: set[tuple[str, str, float]] = set()
        for row in pooled:
            if row.origin != origin or row.destination != destination:
                continue
            if outbound_date and row.outbound_date and row.outbound_date != outbound_date:
                continue
            when = _parse_when(row.observed_at)
            if when is None or when < cutoff:
                continue
            key = (row.observed_at[:19], row.airline, round(row.price, 2))
            if key in seen:
                continue
            seen.add(key)
            selected.append((when, row))

        selected.sort(key=lambda pair: pair[0])
        return [row for _, row in selected]

    # ---------- statistics ----------

    def build(
        self,
        origin: str,
        destination: str,
        days: int = DEFAULT_LOOKBACK_DAYS,
        outbound_date: Optional[str] = None,
    ) -> Baseline:
        """Build the statistical baseline for a route over the lookback window."""
        observations = self.collect(origin, destination, days=days, outbound_date=outbound_date)
        baseline = Baseline(
            origin=origin.upper(),
            destination=destination.upper(),
            days=days,
            samples=len(observations),
        )
        if not observations:
            return baseline

        prices = [row.price for row in observations]
        baseline.currency = observations[-1].currency or "EUR"
        baseline.minimum = round(min(prices), 2)
        baseline.p10 = round(_percentile(prices, 0.10), 2)
        baseline.p25 = round(_percentile(prices, 0.25), 2)
        baseline.median = round(statistics.median(prices), 2)
        baseline.p75 = round(_percentile(prices, 0.75), 2)
        baseline.maximum = round(max(prices), 2)
        baseline.mean = round(statistics.fmean(prices), 2)
        baseline.first_observed = observations[0].observed_at
        baseline.last_observed = observations[-1].observed_at
        baseline.sources = sorted({row.source for row in observations if row.source})

        first = _parse_when(observations[0].observed_at)
        last = _parse_when(observations[-1].observed_at)
        if first and last:
            baseline.days_covered = max((last - first).days, 0)

        recent_cutoff = _now() - timedelta(days=30)
        recent = [
            row.price
            for row in observations
            if (_parse_when(row.observed_at) or _now()) >= recent_cutoff
        ]
        earlier = [
            row.price
            for row in observations
            if (_parse_when(row.observed_at) or _now()) < recent_cutoff
        ]
        if recent:
            baseline.recent_median_30d = round(statistics.median(recent), 2)
        if earlier:
            baseline.previous_median = round(statistics.median(earlier), 2)

        if baseline.recent_median_30d and baseline.previous_median:
            change = (
                (baseline.recent_median_30d - baseline.previous_median)
                / baseline.previous_median
                * 100
            )
            baseline.trend_percent = round(change, 1)
            if change <= -3:
                baseline.trend = "falling"
            elif change >= 3:
                baseline.trend = "rising"
            else:
                baseline.trend = "flat"

        if baseline.samples >= MIN_CONFIDENT_SAMPLES and baseline.days_covered >= 30:
            baseline.confidence = "high"
        elif baseline.samples >= 5:
            baseline.confidence = "medium"
        else:
            baseline.confidence = "low"

        baseline.buy_threshold = baseline.p10
        baseline.good_threshold = baseline.p25
        return baseline

    # ---------- verdict ----------

    def evaluate(
        self,
        origin: str,
        destination: str,
        price: float,
        days: int = DEFAULT_LOOKBACK_DAYS,
        target_price: Optional[float] = None,
        outbound_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Compare a live price against the baseline and return a buy verdict."""
        baseline = self.build(origin, destination, days=days, outbound_date=outbound_date)
        price = float(price)
        reasons: list[str] = []

        if baseline.samples == 0 or baseline.median is None:
            verdict = VERDICT_FAIR if target_price is None or price > target_price else VERDICT_GOOD
            if target_price is not None and price <= target_price:
                reasons.append(f"At or below your target of {target_price} {baseline.currency}.")
            reasons.append(
                f"No price history yet for {baseline.origin}→{baseline.destination} — "
                "record observations so the baseline can form."
            )
            return {
                "verdict": verdict,
                "price": price,
                "currency": baseline.currency,
                "lowest": None,
                "median": None,
                "highest": None,
                "percentile": None,
                "vs_median_percent": None,
                "should_book": verdict in BUY_WORTHY,
                "confidence": "none",
                "reasons": reasons,
                "baseline": asdict(baseline),
            }

        history = [row.price for row in self.collect(origin, destination, days, outbound_date)]
        below = sum(1 for value in history if value < price)
        percentile = round(below / len(history) * 100, 1)
        vs_median = round((price - baseline.median) / baseline.median * 100, 1)

        verdict = verdict_for(price, baseline, target_price)

        if target_price is not None and price <= target_price:
            reasons.append(f"At or below your target of {target_price} {baseline.currency}.")
        elif verdict == VERDICT_BUY:
            reasons.append(
                f"In the cheapest 10% of the last {baseline.days} days "
                f"(≤ {baseline.buy_threshold} {baseline.currency})."
            )
        elif verdict == VERDICT_GOOD:
            reasons.append(
                f"In the cheapest 25% of the last {baseline.days} days "
                f"(≤ {baseline.good_threshold} {baseline.currency})."
            )
        elif verdict == VERDICT_FAIR:
            reasons.append("At or below the historical median, but not a standout deal.")
        elif verdict == VERDICT_WAIT:
            reasons.append("Above the median — history says a better fare is likely.")
        else:
            reasons.append("In the most expensive quarter of the observed year.")

        if baseline.minimum is not None:
            reasons.append(
                f"Recorded range: lowest {baseline.minimum} {baseline.currency}, "
                f"median {baseline.median} {baseline.currency}, "
                f"highest {baseline.maximum} {baseline.currency}."
            )
        if baseline.trend == "falling":
            reasons.append(f"Recent trend is falling ({baseline.trend_percent}% vs earlier).")
        elif baseline.trend == "rising":
            reasons.append(
                f"Recent trend is rising ({baseline.trend_percent}% vs earlier) — waiting is riskier."
            )
        if baseline.confidence != "high":
            reasons.append(
                f"Confidence {baseline.confidence}: only {baseline.samples} observations "
                f"across {baseline.days_covered} days."
            )

        return {
            "verdict": verdict,
            "price": price,
            "currency": baseline.currency,
            "lowest": baseline.minimum,
            "median": baseline.median,
            "highest": baseline.maximum,
            "percentile": percentile,
            "vs_median_percent": vs_median,
            "should_book": verdict in BUY_WORTHY,
            "confidence": baseline.confidence,
            "reasons": reasons,
            "baseline": asdict(baseline),
        }


class BuyDecisionEngine:
    """Join the historical baseline to the booking trigger."""

    def __init__(self, baseline: Optional[PriceBaseline] = None):
        """Initialise the engine over the price baseline and booking agent."""
        self.baseline = baseline or PriceBaseline()
        self.booking = get_booking_agent()

    def auto_book_if_deal(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        price: float,
        booking_url: str,
        airline: str = "",
        return_date: Optional[str] = None,
        currency: str = "EUR",
        passengers: Optional[list[str]] = None,
        target_price: Optional[float] = None,
        max_price: Optional[float] = None,
        days: int = DEFAULT_LOOKBACK_DAYS,
        cabin: str = "economy",
        record: bool = True,
    ) -> dict[str, Any]:
        """Evaluate an offer against its history and trigger a booking intent if it wins.

        The intent is created only when the verdict is ``buy_now`` or ``good``, and it
        still requires human confirmation before the agent may act on it.
        """
        if record:
            self.baseline.record_price(
                origin=origin,
                destination=destination,
                price=price,
                currency=currency,
                outbound_date=outbound_date,
                return_date=return_date or "",
                airline=airline,
                source="live_offer",
                booking_url=booking_url,
            )

        assessment = self.baseline.evaluate(
            origin=origin,
            destination=destination,
            price=price,
            days=days,
            target_price=target_price,
            outbound_date=outbound_date,
        )

        if not assessment["should_book"]:
            return {
                "triggered": False,
                "assessment": assessment,
                "message": (
                    f"Verdict '{assessment['verdict']}' — no booking intent created. "
                    "SkyBuddy keeps watching the route."
                ),
            }

        # Ceiling: what the caller asked for, otherwise the offer price plus a 2%
        # tolerance for taxes and fees that only appear at checkout.
        ceiling = max_price if max_price is not None else price * 1.02

        intent = self.booking.prepare_booking(
            booking_url=booking_url,
            airline=airline or "Unknown",
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            price=price,
            currency=currency,
            cabin=cabin,
            passengers=passengers or [],
            max_price=round(float(ceiling), 2),
            notes=(
                f"Auto-triggered: {assessment['verdict']} at the "
                f"{assessment['percentile']}th percentile of {days} days."
            ),
        )

        return {
            "triggered": intent.get("status") not in ("error", "rejected"),
            "assessment": assessment,
            "booking": intent,
            "message": (
                f"Verdict '{assessment['verdict']}' — booking intent "
                f"{intent.get('intent_id', 'n/a')} created for {airline} at {price} {currency}. "
                "Confirm it to let the agent open the link."
            ),
        }


def get_price_baseline(user: Optional[str] = None) -> PriceBaseline:
    """Return a price baseline scanner bound to a traveller workspace."""
    workspace = get_workspace(user)
    return PriceBaseline(
        baseline_file=workspace.baseline_file,
        observations_file=workspace.observations_file,
        preferences=PreferencesManager(prefs_file=workspace.preferences_file),
    )


def get_buy_engine(user: Optional[str] = None) -> BuyDecisionEngine:
    """Return a buy-decision engine bound to a traveller workspace."""
    engine = BuyDecisionEngine(get_price_baseline(user))
    engine.booking = get_booking_agent(user)
    return engine


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="SkyBuddy historical price baseline and buy-signal engine"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def route_args(target: argparse.ArgumentParser) -> None:
        target.add_argument("--user", help="Traveller workspace (default: the active one)")
        target.add_argument("--origin", required=True)
        target.add_argument("--destination", required=True)
        target.add_argument(
            "--days",
            type=int,
            default=DEFAULT_LOOKBACK_DAYS,
            help=f"Lookback window in days (default {DEFAULT_LOOKBACK_DAYS})",
        )
        target.add_argument("--outbound-date")

    scan = sub.add_parser("scan", help="Scan recorded history and print the baseline")
    route_args(scan)

    record = sub.add_parser("record", help="Record one observed price")
    route_args(record)
    record.add_argument("--price", type=float, required=True)
    record.add_argument("--currency", default="EUR")
    record.add_argument("--return-date", default="")
    record.add_argument("--airline", default="")
    record.add_argument("--source", default="manual")
    record.add_argument("--booking-url", default="")

    evaluate = sub.add_parser("evaluate", help="Evaluate a live price against the baseline")
    route_args(evaluate)
    evaluate.add_argument("--price", type=float, required=True)
    evaluate.add_argument("--target-price", type=float)

    trigger = sub.add_parser(
        "trigger", help="Evaluate an offer and create the booking intent when it is a deal"
    )
    route_args(trigger)
    trigger.add_argument("--price", type=float, required=True)
    trigger.add_argument("--booking-url", required=True)
    trigger.add_argument("--airline", default="")
    trigger.add_argument("--return-date")
    trigger.add_argument("--currency", default="EUR")
    trigger.add_argument("--cabin", default="economy")
    trigger.add_argument("--passenger", action="append", default=[], dest="passengers")
    trigger.add_argument("--target-price", type=float)
    trigger.add_argument("--max-price", type=float)

    return parser


def main() -> int:
    """Run the baseline CLI."""
    args = build_parser().parse_args()
    scanner = get_price_baseline(getattr(args, "user", None))

    if args.command == "scan":
        result = asdict(
            scanner.build(
                args.origin, args.destination, days=args.days, outbound_date=args.outbound_date
            )
        )
    elif args.command == "record":
        result = asdict(
            scanner.record_price(
                origin=args.origin,
                destination=args.destination,
                price=args.price,
                currency=args.currency,
                outbound_date=args.outbound_date or "",
                return_date=args.return_date,
                airline=args.airline,
                source=args.source,
                booking_url=args.booking_url,
            )
        )
    elif args.command == "evaluate":
        result = scanner.evaluate(
            origin=args.origin,
            destination=args.destination,
            price=args.price,
            days=args.days,
            target_price=args.target_price,
            outbound_date=args.outbound_date,
        )
    else:
        engine = BuyDecisionEngine(scanner)
        engine.booking = get_booking_agent(getattr(args, "user", None))
        result = engine.auto_book_if_deal(
            origin=args.origin,
            destination=args.destination,
            outbound_date=args.outbound_date or "",
            price=args.price,
            booking_url=args.booking_url,
            airline=args.airline,
            return_date=args.return_date,
            currency=args.currency,
            cabin=args.cabin,
            passengers=args.passengers,
            target_price=args.target_price,
            max_price=args.max_price,
            days=args.days,
        )

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
