#!/usr/bin/env python3
"""
Wallpaper Tool & Maintenance CLI for Hyprland / Lucy Theme
Unified utility for binary TEX manipulation, subpixel mask generation,
Steam workshop synchronization, dotfiles hard link audits, and process management.
"""

import argparse
import contextlib
import fcntl
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None
    ImageFilter = None


@contextlib.contextmanager
def file_mutex(lock_path: str, non_blocking: bool = True):
    """Context manager acquiring an exclusive file lock, yielding True if acquired."""
    try:
        lock_fd = open(lock_path, "w")
        flags = fcntl.LOCK_EX
        if non_blocking:
            flags |= fcntl.LOCK_NB
        fcntl.flock(lock_fd, flags)
    except (BlockingIOError, IOError):
        yield False
        return

    try:
        yield True
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESSOURCE_DIR = PROJECT_DIR / "ressource"
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
WORKSHOP_DIR = Path(os.path.expanduser(
    "~/.steam/steam/steamapps/workshop/content/431960/3566437475"
))
RENDERER_CONFIG_PATH = DOTFILES_DIR / "hypr" / "wallpaper_renderer.json"


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
    print(f"✓ Masque Blackwall généré : {output_png} ({w}x{h})")
    print(f"✓ Conteneur binaire Blackwall compilé : {output_tex}")


def generate_eye_shine_mask(
    input_png: Path = RESSOURCE_DIR / "lucy.png",
    output_png: Path = RESSOURCE_DIR / "materials" / "masks" / "shine_downsample2_mask_b309bcdf.png",
    output_tex: Path = RESSOURCE_DIR / "materials" / "masks" / "shine_downsample2_mask_b309bcdf.tex",
):
    """
    Génère le masque vectoriel de la pupille (oeil droit et gauche) avec anti-aliasing sous-pixel,
    éliminant strictement la barrette de cheveux, la sclère blanche et les paupières.
    """
    if Image is None or ImageFilter is None:
        sys.exit("Erreur : Pillow (PIL) est requis pour générer le masque.")

    im = Image.open(input_png)
    w, h = im.size
    mask = Image.new("L", (w, h), 0)

    # Calcul dynamique de la courbe de la paupière supérieure (oeil droit)
    top_eyelid_bottom = {}
    for x in range(1085, 1180):
        last_lid = 280
        for y in range(275, 325):
            r, g, b = im.getpixel((x, y))[:3]
            if r < 55 and g < 52 and b < 72:
                last_lid = y
        top_eyelid_bottom[x] = last_lid

    # 1. Iris & Pupille oeil droit (calque organique suivant la paupière et l'iris)
    for y in range(285, 360):
        for x in range(1090, 1180):
            # Strictement en dessous de la ligne de la paupière supérieure
            if y <= top_eyelid_bottom.get(x, 280):
                continue

            r, g, b = im.getpixel((x, y))[:3]
            
            # Exclure le trait sombre de la paupière inférieure
            if r < 50 and g < 46 and b < 64 and y > 330:
                continue
            # Exclure la sclère (blanc de l'oeil) en bas à gauche
            if x < 1100 and y > 343:
                continue
            # Exclure les pixels hors coin externe
            if x > 1172:
                continue
                
            is_cyan = (b - r > 35) and (g - r > 15) and (b > 110)
            is_magenta = (r - g > 20) and (b - g > 10) and (r > 85)
            # Pupille centrale (strictement confinée à l'ellipse centrale sans dépasser en bas)
            is_pupil = (r < 100) and (g < 80) and (b < 105) and (r > 35) and (b > 40) and (x >= 1110) and (x <= 1142) and (y >= 300) and (y <= 328)
            # Reflet spéculaire blanc
            is_specular = (r > 180) and (g > 180) and (b > 180) and (x >= 1130) and (x <= 1170) and (y <= 325)

            if is_cyan or is_magenta or is_pupil or is_specular:
                mask.putpixel((x, y), 255)

    # 2. Iris & Pupille oeil gauche (croissant visible sous la mèche)
    for y in range(390, 440):
        for x in range(730, 788):
            r, g, b = im.getpixel((x, y))[:3]
            is_cyan = (b - r > 25) and (g - r > 12) and (b > 85)
            is_magenta = (r - g > 18) and (b - g > 8) and (r > 75)
            is_specular = (r > 175) and (g > 175) and (b > 175) and (x > 755) and (y < 425)
            if (is_cyan or is_magenta or is_specular) and not (r < 38 and g < 38 and b < 48):
                mask.putpixel((x, y), 255)

    # Remplissage des micro-interstices internes par fermeture morphologique
    mask_closed = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    # Lissage gaussien subpixel doux (0.7px) pour préserver des bords nets et précis
    mask_smooth = mask_closed.filter(ImageFilter.GaussianBlur(radius=0.7))

    # Downsampling haute qualité Lanczos à 960x540 (format natif HalfCompoBuffer)
    mask_540 = mask_smooth.resize((960, 540), Image.Resampling.LANCZOS)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    mask_540.save(output_png)
    pack_png_to_tex(output_png, output_tex, 960, 540)
    print(f"✓ Masque pupille généré : {output_png} (960x540)")
    print(f"✓ Conteneur binaire pupille compilé : {output_tex}")


# ============================================================================
# 3. SYNCHRONISATION & DÉPLOIEMENT STEAM WORKSHOP
# ============================================================================

def unpack_scene_pkg(pkg_file: Path, workshop_dir: Path) -> bool:
    """
    Extracts all files from a Wallpaper Engine scene.pkg archive and renames it
    to scene.pkg.orig to prevent VFS shadowing of loose shader/material assets.
    """
    if not pkg_file.exists():
        return False
    try:
        with open(pkg_file, "rb") as f:
            magic_len = struct.unpack("<I", f.read(4))[0]
            _magic = f.read(magic_len).decode("ascii")
            file_count = struct.unpack("<I", f.read(4))[0]
            entries = []
            for _ in range(file_count):
                nl = struct.unpack("<I", f.read(4))[0]
                name = f.read(nl).decode("utf-8")
                offset = struct.unpack("<I", f.read(4))[0]
                size = struct.unpack("<I", f.read(4))[0]
                entries.append((name, offset, size))
            header_end = f.tell()
            for name, offset, size in entries:
                target = workshop_dir / name
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    f.seek(header_end + offset)
                    target.write_bytes(f.read(size))
        orig_file = workshop_dir / "scene.pkg.orig"
        if orig_file.exists():
            pkg_file.unlink()
        else:
            pkg_file.rename(orig_file)
        print("✓ Archive scene.pkg décompressée et renommée en scene.pkg.orig")
        return True
    except Exception as e:
        print(f"⚠️ Erreur lors du déballage de scene.pkg : {e}")
        return False


def copy_asset(src: Path, dst: Path):
    """Copies src to dst, creating parent directories if needed."""
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def sync_tree(src_dir: Path, dst_dir: Path):
    """Recursively syncs all files from src_dir to dst_dir."""
    if not src_dir.exists():
        return
    for s_file in src_dir.rglob("*"):
        if s_file.is_file():
            rel = s_file.relative_to(src_dir)
            target = dst_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(s_file, target)


def sync_to_workshop():
    """Synchronizes local shaders, materials, and textures into Steam workshop directory."""
    if not WORKSHOP_DIR.exists():
        sys.exit(f"Erreur : Dossier Workshop introuvable : {WORKSHOP_DIR}")

    # 1. Neutralisation de l'archive scene.pkg si présente
    unpack_scene_pkg(WORKSHOP_DIR / "scene.pkg", WORKSHOP_DIR)

    # 2. Synchronisation récursive des arborescences d'assets
    sync_tree(RESSOURCE_DIR / "shaders", WORKSHOP_DIR / "shaders")
    sync_tree(RESSOURCE_DIR / "materials", WORKSHOP_DIR / "materials")

    # 3. Table déclarative des fichiers individuels
    asset_map: List[Tuple[Path, Path]] = [
        (RESSOURCE_DIR / "blackwall" / "blackwall.frag", WORKSHOP_DIR / "shaders" / "effects" / "blackwall.frag"),
        (RESSOURCE_DIR / "blackwall" / "blackwall.vert", WORKSHOP_DIR / "shaders" / "effects" / "blackwall.vert"),
        (RESSOURCE_DIR / "blackwall" / "blackwall_mask.tex", WORKSHOP_DIR / "materials" / "masks" / "blackwall_mask.tex"),
        (RESSOURCE_DIR / "blackwall" / "effect.json", WORKSHOP_DIR / "effects" / "blackwall" / "effect.json"),
        (RESSOURCE_DIR / "blackwall" / "blackwall.json", WORKSHOP_DIR / "materials" / "effects" / "blackwall.json"),
        (RESSOURCE_DIR / "lucy_model.json", WORKSHOP_DIR / "models" / "Diseño sin título.json"),
        (RESSOURCE_DIR / "lucy_material.json", WORKSHOP_DIR / "materials" / "Diseño sin título.json"),
        (RESSOURCE_DIR / "lucy.tex", WORKSHOP_DIR / "materials" / "Diseño sin título.tex"),
        (RESSOURCE_DIR / "scene.json", WORKSHOP_DIR / "scene.json"),
    ]
    for src, dst in asset_map:
        copy_asset(src, dst)

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
# 5. GESTION DU MOTEUR DE RENDU (GPU VS CPU) & PROCESSUS
# ============================================================================

def load_renderer_config() -> dict:
    """Loads renderer configuration (gpu vs cpu, target FPS)."""
    default_cfg = {"renderer": "gpu", "fps_gpu": 60, "fps_cpu": 20}
    if RENDERER_CONFIG_PATH.exists():
        try:
            with open(RENDERER_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_renderer_config(cfg: dict):
    """Saves renderer configuration to wallpaper_renderer.json."""
    RENDERER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RENDERER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def detect_process_renderer(pid: str) -> str:
    """Detects whether a running process is executing on GPU or CPU (LLVMpipe)."""
    env_file = Path(f"/proc/{pid}/environ")
    if env_file.exists():
        try:
            for e in env_file.read_bytes().split(b"\x00"):
                if e in (b"LIBGL_ALWAYS_SOFTWARE=1", b"GALLIUM_DRIVER=llvmpipe"):
                    return "CPU (Mesa LLVMpipe)"
        except Exception:
            pass

    fd_dir = Path(f"/proc/{pid}/fd")
    if fd_dir.exists():
        try:
            for fd in fd_dir.iterdir():
                if fd.is_symlink() and "renderD128" in os.readlink(fd):
                    return "GPU (Intel UHD 630)"
        except Exception:
            pass
    return "GPU (Matériel)"


RESTART_LOCK_FILE = "/tmp/wallpaper_restart.lock"


def is_wallpaper_engine_proc(pid: int) -> bool:
    """Verifies that the process executable is actually linux-wallpaperengine."""
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
        return exe.endswith("/linux-wallpaperengine")
    except Exception:
        return False


def get_running_wallpaper_procs() -> list:
    """Returns list of dicts [{'pid': int, 'screen': str}] for all running wallpaper instances."""
    procs = []
    res = subprocess.run(["pgrep", "-f", "linux-wallpaperengine"], capture_output=True, text=True)
    pids = [p.strip() for p in res.stdout.splitlines() if p.strip()]
    for pid_str in pids:
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        if not is_wallpaper_engine_proc(pid):
            continue
        cmdline_file = Path(f"/proc/{pid}/cmdline")
        if cmdline_file.exists():
            try:
                args = [a.decode("utf-8", errors="ignore") for a in cmdline_file.read_bytes().split(b"\x00") if a]
                if "--screen-root" in args:
                    idx = args.index("--screen-root")
                    if idx + 1 < len(args):
                        procs.append({"pid": pid, "screen": args[idx + 1]})
            except Exception:
                pass
    return procs


def get_running_wallpaper_screens() -> dict:
    """Returns a mapping {screen_name: pid} for currently running wallpaper instances."""
    return {p["screen"]: p["pid"] for p in get_running_wallpaper_procs()}


def get_active_layer_wallpaper_screens() -> dict:
    """Returns {monitor_name: pid} for monitors that have an active Wayland layer in Hyprland."""
    active = {}
    try:
        res = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for mon, mon_data in data.items():
                for lvl, items in mon_data.get("levels", {}).items():
                    for item in items:
                        if item.get("namespace") == "linux-wallpaperengine":
                            active[mon] = item.get("pid")
    except Exception:
        pass
    return active


def get_hyprland_connected_screens() -> list:
    """Returns list of currently active screens under Hyprland."""
    try:
        m_res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        if m_res.returncode == 0:
            m_data = json.loads(m_res.stdout)
            detected = [m.get("name") for m in m_data if m.get("name")]
            if detected:
                return detected
    except Exception:
        pass
    return ["DP-1", "DP-2"]


def cleanup_ghost_wallpapers(screen: str = None):
    """Kills any wallpaper engine processes that have lost their active Wayland layer."""
    active_layers = get_active_layer_wallpaper_screens()
    running_procs = get_running_wallpaper_procs()
    for p in running_procs:
        pid = p["pid"]
        s_name = p["screen"]
        if screen and s_name != screen:
            continue
        if s_name not in active_layers or active_layers[s_name] != pid:
            try:
                os.kill(pid, 9)
            except Exception:
                pass


def build_wallpaper_cmd(screen: str, fps: int) -> List[str]:
    """Constructs optimized command line for linux-wallpaperengine."""
    assets_dir = Path(os.path.expanduser("~/.steam/steam/steamapps/common/wallpaper_engine/assets"))
    return [
        "nohup", "linux-wallpaperengine",
        "--screen-root", screen,
        "--bg", str(WORKSHOP_DIR),
        "--silent",
        "--no-audio-processing",
        "--disable-mouse",
        "--fullscreen-pause-only-active",
        "--fps", str(fps),
        "--disable-parallax",
        "--scaling", "fill",
        "--assets-dir", str(assets_dir),
    ]


def build_wallpaper_env(renderer: str) -> dict:
    """Builds optimized environment variables disabling SDL audio and configuring GPU/CPU."""
    env = os.environ.copy()
    env["SDL_AUDIODRIVER"] = "dummy"
    if renderer == "cpu":
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env["GALLIUM_DRIVER"] = "llvmpipe"
    else:
        env.pop("LIBGL_ALWAYS_SOFTWARE", None)
        env.pop("GALLIUM_DRIVER", None)
    return env


def ensure_wallpapers(target_screen: str = None):
    """
    Ensures Wallpaper Engine is active on connected screen(s).
    Crucially: NEVER kills or restarts an already running screen instance with an active Wayland layer!
    Kills any ghost/hung processes that lost their Wayland layer upon screen disconnect.
    """
    with file_mutex(RESTART_LOCK_FILE) as acquired:
        if not acquired:
            return

        cleanup_ghost_wallpapers()
        active_layers = get_active_layer_wallpaper_screens()
        connected = get_hyprland_connected_screens()

        screens_to_start = []
        if target_screen:
            if target_screen in connected and target_screen not in active_layers:
                screens_to_start.append(target_screen)
        else:
            for s in connected:
                if s not in active_layers:
                    screens_to_start.append(s)

        if not screens_to_start:
            return

        cfg = load_renderer_config()
        current_renderer = cfg.get("renderer", "gpu").lower()
        fps = cfg.get("fps_cpu", 20) if current_renderer == "cpu" else cfg.get("fps_gpu", 30)

        env = build_wallpaper_env(current_renderer)

        for screen in screens_to_start:
            cmd = build_wallpaper_cmd(screen, fps)
            subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        mode_label = "CPU (Mesa LLVMpipe)" if current_renderer == "cpu" else "GPU (Intel UHD 630)"
        print(f"✓ Wallpaper Engine démarré sélectivement sur {', '.join(screens_to_start)} [{mode_label} @ {fps} FPS] (autres écrans inchangés).")


DAEMON_LOCK_FILE = "/tmp/wallpaper_daemon.lock"


def get_event_socket_path() -> str:
    """Discovers the active Hyprland event socket path (.socket2.sock)."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        return ""
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if his:
        sock = os.path.join(runtime_dir, "hypr", his, ".socket2.sock")
        if os.path.exists(sock):
            return sock
    hypr_dir = os.path.join(runtime_dir, "hypr")
    if os.path.isdir(hypr_dir):
        for entry in os.listdir(hypr_dir):
            candidate = os.path.join(hypr_dir, entry, ".socket2.sock")
            if os.path.exists(candidate):
                return candidate
    return ""


def run_wallpaper_daemon():
    """
    Continuous background daemon monitoring Hyprland monitor events (.socket2.sock).
    Automatically restores Wallpaper Engine on reconnected/woken monitors without touching
    already running screens.
    """
    import fcntl
    import signal
    import select
    import socket

    try:
        lock_fd = open(DAEMON_LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
    except (BlockingIOError, IOError):
        print("Le démon Wallpaper Engine est déjà actif.", file=sys.stderr)
        sys.exit(0)

    event_sock_path = get_event_socket_path()
    if not event_sock_path or not os.path.exists(event_sock_path):
        print("Erreur: Socket événement Hyprland introuvable.", file=sys.stderr)
        sys.exit(1)

    def handle_exit(sig, frame):
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            if os.path.exists(DAEMON_LOCK_FILE):
                os.remove(DAEMON_LOCK_FILE)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Initialisation au démarrage : garantir la présence sur les écrans connectés
    ensure_wallpapers()

    print(f"✓ Démon Wallpaper Engine démarré (PID {os.getpid()}), écoute sur {event_sock_path}...")
    sys.stdout.flush()

    pending_ensure = {}  # {target_screen: timestamp}
    debounce_delay = 0.4
    last_config_reload = 0.0

    def extract_monitor_name(ev_line: str) -> str:
        if ">>" not in ev_line:
            return ""
        payload = ev_line.split(">>", 1)[1]
        parts = [p.strip() for p in payload.split(",")]
        for p in parts:
            if p in ("DP-1", "DP-2") or p.startswith("DP-") or p.startswith("HDMI-") or p.startswith("eDP-"):
                return p
        return parts[0] if parts else ""

    while True:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(event_sock_path)
            s.setblocking(False)
            buf = ""
            while True:
                now = time.time()
                timeout = 2.0
                if pending_ensure:
                    earliest = min(pending_ensure.values())
                    timeout = min(timeout, max(0.0, earliest - now))

                rlist, _, _ = select.select([s], [], [], timeout)

                if s in rlist:
                    data = s.recv(4096)
                    if not data:
                        break
                    buf += data.decode("utf-8", errors="replace")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        ev_type = line.split(">>")[0]
                        if ev_type.startswith("monitoradded"):
                            mon = extract_monitor_name(line)
                            target = mon if mon in ("DP-1", "DP-2") else "all"
                            pending_ensure[target] = time.time() + debounce_delay
                        elif ev_type.startswith("monitorremoved"):
                            mon = extract_monitor_name(line)
                            cleanup_ghost_wallpapers(screen=mon if mon in ("DP-1", "DP-2") else None)
                        elif ev_type == "configreloaded":
                            now_t = time.time()
                            if now_t - last_config_reload > 1.0:
                                last_config_reload = now_t
                                pending_ensure["all"] = time.time() + 0.3

                now_check = time.time()
                ready = [m for m, t in list(pending_ensure.items()) if now_check >= t]
                if ready:
                    for m in ready:
                        pending_ensure.pop(m, None)
                    for m in ready:
                        ensure_wallpapers(target_screen=None if m == "all" else m)
                elif not os.path.exists("/tmp/hypr_locked"):
                    # Auto-guérison si un écran s'est rallumé sans événement (ex. sortie de veille DPMS)
                    try:
                        active_layers = get_active_layer_wallpaper_screens()
                        connected = get_hyprland_connected_screens()
                        if any(scr not in active_layers for scr in connected):
                            ensure_wallpapers()
                    except Exception:
                        pass

            s.close()
        except Exception:
            time.sleep(1.0)
            event_sock_path = get_event_socket_path()
            if not event_sock_path or not os.path.exists(event_sock_path):
                time.sleep(2.0)


def restart_wallpapers(renderer: str = None, fps: int = None, screen: str = None):
    """Safely terminates and restarts linux-wallpaperengine across dual monitors with GPU/CPU selection."""
    with file_mutex(RESTART_LOCK_FILE) as acquired:
        if not acquired:
            # Un redémarrage est déjà en cours d'exécution
            return

        if screen:
            for p in get_running_wallpaper_procs():
                if p["screen"] == screen:
                    try:
                        os.kill(p["pid"], 9)
                    except Exception:
                        pass
            time.sleep(0.1)
            active_screens = [screen]
        else:
            for p in get_running_wallpaper_procs():
                try:
                    os.kill(p["pid"], 9)
                except Exception:
                    pass
            for _ in range(10):
                if not get_running_wallpaper_procs():
                    break
                time.sleep(0.05)
            active_screens = get_hyprland_connected_screens()

        assets_dir = Path(os.path.expanduser("~/.steam/steam/steamapps/common/wallpaper_engine/assets"))

        cfg = load_renderer_config()
        changed = False
        if renderer:
            cfg["renderer"] = renderer.lower()
            changed = True
        if fps:
            if cfg.get("renderer", "gpu").lower() == "cpu":
                cfg["fps_cpu"] = fps
            else:
                cfg["fps_gpu"] = fps
            changed = True
        if changed:
            save_renderer_config(cfg)

        current_renderer = cfg.get("renderer", "gpu").lower()
        if fps is None:
            fps = cfg.get("fps_cpu", 20) if current_renderer == "cpu" else cfg.get("fps_gpu", 30)

        env = build_wallpaper_env(current_renderer)

        for scr in active_screens:
            cmd = build_wallpaper_cmd(scr, fps)
            subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        mode_label = "CPU (Mesa LLVMpipe)" if current_renderer == "cpu" else "GPU (Intel UHD 630)"
        print(f"✓ Moteurs Wallpaper Engine relancés sur {', '.join(active_screens)} en mode [{mode_label}] @ {fps} FPS.")


def set_renderer_command(mode: str = None):
    """CLI handler for viewing or setting the renderer mode (gpu or cpu)."""
    cfg = load_renderer_config()
    if not mode:
        current = cfg.get("renderer", "gpu").upper()
        label = "Matériel (Intel UHD 630)" if current == "GPU" else "Logiciel (Mesa LLVMpipe)"
        print(f"Mode de rendu configuré pour Lucy : [{current}] — {label}")
        print(f"  • Cadences cibles : GPU={cfg.get('fps_gpu', 30)} FPS | CPU={cfg.get('fps_cpu', 20)} FPS")
        print("\nPour basculer :")
        print("  ./scripts/wallpaper_tool.py renderer gpu")
        print("  ./scripts/wallpaper_tool.py renderer cpu")
        return

    mode = mode.lower()
    if mode not in ("gpu", "cpu"):
        sys.exit(f"✗ Mode invalide '{mode}'. Choisissez 'gpu' ou 'cpu'.")

    cfg["renderer"] = mode
    save_renderer_config(cfg)
    print(f"✓ Configuration enregistrée : [{mode.upper()}]")
    restart_wallpapers(renderer=mode)


def show_status():
    """Displays running state of Wallpaper Engine processes, monitors and Wayland layers."""
    cfg = load_renderer_config()
    current_mode = cfg.get("renderer", "gpu").upper()
    mode_desc = "Accélération Matérielle (Intel UHD 630)" if current_mode == "GPU" else "Rendu Logiciel (Mesa LLVMpipe)"

    print(f"=== Moteur Lucy : Mode Configuré [{current_mode}] ({mode_desc}) ===")

    daemon_pid = None
    if os.path.exists(DAEMON_LOCK_FILE):
        try:
            with open(DAEMON_LOCK_FILE, "r") as f:
                content = f.read().strip()
                if content.isdigit():
                    d_pid = int(content)
                    if os.path.exists(f"/proc/{d_pid}"):
                        daemon_pid = d_pid
        except Exception:
            pass
    if daemon_pid:
        print(f"=== Démon Hotplug IPC : Actif [PID {daemon_pid}] ===")
    else:
        print("=== Démon Hotplug IPC : Inactif ===")

    print("=== État des Processus Wallpaper Engine ===")
    res = subprocess.run(["pgrep", "-f", "linux-wallpaperengine"], capture_output=True, text=True)
    pids = [p.strip() for p in res.stdout.strip().splitlines() if p.strip()]
    valid_pids = [p for p in pids if p.isdigit() and is_wallpaper_engine_proc(int(p))]

    if not valid_pids:
        print("✗ Aucun processus linux-wallpaperengine actif.")
    else:
        total_rss = 0.0
        total_cpu = 0.0
        for pid in valid_pids:
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
            if not cmd_display:
                cmd_display = "linux-wallpaperengine"

            # Extraction métriques ressources (CPU & RAM RSS)
            rss_mb = 0.0
            status_file = Path(f"/proc/{pid}/status")
            if status_file.exists():
                try:
                    for sline in status_file.read_text().splitlines():
                        if sline.startswith("VmRSS:"):
                            rss_mb = int(sline.split()[1]) / 1024
                            break
                except Exception:
                    pass

            cpu_pct = "0.0"
            try:
                ps_res = subprocess.run(["ps", "-p", pid, "-o", "%cpu", "--no-headers"], capture_output=True, text=True)
                if ps_res.returncode == 0:
                    cpu_pct = ps_res.stdout.strip()
                    total_cpu += float(cpu_pct.replace(",", "."))
            except Exception:
                pass
            total_rss += rss_mb

            proc_renderer = detect_process_renderer(pid)
            cpu_val = float(cpu_pct.replace(",", "."))
            num_cpus = os.cpu_count() or 1
            global_pct = cpu_val / num_cpus
            print(f"  • PID {pid} : Moniteur [{screen}] | Moteur: [{proc_renderer}] | CPU: {cpu_pct}% ({global_pct:.1f}% global) | RAM: {rss_mb:.1f} Mo")
        num_cpus = os.cpu_count() or 1
        total_cores_pct = num_cpus * 100.0
        total_global = total_cpu / num_cpus
        print(f"✓ Total : {len(valid_pids)} processus actif(s) | CPU: {total_cpu:.1f}% (sur {total_cores_pct:.0f}% max, soit {total_global:.1f}% global) | RAM: {total_rss:.1f} Mo")

        # Fréquence iGPU
        gpu_freq_file = Path("/sys/class/drm/card1/gt_act_freq_mhz")
        if not gpu_freq_file.exists():
            gpu_freq_file = Path("/sys/class/drm/card0/gt_act_freq_mhz")
        if gpu_freq_file.exists():
            try:
                freq = gpu_freq_file.read_text().strip()
                print(f"  • Fréquence GPU active : {freq} MHz")
            except Exception:
                pass

    # Vérification des couches Hyprland
    try:
        layers = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if layers.returncode == 0:
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

    # renderer
    p_rend = subparsers.add_parser("renderer", help="Choisir ou afficher le mode de rendu (gpu ou cpu) pour Lucy")
    p_rend.add_argument("mode", nargs="?", choices=["gpu", "cpu"], help="Mode de rendu : 'gpu' (matériel) ou 'cpu' (logiciel LLVMpipe)")

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
    p_rest = subparsers.add_parser("restart", help="Redémarrer les instances linux-wallpaperengine multi-écrans")
    p_rest.add_argument("--renderer", choices=["gpu", "cpu"], help="Forcer le mode de rendu GPU ou CPU")
    p_rest.add_argument("--fps", type=int, help="Forcer le nombre d'images par seconde (FPS)")
    p_rest.add_argument("--screen", choices=["DP-1", "DP-2"], help="Redémarrer uniquement un écran spécifique")

    # ensure
    p_ens = subparsers.add_parser("ensure", help="Démarrer Wallpaper Engine sur un écran sans redémarrer les autres")
    p_ens.add_argument("screen", nargs="?", help="Écran spécifique à démarrer si absent (ex: DP-1)")

    # daemon
    subparsers.add_parser("daemon", help="Lancer le démon d'écoute hotplug IPC pour restauration automatique")

    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "renderer":
        set_renderer_command(args.mode)
    elif args.command == "daemon":
        run_wallpaper_daemon()
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
        generate_eye_shine_mask()
    elif args.command == "sync":
        sync_to_workshop()
    elif args.command == "check-links":
        if not audit_hardlinks():
            sys.exit(1)
    elif args.command == "ensure":
        ensure_wallpapers(target_screen=args.screen)
    elif args.command == "restart":
        restart_wallpapers(renderer=args.renderer, fps=args.fps, screen=args.screen)


if __name__ == "__main__":
    main()

