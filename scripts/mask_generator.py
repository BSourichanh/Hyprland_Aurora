#!/usr/bin/env python3
"""
Mask Generator Module for Aurora Wallpaper Engine
Mathematical subpixel mask generation for blackwall cutouts and eye shine shaders.
"""

import math
import sys
from collections import deque
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None
    ImageFilter = None

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESSOURCE_DIR = PROJECT_DIR / "ressource"


def generate_blackwall_mask(
    input_png: Optional[Path] = None,
    output_png: Optional[Path] = None,
):
    """
    Generates a subpixel anti-aliased mask from Lucy artwork using mathematical
    gradient decomposition and BFS propagation, preserving hair strands while
    eliminating trapped background and opaque patches.
    """
    if Image is None:
        sys.exit("Erreur : Pillow (PIL) est requis pour générer le masque.")

    if input_png is None:
        input_png = RESSOURCE_DIR / "lucy.png"
    if output_png is None:
        output_png = RESSOURCE_DIR / "blackwall" / "blackwall_mask.png"

    im = Image.open(input_png)
    w, h = im.size

    # 1. Calcul de la déviation euclidienne par rapport au fond théorique
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
                if not visited[nidx]:
                    if diffs[nidx] < 18.0:
                        visited[nidx] = 1
                        q.append((nx, ny))

    # 4. Reconstruction de l'opacité sous-pixel par projection linéaire
    mask = Image.new("L", (w, h), 0)
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if visited[idx]:
                d = diffs[idx]
                if d <= 1.8:
                    val = 255
                else:
                    t = (d - 1.8) / (18.0 - 1.8)
                    val = int(round((1.0 - t) * 255.0))
                if val > 0:
                    mask.putpixel((x, y), val)

    # 5. Filtrage morphologique des composantes connexes parasites
    mask_arr = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if mask.getpixel((x, y)) > 0:
                mask_arr[y * w + x] = 1

    visited_cc = bytearray(w * h)
    components = []
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if mask_arr[idx] and not visited_cc[idx]:
                comp = []
                cq = deque([(x, y)])
                visited_cc[idx] = 1
                comp.append((x, y))
                while cq:
                    curr_x, curr_y = cq.popleft()
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = curr_x + dx, curr_y + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            nidx = ny * w + nx
                            if mask_arr[nidx] and not visited_cc[nidx]:
                                visited_cc[nidx] = 1
                                cq.append((nx, ny))
                                comp.append((nx, ny))
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

    # 6. Intégration des deux ouvertures entre les doigts
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

    output_png.parent.mkdir(parents=True, exist_ok=True)
    wave_png = RESSOURCE_DIR / "waterwaves_mask.png"
    flow_png = RESSOURCE_DIR / "shake_flowmask.png"
    if wave_png.exists() and flow_png.exists():
        wave_im = Image.open(wave_png).convert("L")
        if wave_im.size != (w, h):
            wave_im = wave_im.resize((w, h), Image.Resampling.LANCZOS)
        flow_im = Image.open(flow_png).convert("RGB")
        if flow_im.size != (w, h):
            flow_im = flow_im.resize((w, h), Image.Resampling.LANCZOS)
        flow_r, flow_g, _ = flow_im.split()
        comp_mask = Image.merge("RGBA", (mask, flow_g, flow_r, wave_im))
        comp_mask.save(output_png)
    else:
        mask.save(output_png)
    print(f"✓ Masque Blackwall 4-Canaux (Cutout + FlowMap + Ondulations) généré : {output_png} ({w}x{h})")


def generate_eye_shine_mask(
    input_png: Optional[Path] = None,
    output_png: Optional[Path] = None,
):
    """Génère le masque vectoriel de la pupille avec anti-aliasing sous-pixel."""
    if Image is None or ImageFilter is None:
        sys.exit("Erreur : Pillow (PIL) est requis pour générer le masque.")

    if input_png is None:
        input_png = RESSOURCE_DIR / "lucy.png"
    if output_png is None:
        output_png = RESSOURCE_DIR / "materials" / "masks" / "shine_downsample2_mask_b309bcdf.png"

    im = Image.open(input_png)
    w, h = im.size
    mask = Image.new("L", (w, h), 0)

    top_eyelid_bottom = {}
    for x in range(1085, 1180):
        last_lid = 280
        for y in range(275, 325):
            r, g, b = im.getpixel((x, y))[:3]
            if r < 55 and g < 52 and b < 72:
                last_lid = y
        top_eyelid_bottom[x] = last_lid

    for y in range(285, 360):
        for x in range(1090, 1180):
            if y <= top_eyelid_bottom.get(x, 280):
                continue
            r, g, b = im.getpixel((x, y))[:3]
            if r < 50 and g < 46 and b < 64 and y > 330:
                continue
            if x < 1100 and y > 343:
                continue
            if x > 1172:
                continue
            is_cyan = (b - r > 35) and (g - r > 15) and (b > 110)
            is_magenta = (r - g > 20) and (b - g > 10) and (r > 85)
            is_pupil = (r < 100) and (g < 80) and (b < 105) and (r > 35) and (b > 40) and (x >= 1110) and (x <= 1142) and (y >= 300) and (y <= 328)
            is_specular = (r > 180) and (g > 180) and (b > 180) and (x >= 1130) and (x <= 1170) and (y <= 325)
            if is_cyan or is_magenta or is_pupil or is_specular:
                mask.putpixel((x, y), 255)

    for y in range(390, 440):
        for x in range(730, 788):
            r, g, b = im.getpixel((x, y))[:3]
            is_cyan = (b - r > 25) and (g - r > 12) and (b > 85)
            is_magenta = (r - g > 18) and (b - g > 8) and (r > 75)
            is_specular = (r > 175) and (g > 175) and (b > 175) and (x > 755) and (y < 425)
            if (is_cyan or is_magenta or is_specular) and not (r < 38 and g < 38 and b < 48):
                mask.putpixel((x, y), 255)

    mask_closed = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    mask_smooth = mask_closed.filter(ImageFilter.GaussianBlur(radius=0.7))
    mask_540 = mask_smooth.resize((960, 540), Image.Resampling.LANCZOS)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    mask_540.save(output_png)
    print(f"✓ Masque pupille généré : {output_png} (960x540)")
