#!/usr/bin/env python3
"""Multi-user travel workspaces for SkyBuddy.

Every traveller gets an isolated workspace: their own preferences, watched
routes, passenger profiles, loyalty cards, alerts, booking intents and price
history. Nothing is shared between users except the code itself.

Layout::

    config/users.json                     registry + active user
    config/users/<user>/preferences.json  routes and preferences
    config/users/<user>/passengers.json
    config/users/<user>/cards.json
    data/users/<user>/alerts.json
    data/users/<user>/bookings.json
    data/users/<user>/price_baseline.csv
    data/users/<user>/price_observations.csv

The built-in ``default`` user keeps the original top-level paths
(``config/preferences.json``, ``data/alerts.json``, …) so existing installs
keep working untouched.

Usage (CLI)::

    python scripts/users.py create --user harold --display-name "Harold Mateo" \
        --email harold@example.com --home-airport BIO --currency EUR
    python scripts/users.py list
    python scripts/users.py switch --user ana
    python scripts/users.py show --user ana
    python scripts/users.py update --user ana --home-airport MAD
    python scripts/users.py delete --user ana --remove-data
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
USERS_FILE = ROOT / "config" / "users.json"
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"

#: The implicit workspace used when nobody has created a user yet.
DEFAULT_USER = "default"

USER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,38}$")


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601 form."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    """Turn a display name into a usable user id."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-.")
    return slug[:39]


@dataclass
class UserProfile:
    """A traveller who owns a SkyBuddy workspace."""

    user_id: str
    display_name: str = ""
    email: str = ""
    home_airport: str = ""
    currency: str = "EUR"
    notes: str = ""
    created_at: str = ""
    last_active: str = ""


@dataclass
class Workspace:
    """Resolved file locations for one traveller."""

    user_id: str
    config_dir: Path
    data_dir: Path
    preferences_file: Path
    passengers_file: Path
    cards_file: Path
    alerts_file: Path
    bookings_file: Path
    baseline_file: Path
    observations_file: Path

    def ensure(self) -> "Workspace":
        """Create the workspace directories if they do not exist yet."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self

    def as_dict(self) -> dict[str, str]:
        """Return the workspace paths as plain strings."""
        return {
            "user_id": self.user_id,
            "config_dir": str(self.config_dir),
            "data_dir": str(self.data_dir),
            "preferences_file": str(self.preferences_file),
            "passengers_file": str(self.passengers_file),
            "cards_file": str(self.cards_file),
            "alerts_file": str(self.alerts_file),
            "bookings_file": str(self.bookings_file),
            "baseline_file": str(self.baseline_file),
            "observations_file": str(self.observations_file),
        }


def build_workspace(user_id: str, root: Path = ROOT) -> Workspace:
    """Resolve the workspace paths for a user id.

    The ``default`` user maps to SkyBuddy's original top-level files so that
    single-user installs keep working without a migration.
    """
    config_root = root / "config"
    data_root = root / "data"

    if user_id == DEFAULT_USER:
        return Workspace(
            user_id=user_id,
            config_dir=config_root,
            data_dir=data_root,
            preferences_file=config_root / "preferences.json",
            passengers_file=config_root / "passengers.json",
            cards_file=config_root / "cards.json",
            alerts_file=data_root / "alerts.json",
            bookings_file=data_root / "bookings.json",
            baseline_file=data_root / "price_baseline.csv",
            observations_file=data_root / "price_observations.csv",
        )

    config_dir = config_root / "users" / user_id
    data_dir = data_root / "users" / user_id
    return Workspace(
        user_id=user_id,
        config_dir=config_dir,
        data_dir=data_dir,
        preferences_file=config_dir / "preferences.json",
        passengers_file=config_dir / "passengers.json",
        cards_file=config_dir / "cards.json",
        alerts_file=data_dir / "alerts.json",
        bookings_file=data_dir / "bookings.json",
        baseline_file=data_dir / "price_baseline.csv",
        observations_file=data_dir / "price_observations.csv",
    )


class UserManager:
    """Create, switch between and delete traveller workspaces."""

    def __init__(self, users_file: Path = USERS_FILE, root: Path = ROOT):
        """Load the user registry."""
        self.users_file = users_file
        self.root = root
        self.users: dict[str, UserProfile] = {}
        self.active: str = DEFAULT_USER
        self._load()

    # ---------- persistence ----------

    def _load(self) -> None:
        """Read the registry from disk."""
        if not self.users_file.exists():
            return
        try:
            with open(self.users_file, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as error:  # pragma: no cover - defensive
            print(f"Error loading users: {error}")
            return

        self.users = {
            user_id: UserProfile(**payload)
            for user_id, payload in data.get("users", {}).items()
        }
        self.active = data.get("active") or DEFAULT_USER

    def save(self) -> None:
        """Write the registry to disk."""
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active": self.active,
            "updated_at": _now(),
            "users": {user_id: asdict(user) for user_id, user in self.users.items()},
        }
        with open(self.users_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    # ---------- lifecycle ----------

    def create_user(
        self,
        user: str,
        display_name: str = "",
        email: str = "",
        home_airport: str = "",
        currency: str = "EUR",
        notes: str = "",
        make_active: bool = True,
    ) -> dict[str, Any]:
        """Create a traveller workspace.

        Args:
            user: Unique id — lowercase letters, digits, ``.``, ``_`` and ``-``.
            display_name: Human-readable name; defaults to the id.
            email: Contact address used for alerts.
            home_airport: Default origin IATA code.
            currency: Preferred currency for this traveller.
            notes: Free-text context stored with the profile.
            make_active: Switch to this traveller immediately.

        Returns:
            The created profile and its workspace paths, or an error.
        """
        user_id = user.strip().lower()
        if not USER_ID_PATTERN.match(user_id):
            return {
                "status": "error",
                "error": (
                    "User id must start with a letter or digit and use only "
                    "lowercase letters, digits, dots, underscores or hyphens."
                ),
            }
        if user_id in self.users:
            return {"status": "error", "error": f"User '{user_id}' already exists."}

        profile = UserProfile(
            user_id=user_id,
            display_name=display_name or user_id,
            email=email,
            home_airport=home_airport.upper(),
            currency=currency,
            notes=notes,
            created_at=_now(),
            last_active=_now() if make_active else "",
        )
        self.users[user_id] = profile
        workspace = build_workspace(user_id, self.root).ensure()
        if make_active:
            self.active = user_id
        self.save()

        return {
            "status": "created",
            "user": asdict(profile),
            "workspace": workspace.as_dict(),
            "active": self.active,
        }

    def get_user(self, user: Optional[str] = None) -> Optional[UserProfile]:
        """Return a profile, defaulting to the active user."""
        return self.users.get((user or self.active).strip().lower())

    def list_users(self) -> dict[str, Any]:
        """List every traveller and mark the active one."""
        return {
            "active": self.active,
            "total": len(self.users),
            "users": [
                {**asdict(profile), "is_active": profile.user_id == self.active}
                for profile in sorted(self.users.values(), key=lambda item: item.user_id)
            ],
        }

    def switch_user(self, user: str) -> dict[str, Any]:
        """Make a traveller the active one."""
        user_id = user.strip().lower()
        if user_id != DEFAULT_USER and user_id not in self.users:
            return {
                "status": "error",
                "error": f"Unknown user '{user_id}'. Create it first with create_user().",
            }

        self.active = user_id
        profile = self.users.get(user_id)
        if profile is not None:
            profile.last_active = _now()
        self.save()
        return {
            "status": "switched",
            "active": user_id,
            "workspace": build_workspace(user_id, self.root).ensure().as_dict(),
        }

    def update_user(self, user: str, **fields: Any) -> dict[str, Any]:
        """Update profile fields for a traveller."""
        profile = self.users.get(user.strip().lower())
        if profile is None:
            return {"status": "error", "error": f"Unknown user '{user}'."}

        allowed = {"display_name", "email", "home_airport", "currency", "notes"}
        applied = {}
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(profile, key, value.upper() if key == "home_airport" else value)
                applied[key] = getattr(profile, key)

        self.save()
        return {"status": "updated", "user": asdict(profile), "applied": applied}

    def delete_user(self, user: str, remove_data: bool = False) -> dict[str, Any]:
        """Remove a traveller, optionally deleting their stored data."""
        user_id = user.strip().lower()
        if user_id == DEFAULT_USER:
            return {"status": "error", "error": "The default workspace cannot be deleted."}
        if user_id not in self.users:
            return {"status": "error", "error": f"Unknown user '{user_id}'."}

        del self.users[user_id]
        removed_paths: list[str] = []
        if remove_data:
            workspace = build_workspace(user_id, self.root)
            for directory in (workspace.config_dir, workspace.data_dir):
                if directory.exists():
                    shutil.rmtree(directory, ignore_errors=True)
                    removed_paths.append(str(directory))

        if self.active == user_id:
            self.active = next(iter(sorted(self.users)), DEFAULT_USER)

        self.save()
        return {
            "status": "deleted",
            "user_id": user_id,
            "data_removed": removed_paths,
            "active": self.active,
        }

    # ---------- workspaces ----------

    def workspace(self, user: Optional[str] = None) -> Workspace:
        """Return the workspace for a traveller (the active one by default)."""
        user_id = (user or self.active or DEFAULT_USER).strip().lower()
        return build_workspace(user_id, self.root).ensure()

    def current(self) -> dict[str, Any]:
        """Describe the active traveller and workspace."""
        profile = self.users.get(self.active)
        return {
            "active": self.active,
            "user": asdict(profile) if profile else None,
            "is_default_workspace": self.active == DEFAULT_USER,
            "workspace": self.workspace().as_dict(),
        }


def get_user_manager() -> UserManager:
    """Return a ready-to-use user manager."""
    return UserManager()


def get_workspace(user: Optional[str] = None) -> Workspace:
    """Return a workspace without keeping the manager around."""
    return UserManager().workspace(user)


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="SkyBuddy traveller workspaces")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a traveller workspace")
    create.add_argument("--user", required=True)
    create.add_argument("--display-name", default="")
    create.add_argument("--email", default="")
    create.add_argument("--home-airport", default="")
    create.add_argument("--currency", default="EUR")
    create.add_argument("--notes", default="")
    create.add_argument("--no-switch", action="store_true", help="Do not make this the active traveller")

    sub.add_parser("list", help="List travellers")

    switch = sub.add_parser("switch", help="Set the active traveller")
    switch.add_argument("--user", required=True)

    show = sub.add_parser("show", help="Show a traveller and their workspace paths")
    show.add_argument("--user")

    update = sub.add_parser("update", help="Update a traveller profile")
    update.add_argument("--user", required=True)
    update.add_argument("--display-name")
    update.add_argument("--email")
    update.add_argument("--home-airport")
    update.add_argument("--currency")
    update.add_argument("--notes")

    delete = sub.add_parser("delete", help="Delete a traveller")
    delete.add_argument("--user", required=True)
    delete.add_argument("--remove-data", action="store_true", help="Also delete their stored files")

    return parser


def main() -> int:
    """Run the users CLI."""
    args = build_parser().parse_args()
    manager = UserManager()

    if args.command == "create":
        result = manager.create_user(
            user=args.user,
            display_name=args.display_name,
            email=args.email,
            home_airport=args.home_airport,
            currency=args.currency,
            notes=args.notes,
            make_active=not args.no_switch,
        )
    elif args.command == "list":
        result = manager.list_users()
    elif args.command == "switch":
        result = manager.switch_user(args.user)
    elif args.command == "show":
        profile = manager.get_user(args.user)
        result = {
            "user": asdict(profile) if profile else None,
            "workspace": manager.workspace(args.user).as_dict(),
        }
    elif args.command == "update":
        result = manager.update_user(
            args.user,
            display_name=args.display_name,
            email=args.email,
            home_airport=args.home_airport,
            currency=args.currency,
            notes=args.notes,
        )
    else:
        result = manager.delete_user(args.user, remove_data=args.remove_data)

    print(json.dumps(result, indent=2, default=str))
    return 1 if result.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
