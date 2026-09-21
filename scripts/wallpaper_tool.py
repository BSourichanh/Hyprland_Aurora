#!/usr/bin/env python3
"""
Wallpaper Tool & Maintenance CLI for Hyprland / Lucy Theme
Unified utility for binary TEX manipulation, subpixel mask generation,
Steam workshop synchronization, dotfiles hard link audits, and process management.
"""

import argparse
import math
import os
import shutil
import struct
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import List, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESSOURCE_DIR = PROJECT_DIR / "ressource"
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
WORKSHOP_DIR = Path(os.path.expanduser(
    "~/.steam/steam/steamapps/workshop/content/431960/3566437475"
))


# ============================================================================
# 1. BINARY TEX COMPILATION & EXTRACTION (TEXV0005 / TEXB0004)
# ============================================================================

def pack_png_to_tex(png_path: Path, tex_path: Path, width: int = 1920, height: int = 1080):
    """Packs a PNG image into Wallpaper Engine TEXV0005 binary container."""
    with open(png_path, "rb") as f:
        png_data = f.read()

    header = bytearray()
    header += b"TEXV0005\x00"
    header += b"TEXI0001\x00"
    # Format: type=0, flags=2 (ClampUVs), texture_w, texture_h, img_w, img_h, unk=0
    header += struct.pack("<IIIIIII", 0, 2, width, height, width, height, 0)
    header += b"TEXB0004\x00"
    # imageCount=1, freeImageFormat=13 (FIF_PNG), isMp4=0
    header += struct.pack("<III", 1, 13, 0)
    # mipmapCount=1
    header += struct.pack("<I", 1)
    # mipmap entry: width, height, compression=0, uncompressedSize, compressedSize
    header += struct.pack("<IIiii", width, height, 0, len(png_data), len(png_data))

    tex_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tex_path, "wb") as f:
        f.write(header)
        f.write(png_data)


def unpack_tex_to_png(tex_path: Path, png_path: Path) -> bool:
    """Extracts raw PNG data from a TEXV0005 binary container."""
    with open(tex_path, "rb") as f:
        data = f.read()

    png_magic = b"\x89PNG\r\n\x1a\n"
    idx = data.find(png_magic)
    if idx == -1:
        return False

    png_path.parent.mkdir(parents=True, exist_ok=True)
    with open(png_path, "wb") as f:
        f.write(data[idx:])
    return True


# ============================================================================
# 2. MATHEMATICAL SUBPIXEL MASK GENERATION
# ============================================================================

def generate_blackwall_mask(
    input_png: Path = RESSOURCE_DIR / "lucy.png",
    output_png: Path = RESSOURCE_DIR / "blackwall" / "blackwall_mask.png",
    output_tex: Path = RESSOURCE_DIR / "blackwall" / "blackwall_mask.tex",
):
    """
    Generates a subpixel anti-aliased mask from Lucy artwork using mathematical
    gradient decomposition and BFS propagation, preserving hair strands while
    eliminating trapped background and opaque patches.
    """
    if Image is None:
        sys.exit("Erreur : Pillow (PIL) est requis pour générer le masque.")

    im = Image.open(input_png)
    w, h = im.size

    # 1. Calcul de la déviation euclidienne par rapport au fond théorique
    # Background gradient: R(y) = y * 170 / 1079, G = 0, B(y) = y * 88 / 1079
    diffs = [0.0] * (w * h)
    for y in range(h):
        by_r = y * 170.0 / 1079.0
        by_b = y * 88.0 / 1079.0
        for x in range(w):
            r, g, b = im.getpixel((x, y))
            d = math.sqrt((r - by_r) ** 2 + (g - 0.0) ** 2 + (b - by_b) ** 2)
            diffs[y * w + x] = d

    # 2. Ensemencement global sur tout pixel avec D <= 1.8 (fond garanti à 100%)
    visited = bytearray(w * h)
    q = deque()
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if diffs[idx] <= 1.8:
                visited[idx] = 1
                q.append((x, y))

    # 3. Propagation BFS à travers l'anti-aliasing (s'arrête avant le premier plan à D >= 18.0)
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h:
                nidx = ny * w + nx
                if not visited[nidx] and diffs[nidx] < 18.0:
                    visited[nidx] = 1
                    q.append((nx, ny))

    # 4. Construction du masque lissé (smoothstep entre D=1.8 et D=18.0)
    mask = Image.new("L", (w, h), 0)
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if visited[idx]:
                d = diffs[idx]
                if d <= 1.8:
                    m = 255
                elif d >= 18.0:
                    m = 0
                else:
                    t = (d - 1.8) / (18.0 - 1.8)
                    smooth = t * t * (3.0 - 2.0 * t)
                    m = int((1.0 - smooth) * 255)
                mask.putpixel((x, y), m)

    # 5. Filtrage des composantes connexes :
    # - Préserver la fente du col/dos (demande utilisateur de retirer les trous)
    # - Nettoyer le bruit isolé (< 10 px)
    comp_visited = bytearray(w * h)
    components = []
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if not comp_visited[idx] and mask.getpixel((x, y)) > 0:
                comp = []
                cq = deque([(x, y)])
                comp_visited[idx] = 1
                while cq:
                    cx, cy = cq.popleft()
                    comp.append((cx, cy))
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            nidx = ny * w + nx
                            if not comp_visited[nidx] and mask.getpixel((nx, ny)) > 0:
                                comp_visited[nidx] = 1
                                cq.append((nx, ny))
                components.append(comp)

    for comp in components:
        xs = [p[0] for p in comp]
        ys = [p[1] for p in comp]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        is_slit = (min_x >= 1340 and max_x <= 1490 and min_y >= 650 and max_y <= 1010)
        is_noise = len(comp) < 10
        if is_slit or is_noise:
            for x, y in comp:
                mask.putpixel((x, y), 0)

    # 6. Intégration des deux ouvertures entre les doigts (suppression des fonds opaques)
    for y in range(786, 814):
        for x in range(984, 1004):
            r, g, b = im.getpixel((x, y))
            diff = r - g
            if diff >= 75:
                m = 255
            elif diff <= 20:
                m = 0
            else:
                t = (diff - 20.0) / (75.0 - 20.0)
                m = int(t * t * (3.0 - 2.0 * t) * 255)
            if m > mask.getpixel((x, y)):
                mask.putpixel((x, y), m)

    for y in range(896, 934):
        for x in range(878, 938):
            r, g, b = im.getpixel((x, y))
            diff = r - g
            if diff >= 75:
                m = 255
            elif diff <= 20:
                m = 0
            else:
                t = (diff - 20.0) / (75.0 - 20.0)
                m = int(t * t * (3.0 - 2.0 * t) * 255)
            if m > mask.getpixel((x, y)):
                mask.putpixel((x, y), m)

    # Sauvegarde PNG & TEX
    output_png.parent.mkdir(parents=True, exist_ok=True)
    mask.save(output_png)
    pack_png_to_tex(output_png, output_tex, w, h)
    print(f"✓ Masque généré : {output_png} ({w}x{h})")
    print(f"✓ Conteneur binaire compilé : {output_tex}")


# ============================================================================
# 3. SYNCHRONISATION & DÉPLOIEMENT STEAM WORKSHOP
# ============================================================================

def sync_to_workshop():
    """Synchronizes local shaders, materials, and textures into Steam workshop directory."""
    if not WORKSHOP_DIR.exists():
        sys.exit(f"Erreur : Dossier Workshop introuvable : {WORKSHOP_DIR}")

    # Shaders
    src_frag = RESSOURCE_DIR / "blackwall" / "blackwall.frag"
    src_vert = RESSOURCE_DIR / "blackwall" / "blackwall.vert"
    dst_frag = WORKSHOP_DIR / "shaders" / "effects" / "blackwall.frag"
    dst_vert = WORKSHOP_DIR / "shaders" / "effects" / "blackwall.vert"

    if src_frag.exists():
        dst_frag.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_frag, dst_frag)
    if src_vert.exists():
        shutil.copyfile(src_vert, dst_vert)

    # Masque Blackwall
    src_mask_tex = RESSOURCE_DIR / "blackwall" / "blackwall_mask.tex"
    dst_mask_tex = WORKSHOP_DIR / "materials" / "masks" / "blackwall_mask.tex"
    if src_mask_tex.exists():
        dst_mask_tex.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_mask_tex, dst_mask_tex)

    # Texture Lucy
    src_lucy_tex = RESSOURCE_DIR / "lucy.tex"
    dst_lucy_tex = WORKSHOP_DIR / "materials" / "Diseño sin título.tex"
    if src_lucy_tex.exists():
        shutil.copyfile(src_lucy_tex, dst_lucy_tex)

    # Scene JSON
    src_scene = RESSOURCE_DIR / "scene.json"
    dst_scene = WORKSHOP_DIR / "scene.json"
    if src_scene.exists():
        shutil.copyfile(src_scene, dst_scene)

    print("✓ Synchronisation vers Steam Workshop effectuée.")


# ============================================================================
# 4. AUDIT DES HARD LINKS (CONFORMITÉ GEMINI.MD)
# ============================================================================

def audit_hardlinks() -> bool:
    """Verifies that all dotfiles match identical inodes in ~/.config/."""
    mismatches = []
    missing = []
    checked = 0

    for root, _, files in os.walk(DOTFILES_DIR):
        for f in files:
            if f.endswith((".bak", "-bak", ".pyc", ".so")):
                continue
            dot_path = Path(root) / f
            rel = dot_path.relative_to(DOTFILES_DIR)
            conf_path = CONFIG_DIR / rel

            if not conf_path.exists():
                missing.append(rel)
                continue

            checked += 1
            if dot_path.stat().st_ino != conf_path.stat().st_ino:
                mismatches.append(rel)

    print(f"Audit Hardlinks: {checked} fichiers vérifiés.")
    if not mismatches and not missing:
        print("✓ Tous les hard links sont intacts (inodes identiques).")
        return True

    if missing:
        print(f"✗ Fichiers manquants dans ~/.config : {missing}")
    if mismatches:
        print(f"✗ Inodes divergents (liens rompus) : {mismatches}")
    return False


# ============================================================================
# 5. GESTION DES PROCESSUS D'ARRIÈRE-PLAN
# ============================================================================

def restart_wallpapers():
    """Safely terminates and restarts linux-wallpaperengine across dual monitors."""
    subprocess.run(["pkill", "-f", "linux-wallpaperengine"], check=False)
    assets_dir = Path(os.path.expanduser("~/.steam/steam/steamapps/common/wallpaper_engine/assets"))

    cmd_base = [
        "linux-wallpaperengine",
        "--bg", str(WORKSHOP_DIR),
        "--volume", "100",
        "--fps", "30",
        "--disable-parallax",
        "--scaling", "fill",
        "--assets-dir", str(assets_dir),
    ]

    for screen in ["DP-1", "DP-2"]:
        cmd = ["nohup", "linux-wallpaperengine", "--screen-root", screen] + cmd_base[1:]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    print("✓ Moteurs Wallpaper Engine relancés sur DP-1 et DP-2.")


def show_status():
    """Displays running state of Wallpaper Engine processes, monitors and Wayland layers."""
    print("=== État des Processus Wallpaper Engine ===")
    res = subprocess.run(["pgrep", "-fl", "linux-wallpaperengine"], capture_output=True, text=True)
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]

    if not lines:
        print("✗ Aucun processus linux-wallpaperengine actif.")
    else:
        for line in lines:
            parts = line.split(maxsplit=1)
            pid = parts[0]
            screen = "Inconnu"
            cmd_display = ""
            cmdline_file = Path(f"/proc/{pid}/cmdline")
            if cmdline_file.exists():
                try:
                    args_list = cmdline_file.read_bytes().split(b"\x00")
                    args_str = [a.decode("utf-8", errors="ignore") for a in args_list if a]
                    if "--screen-root" in args_str:
                        idx = args_str.index("--screen-root")
                        if idx + 1 < len(args_str):
                            screen = args_str[idx + 1]
                    cmd_display = " ".join(args_str)
                except Exception:
                    pass
            if not cmd_display and len(parts) > 1:
                cmd_display = parts[1]
            print(f"  • PID {pid} : Moniteur [{screen}] ({cmd_display[:70]}...)")
        print(f"✓ Total : {len(lines)} processus actif(s).")

    # Vérification des couches Hyprland
    try:
        layers = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if layers.returncode == 0:
            import json
            data = json.loads(layers.stdout)
            print("\n=== Couches Wayland Détectées (Hyprland) ===")
            layer_names = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}
            for mon, mon_data in data.items():
                active_layers = []
                for lvl_num, lvl_items in mon_data.get("levels", {}).items():
                    lvl_desc = layer_names.get(str(lvl_num), f"Lvl{lvl_num}")
                    for item in lvl_items:
                        active_layers.append(f"{lvl_desc}:{item.get('namespace', '?')}[pid:{item.get('pid', '?')}]")
                print(f"  • {mon} : {' | '.join(active_layers) if active_layers else 'Aucune'}")
    except Exception:
        pass


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Wallpaper Tool & Dotfiles Maintenance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Afficher l'état des processus Wallpaper Engine et couches Wayland")

    # pack
    p_pack = subparsers.add_parser("pack", help="Compresser un PNG en conteneur binaire TEXV0005")
    p_pack.add_argument("input_png", type=Path)
    p_pack.add_argument("output_tex", type=Path)
    p_pack.add_argument("--width", type=int, default=1920)
    p_pack.add_argument("--height", type=int, default=1080)

    # unpack
    p_unpack = subparsers.add_parser("unpack", help="Extraire le PNG d'un conteneur binaire TEXV0005")
    p_unpack.add_argument("input_tex", type=Path)
    p_unpack.add_argument("output_png", type=Path)

    # mask
    subparsers.add_parser("mask", help="Régénérer le masque Blackwall vectoriel haute fidélité")

    # sync
    subparsers.add_parser("sync", help="Synchroniser les assets locaux vers Steam Workshop")

    # check-links
    subparsers.add_parser("check-links", help="Vérifier la stricte intégrité des hard links dotfiles")

    # restart
    subparsers.add_parser("restart", help="Redémarrer les instances linux-wallpaperengine multi-écrans")

    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "pack":
        pack_png_to_tex(args.input_png, args.output_tex, args.width, args.height)
        print(f"✓ Packé : {args.input_png} -> {args.output_tex}")
    elif args.command == "unpack":
        if unpack_tex_to_png(args.input_tex, args.output_png):
            print(f"✓ Décompressé : {args.input_tex} -> {args.output_png}")
        else:
            sys.exit(f"✗ Échec : Impossible d'extraire le PNG de {args.input_tex}")
    elif args.command == "mask":
        generate_blackwall_mask()
    elif args.command == "sync":
        sync_to_workshop()
    elif args.command == "check-links":
        if not audit_hardlinks():
            sys.exit(1)
    elif args.command == "restart":
        restart_wallpapers()


if __name__ == "__main__":
    main()
