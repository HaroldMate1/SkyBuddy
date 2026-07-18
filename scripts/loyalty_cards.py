#!/usr/bin/env python3
"""Credit card and loyalty points management for flight bookings."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_FILE = ROOT / "config" / "cards.json"


@dataclass
class CreditCard:
    """Credit card for earning rewards/points."""

    id: str  # Unique slug (e.g., 'amex-plat')
    issuer: str  # American Express, Visa, Mastercard, etc.
    product: str  # Product name (e.g., 'Platinum')
    network: str = "unknown"  # amex, visa, mastercard
    region: str = "US"  # Card region/country
    annual_fee: float = 0.0
    points_per_dollar: float = 1.0
    transfer_partners: list[str] = field(default_factory=list)  # Airlines/programs
    notes: str = ""


@dataclass
class LoyaltyProgram:
    """Loyalty program balance."""

    program: str  # Amex Membership Rewards, United MileagePlus, etc.
    balance: int  # Current points/miles
    tier: str = "member"  # member, silver, gold, platinum, etc.
    expiry_date: str = ""  # If points expire
    earning_rate: float = 1.0  # Points per dollar spent


class LoyaltyManager:
    """Manage credit cards and loyalty points."""

    def __init__(self, cards_file: Path = CARDS_FILE):
        """Initialize loyalty manager."""
        self.cards_file = cards_file
        self.cards, self.programs = self._load_data()

    def _load_data(self) -> tuple[dict[str, CreditCard], dict[str, LoyaltyProgram]]:
        """Load cards and loyalty programs from file."""
        if not self.cards_file.exists():
            return {}, {}

        try:
            with open(self.cards_file) as f:
                data = json.load(f)

            cards = {
                card_id: CreditCard(**card_data)
                for card_id, card_data in data.get("cards", {}).items()
            }

            programs = {
                prog_name: LoyaltyProgram(**prog_data)
                for prog_name, prog_data in data.get("programs", {}).items()
            }

            return cards, programs
        except Exception as e:
            print(f"Error loading cards/programs: {e}")
            return {}, {}

    def save(self) -> None:
        """Save cards and programs to file."""
        self.cards_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "cards": {card_id: asdict(card) for card_id, card in self.cards.items()},
            "programs": {prog_name: asdict(prog) for prog_name, prog in self.programs.items()},
        }

        with open(self.cards_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_card(
        self,
        card_id: str,
        issuer: str,
        product: str,
        network: str = "unknown",
        region: str = "US",
        annual_fee: float = 0.0,
        points_per_dollar: float = 1.0,
        transfer_partners: list[str] | None = None,
        notes: str = "",
    ) -> CreditCard:
        """Add a credit card."""
        card = CreditCard(
            id=card_id.lower(),
            issuer=issuer,
            product=product,
            network=network,
            region=region,
            annual_fee=annual_fee,
            points_per_dollar=points_per_dollar,
            transfer_partners=transfer_partners or [],
            notes=notes,
        )

        self.cards[card_id.lower()] = card
        self.save()
        return card

    def remove_card(self, card_id: str) -> bool:
        """Remove a card."""
        if card_id.lower() in self.cards:
            del self.cards[card_id.lower()]
            self.save()
            return True
        return False

    def list_cards(self) -> list[CreditCard]:
        """List all cards."""
        return list(self.cards.values())

    def add_loyalty_program(
        self,
        program: str,
        balance: int,
        tier: str = "member",
        expiry_date: str = "",
        earning_rate: float = 1.0,
    ) -> LoyaltyProgram:
        """Add or update loyalty program balance."""
        prog = LoyaltyProgram(
            program=program,
            balance=balance,
            tier=tier,
            expiry_date=expiry_date,
            earning_rate=earning_rate,
        )

        self.programs[program] = prog
        self.save()
        return prog

    def update_balance(self, program: str, new_balance: int) -> bool:
        """Update a program's point balance."""
        if program not in self.programs:
            return False

        self.programs[program].balance = new_balance
        self.save()
        return True

    def list_programs(self) -> list[LoyaltyProgram]:
        """List all loyalty programs."""
        return list(self.programs.values())

    def get_total_points(self) -> dict[str, int]:
        """Get total points by program."""
        return {prog.program: prog.balance for prog in self.programs.values()}

    def can_book_with_points(self, program: str, minimum_points: int) -> bool:
        """Check if program has enough points for award booking."""
        prog = self.programs.get(program)
        return prog is not None and prog.balance >= minimum_points

    def estimate_earnings(self, flight_cost: float) -> dict[str, float]:
        """Estimate points earned from a flight purchase using all cards."""
        earnings = {}

        for card in self.cards.values():
            points = flight_cost * card.points_per_dollar
            earnings[card.id] = points

        return earnings

    def print_summary(self) -> None:
        """Print cards and loyalty summary."""
        print("\n" + "=" * 100)
        print("CREDIT CARDS & LOYALTY PROGRAMS")
        print("=" * 100 + "\n")

        if self.cards:
            print("CREDIT CARDS:")
            for card in self.cards.values():
                print(f"  {card.id}: {card.issuer} {card.product}")
                print(f"    Network: {card.network.upper()} | Region: {card.region}")
                if card.annual_fee:
                    print(f"    Annual fee: ${card.annual_fee:.0f}")
                print(f"    Earning rate: {card.points_per_dollar:.1f}x points per $1")
                if card.transfer_partners:
                    print(f"    Transfer partners: {', '.join(card.transfer_partners)}")
                if card.notes:
                    print(f"    Notes: {card.notes}")
                print()

        if self.programs:
            print("LOYALTY PROGRAMS:")
            for prog in self.programs.values():
                print(
                    f"  {prog.program}: {prog.balance:,} points | "
                    f"Tier: {prog.tier.title()}"
                )
                if prog.expiry_date:
                    print(f"    Expires: {prog.expiry_date}")
                print()

        print("=" * 100 + "\n")


def get_loyalty_manager() -> LoyaltyManager:
    """Get or create loyalty manager singleton."""
    return LoyaltyManager()
