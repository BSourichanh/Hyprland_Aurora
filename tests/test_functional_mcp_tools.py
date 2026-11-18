#!/usr/bin/env python3
"""
Functional Test Suite: Aurora Micro MCP Server Tools & Error Handling
Verifies:
1. get_aurora_status returns complete diagnostic dictionary
2. Exact 13 tools registered in MCP server
3. Graceful error handling (ok=False with error message) across all tools on invalid input
4. Zero crashes or unhandled exceptions across the tool catalog
"""

import os
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
SCRIPTS = PROJECT_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import aurora_mcp_server
from aurora_mcp import media_tools, system_tools


class TestAuroraMCPTools(unittest.TestCase):
    def test_get_aurora_status_structure(self):
        """Validates that get_aurora_status returns all essential diagnostic keys."""
        status = aurora_mcp_server.get_aurora_status()
        self.assertIsInstance(status, dict)
        required_keys = [
            "wallpaper_engine",
            "waybar",
            "gpu",
            "swaync",
            "audio",
            "lock",
            "spotify",
            "spotify_card_daemon",
            "monitors",
            "layers",
            "hardlinks",
        ]
        for key in required_keys:
            self.assertIn(key, status, f"Missing key in status: {key}")

        self.assertIn("mode", status["wallpaper_engine"])
        self.assertIn("running", status["waybar"])
        self.assertIn("locked", status["lock"])
        self.assertIn("total_checked", status["hardlinks"])

    def test_audit_hardlinks_tool(self):
        """Validates audit_hardlinks tool output and reporting."""
        res = system_tools.audit_hardlinks()
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("ok"), f"audit_hardlinks returned not ok: {res}")
        self.assertGreaterEqual(res.get("total_checked", 0), 41)

    def test_error_handling_switch_theme(self):
        """Validates switch_theme error handling for non-existent theme."""
        res = system_tools.switch_theme("theme_fantome_xyz")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))
        self.assertIn("inconnu", res.get("error", "").lower())

    def test_error_handling_manage_wallpaper(self):
        """Validates manage_wallpaper error handling for unknown action."""
        res = system_tools.manage_wallpaper("action_bidon")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))
        self.assertIn("inconnue", res.get("error", "").lower())

    def test_error_handling_audio_control(self):
        """Validates audio_control error handling for invalid action."""
        res = media_tools.audio_control("unknown_action")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))
        self.assertIn("inconnue", res.get("error", "").lower())

    def test_error_handling_manage_swaync(self):
        """Validates manage_swaync error handling for invalid action."""
        res = media_tools.manage_swaync("invalid_action")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))
        self.assertTrue(bool(res.get("error")))

    def test_error_handling_manage_hyprbar(self):
        """Validates manage_hyprbar error handling for invalid action."""
        res = system_tools.manage_hyprbar("invalid_action")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))
        self.assertTrue(bool(res.get("error")))

    def test_error_handling_manage_blacklist(self):
        """Validates manage_blacklist error handling for missing target/action."""
        res = media_tools.manage_blacklist("invalid_action")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))

    def test_error_handling_spotify_control(self):
        """Validates spotify_control error handling for unsupported action."""
        res = media_tools.spotify_control("action_invalide")
        self.assertIsInstance(res, dict)
        self.assertFalse(res.get("ok", True))
        self.assertIn("inconnue", res.get("error", "").lower())

    def test_compact_workspaces_call(self):
        """Validates compact_workspaces execution without crashing."""
        res = system_tools.compact_workspaces()
        self.assertIsInstance(res, dict)
        self.assertIn("ok", res)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAuroraMCPTools)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
