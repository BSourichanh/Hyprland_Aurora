#!/usr/bin/env python3
"""
Test Suite: Hard Links and Inode Audit between dotfiles/ and ~/.config/
Verifies:
1. Physical inode identity between dotfiles/ and ~/.config/ (canonical 42 hardlinks)
2. Structural nature: True hard link (st_nlink >= 2, no directory or file symlinks)
3. Permissions audit: 0700 for directories / $AURORA_RUNTIME_DIR, 0600 for runtime state/locks
4. Blocking exit code (exit 1 on any failure, exit 0 strictly on 42/42 pass)
"""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES_DIR = PROJECT_ROOT / "dotfiles"
CONFIG_DIR = Path.home() / ".config"

EXCLUDED_EXTS = (".bak", "-bak", ".pyc")
NOMINAL_HARDLINKS_COUNT = 42


def audit_hardlinks() -> bool:
    print("==================================================")
    print("HARD LINKS & INODE AUDIT SUITE")
    print("==================================================")
    print(f"Project root:    {PROJECT_ROOT}")
    print(f"Source dotfiles: {DOTFILES_DIR}")
    print(f"Target config:   {CONFIG_DIR}\n")

    if not DOTFILES_DIR.is_dir():
        print(f"✗ ERROR: Dotfiles directory does not exist: {DOTFILES_DIR}")
        return False

    checked = 0
    true_hardlinks = []
    dir_symlinks = []
    missing_files = []
    mismatches = []
    skipped_excluded = []
    perm_warnings = []

    for root, dirs, files in os.walk(DOTFILES_DIR):
        if "__pycache__" in Path(root).parts:
            continue
        for f in sorted(files):
            src_path = Path(root) / f
            rel_path = src_path.relative_to(DOTFILES_DIR)
            dest_path = CONFIG_DIR / rel_path

            if f.endswith(EXCLUDED_EXTS) or any(src_path.name.endswith(ex) for ex in EXCLUDED_EXTS):
                skipped_excluded.append(str(rel_path))
                continue

            checked += 1

            if not dest_path.exists() and not dest_path.is_symlink():
                missing_files.append(str(rel_path))
                continue

            src_stat = src_path.stat()
            dest_stat = dest_path.stat()

            # Check if linked through an ancestor directory symlink
            parent_symlink = None
            curr = dest_path
            while curr != CONFIG_DIR and curr != curr.parent:
                if curr.is_symlink():
                    parent_symlink = curr
                    break
                curr = curr.parent

            if parent_symlink:
                dir_symlinks.append({
                    "file": str(rel_path),
                    "inode": src_stat.st_ino,
                    "symlink_root": str(parent_symlink),
                })
            elif src_stat.st_ino != dest_stat.st_ino:
                mismatches.append({
                    "file": str(rel_path),
                    "src_ino": src_stat.st_ino,
                    "dst_ino": dest_stat.st_ino,
                    "reason": "Inode mismatch between source and destination",
                })
            elif src_stat.st_nlink < 2 or dest_stat.st_nlink < 2:
                mismatches.append({
                    "file": str(rel_path),
                    "src_ino": src_stat.st_ino,
                    "src_nlink": src_stat.st_nlink,
                    "dst_nlink": dest_stat.st_nlink,
                    "reason": "Single link (nlink < 2)",
                })
            else:
                true_hardlinks.append({
                    "file": str(rel_path),
                    "inode": src_stat.st_ino,
                    "nlink": dest_stat.st_nlink,
                    "mode": oct(dest_stat.st_mode & 0o777),
                })

            # Check execution permission for scripts
            if rel_path.suffix in (".sh", ".py") or "scripts" in rel_path.parts:
                if not (dest_stat.st_mode & 0o111):
                    perm_warnings.append(f"Script not executable: {rel_path} ({oct(dest_stat.st_mode & 0o777)})")

    # Audit $AURORA_RUNTIME_DIR permissions (CONTRAT-RUNTIME.md: 0700 dir, 0600 files)
    runtime_base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    runtime_dir = Path(runtime_base) / "aurora"
    runtime_perm_ok = True
    if runtime_dir.exists():
        r_mode = runtime_dir.stat().st_mode & 0o777
        if r_mode != 0o700:
            perm_warnings.append(f"$AURORA_RUNTIME_DIR mode {oct(r_mode)} != 0700 ({runtime_dir})")
            runtime_perm_ok = False
        for rf in runtime_dir.iterdir():
            if rf.is_file() and not rf.is_symlink():
                f_mode = rf.stat().st_mode & 0o777
                if f_mode != 0o600:
                    perm_warnings.append(f"Runtime lock/state file mode {oct(f_mode)} != 0600 ({rf.name})")
                    runtime_perm_ok = False

    print(f"Total dotfiles analyzed:     {checked} (Expected nominal: {NOMINAL_HARDLINKS_COUNT})")
    print(f"Excluded files (.bak, .pyc): {len(skipped_excluded)}")
    print(f"True Hard Links (nlink >= 2): {len(true_hardlinks)}")
    print(f"Directory-level Symlinks:    {len(dir_symlinks)}")
    print(f"Missing in ~/.config/:       {len(missing_files)}")
    print(f"Inode mismatches:            {len(mismatches)}")
    print(f"Permission anomalies:        {len(perm_warnings)}")

    print("\n--- [1] TRUE HARD LINKS (Individually linked inodes) ---")
    for item in true_hardlinks:
        print(f"  ✓ [HARDLINK] {item['file']:<45} (Inode: {item['inode']}, Links: {item['nlink']}, Mode: {item['mode']})")

    if dir_symlinks:
        print("\n--- [2] DIRECTORY SYMLINKS (FORBIDDEN) ---")
        for item in dir_symlinks:
            print(f"  ✗ [SYMLINK] {item['file']} via {item['symlink_root']}")

    if missing_files:
        print("\n--- [3] MISSING FILES ---")
        for m in missing_files:
            print(f"  ✗ [MISSING] {m}")

    if mismatches:
        print("\n--- [4] INODE MISMATCHES / DISCONNECTED ---")
        for mis in mismatches:
            print(f"  ✗ [MISMATCH] {mis}")

    if perm_warnings:
        print("\n--- [5] PERMISSION ANOMALIES ---")
        for pw in perm_warnings:
            print(f"  ✗ [PERM] {pw}")

    nominal_count_ok = (checked == NOMINAL_HARDLINKS_COUNT and len(true_hardlinks) == NOMINAL_HARDLINKS_COUNT)
    all_passed = (
        nominal_count_ok
        and len(missing_files) == 0
        and len(mismatches) == 0
        and len(dir_symlinks) == 0
        and runtime_perm_ok
    )

    print("\n==================================================")
    if all_passed:
        print(f"RESULT: PASS — 100% True Hard Links ({len(true_hardlinks)}/{NOMINAL_HARDLINKS_COUNT}) with valid inodes & permissions!")
    elif not nominal_count_ok:
        print(f"RESULT: FAIL — Hardlinks count mismatch (got {len(true_hardlinks)}, expected {NOMINAL_HARDLINKS_COUNT}).")
    else:
        print("RESULT: FAIL — Disconnected, missing files, symlinks, or permission errors detected.")
    print("==================================================")
    return all_passed


if __name__ == "__main__":
    success = audit_hardlinks()
    sys.exit(0 if success else 1)
