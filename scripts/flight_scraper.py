#!/usr/bin/env python3
"""Automated flight price scraper - generates booking URLs for any route.

Usage:
  python flight_scraper.py                           # Uses config/search_config.json
  python flight_scraper.py BIO BOG 2026-12-04 2027-01-08  # Custom route/dates
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "search_config.json"


def load_config() -> dict:
    """Load search configuration."""
    with open(CONFIG) as f:
        return json.load(f)


def parse_args() -> dict:
    """Parse command-line arguments or load from config."""
    if len(sys.argv) > 1:
        if len(sys.argv) < 5:
            print("Usage: flight_scraper.py ORIGIN DESTINATION OUTBOUND RETURN")
            print("Example: flight_scraper.py BIO BOG 2026-12-04 2027-01-08")
            sys.exit(1)

        return {
            "origin": sys.argv[1].upper(),
            "destination": sys.argv[2].upper(),
            "outbound_target_date": sys.argv[3],
            "return_target_date": sys.argv[4],
            "currency": sys.argv[5] if len(sys.argv) > 5 else "EUR",
        }
    else:
        return load_config()


def generate_google_flights_url(config: dict) -> str:
    """Generate a Google Flights search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]
    currency = config.get("currency", "EUR")

    base_url = "https://www.google.com/travel/flights"
    params = {
        "q": f"{origin} to {destination} {outbound} to {return_date}",
        "curr": currency,
        "hl": "en",
    }
    return f"{base_url}?{urlencode(params)}"


def generate_avianca_url(config: dict) -> str:
    """Generate Avianca search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]

    try:
        out_date = datetime.strptime(outbound, "%Y-%m-%d").strftime("%d%m%Y")
        ret_date = datetime.strptime(return_date, "%Y-%m-%d").strftime("%d%m%Y")
    except ValueError:
        return f"https://www.avianca.com/en-us/flight-search?origin={origin}&destination={destination}"

    return (
        f"https://www.avianca.com/en-us/flight-search"
        f"?origin={origin}&destination={destination}"
        f"&departure={out_date}&return={ret_date}&adults=1"
    )


def generate_iberia_url(config: dict) -> str:
    """Generate Iberia search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]

    return (
        f"https://www.iberia.com/en/flight-search"
        f"?origin={origin}&destination={destination}"
        f"&departure={outbound}&return={return_date}&adults=1"
    )


def generate_klm_url(config: dict) -> str:
    """Generate KLM search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]

    try:
        out_date = datetime.strptime(outbound, "%Y-%m-%d").strftime("%d/%m/%Y")
        ret_date = datetime.strptime(return_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return f"https://www.klm.com/experience/booking?origin={origin}&destination={destination}"

    return (
        f"https://www.klm.com/experience/booking"
        f"?origin={origin}&destination={destination}"
        f"&departure={out_date}&return={ret_date}&adults=1"
    )


def generate_air_france_url(config: dict) -> str:
    """Generate Air France search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]

    return (
        f"https://www.airfrance.com/en/flight-search"
        f"?origin={origin}&destination={destination}"
        f"&departure={outbound}&return={return_date}&adults=1"
    )


def generate_kayak_url(config: dict) -> str:
    """Generate Kayak search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]
    currency = config.get("currency", "EUR")

    return (
        f"https://www.kayak.com/flights/{origin}-{destination}/"
        f"{outbound}/{return_date}?sort=bestflight_a&currency={currency}"
    )


def generate_skyscanner_url(config: dict) -> str:
    """Generate Skyscanner search URL."""
    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]

    out_parts = outbound.split("-")
    ret_parts = return_date.split("-")

    return (
        f"https://www.skyscanner.es/transport/flights/{origin}/{destination}/"
        f"{out_parts[2]}{out_parts[1]}{out_parts[0]}/"
        f"{ret_parts[2]}{ret_parts[1]}{ret_parts[0]}/"
    )


def generate_search_urls(config: dict) -> dict[str, str]:
    """Generate search URLs for all sources."""
    return {
        "Google Flights": generate_google_flights_url(config),
        "Avianca": generate_avianca_url(config),
        "Iberia": generate_iberia_url(config),
        "KLM": generate_klm_url(config),
        "Air France": generate_air_france_url(config),
        "Kayak": generate_kayak_url(config),
        "Skyscanner": generate_skyscanner_url(config),
    }


def main() -> None:
    """Print search URLs for manual inspection."""
    config = parse_args()
    urls = generate_search_urls(config)

    origin = config["origin"]
    destination = config["destination"]
    outbound = config["outbound_target_date"]
    return_date = config["return_target_date"]

    print("\n" + "=" * 140)
    print(f"FLIGHT SEARCH URLS - {origin} to {destination}")
    print(f"Outbound: {outbound} | Return: {return_date}")
    print("=" * 140 + "\n")

    for i, (source, url) in enumerate(urls.items(), 1):
        print(f"{i}. [{source}]")
        print(f"   {url}\n")

    print("=" * 140)
    print("INSTRUCTIONS:")
    print("1. Click each link to search for current prices")
    print("2. Note the cheapest flight and its price")
    print("3. Copy the specific booking URL from your search results")
    print("4. Add entry to data/price_observations.csv")
    print("=" * 140 + "\n")


if __name__ == "__main__":
    main()
