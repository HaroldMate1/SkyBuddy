#!/usr/bin/env python3
"""Render a Flight Finder-inspired SkyBuddy dashboard for Telegram."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def eur(value: float | None) -> str:
    return "Not verified" if value is None else f"€{value:,.2f}"


def short_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%d %b %Y")


def continuous_fare_series(quotes: list[dict[str, Any]]) -> tuple[list[datetime], list[float]]:
    """Return genuine daily fares without inserting gaps for unavailable days."""
    daily_quotes: dict[Any, dict[str, Any]] = {}
    for quote in quotes:
        stamp = parse_iso(str(quote["observed_at"]))
        day = stamp.date()
        previous_quote = daily_quotes.get(day)
        if previous_quote is None or stamp > parse_iso(str(previous_quote["observed_at"])):
            daily_quotes[day] = quote

    priced_quotes = [
        daily_quotes[day]
        for day in sorted(daily_quotes)
        if daily_quotes[day].get("no_checked_bag_eur") is not None
    ]
    dates = [
        parse_iso(str(quote["observed_at"])).replace(hour=12, minute=0, second=0, microsecond=0)
        for quote in priced_quotes
    ]
    fares = [float(quote["no_checked_bag_eur"]) for quote in priced_quotes]
    return dates, fares


def render_dashboard(
    rows: list[dict[str, Any]],
    graph_path: Path,
    threshold: float = 1100.0,
    airline_rows: list[dict[str, Any]] | None = None,
) -> None:
    if not rows:
        return
    airline_rows = airline_rows or []

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import FancyBboxPatch

    # Flight Finder-inspired, but deliberately branded and structured for SkyBuddy.
    BG_TOP = "#08272f"
    BG_BOTTOM = "#03171d"
    CARD = "#0a2b34"
    CARD_ALT = "#0d333d"
    BORDER = "#24505a"
    GRID = "#244852"
    TEXT = "#a8c4c1"
    MUTED = "#789894"
    CREAM = "#e7d3aa"
    NO_BAG = "#6d8df7"
    CHECKED = "#f5b36b"
    TARGET = "#ef4965"
    GOOD = "#83c9b4"

    latest = rows[-1]
    previous = rows[-2] if len(rows) > 1 else None
    observed = parse_iso(str(latest["observed_at"]))
    outbound = datetime.fromisoformat(str(latest["outbound_date"])).date()
    days_to_departure = (outbound - observed.date()).days
    no_bag_price = float(latest["no_checked_bag_eur"])
    checked_price = (
        float(latest["checked_bag_eur"])
        if latest.get("checked_bag_eur") is not None
        else None
    )
    no_bag_delta = (
        no_bag_price - float(previous["no_checked_bag_eur"])
        if previous is not None
        else None
    )
    checked_delta = (
        checked_price - float(previous["checked_bag_eur"])
        if previous is not None
        and checked_price is not None
        and previous.get("checked_bag_eur") is not None
        else None
    )
    historical_no_bag = min(float(row["no_checked_bag_eur"]) for row in rows)
    checked_history = [
        float(row["checked_bag_eur"])
        for row in rows
        if row.get("checked_bag_eur") is not None
    ]
    historical_checked = min(checked_history) if checked_history else None

    fig = plt.figure(figsize=(12, 15), dpi=100, facecolor=BG_BOTTOM)

    # Subtle vertical gradient, avoiding the flat exported-chart appearance.
    background = fig.add_axes([0, 0, 1, 1], zorder=0)
    top_rgb = np.array(matplotlib.colors.to_rgb(BG_TOP))
    bottom_rgb = np.array(matplotlib.colors.to_rgb(BG_BOTTOM))
    gradient = np.linspace(top_rgb, bottom_rgb, 1500).reshape(1500, 1, 3)
    background.imshow(gradient, aspect="auto", extent=[0, 1, 0, 1], origin="upper")
    background.axis("off")

    def card(x: float, y: float, width: float, height: float, *, alt: bool = False) -> None:
        fig.patches.append(
            FancyBboxPatch(
                (x, y),
                width,
                height,
                transform=fig.transFigure,
                boxstyle="round,pad=0.008,rounding_size=0.014",
                facecolor=CARD_ALT if alt else CARD,
                edgecolor=BORDER,
                linewidth=1.2,
                alpha=0.96,
                zorder=1,
            )
        )

    def pill(x: float, y: float, text: str, color: str = TEXT, width: float | None = None) -> None:
        pill_width = width or max(0.09, 0.0105 * len(text) + 0.03)
        fig.patches.append(
            FancyBboxPatch(
                (x, y - 0.013),
                pill_width,
                0.028,
                transform=fig.transFigure,
                boxstyle="round,pad=0.004,rounding_size=0.012",
                facecolor="#0b3039",
                edgecolor=BORDER,
                linewidth=0.9,
                zorder=3,
            )
        )
        fig.text(
            x + 0.011,
            y,
            text,
            color=color,
            fontsize=9.5,
            va="center",
            fontfamily="DejaVu Sans Mono",
            zorder=4,
        )

    def delta_text(value: float | None) -> tuple[str, str]:
        if value is None:
            return "First observation", MUTED
        if abs(value) < 0.005:
            return "No change", MUTED
        direction = "down" if value < 0 else "up"
        return f"€{abs(value):,.2f} {direction} since yesterday", GOOD if value < 0 else TARGET

    # Header
    fig.text(0.075, 0.953, "SKYBUDDY", color=TEXT, fontsize=14, weight="bold", zorder=3)
    fig.text(
        0.177,
        0.953,
        "DAILY FARE MONITOR",
        color=MUTED,
        fontsize=10,
        fontfamily="DejaVu Sans Mono",
        zorder=3,
    )
    fig.text(
        0.925,
        0.953,
        f"{len(rows):02d} OBS",
        color=MUTED,
        fontsize=10,
        ha="right",
        fontfamily="DejaVu Sans Mono",
        zorder=3,
    )
    fig.text(
        0.075,
        0.895,
        f"{latest['origin']} → {latest['destination']}",
        color=TEXT,
        fontsize=31,
        weight="bold",
        fontfamily="DejaVu Sans Mono",
        zorder=3,
    )
    fig.text(
        0.075,
        0.858,
        f"Flexible dates  ·  {short_date(str(latest['outbound_date']))} — {short_date(str(latest['return_date']))}",
        color=CREAM,
        fontsize=11.5,
        zorder=3,
    )
    departure_label = (
        f"Departs in {days_to_departure} days"
        if days_to_departure >= 0
        else "Travel date passed"
    )
    pill(0.075, 0.818, departure_label)
    pill(0.256, 0.818, "1 adult · Economy", width=0.17)
    pill(0.443, 0.818, "Round trip", width=0.12)
    fig.text(
        0.925,
        0.818,
        f"Observed {observed.strftime('%d %b %Y · %H:%M %Z')}",
        color=MUTED,
        fontsize=9.5,
        ha="right",
        fontfamily="DejaVu Sans Mono",
        zorder=3,
    )
    fig.lines.append(
        matplotlib.lines.Line2D(
            [0.075, 0.925], [0.783, 0.783], transform=fig.transFigure, color=BORDER, linewidth=1
        )
    )

    # Chart card — carriers are dynamic: every distinct carrier combination
    # returned by the latest Google Flights sweep gets its own series.
    palette = [
        "#ef4965",
        "#f2bf63",
        "#48b7d4",
        "#7f7af2",
        "#e66a55",
        "#69c78f",
        "#d78bd4",
        "#72a7f2",
        "#d9a35c",
        "#8cc9c3",
        "#c88c66",
        "#a7b861",
    ]
    latest_carriers: dict[str, dict[str, Any]] = {}
    if airline_rows:
        latest_stamp = max(parse_iso(str(quote["observed_at"])) for quote in airline_rows)
        for quote in airline_rows:
            if parse_iso(str(quote["observed_at"])) == latest_stamp:
                latest_carriers[str(quote["airline"])] = quote
    monitored = sorted(
        latest_carriers,
        key=lambda airline: (
            latest_carriers[airline].get("no_checked_bag_eur") is None,
            float(latest_carriers[airline].get("no_checked_bag_eur") or math.inf),
            airline,
        ),
    )
    carrier_colors = {airline: palette[index % len(palette)] for index, airline in enumerate(monitored)}
    verified_count = sum(
        1 for quote in latest_carriers.values() if quote.get("no_checked_bag_eur") is not None
    )

    card(0.075, 0.39, 0.85, 0.355)
    fig.text(0.096, 0.714, "PRICE HISTORY · BY AIRLINE", color=CREAM, fontsize=10, weight="bold", zorder=3)
    fig.text(
        0.905,
        0.714,
        f"{len(monitored)} GOOGLE RESULTS · {verified_count} CABIN FARES",
        color=MUTED,
        fontsize=9,
        ha="right",
        fontfamily="DejaVu Sans Mono",
        zorder=3,
    )

    chart = fig.add_axes([0.12, 0.485, 0.76, 0.19], facecolor="none", zorder=3)
    plot_dates: list[datetime] = []
    all_values: list[float] = [threshold]
    plotted_carriers = 0
    for airline in monitored:
        carrier_quotes = [quote for quote in airline_rows if str(quote["airline"]) == airline]
        if not carrier_quotes:
            continue
        carrier_dates, carrier_values = continuous_fare_series(carrier_quotes)
        if not carrier_values:
            continue
        chart.plot(
            carrier_dates,
            carrier_values,
            color=carrier_colors[airline],
            linewidth=2.7,
            marker="o",
            markersize=6,
            markeredgecolor=BG_BOTTOM,
            markeredgewidth=1.2,
            zorder=5,
        )
        plotted_carriers += 1
        plot_dates.extend(carrier_dates)
        all_values.extend(value for value in carrier_values if math.isfinite(value))

    # Backward-compatible fallback until the first per-airline observations exist.
    if plotted_carriers == 0:
        plot_dates = [parse_iso(str(row["observed_at"])) for row in rows]
        fallback_values = [float(row["no_checked_bag_eur"]) for row in rows]
        chart.plot(
            plot_dates,
            fallback_values,
            color=NO_BAG,
            linewidth=2.7,
            marker="o",
            markersize=6,
            markeredgecolor=BG_BOTTOM,
            markeredgewidth=1.2,
            zorder=5,
        )
        all_values.extend(fallback_values)

    chart.axhline(
        threshold,
        color=TARGET,
        linewidth=1.5,
        linestyle=(0, (5, 5)),
        zorder=2,
    )
    chart.text(
        0.99,
        threshold,
        f"  EMAIL TARGET €{threshold:,.0f}",
        color=TARGET,
        fontsize=7.8,
        va="bottom",
        ha="right",
        transform=chart.get_yaxis_transform(),
        fontfamily="DejaVu Sans Mono",
    )
    unique_dates = sorted(set(plot_dates))
    if len(unique_dates) == 1:
        chart.set_xlim(unique_dates[0] - timedelta(days=3), unique_dates[0] + timedelta(days=3))
    low, high = min(all_values), max(all_values)
    padding = max((high - low) * 0.16, 70)
    chart.set_ylim(max(0, low - padding), high + padding)
    chart.grid(True, color=GRID, linewidth=0.8, alpha=0.65)
    chart.set_axisbelow(True)
    chart.tick_params(colors=MUTED, labelsize=8.5, length=0, pad=8)
    chart.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda value, _: f"€{value:,.0f}"))
    chart.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    chart.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    for spine in chart.spines.values():
        spine.set_visible(False)

    # Every carrier combination in the latest Google Flights sweep remains visible.
    coverage_columns = 2 if any(len(airline) > 24 for airline in monitored) else 4
    coverage_width = 0.405 if coverage_columns == 2 else 0.205
    coverage_rows = max(1, math.ceil(len(monitored) / coverage_columns))
    coverage_step = min(0.024, 0.064 / coverage_rows)
    for index, airline in enumerate(monitored):
        row_index, column_index = divmod(index, coverage_columns)
        x = 0.096 + column_index * coverage_width
        y = 0.454 - row_index * coverage_step
        quote = latest_carriers[airline]
        cabin_price = quote.get("no_checked_bag_eur")
        checked_quote = quote.get("checked_bag_eur")
        if cabin_price is not None:
            suffix = f" €{float(cabin_price):,.0f}"
        elif checked_quote is not None:
            suffix = f" BAG €{float(checked_quote):,.0f}"
        else:
            suffix = " N/V"
        active = cabin_price is not None or checked_quote is not None
        fig.text(
            x,
            y,
            f"● {airline}{suffix}",
            color=carrier_colors[airline] if active else MUTED,
            fontsize=6.7,
            fontfamily="DejaVu Sans Mono",
            zorder=3,
        )

    # Current fare cards
    fig.text(0.075, 0.365, "TODAY'S BEST VERIFIED FARES", color=CREAM, fontsize=10, weight="bold", zorder=3)
    card(0.075, 0.178, 0.41, 0.16, alt=True)
    card(0.515, 0.178, 0.41, 0.16, alt=True)

    no_delta_label, no_delta_color = delta_text(no_bag_delta)
    checked_delta_label, checked_delta_color = delta_text(checked_delta)

    fig.text(0.096, 0.306, "CABIN ONLY", color=MUTED, fontsize=9.5, fontfamily="DejaVu Sans Mono", zorder=3)
    fig.text(0.096, 0.257, eur(no_bag_price), color=TEXT, fontsize=27, weight="bold", zorder=3)
    fig.text(0.096, 0.226, str(latest.get("airline") or "Airline not recorded"), color=CREAM, fontsize=11, weight="bold", zorder=3)
    fig.text(0.096, 0.199, no_delta_label, color=no_delta_color, fontsize=9.5, zorder=3)
    fig.text(0.464, 0.199, f"Low {eur(historical_no_bag)}", color=MUTED, fontsize=8.5, ha="right", fontfamily="DejaVu Sans Mono", zorder=3)

    bag_status = "VERIFIED" if checked_price is not None else "AWAITING VERIFICATION"
    bag_status_color = GOOD if checked_price is not None else CHECKED
    fig.text(0.536, 0.306, "WITH 1 CHECKED BAG", color=MUTED, fontsize=9.5, fontfamily="DejaVu Sans Mono", zorder=3)
    fig.text(0.536, 0.257, eur(checked_price), color=TEXT if checked_price is not None else CHECKED, fontsize=25 if checked_price is not None else 19, weight="bold", zorder=3)
    if checked_price is not None:
        fig.text(0.536, 0.226, str(latest.get("checked_airline") or latest.get("airline") or "Airline not recorded"), color=CREAM, fontsize=10.2, weight="bold", zorder=3)
        fig.text(0.536, 0.199, f"{bag_status} · {checked_delta_label}", color=bag_status_color, fontsize=8.8, weight="bold", fontfamily="DejaVu Sans Mono", zorder=3)
        fig.text(0.904, 0.199, f"Low {eur(historical_checked)}", color=MUTED, fontsize=8.5, ha="right", fontfamily="DejaVu Sans Mono", zorder=3)
    else:
        fig.text(0.536, 0.226, bag_status, color=bag_status_color, fontsize=10, weight="bold", fontfamily="DejaVu Sans Mono", zorder=3)
        fig.text(0.536, 0.199, "No estimate used · email alert disabled", color=MUTED, fontsize=9.2, zorder=3)

    # Footer/source strip
    card(0.075, 0.078, 0.85, 0.066)
    fig.text(0.096, 0.119, "SOURCE", color=MUTED, fontsize=8.5, fontfamily="DejaVu Sans Mono", zorder=3)
    fig.text(0.096, 0.095, str(latest.get("source") or "Not recorded"), color=TEXT, fontsize=10.5, weight="bold", zorder=3)
    fig.text(
        0.905,
        0.107,
        f"Alert at or below €{threshold:,.0f} · checked baggage required",
        color=TARGET,
        fontsize=9.3,
        ha="right",
        fontfamily="DejaVu Sans Mono",
        zorder=3,
    )
    fig.text(
        0.075,
        0.040,
        "Informational tracker · Verify the final fare and baggage terms directly before booking.",
        color=MUTED,
        fontsize=8.8,
        zorder=3,
    )
    fig.text(0.925, 0.040, f"SKYBUDDY / {latest['origin']}–{latest['destination']}", color=MUTED, fontsize=8.8, ha="right", fontfamily="DejaVu Sans Mono", zorder=3)

    graph_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = graph_path.with_name(graph_path.stem + ".tmp" + graph_path.suffix)
    fig.savefig(tmp, format="png", facecolor=fig.get_facecolor(), dpi=100)
    plt.close(fig)
    tmp.replace(graph_path)
