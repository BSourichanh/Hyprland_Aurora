#!/usr/bin/env python3
"""
SwayNC Blacklist Helper - Aurora Theme
Ajoute une application à la liste des notifications ignorées (notification-visibility)
sans briser les hardlinks GTK / ~/.config/swaync/config.json.
"""

import sys
import os
import json
import re
import subprocess

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
        # Lecture et modification in-place pour préserver strictement l'inode (hardlink)
        with open(config_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            visibilities = data.setdefault("notification-visibility", {})

            # 1. Règle desktop-entry (applications classiques et confinées Snap/Flatpak/Portal)
            if clean_entry:
                key_entry = "blacklist-entry-" + re.sub(r"[^a-zA-Z0-9_-]", "-", clean_entry.lower()).strip("-")
                visibilities[key_entry] = {
                    "state": "ignored",
                    "desktop-entry": f"^(?i){re.escape(clean_entry)}$"
                }

                # Cas spécifique des paquets Snap (ex: snap.antigravity -> snap.antigravity.*)
                if clean_entry.startswith("snap."):
                    snap_base = clean_entry[5:]
                    key_snap = "blacklist-snap-" + re.sub(r"[^a-zA-Z0-9_-]", "-", snap_base.lower()).strip("-")
                    visibilities[key_snap] = {
                        "state": "ignored",
                        "desktop-entry": f"^(?i)snap\\.{re.escape(snap_base)}(\\..*)?$"
                    }

            # 2. Règle app-name (notifications transmettant le nom du binaire)
            if clean_app:
                key_app = "blacklist-app-" + re.sub(r"[^a-zA-Z0-9_-]", "-", clean_app.lower()).strip("-")
                visibilities[key_app] = {
                    "state": "ignored",
                    "app-name": f"^(?i){re.escape(clean_app)}$"
                }

            # 3. Règle display-name si distinct de app_name et desktop_entry
            if clean_display and clean_display not in (clean_app, clean_entry):
                key_disp = "blacklist-app-" + re.sub(r"[^a-zA-Z0-9_-]", "-", clean_display.lower()).strip("-")
                visibilities[key_disp] = {
                    "state": "ignored",
                    "app-name": f"^(?i){re.escape(clean_display)}$"
                }

            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        # Rechargement à chaud de SwayNC
        subprocess.run(["swaync-client", "-R"], check=False)

        # Notification visuelle de confirmation
        subprocess.run([
            "notify-send",
            "SwayNC — Blacklist",
            f"🚫 Notifications de « {label} » désormais bloquées.",
            "-a", "SwayNC",
            "-u", "normal"
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
