#!/usr/bin/env python3
"""
Functional Test Suite: Screen Lock and Idle / Suspend Policy (P1 Decision)
Verifies:
1. hypridle.conf: inhibit_sleep = 3 in general block
2. hypridle.conf: Palier 4 (1800s) inhibits 'systemctl suspend' if session is locked
3. lock.sh: executes hyprlock under 'systemd-inhibit --what=sleep'
4. lock.sh: enforces singleton mutex flock and cleans $AURORA_RUNTIME_DIR/hypr_locked on exit
"""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES = PROJECT_ROOT / "dotfiles"
HYPR_DIR = DOTFILES / "hypr"


class TestLockAndIdlePolicy(unittest.TestCase):
    def setUp(self):
        self.idle_conf = HYPR_DIR / "hypridle.conf"
        self.lock_sh = HYPR_DIR / "lock.sh"
        self.assertTrue(self.idle_conf.exists(), f"Missing {self.idle_conf}")
        self.assertTrue(self.lock_sh.exists(), f"Missing {self.lock_sh}")
        self.idle_content = self.idle_conf.read_text(encoding="utf-8")
        self.lock_content = self.lock_sh.read_text(encoding="utf-8")

    def test_hypridle_inhibit_sleep_setting(self):
        """Validates that general { inhibit_sleep = 3 } is configured."""
        match = re.search(r"inhibit_sleep\s*=\s*(\d+)", self.idle_content)
        self.assertIsNotNone(match, "inhibit_sleep not declared in hypridle.conf")
        self.assertEqual(int(match.group(1)), 3, "inhibit_sleep must be 3")

    def test_hypridle_palier_4_condition_under_lock(self):
        """Simulates hypridle Palier 4 bash test under mock lock condition in /tmp with isolated pgrep mock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            mock_runtime = tmp_path / "aurora"
            mock_runtime.mkdir(mode=0o700, parents=True)
            mock_lock_flag = mock_runtime / "hypr_locked"

            mock_bin = tmp_path / "bin"
            mock_bin.mkdir(mode=0o755)
            mock_pgrep = mock_bin / "pgrep"

            custom_env = os.environ.copy()
            custom_env["XDG_RUNTIME_DIR"] = tmpdir
            custom_env["PATH"] = f"{mock_bin}:{custom_env.get('PATH', '')}"

            cmd = '[ ! -f "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora/hypr_locked" ] && ! pgrep -x hyprlock >/dev/null'

            # Branch 1: Sous verrou (hypr_locked présent ET mock pgrep -x hyprlock renvoyant 0) -> commande retourne code 1 (inhibition)
            mock_lock_flag.touch(mode=0o600)
            mock_pgrep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mock_pgrep.chmod(0o755)
            res1 = subprocess.run(cmd, shell=True, env=custom_env)
            self.assertEqual(res1.returncode, 1, "Palier 4 condition must return exit code 1 (inhibition) under lock")

            # Branch 2: Sans verrou (aucun fichier ET mock pgrep renvoyant 1) -> commande retourne code 0
            if mock_lock_flag.exists():
                mock_lock_flag.unlink()
            mock_pgrep.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            mock_pgrep.chmod(0o755)
            res2 = subprocess.run(cmd, shell=True, env=custom_env)
            self.assertEqual(res2.returncode, 0, "Palier 4 condition must return exit code 0 when session is unlocked")

    def test_hypridle_palier_3_no_black_screen_under_lock(self):
        """Verifies Palier 1 (150s) and Palier 3 (330s) guard against dimming/DPMS off under lock, and lock.sh inhibit settings."""
        guard = '[ ! -f "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora/hypr_locked" ] && ! pgrep -x hyprlock >/dev/null'
        listeners = re.findall(r"listener\s*\{([\s\S]*?)\n\}", self.idle_content)

        # Palier 1 (timeout = 150, dimming) : garde anti-verrou
        p1_blocks = [b for b in listeners if re.search(r"timeout\s*=\s*150", b)]
        self.assertEqual(len(p1_blocks), 1, "Palier 1 listener (timeout = 150) must appear once in hypridle.conf")
        p1_block = p1_blocks[0]
        self.assertIn(guard, p1_block, "Palier 1 (dimming) must contain anti-lock guard")
        self.assertIn("brightnessctl", p1_block, "Palier 1 must handle backlight dimming")

        # Palier 3 (timeout = 330, DPMS off) : garde anti-verrou
        p3_blocks = [b for b in listeners if re.search(r"timeout\s*=\s*330", b)]
        self.assertEqual(len(p3_blocks), 1, "Palier 3 listener (timeout = 330) must appear once in hypridle.conf")
        p3_block = p3_blocks[0]
        self.assertIn(guard, p3_block, "Palier 3 (DPMS off) must contain anti-lock guard")
        self.assertIn("hyprctl dispatch dpms off", p3_block, "Palier 3 must dispatch dpms off")

        # Vérifier que lock.sh contient systemd-inhibit --what=sleep:idle et hyprctl dispatch dpms on
        self.assertIn("--what=sleep:idle", self.lock_content, "lock.sh must inhibit both sleep and idle")
        self.assertIn("hyprctl dispatch dpms on", self.lock_content, "lock.sh must turn dpms on at lock time")

    def test_lock_script_systemd_inhibit(self):
        """Validates that lock.sh uses systemd-inhibit --what=sleep to disable suspend."""
        self.assertIn("systemd-inhibit", self.lock_content)
        self.assertIn("--what=sleep", self.lock_content)
        self.assertIn("hyprlock", self.lock_content)

    def test_lock_script_runtime_mutex_and_flag(self):
        """Validates that lock.sh creates $AURORA_RUNTIME_DIR/hypr_locked and uses flock mutex."""
        self.assertIn('AURORA_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora"', self.lock_content)
        self.assertIn('LOCK_FLAG="$AURORA_RUNTIME_DIR/hypr_locked"', self.lock_content)
        self.assertIn('INSTANCE_LOCK="$AURORA_RUNTIME_DIR/hypr_lock_instance.lock"', self.lock_content)
        self.assertIn("flock -n 9", self.lock_content)
        self.assertIn('rm -f "$LOCK_FLAG"', self.lock_content)

    def test_lua_0572_dpms_and_window_pin_syntax(self):
        """Validates Hyprland 0.57.2 table syntax for hl.dsp.dpms and hl.dsp.window.pin."""
        self.assertIn("hl.dsp.dpms({ action =", self.idle_content)
        self.assertIn("hl.dsp.dpms({ action =", self.lock_content)
        self.assertNotIn('hl.dsp.dpms("', self.idle_content)
        self.assertNotIn('hl.dsp.dpms("', self.lock_content)

        state_src = (HYPR_DIR / "scripts" / "hyprlock_state.py").read_text(encoding="utf-8")
        self.assertIn('hl.dsp.window.pin({{ window = "address:', state_src)
        self.assertNotIn("pin({ address =", state_src)
        self.assertNotIn("pin({{ address =", state_src)


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLockAndIdlePolicy)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
