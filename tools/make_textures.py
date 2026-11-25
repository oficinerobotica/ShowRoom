# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Make the procedural textures in Resources/Textures.

    python3 tools/make_textures.py            # writes them in Resources/Textures
    python3 tools/make_textures.py OUT_DIR    # writes them elsewhere

Every image is 512 x 512 and tiles without a seam: the patterns repeat a whole
number of times across the image, the noise is made in the frequency domain
(an FFT of white noise, periodic by construction) and the relief is lit with
gradients that wrap around the border.  The output is the same on every run
(fixed seeds).  Needs numpy and Pillow; no outside images are used.

    PorcelainTiles.jpg      large light grey speckled porcelain tiles, thin joints
    RusticTiles.jpg         worn light grey country tiles, laid in running bond
    HerringboneParquet.jpg  oak planks laid in herringbone
    SteelGrating.png        galvanised welded steel grating (alpha: the openings)
"""
import os
import sys

import numpy as np
from PIL import Image

SIZE = 512
HERE = os.path.dirname(os.path.abspath(__file__))
TEXTURES = os.path.join(os.path.dirname(HERE), 'Resources', 'Textures')
LIGHT = np.array([-0.45, -0.55, 0.70])          # from the top left (image y points down)
LIGHT = LIGHT / np.linalg.norm(LIGHT)


# --------------------------------------------------------------------- helpers
def noise(seed, scale, aspect=(1.0, 1.0), size=SIZE):
    """Tileable noise, about -1..1: white noise low-passed in the frequency domain.

    ``scale`` is the feature size in pixels; ``aspect`` stretches it along (x, y)."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size)[:, None] * scale * aspect[1]
    fx = np.fft.fftfreq(size)[None, :] * scale * aspect[0]
    smooth = np.real(np.fft.ifft2(np.fft.fft2(white) * np.exp(-(fx ** 2 + fy ** 2) * 4.0)))
    return smooth / (np.abs(smooth).max() + 1e-12)


def fbm(seed, scales, gains=None):
    gains = gains or [0.5 ** i for i in range(len(scales))]
    out = sum(g * noise(seed + i, s) for i, (s, g) in enumerate(zip(scales, gains)))
    return out / sum(gains)


def coords(size=SIZE):
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    return x + 0.5, y + 0.5


def mix(a, b, t):
    t = np.clip(t, 0.0, 1.0)[..., None]
    return np.asarray(a, float) * (1.0 - t) + np.asarray(b, float) * t


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hashed(*keys):
    """A repeatable pseudo random number in 0..1 for integer keys (arrays welcome)."""
    h = np.uint64(1469598103934665603)
    for k in keys:
        h = (h ^ np.asarray(k).astype(np.uint64)) * np.uint64(1099511628211)
        h ^= h >> np.uint64(29)
    return (h % np.uint64(1 << 20)).astype(np.float64) / float(1 << 20)


def shade(height, strength):
    """Lambert lighting of a height field, 1.0 on flat ground; wraps around the border."""
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5 * strength
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5 * strength
    norm = np.sqrt(gx * gx + gy * gy + 1.0)
    lit = (-gx * LIGHT[0] - gy * LIGHT[1] + LIGHT[2]) / norm
    return lit / LIGHT[2]


def blur(a, radius):
    """Tileable gaussian blur (frequency domain)."""
    fy = np.fft.fftfreq(a.shape[0])[:, None]
    fx = np.fft.fftfreq(a.shape[1])[None, :]
    g = np.exp(-2.0 * (np.pi * radius) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def rounded_box(px, py, hw, hh, r):
    """Distance inside a rounded rectangle centred on 0 (positive inside)."""
    qx, qy = np.abs(px) - (hw - r), np.abs(py) - (hh - r)
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
    return r - outside


def to_image(rgb, alpha=None):
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    if alpha is None:
        return Image.fromarray(rgb, 'RGB')
    a = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), 'RGBA')


# ------------------------------------------------------------------- textures
def porcelain_tiles():
    """2 x 2 large matt porcelain tiles, light grey with fine dark and light specks."""
    x, y = coords()
    cell = SIZE / 2
    ix, iy = (x // cell).astype(int), (y // cell).astype(int)
    d = rounded_box(x % cell - cell / 2, y % cell - cell / 2, cell / 2, cell / 2, 2.0)
    joint = 1.3
    tile = smoothstep(joint - 0.5, joint + 0.5, d)
    edge = smoothstep(joint, joint + 3.0, d)

    tone = (hashed(ix % 2, iy % 2, 31) - 0.5) * 5.0
    body = (fbm(40, [90, 30]) * 4.0 + noise(42, 1.2) * 3.5 + tone)[..., None]
    img = np.array([221.0, 221.0, 217.0]) + body
    # specks: small blobs where very fine noise peaks
    dark = smoothstep(0.42, 0.66, noise(43, 0.9)) * (0.6 + 0.4 * (noise(44, 30) > -0.2))
    darker = smoothstep(0.62, 0.80, noise(45, 1.1))
    light = smoothstep(0.55, 0.75, noise(46, 0.8))
    img = mix(img, np.array([150.0, 150.0, 148.0]), dark * 0.85)
    img = mix(img, np.array([95.0, 95.0, 96.0]), darker)
    img = mix(img, np.array([240.0, 240.0, 238.0]), light * 0.7)

    height = edge * 1.0 + tile * 0.0
    img = img * (0.92 + 0.08 * shade(height, 2.0))[..., None]
    grout = np.array([188.0, 187.0, 182.0]) + (noise(47, 1.5) * 6.0)[..., None]
    img = mix(grout, img, tile)
    return to_image(img)


def rustic_tiles():
    """Worn light grey country tiles, 2:1, running bond (4 rows of 2)."""
    x, y = coords()
    w, h = SIZE / 2, SIZE / 4
    row = np.floor(y / h).astype(int)
    shift = np.where(row % 2 == 1, w / 2, 0.0)
    col = np.floor((x + shift) / w).astype(int)
    lx = (x + shift) % w - w / 2
    ly = y % h - h / 2
    # irregular, hand made edges: the outline wobbles a little
    wob = noise(50, 7) * 2.0 + noise(51, 30) * 2.0 + noise(49, 2.0) * 1.2
    d = rounded_box(lx, ly, w / 2, h / 2, 9.0) + wob
    joint = 4.0
    tile = smoothstep(joint - 0.8, joint + 0.8, d)
    crown = smoothstep(joint, joint + 7.0, d)            # rounded, worn edges

    key = (col % 2, row % 4)
    tone = hashed(*key, 9) - 0.5
    mottle = fbm(52, [70, 30, 12, 4])
    patches = smoothstep(-0.1, 0.5, fbm(56, [45, 15]))
    pale = np.array([214.0, 209.0, 198.0])
    shadowy = np.array([176.0, 168.0, 155.0])
    img = mix(pale, shadowy, 0.40 + 0.75 * mottle + tone * 0.35)
    img = mix(img, np.array([226.0, 223.0, 215.0]), patches * 0.35)
    # worn edges are paler, like chipped glaze
    img = mix(img, np.array([224.0, 220.0, 211.0]), (1.0 - crown) * tile * 0.6)

    # relief: a domed tile with a pitted, uneven face
    pits = smoothstep(0.45, 0.75, noise(60, 1.6)) * 0.6
    bump = fbm(61, [30, 10, 3.5, 1.3], [1.0, 0.8, 0.6, 0.35]) * 2.2 - pits
    height = tile * (crown * 1.6 + bump * crown) + (1.0 - tile) * (noise(62, 2.0) * 0.3)
    img = img * (0.78 + 0.22 * shade(height, 1.3))[..., None]
    img = mix(img, np.array([120.0, 115.0, 105.0]), pits * 0.25)

    grout = np.array([158.0, 151.0, 139.0]) + (fbm(63, [6, 2]) * 14.0)[..., None]
    grout = grout * (0.75 + 0.25 * smoothstep(0.0, joint, d))[..., None]   # in the shade of the tiles
    return to_image(mix(grout, img, tile))


def herringbone_parquet():
    """Oak planks 1 x 4, laid in herringbone; 2 x 2 repeats of the pattern."""
    n = 4                                   # plank length / width
    unit = SIZE / (4 * n)                   # plank width in pixels (32)
    period = 4 * n                          # in units: the image width
    x, y = coords()
    u, v = x / unit, y / unit
    cu, cv = np.floor(u).astype(int), np.floor(v).astype(int)

    # Lattice (1, 1) and (n, -n).  Horizontal planks cover cells (t .. t+n-1, t),
    # vertical planks cover (t+n, t-n+1 .. t), plus their translates by (n, -n).
    kind = np.zeros(cu.shape, int)
    ox = np.zeros(cu.shape, int)
    oy = np.zeros(cu.shape, int)
    found = np.zeros(cu.shape, bool)
    for m in range(-2 * n, 2 * n + 1):
        px, py = cu - m * n, cv + m * n
        t = py
        hit = (~found) & (px - t >= 0) & (px - t < n)
        kind[hit], ox[hit], oy[hit] = 0, (t + m * n)[hit], (t - m * n)[hit]
        found |= hit
        t = px - n
        hit = (~found) & (t - py >= 0) & (t - py < n)
        kind[hit], ox[hit], oy[hit] = 1, (t + n + m * n)[hit], (t - m * n)[hit]
        found |= hit
    assert found.all(), 'herringbone: uncovered cells'

    along = np.where(kind == 0, u - ox, v - (oy - n + 1)) * unit
    across = np.where(kind == 0, v - oy, u - ox) * unit
    length = n * unit

    r1 = hashed(ox % period, oy % period, kind)
    r2 = hashed(ox % period, oy % period, kind, 5)
    r3 = hashed(ox % period, oy % period, kind, 8)
    # oak board: grain lines along the plank, read from tileable noise fields,
    # each plank cut from a different place of the "log"
    def sample(field, a, c):
        return field[(c.astype(int)) % SIZE, (a.astype(int)) % SIZE]
    warp_f = noise(70, 40)
    lines_f = noise(71, 3, (8.0, 0.5))          # long thin streaks (along x)
    pores_f = noise(72, 0.9, (10.0, 0.6))
    a0 = along + r1 * 512.0
    c0 = across * 1.0 + r2 * 512.0
    warp = sample(warp_f, a0 * 0.5, c0) * 6.0
    rings = np.sin((across + warp + r3 * 30.0) * (0.30 + 0.25 * r2))
    figure = smoothstep(-0.2, 0.9, rings)
    streak = sample(lines_f, a0, c0 + warp)
    pores = smoothstep(0.35, 0.75, sample(pores_f, a0 * 1.3, c0 + warp))

    light = np.array([212.0, 172.0, 122.0])
    dark = np.array([168.0, 121.0, 74.0])
    tone = (r1 - 0.5) * 0.45 + (r3 - 0.5) * 0.15
    wood = mix(light, dark, 0.35 + 0.30 * figure + 0.25 * streak + tone)
    wood = mix(wood, np.array([120.0, 82.0, 46.0]), pores * 0.45)
    # varnish sheen differs a little from plank to plank
    wood = wood * (0.96 + 0.08 * r2)[..., None]

    gap = np.minimum(np.minimum(along, length - along), np.minimum(across, unit - across))
    seam = smoothstep(0.2, 1.0, gap)
    bevel = smoothstep(0.0, 3.0, gap)
    wood = wood * (0.90 + 0.10 * bevel)[..., None]
    return to_image(mix(np.array([96.0, 66.0, 38.0]), wood, seam))


def steel_grating():
    """Galvanised welded steel grating: flat bearing bars, twisted cross rods.

    The openings are transparent (alpha 0): a walkway, a platform, a fence."""
    x, y = coords()
    pitch_x, pitch_y = SIZE / 16, SIZE / 8        # bars every 32 px, rods every 64 px
    bar_half, rod_half = 2.6, 3.2
    bx = (x % pitch_x) - pitch_x / 2
    ry = (y % pitch_y) - pitch_y / 2
    bar = smoothstep(bar_half + 0.6, bar_half - 0.6, np.abs(bx))
    rod = smoothstep(rod_half + 0.6, rod_half - 0.6, np.abs(ry))
    alpha = np.maximum(bar, rod)

    # zinc spangle: large flat crystals of slightly different grey
    rng = np.random.default_rng(80)
    pts = rng.random((260, 2)) * SIZE
    best = np.full(x.shape, 1e9)
    cell = np.zeros(x.shape)
    for i, (px, py) in enumerate(pts):
        dx = np.abs(x - px)
        dy = np.abs(y - py)
        dx = np.minimum(dx, SIZE - dx)
        dy = np.minimum(dy, SIZE - dy)
        dist = dx * dx + dy * dy
        closer = dist < best
        best[closer] = dist[closer]
        cell[closer] = (i * 0.6180339887) % 1.0
    zinc = (np.array([168.0, 172.0, 174.0]) + ((cell - 0.5) * 22.0)[..., None]
            + (noise(81, 1.2) * 5.0 + noise(82, 40) * 8.0)[..., None])
    stains = smoothstep(0.3, 0.8, fbm(83, [60, 20]))
    zinc = mix(zinc, np.array([132.0, 136.0, 134.0]), stains * 0.35)

    # bearing bars: a flat top with rounded edges; rods: round and twisted
    bar_h = np.sqrt(np.clip(1.0 - (bx / (bar_half + 0.6)) ** 2, 0, 1)) ** 0.3 * 2.0
    twist = 0.5 + 0.5 * np.sin((x + ry * 1.6) * 2 * np.pi / 6.0)
    rod_h = np.sqrt(np.clip(1.0 - (ry / (rod_half + 0.6)) ** 2, 0, 1)) * 3.5 + twist * 0.5
    height = np.where(rod > 0.01, np.maximum(rod_h * rod + 0.4, bar_h * bar), bar_h * bar)
    img = zinc * (0.62 + 0.38 * shade(height, 1.4))[..., None]
    # the bars go down under the rods: a little contact shadow beside each rod
    near_rod = smoothstep(rod_half + 4.0, rod_half, np.abs(ry)) * (1.0 - rod)
    img = img * (1.0 - 0.25 * near_rod * bar)[..., None]
    return to_image(img, alpha=alpha)


TEXTURES_TO_MAKE = (
    ('PorcelainTiles.jpg', porcelain_tiles),
    ('RusticTiles.jpg', rustic_tiles),
    ('HerringboneParquet.jpg', herringbone_parquet),
    ('SteelGrating.png', steel_grating),
)


def main(out_dir=TEXTURES):
    for name, make in TEXTURES_TO_MAKE:
        image = make()
        path = os.path.join(out_dir, name)
        if name.endswith('.jpg'):
            image.save(path, quality=90, optimize=True)
        else:
            image.save(path, optimize=True)
        print(path, image.size, image.mode)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else TEXTURES)
