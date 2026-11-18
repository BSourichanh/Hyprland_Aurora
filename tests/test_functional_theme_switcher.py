#!/usr/bin/env python3
"""
Functional Test Suite: Theme Switcher & In-Place CSS Palette Regeneration
Verifies:
1. Double successive theme switch in isolated /tmp directory without freezing
2. Sentinel blocks /* AURORA_PALETTE_START */ ... /* AURORA_PALETTE_END */ properly updated
3. Correct consumption of @define-color tokens in Waybar, Wofi, SwayNC, Kitty
4. In-place hardlink inode preservation across theme switches
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
SCRIPTS = PROJECT_ROOT / "scripts"
DOTFILES = PROJECT_ROOT / "dotfiles"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import theme_models
import theme_switcher


class TestThemeSwitcherDoubleSwitch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.tmp_dotfiles = self.tmp_path / "dotfiles"
        shutil.copytree(DOTFILES, self.tmp_dotfiles)
        self.tmp_scripts = self.tmp_path / "scripts"
        self.tmp_scripts.mkdir()
        shutil.copy2(SCRIPTS / "aurora_osd.py", self.tmp_scripts / "aurora_osd.py")
        self.tmp_state = self.tmp_path / ".theme_state"
        self.tmp_state.write_text("aurora\n", encoding="utf-8")

        # Redirect theme_switcher module targets to temporary directory
        self.orig_dotfiles = theme_switcher.DOTFILES_DIR
        self.orig_state = theme_switcher.THEME_STATE_FILE
        self.orig_script_dir = theme_switcher.SCRIPT_DIR
        theme_switcher.DOTFILES_DIR = self.tmp_dotfiles
        theme_switcher.THEME_STATE_FILE = self.tmp_state
        theme_switcher.SCRIPT_DIR = self.tmp_scripts

    def tearDown(self):
        theme_switcher.DOTFILES_DIR = self.orig_dotfiles
        theme_switcher.THEME_STATE_FILE = self.orig_state
        theme_switcher.SCRIPT_DIR = self.orig_script_dir
        self.tmpdir.cleanup()

    def test_double_successive_theme_switch(self):
        """Validates that switching theme twice successively updates CSS without freezing."""
        wb_css = self.tmp_dotfiles / "waybar" / "style.css"
        wofi_css = self.tmp_dotfiles / "wofi" / "style.css"
        svg_bg = self.tmp_dotfiles / "waybar" / "bar-bg.svg"

        # Record original inodes
        wb_ino = wb_css.stat().st_ino
        wofi_ino = wofi_css.stat().st_ino

        # --- SWITCH 1: tokyo-night ---
        theme1 = theme_models.get_theme("tokyo-night")
        theme_switcher.update_bar_svg(theme1)
        theme_switcher.update_waybar_css(theme1)
        theme_switcher.update_wofi_css(theme1)
        theme_switcher.update_swaync_css(theme1)
        theme_switcher.update_kitty_conf(theme1)

        wb_text1 = wb_css.read_text(encoding="utf-8")
        wofi_text1 = wofi_css.read_text(encoding="utf-8")
        svg_text1 = svg_bg.read_text(encoding="utf-8")

        self.assertIn("@define-color waybar-primary #7aa2f7;", wb_text1)
        self.assertIn("@define-color wofi-primary #7aa2f7;", wofi_text1)
        self.assertIn("#7aa2f7", svg_text1)
        self.assertEqual(wb_text1.count("/* AURORA_PALETTE_START */"), 1)
        self.assertEqual(wofi_text1.count("/* AURORA_PALETTE_START */"), 1)

        # Verify inodes preserved
        self.assertEqual(wb_css.stat().st_ino, wb_ino, "Hardlink inode broken on switch 1 for Waybar")
        self.assertEqual(wofi_css.stat().st_ino, wofi_ino, "Hardlink inode broken on switch 1 for Wofi")

        # --- SWITCH 2: cyberpunk-amber ---
        theme2 = theme_models.get_theme("cyberpunk-amber")
        theme_switcher.update_bar_svg(theme2)
        theme_switcher.update_waybar_css(theme2)
        theme_switcher.update_wofi_css(theme2)
        theme_switcher.update_swaync_css(theme2)
        theme_switcher.update_kitty_conf(theme2)

        wb_text2 = wb_css.read_text(encoding="utf-8")
        wofi_text2 = wofi_css.read_text(encoding="utf-8")
        svg_text2 = svg_bg.read_text(encoding="utf-8")

        # Validate that Tokyo Night primary is replaced by Cyberpunk Amber (#ffb800)
        self.assertIn("@define-color waybar-primary #ffb800;", wb_text2)
        self.assertIn("@define-color wofi-primary #ffb800;", wofi_text2)
        self.assertNotIn("@define-color waybar-primary #7aa2f7;", wb_text2, "CSS frozen on first theme!")
        self.assertNotIn("@define-color wofi-primary #7aa2f7;", wofi_text2, "Wofi frozen on first theme!")
        self.assertIn("#ffb800", svg_text2)

        # Validate exactly one sentinel block exists
        self.assertEqual(wb_text2.count("/* AURORA_PALETTE_START */"), 1)
        self.assertEqual(wofi_text2.count("/* AURORA_PALETTE_START */"), 1)

        # Inodes still preserved
        self.assertEqual(wb_css.stat().st_ino, wb_ino, "Hardlink inode broken on switch 2 for Waybar")
        self.assertEqual(wofi_css.stat().st_ino, wofi_ino, "Hardlink inode broken on switch 2 for Wofi")

        # --- SWITCH 3: Revert to default aurora ---
        theme_def = theme_models.get_theme("aurora")
        theme_switcher.update_bar_svg(theme_def)
        theme_switcher.update_waybar_css(theme_def)
        theme_switcher.update_wofi_css(theme_def)

        wb_text3 = wb_css.read_text(encoding="utf-8")
        self.assertIn("@define-color waybar-primary #00f0ff;", wb_text3)
        self.assertEqual(wb_text3.count("/* AURORA_PALETTE_START */"), 1)

    def test_hyprland_lua_theme_switch_and_verify(self):
        """Validates hyprland.lua theme round-trip (aurora -> tokyo-night -> aurora), hardlink inode, and Hyprland --verify-config."""
        lua_path = self.tmp_dotfiles / "hypr" / "hyprland.lua"
        hardlink_peer = self.tmp_path / "hyprland_hardlink.lua"
        os.link(lua_path, hardlink_peer)

        orig_text = lua_path.read_text(encoding="utf-8")
        orig_ino = lua_path.stat().st_ino
        self.assertEqual(lua_path.stat().st_nlink, 2)
        self.assertEqual(hardlink_peer.stat().st_ino, orig_ino)
        self.assertIs(theme_switcher.update_hyprland_lua, theme_switcher.update_hyprland_conf)

        aurora = theme_models.get_theme("aurora")
        tokyo = theme_models.get_theme("tokyo-night")
        self.assertIsNotNone(aurora)
        self.assertIsNotNone(tokyo)

        # Baseline aurora should already match repository defaults
        self.assertFalse(theme_switcher.update_hyprland_conf(aurora))

        # Switch aurora -> tokyo-night
        self.assertTrue(theme_switcher.update_hyprland_conf(tokyo))
        self.assertEqual(lua_path.stat().st_ino, orig_ino, "Inode changed on tokyo-night switch")
        self.assertEqual(lua_path.stat().st_nlink, 2, "Hardlink count changed on tokyo-night switch")
        self.assertEqual(hardlink_peer.stat().st_ino, orig_ino)

        tn_text = lua_path.read_text(encoding="utf-8")
        self.assertEqual(tn_text, hardlink_peer.read_text(encoding="utf-8"))
        self.assertIn(
            '            active_border = { colors = { "rgba(7AA2F7FF)", "rgba(7DCFFFFF)", "rgba(BB9AF7FF)", "rgba(7AA2F7FF)" }, angle = 45 },',
            tn_text,
        )
        self.assertIn('            inactive_border = "rgba(1F2335aa)",', tn_text)
        self.assertFalse(theme_switcher.update_hyprland_conf(tokyo), "Idempotent tokyo-night call must return False")

        res_tn = subprocess.run(
            ["Hyprland", "--config", str(lua_path), "--verify-config"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(res_tn.returncode, 0, f"Hyprland --verify-config failed (tokyo-night):\n{res_tn.stdout}\n{res_tn.stderr}")
        self.assertIn("config ok", res_tn.stdout + res_tn.stderr)

        # Switch back tokyo-night -> aurora (identical round-trip)
        self.assertTrue(theme_switcher.update_hyprland_conf(aurora))
        self.assertEqual(lua_path.stat().st_ino, orig_ino, "Inode changed on aurora revert")
        self.assertEqual(lua_path.stat().st_nlink, 2, "Hardlink count changed on aurora revert")
        self.assertEqual(hardlink_peer.stat().st_ino, orig_ino)
        self.assertEqual(lua_path.read_text(encoding="utf-8"), orig_text)
        self.assertEqual(hardlink_peer.read_text(encoding="utf-8"), orig_text)

        res_au = subprocess.run(
            ["Hyprland", "--config", str(lua_path), "--verify-config"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(res_au.returncode, 0, f"Hyprland --verify-config failed (aurora):\n{res_au.stdout}\n{res_au.stderr}")
        self.assertIn("config ok", res_au.stdout + res_au.stderr)

    def test_aurora_osd_palette_update_and_inode(self):
        """Validates update_aurora_osd() preserves hardlink inode and updates palette sentinel."""
        osd_path, osd_peer = self.tmp_scripts / "aurora_osd.py", self.tmp_path / "aurora_osd_hardlink.py"
        os.link(osd_path, osd_peer)
        orig_ino = osd_path.stat().st_ino
        self.assertEqual(osd_path.stat().st_nlink, 2)

        theme_switcher.update_aurora_osd(theme_models.get_theme("tokyo-night"))
        self.assertEqual((osd_path.stat().st_ino, osd_path.stat().st_nlink, osd_peer.stat().st_ino), (orig_ino, 2, orig_ino))
        tn_text = osd_path.read_text(encoding="utf-8")
        self.assertEqual(tn_text, osd_peer.read_text(encoding="utf-8"))
        self.assertTrue("#7aa2f7" in tn_text and ".osd-overdrive" in tn_text and tn_text.count("# AURORA_PALETTE_START") == 1)

        theme_switcher.update_aurora_osd(theme_models.get_theme("aurora"))
        self.assertEqual(osd_path.stat().st_ino, orig_ino)
        self.assertIn("#00f0ff", osd_path.read_text(encoding="utf-8"))


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestThemeSwitcherDoubleSwitch)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
