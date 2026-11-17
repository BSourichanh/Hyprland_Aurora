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

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES = PROJECT_ROOT / "dotfiles"
HYPR_SCRIPTS = DOTFILES / "hypr" / "scripts"
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


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAutocompactAndC99)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
