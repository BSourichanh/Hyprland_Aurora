#!/usr/bin/env python3
"""
Functional Test Suite: Workspace Autocompact Bounding & C99 Compilation
Verifies:
1. workspace-autocompact.py: Bounding logic and zero leakage across monitors
2. workspace-autocompact.py: Overflow workspaces (> max) bypass other monitor pool & reserved 90-99
3. C99 Dry Compilation in /tmp: 0 warnings under -std=c99 -Wall -Wextra -Wpedantic and clean link
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES = PROJECT_ROOT / "dotfiles"
HYPR_SCRIPTS = DOTFILES / "hypr" / "scripts"
SCRIPTS = PROJECT_ROOT / "scripts"
SRC_C99 = PROJECT_ROOT / "src" / "aurora_wallpaper"


class TestAutocompactAndC99(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script_path = HYPR_SCRIPTS / "workspace-autocompact.py"
        spec = importlib.util.spec_from_file_location("autocompact", script_path)
        cls.compact_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.compact_mod)

    def test_autocompact_nominal_pool_bounding(self):
        """Validates that normal workspace counts stay strictly within base..max."""
        global_bound = {6, 7, 8, 9, 10}
        other_occ = {6, 7}
        targets = self.compact_mod._build_targets(
            count=3,
            base=1,
            max_ws=5,
            global_bound=global_bound,
            other_occupied=other_occ,
            max_pool_ws=10,
        )
        self.assertEqual(targets, [1, 2, 3], "Nominal target workspaces should be [1, 2, 3]")
        self.assertTrue(all(1 <= t <= 5 for t in targets), "Workspaces must stay in DP-2 range (1..5)")

    def test_autocompact_overflow_no_inter_monitor_leakage(self):
        """Validates that overflow (> max) skips other monitors' range (6..10) and reserved (90..99)."""
        global_bound = {6, 7, 8, 9, 10}
        other_occ = {6, 7, 8}
        targets = self.compact_mod._build_targets(
            count=7,
            base=1,
            max_ws=5,
            global_bound=global_bound,
            other_occupied=other_occ,
            max_pool_ws=10,
        )
        self.assertEqual(targets, [1, 2, 3, 4, 5, 11, 12])
        # Ensure zero leakage into DP-1 pool (6..10)
        self.assertFalse(any(t in global_bound for t in targets), "Leak detected into DP-1 workspace pool!")
        # Ensure zero collision with reserved range 90..99
        self.assertFalse(any(90 <= t <= 99 for t in targets), "Collision with reserved range 90..99!")

    def test_autocompact_dp1_monitor_bounding(self):
        """Validates that DP-1 (base 6, max 10) compacts within its range."""
        global_bound = {1, 2, 3, 4, 5}
        other_occ = {1, 2}
        targets = self.compact_mod._build_targets(
            count=4,
            base=6,
            max_ws=10,
            global_bound=global_bound,
            other_occupied=other_occ,
            max_pool_ws=10,
        )
        self.assertEqual(targets, [6, 7, 8, 9])
        self.assertFalse(any(t in global_bound for t in targets), "Leak detected into DP-2 workspace pool!")

    def test_c99_dry_compilation_and_link(self):
        """Compiles aurora-wallpaper in /tmp under strict -std=c99 -Wall -Wextra -Wpedantic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            c_flags = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Wpedantic"]
            
            # Compile main.c and gl_utils.c with pedantic flags
            c1 = subprocess.run(
                ["gcc", *c_flags, "-c", str(SRC_C99 / "main.c"), "-o", str(tmp_path / "main.o")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(c1.returncode, 0, f"Compilation of main.c failed:\n{c1.stderr}")
            self.assertEqual(c1.stderr.strip(), "", f"Unexpected compiler warnings on main.c:\n{c1.stderr}")

            c2 = subprocess.run(
                ["gcc", *c_flags, "-c", str(SRC_C99 / "gl_utils.c"), "-o", str(tmp_path / "gl_utils.o")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(c2.returncode, 0, f"Compilation of gl_utils.c failed:\n{c2.stderr}")
            self.assertEqual(c2.stderr.strip(), "", f"Unexpected compiler warnings on gl_utils.c:\n{c2.stderr}")

            # Compile protocol files
            p1 = subprocess.run(
                ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-c",
                 str(SRC_C99 / "wlr-layer-shell-unstable-v1-protocol.c"), "-o", str(tmp_path / "wlr.o")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p1.returncode, 0, f"Compilation of wlr protocol failed:\n{p1.stderr}")

            p2 = subprocess.run(
                ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-c",
                 str(SRC_C99 / "xdg-shell-protocol.c"), "-o", str(tmp_path / "xdg.o")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p2.returncode, 0, f"Compilation of xdg protocol failed:\n{p2.stderr}")

            # Link aurora-wallpaper
            link = subprocess.run(
                ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra",
                 str(tmp_path / "main.o"), str(tmp_path / "gl_utils.o"),
                 str(tmp_path / "wlr.o"), str(tmp_path / "xdg.o"),
                 "-lwayland-client", "-lwayland-egl", "-lEGL", "-lGLESv2", "-lm",
                 "-o", str(tmp_path / "aurora-wallpaper")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(link.returncode, 0, f"Linking failed:\n{link.stderr}")
            out_bin = tmp_path / "aurora-wallpaper"
            self.assertTrue(out_bin.exists() and os.access(out_bin, os.X_OK), "Executable not generated or not executable")

    def test_autocompact_emits_lua_0572_dispatchers(self):
        """Validates exclusive emission of 0.57.2 Lua dispatchers without legacy commands."""
        captured = []
        monitors = [{"name": "DP-2", "focused": True, "activeWorkspace": {"id": 3}}]
        clients = [{"mapped": True, "pinned": False, "workspace": {"id": 3}, "address": "0xabc"}]
        workspaces = [{"id": 3, "monitor": "DP-2"}]

        def fake_json(query, timeout=1.0):
            return {"j/monitors": monitors, "j/clients": clients, "j/workspaces": workspaces}.get(query, [])

        with patch.object(self.compact_mod, "is_session_locked", return_value=False), \
             patch.object(self.compact_mod, "get_monitor_configs", return_value={"DP-2": {"base": 1, "max": 5}, "DP-1": {"base": 6, "max": 10}}), \
             patch.object(self.compact_mod, "hypr_json", side_effect=fake_json), \
             patch.object(self.compact_mod, "hypr_batch", side_effect=lambda d: captured.extend(d) or "ok"):
            self.assertTrue(self.compact_mod.compact_workspaces())

        self.assertTrue(captured, "Expected non-empty Lua dispatches")
        for cmd in captured:
            self.assertTrue(cmd.startswith("dispatch hl.dsp.window.move(") or cmd.startswith("dispatch hl.dsp.focus("), f"Unexpected dispatch: {cmd}")
            self.assertNotIn("movetoworkspacesilent", cmd)
            self.assertNotIn("focusmonitor", cmd)

    def test_hypr_ipc_move_window_pixel_lua_0572(self):
        """Validates move_window_pixel emits Hyprland 0.57.2 hl.dsp.window.move syntax."""
        if str(HYPR_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(HYPR_SCRIPTS))
        import hypr_ipc
        with patch.object(hypr_ipc, "hypr_cmd") as mock_cmd:
            hypr_ipc.move_window_pixel(600, 44, "spotify-card")
            mock_cmd.assert_called_once_with(
                'dispatch hl.dsp.window.move({ x = 600, y = 44, window = "class:spotify-card" })',
                timeout=0.05,
            )

    def test_aurora_osd_caps_and_overdrive(self):
        """Validates aurora_osd caps-lock j/devices query and >100% overdrive payload."""
        spec = importlib.util.spec_from_file_location("aurora_osd", SCRIPTS / "aurora_osd.py")
        osd_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(osd_mod)

        with patch.object(osd_mod, "hypr_json", return_value={"keyboards": [{"main": True, "capsLock": True}]}):
            caps = osd_mod.handle_action("caps-lock")
        self.assertEqual(caps["kind"], "caps")
        self.assertFalse(caps["muted"])
        self.assertFalse(caps["overdrive"])
        self.assertEqual(caps["fraction"], 1.0)
        self.assertIn("activé", caps["label"])

        with patch.object(osd_mod.subprocess, "run"), \
             patch.object(osd_mod, "_parse_wpctl", return_value=(125, False)):
            vol = osd_mod.handle_action("volume-up")
        self.assertEqual(vol["kind"], "volume")
        self.assertTrue(vol["overdrive"])
        self.assertFalse(vol["muted"])
        self.assertEqual(vol["fraction"], 1.0)
        self.assertEqual(vol["label"], "125%")

        osd_src = (SCRIPTS / "aurora_osd.py").read_text(encoding="utf-8")
        self.assertIn("bar.set_no_show_all(True)", osd_src)
        self.assertLess(
            osd_src.index("win.show_all()"),
            osd_src.index('bar.set_visible(payload.get("kind") != "caps")'),
        )


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAutocompactAndC99)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
