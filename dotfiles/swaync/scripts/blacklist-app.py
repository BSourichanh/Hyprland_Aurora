#!/usr/bin/env python3
"""
SwayNC Blacklist Helper - Aurora Theme
Ajoute une application à la liste des notifications ignorées (notification-visibility)
avec verrou flock, sérialisation validée et préservation stricte des hardlinks.
"""

import fcntl
import json
import os
import re
import subprocess
import sys


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", value.lower()).strip("-")


def blacklist_application(app_name: str = None, desktop_entry: str = None, display_name: str = None) -> bool:
    clean_app = app_name.strip() if app_name and app_name.strip() else None
    clean_entry = desktop_entry.strip() if desktop_entry and desktop_entry.strip() else None
    clean_display = display_name.strip() if display_name and display_name.strip() else None

    if not clean_app and not clean_entry and not clean_display:
        return False

    label = clean_display or clean_app or clean_entry
    config_path = os.path.expanduser("~/.config/swaync/config.json")
    if not os.path.exists(config_path):
        return False

    try:
        with open(config_path, "r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = json.load(f)
                visibilities = data.setdefault("notification-visibility", {})
                existing_keys_lower = {k.lower(): k for k in visibilities.keys()}

                def upsert_rule(key: str, rule: dict) -> None:
                    old_key = existing_keys_lower.get(key.lower())
                    if old_key and old_key != key:
                        visibilities.pop(old_key, None)
                    visibilities[key] = rule
                    existing_keys_lower[key.lower()] = key

                if clean_entry:
                    key_entry = "blacklist-entry-" + _slugify(clean_entry)
                    upsert_rule(key_entry, {
                        "state": "ignored",
                        "desktop-entry": f"^(?i){re.escape(clean_entry)}$",
                    })
                    if clean_entry.lower().startswith("snap."):
                        snap_base = clean_entry[5:]
                        key_snap = "blacklist-snap-" + _slugify(snap_base)
                        upsert_rule(key_snap, {
                            "state": "ignored",
                            "desktop-entry": f"^(?i)snap\\.{re.escape(snap_base)}(\\..*)?$",
                        })

                key_app = None
                if clean_app:
                    key_app = "blacklist-app-" + _slugify(clean_app)
                    upsert_rule(key_app, {
                        "state": "ignored",
                        "app-name": f"^(?i){re.escape(clean_app)}$",
                    })

                seen_lower = {k.lower() for k in (clean_app, clean_entry) if k}
                if clean_display and clean_display.lower() not in seen_lower:
                    key_disp = "blacklist-app-" + _slugify(clean_display)
                    if key_disp != key_app:
                        upsert_rule(key_disp, {
                            "state": "ignored",
                            "app-name": f"^(?i){re.escape(clean_display)}$",
                        })

                serialized = json.dumps(data, indent=2) + "\n"
                json.loads(serialized)
                f.seek(0)
                f.write(serialized)
                f.truncate()
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        subprocess.run(["swaync-client", "-R"], check=False)
        subprocess.run([
            "notify-send",
            "SwayNC — Blacklist",
            f"🚫 Notifications de « {label} » désormais bloquées.",
            "-a", "SwayNC",
            "-u", "normal",
        ], check=False)
        return True
    except Exception as e:
        sys.stderr.write(f"Erreur blacklist_application: {e}\n")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    app = sys.argv[1] if len(sys.argv) > 1 else ""
    entry = sys.argv[2] if len(sys.argv) > 2 else ""
    display = sys.argv[3] if len(sys.argv) > 3 else ""
    success = blacklist_application(app, entry, display)
    sys.exit(0 if success else 1)