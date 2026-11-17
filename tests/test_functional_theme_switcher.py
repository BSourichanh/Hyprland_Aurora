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
        self.tmp_state = self.tmp_path / ".theme_state"
        self.tmp_state.write_text("aurora\n", encoding="utf-8")

        # Redirect theme_switcher module targets to temporary directory
        self.orig_dotfiles = theme_switcher.DOTFILES_DIR
        self.orig_state = theme_switcher.THEME_STATE_FILE
        theme_switcher.DOTFILES_DIR = self.tmp_dotfiles
        theme_switcher.THEME_STATE_FILE = self.tmp_state

    def tearDown(self):
        theme_switcher.DOTFILES_DIR = self.orig_dotfiles
        theme_switcher.THEME_STATE_FILE = self.orig_state
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


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestThemeSwitcherDoubleSwitch)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
