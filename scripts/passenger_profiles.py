#!/usr/bin/env python3
"""Passenger/traveler profile management for flight bookings."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES_FILE = ROOT / "config" / "passengers.json"


@dataclass
class PassengerProfile:
    """Traveler profile for booking."""

    name: str
    given_name: str
    family_name: str
    born_on: str  # YYYY-MM-DD
    gender: str  # M, F, X
    title: str = "mr"  # mr, ms, mrs, mx
    email: str = ""
    phone_number: str = ""
    passport: str = ""  # Passport number
    nationality: str = ""  # Country code
    frequent_flyer: dict = field(default_factory=dict)  # {airline: number}


class PassengerManager:
    """Manage traveler profiles."""

    def __init__(self, profiles_file: Path = PROFILES_FILE):
        """Initialize passenger manager."""
        self.profiles_file = profiles_file
        self.profiles = self._load_profiles()

    def _load_profiles(self) -> dict[str, PassengerProfile]:
        """Load passenger profiles from file."""
        if not self.profiles_file.exists():
            return {}

        try:
            with open(self.profiles_file) as f:
                data = json.load(f)
                return {
                    name: PassengerProfile(**profile_data)
                    for name, profile_data in data.get("passengers", {}).items()
                }
        except Exception as e:
            print(f"Error loading passengers: {e}")
            return {}

    def save(self) -> None:
        """Save profiles to file."""
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "passengers": {
                name: asdict(profile) for name, profile in self.profiles.items()
            }
        }

        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_passenger(
        self,
        name: str,
        given_name: str,
        family_name: str,
        born_on: str,
        gender: str,
        title: str = "mr",
        email: str = "",
        phone_number: str = "",
        passport: str = "",
        nationality: str = "",
    ) -> PassengerProfile:
        """Add a new passenger profile."""
        profile = PassengerProfile(
            name=name.lower(),
            given_name=given_name,
            family_name=family_name,
            born_on=born_on,
            gender=gender,
            title=title,
            email=email,
            phone_number=phone_number,
            passport=passport,
            nationality=nationality,
        )

        self.profiles[name.lower()] = profile
        self.save()
        return profile

    def get_passenger(self, name: str) -> PassengerProfile | None:
        """Get a passenger by name."""
        return self.profiles.get(name.lower())

    def list_passengers(self) -> list[PassengerProfile]:
        """List all passengers."""
        return list(self.profiles.values())

    def remove_passenger(self, name: str) -> bool:
        """Remove a passenger."""
        if name.lower() in self.profiles:
            del self.profiles[name.lower()]
            self.save()
            return True
        return False

    def add_frequent_flyer(self, name: str, airline: str, number: str) -> bool:
        """Add frequent flyer number to passenger."""
        profile = self.get_passenger(name)
        if not profile:
            return False

        profile.frequent_flyer[airline] = number
        self.save()
        return True

    def get_passengers_for_booking(self, names: list[str]) -> dict[str, PassengerProfile]:
        """Get multiple passengers for booking."""
        return {name: self.get_passenger(name) for name in names if self.get_passenger(name)}


def get_passenger_manager() -> PassengerManager:
    """Get or create passenger manager singleton."""
    return PassengerManager()
