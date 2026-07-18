#!/usr/bin/env python3
"""Price alerts and notifications system."""
from __future__ import annotations

import json
import smtplib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
ALERTS_FILE = ROOT / "data" / "alerts.json"


@dataclass
class PriceAlert:
    """A price alert event."""

    route_name: str
    origin: str
    destination: str
    current_price: float
    currency: str
    previous_price: Optional[float]
    price_drop_percent: float
    alert_type: str  # "below_target", "below_median", "price_drop"
    booking_url: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AlertsManager:
    """Manage flight price alerts and notifications."""

    def __init__(self, alerts_file: Path = ALERTS_FILE):
        """Initialize alerts manager."""
        self.alerts_file = alerts_file
        self.alerts: list[PriceAlert] = self._load_alerts()

    def _load_alerts(self) -> list[PriceAlert]:
        """Load previous alerts from file."""
        if not self.alerts_file.exists():
            return []

        try:
            with open(self.alerts_file) as f:
                data = json.load(f)
                return [PriceAlert(**alert) for alert in data.get("alerts", [])]
        except Exception as e:
            print(f"Error loading alerts: {e}")
            return []

    def save_alerts(self) -> None:
        """Save alerts to file."""
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)

        data = {"alerts": [asdict(alert) for alert in self.alerts[-100:]]}  # Keep last 100

        with open(self.alerts_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_alert(
        self,
        route_name: str,
        origin: str,
        destination: str,
        current_price: float,
        currency: str,
        previous_price: Optional[float],
        alert_type: str,
        booking_url: str,
    ) -> PriceAlert:
        """Create and store a price alert."""
        price_drop = 0.0
        if previous_price:
            price_drop = ((previous_price - current_price) / previous_price) * 100

        alert = PriceAlert(
            route_name=route_name,
            origin=origin,
            destination=destination,
            current_price=current_price,
            currency=currency,
            previous_price=previous_price,
            price_drop_percent=price_drop,
            alert_type=alert_type,
            booking_url=booking_url,
        )

        self.alerts.append(alert)
        self.save_alerts()
        return alert

    def get_recent_alerts(self, hours: int = 24) -> list[PriceAlert]:
        """Get alerts from the last N hours."""
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            alert
            for alert in self.alerts
            if datetime.fromisoformat(alert.timestamp) > cutoff_time
        ]

    def format_alert_message(self, alert: PriceAlert) -> str:
        """Format alert for display/notification."""
        message = f"[FLIGHT ALERT] {alert.route_name}\n"
        message += f"{alert.origin} → {alert.destination}\n"
        message += f"Price: {alert.currency} {alert.current_price:.2f}"

        if alert.previous_price:
            message += f" (was {alert.currency} {alert.previous_price:.2f})"
            message += f" — {alert.price_drop_percent:.1f}% drop\n"
        else:
            message += "\n"

        message += f"Type: {alert.alert_type}\n"
        message += f"Book now: {alert.booking_url}\n"
        message += f"Time: {alert.timestamp}\n"

        return message

    def send_email_alert(
        self,
        alert: PriceAlert,
        recipient_email: str,
        sender_email: Optional[str] = None,
        sender_password: Optional[str] = None,
    ) -> bool:
        """Send alert via email."""
        if not sender_email or not sender_password:
            print("Email credentials not configured")
            return False

        try:
            message = MIMEText(self.format_alert_message(alert))
            message["Subject"] = f"Flight Alert: {alert.route_name} - {alert.currency} {alert.current_price:.2f}"
            message["From"] = sender_email
            message["To"] = recipient_email

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(message)

            print(f"Alert sent to {recipient_email}")
            return True

        except Exception as e:
            print(f"Error sending email alert: {e}")
            return False

    def print_alert(self, alert: PriceAlert) -> None:
        """Print alert to console."""
        print("\n" + "=" * 80)
        print(self.format_alert_message(alert))
        print("=" * 80 + "\n")

    def get_alerts_by_route(self, route_name: str) -> list[PriceAlert]:
        """Get all alerts for a specific route."""
        return [alert for alert in self.alerts if alert.route_name == route_name]


def get_alerts_manager() -> AlertsManager:
    """Get or create alerts manager singleton."""
    return AlertsManager()
