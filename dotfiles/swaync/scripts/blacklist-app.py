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

def blacklist_application(app_name: str, desktop_entry: str = None) -> bool:
    if not app_name or not app_name.strip():
        return False
    
    app_name = app_name.strip()
    config_path = os.path.expanduser("~/.config/swaync/config.json")
    if not os.path.exists(config_path):
        return False

    try:
        # Lecture et modification in-place pour préserver strictement l'inode (hardlink)
        with open(config_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            visibilities = data.setdefault("notification-visibility", {})
            
            # Clé normalisée
            sanitized_key = "blacklist-" + re.sub(r"[^a-zA-Z0-9_-]", "-", app_name.lower()).strip("-")
            
            rule = {
                "state": "ignored",
                "app-name": f"^{re.escape(app_name)}$"
            }
            if desktop_entry and desktop_entry.strip() and desktop_entry.strip() != app_name:
                rule["desktop-entry"] = f"^{re.escape(desktop_entry.strip())}$"

            visibilities[sanitized_key] = rule

            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        # Rechargement à chaud de SwayNC
        subprocess.run(["swaync-client", "-R"], check=False)

        # Notification visuelle de confirmation
        subprocess.run([
            "notify-send",
            "SwayNC — Blacklist",
            f"🚫 Notifications de « {app_name} » désormais bloquées.",
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
    
    app = sys.argv[1]
    entry = sys.argv[2] if len(sys.argv) > 2 else None
    success = blacklist_application(app, entry)
    sys.exit(0 if success else 1)
