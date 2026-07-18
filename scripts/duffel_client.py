#!/usr/bin/env python3
"""Duffel API client for real-time flight search and price monitoring.

Requires DUFFEL_API_KEY environment variable or API key in config.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Flight:
    """Flight search result."""

    id: str
    airline: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    stops: int
    price: float
    currency: str
    booking_url: str


@dataclass
class FlightSearchResult:
    """Result of a flight search."""

    origin: str
    destination: str
    outbound_date: str
    return_date: Optional[str]
    flights: list[Flight]
    search_url: str


class DuffelClient:
    """Duffel API client for flight searches."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Duffel client.

        Args:
            api_key: Optional API key. If not provided, uses DUFFEL_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("DUFFEL_API_KEY")
        self.base_url = "https://api.duffel.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.available = bool(self.api_key)

    def search_flights(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy",
    ) -> FlightSearchResult:
        """Search for flights using Duffel API.

        Args:
            origin: IATA code (e.g., 'BIO')
            destination: IATA code (e.g., 'BOG')
            outbound_date: Date in YYYY-MM-DD format
            return_date: Optional return date in YYYY-MM-DD format
            passengers: Number of passengers
            cabin_class: 'economy', 'business', 'first', etc.

        Returns:
            FlightSearchResult with list of flights
        """
        if not self.available:
            return FlightSearchResult(
                origin=origin,
                destination=destination,
                outbound_date=outbound_date,
                return_date=return_date,
                flights=[],
                search_url="",
            )

        try:
            payload = {
                "type": "search",
                "passengers": [{"type": "adult"} for _ in range(passengers)],
                "slices": [
                    {
                        "origin_airport_iata_code": origin,
                        "destination_airport_iata_code": destination,
                        "departure_date": outbound_date,
                    }
                ],
                "cabin_class": cabin_class,
            }

            if return_date:
                payload["slices"].append(
                    {
                        "origin_airport_iata_code": destination,
                        "destination_airport_iata_code": origin,
                        "departure_date": return_date,
                    }
                )

            response = requests.post(
                f"{self.base_url}/air/search_sessions",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            flights = self._parse_flights(data, origin, destination)

            return FlightSearchResult(
                origin=origin,
                destination=destination,
                outbound_date=outbound_date,
                return_date=return_date,
                flights=flights,
                search_url=self._build_search_url(origin, destination, outbound_date, return_date),
            )

        except Exception as e:
            print(f"Error searching flights: {e}")
            return FlightSearchResult(
                origin=origin,
                destination=destination,
                outbound_date=outbound_date,
                return_date=return_date,
                flights=[],
                search_url="",
            )

    def _parse_flights(self, data: dict, origin: str, destination: str) -> list[Flight]:
        """Parse Duffel API response into Flight objects."""
        flights = []
        try:
            for offer in data.get("data", {}).get("offers", [])[:10]:  # Top 10 offers
                price = offer.get("total_emissions_kg", 0)
                for slice_item in offer.get("slices", []):
                    flight_info = slice_item.get("segments", [{}])[0]
                    flights.append(
                        Flight(
                            id=offer.get("id", ""),
                            airline=flight_info.get("operating_carrier_iata_code", ""),
                            departure_time=flight_info.get("departing_at", ""),
                            arrival_time=flight_info.get("arriving_at", ""),
                            duration_minutes=flight_info.get("duration", 0),
                            stops=len(flight_info.get("stops", [])),
                            price=price,
                            currency=offer.get("base_currency", "EUR"),
                            booking_url=self._build_booking_url(
                                offer.get("id", ""), origin, destination
                            ),
                        )
                    )
        except Exception as e:
            print(f"Error parsing flights: {e}")
        return flights

    def _build_search_url(
        self,
        origin: str,
        destination: str,
        outbound_date: str,
        return_date: Optional[str],
    ) -> str:
        """Build a Duffel search URL."""
        base = f"https://www.duffel.com/search/{origin}-{destination}/{outbound_date}"
        if return_date:
            base += f"/{return_date}"
        return base

    def _build_booking_url(self, offer_id: str, origin: str, destination: str) -> str:
        """Build a booking URL for an offer."""
        return f"https://www.duffel.com/booking/{offer_id}?origin={origin}&destination={destination}"


def get_duffel_client() -> DuffelClient:
    """Get or create Duffel client singleton."""
    return DuffelClient()
