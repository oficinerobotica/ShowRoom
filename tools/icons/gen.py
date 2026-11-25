# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2026 OficineRobotica
"""Draws the ShowRoom icons in the style of the scene configuration icon:
rounded tile with a dark-to-light diagonal gradient, isometric floor grid,
red and green axes, soft floor shadow and the lilac cube."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = open(os.path.join(HERE, 'grid.txt')).read().split()
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'

HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
<!-- Copyright (c) 2026 OficineRobotica - ShowRoom add-on for FreeCAD -->
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 105.83333 105.83333">
<defs>
  <linearGradient id="bg" x1="105.83" y1="0" x2="0" y2="105.83" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#231c39"/><stop offset="1" stop-color="#f9f7ff" stop-opacity="0.75"/>
  </linearGradient>
  <linearGradient id="floor" x1="55.45" y1="55.08" x2="42.48" y2="97.14" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#545454"/><stop offset="1" stop-color="#969696" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff1d4" stop-opacity="0.95"/><stop offset="1" stop-color="#ffeabe" stop-opacity="0.35"/>
  </linearGradient>
  <radialGradient id="sun" cx="0.4" cy="0.35" r="0.7">
    <stop offset="0" stop-color="#fff6c8"/><stop offset="0.6" stop-color="#ffd24a"/><stop offset="1" stop-color="#e89a12"/>
  </radialGradient>
  <linearGradient id="metal" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#8d8d8d"/><stop offset="0.45" stop-color="#f2f2f2"/><stop offset="1" stop-color="#7a7a7a"/>
  </linearGradient>
  <linearGradient id="cap" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#1b1b1b"/><stop offset="0.4" stop-color="#5a5a5a"/><stop offset="1" stop-color="#151515"/>
  </linearGradient>
  <pattern id="wood" width="9" height="6" patternUnits="userSpaceOnUse" patternTransform="skewY(-25)">
    <rect width="9" height="6" fill="#c9965a"/><path d="M0 6 H9 M4.5 0 V6" stroke="#7e5026" stroke-width="0.9"/>
  </pattern>
  <filter id="blur" x="-0.3" y="-0.3" width="1.6" height="1.6"><feGaussianBlur stdDeviation="1.8"/></filter>
  <filter id="soft" x="-0.3" y="-0.3" width="1.6" height="1.6"><feGaussianBlur stdDeviation="3.2"/></filter>
  <clipPath id="tile"><path d="{tile}"/></clipPath>
</defs>
'''
TILE = ("m 13.99,0.52 c -4.28,0 -13.47,8.95 -13.47,13.23 l 0,76.49 c 0,4.28 8.05,15.07 15.15,15.07 "
        "H 91.55 c 4.28,0 13.76,-8.42 13.76,-14.2 l 0,-78.21 c 0,-4.28 -7.79,-12.37 -12.07,-12.37 z")
FOOTER = ('<rect x="0.98" y="0.98" width="103.87" height="103.87" ry="14.3" fill="none" '
          'stroke="#444444" stroke-width="1.96"/>\n</svg>\n')


def backdrop(axes=True, grid=True):
    out = ['<path d="%s" fill="url(#bg)" stroke="#ffffff" stroke-width="1.05"/>' % TILE,
           '<g clip-path="url(#tile)">']
    if grid:
        out += ['<path d="%s" fill="none" stroke="#c6c6c6" stroke-width="0.27"/>' % d for d in GRID]
    if axes:
        out += ['<path d="M 0,41 105.08,90" stroke="#ff0025" stroke-width="0.53"/>',
                '<path d="M 0,84.74 105.08,35.74" stroke="#11ff00" stroke-width="0.53"/>']
    return out


def close_backdrop():
    return ['</g>']


def cube(x, y, a, h, faces=('#5b488f', '#9d90c3', '#dcd7ea'), sw=0.4, left_fill=None):
    """Isometric cube; (x, y) is the front corner of the top face."""
    b = a * 13.0 / 27.88
    left = 'M %g,%g %g,%g %g,%g %g,%g Z' % (x, y, x - a, y - b, x - a, y - b + h, x, y + h)
    right = 'M %g,%g %g,%g %g,%g %g,%g Z' % (x, y, x + a, y - b, x + a, y - b + h, x, y + h)
    top = 'M %g,%g %g,%g %g,%g %g,%g Z' % (x, y, x - a, y - b, x, y - 2 * b, x + a, y - b)
    return ['<path d="%s" fill="%s" stroke="#000" stroke-width="%g" stroke-linejoin="round"/>'
            % (left, left_fill or faces[0], sw),
            '<path d="%s" fill="%s" stroke="#000" stroke-width="%g" stroke-linejoin="round"/>'
            % (right, faces[1], sw),
            '<path d="%s" fill="%s" stroke="#000" stroke-width="%g" stroke-linejoin="round"/>'
            % (top, faces[2], sw)]


def floor_shadow(x, y, a, h, dx=-26, dy=14, op=0.85):
    """Soft cast shadow on the floor from the base of a cube."""
    b = a * 13.0 / 27.88
    base = [(x - a, y - b + h), (x, y + h), (x + a, y - b + h)]
    far = [(px + dx, py + dy) for px, py in base]
    pts = base + far[::-1]
    d = 'M ' + ' '.join('%g,%g' % p for p in pts) + ' Z'
    return ['<path d="%s" fill="#3c3c3c" opacity="%g" filter="url(#blur)"/>' % (d, op)]


def ellipse(cx, cy, rx, ry, fill, stroke='#000', sw=0.4, extra=''):
    return ['<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="%s" stroke="%s" stroke-width="%g" %s/>'
            % (cx, cy, rx, ry, fill, stroke, sw, extra)]


def sun(cx, cy, r, rays=True):
    out = []
    if rays:
        for i in range(8):
            a = i * math.pi / 4
            out.append('<path d="M %g,%g %g,%g" stroke="#ffd24a" stroke-width="2.6" stroke-linecap="round"/>'
                       % (cx + math.cos(a) * r * 1.45, cy + math.sin(a) * r * 1.45,
                          cx + math.cos(a) * r * 1.95, cy + math.sin(a) * r * 1.95))
    out += ellipse(cx, cy, r, r, 'url(#sun)', '#9a5a10', 0.6)
    return out


def lamp(x, y, angle, size=1.0):
    """A small studio lamp (trapezoid body + warm lens) pointing along ``angle`` (deg)."""
    s = size
    body = ('<g transform="translate(%g %g) rotate(%g) scale(%g)">'
            '<path d="M -7,-5 L 5,-8 L 5,8 L -7,5 Z" fill="#3d3d3d" stroke="#000" stroke-width="0.6"/>'
            '<path d="M 5,-8 L 8,-9 L 8,9 L 5,8 Z" fill="#ffd36b" stroke="#000" stroke-width="0.6"/>'
            '</g>' % (x, y, angle, s))
    return [body]


def beam(points, op=0.75):
    d = 'M ' + ' '.join('%g,%g' % p for p in points) + ' Z'
    return ['<path d="%s" fill="url(#beam)" opacity="%g"/>' % (d, op)]


def arrow_arc(cx, cy, rx, ry, a0, a1, color='#0a6fd6', w=3.4, head=True):
    """Elliptic arc from a0 to a1 (degrees, clockwise on screen) with an arrow head."""
    pts = []
    n = 24
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    d = 'M ' + ' '.join('%g,%g' % p for p in pts)
    out = ['<path d="%s" fill="none" stroke="#0b2a55" stroke-width="%g" stroke-linecap="round"/>' % (d, w + 1.6),
           '<path d="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="round"/>' % (d, color, w)]
    if head:
        (x1, y1), (x0, y0) = pts[-1], pts[-2]
        ang = math.atan2(y1 - y0, x1 - x0)
        L, W = 7.5, 5.0
        tip = (x1 + math.cos(ang) * L * 0.6, y1 + math.sin(ang) * L * 0.6)
        back = (x1 - math.cos(ang) * L * 0.4, y1 - math.sin(ang) * L * 0.4)
        p1 = (back[0] + math.cos(ang + math.pi / 2) * W, back[1] + math.sin(ang + math.pi / 2) * W)
        p2 = (back[0] - math.cos(ang + math.pi / 2) * W, back[1] - math.sin(ang + math.pi / 2) * W)
        out.append('<path d="M %g,%g %g,%g %g,%g Z" fill="%s" stroke="#0b2a55" stroke-width="0.8" '
                   'stroke-linejoin="round"/>' % (tip + p1 + p2 + (color,)))
    return out


def straight_arrow(x0, y0, x1, y1, color='#0a6fd6', w=3.4, both=False):
    ang = math.atan2(y1 - y0, x1 - x0)
    L, W = 8.0, 5.2

    def head(x, y, a):
        tip = (x, y)
        back = (x - math.cos(a) * L, y - math.sin(a) * L)
        p1 = (back[0] + math.cos(a + math.pi / 2) * W, back[1] + math.sin(a + math.pi / 2) * W)
        p2 = (back[0] - math.cos(a + math.pi / 2) * W, back[1] - math.sin(a + math.pi / 2) * W)
        return ('<path d="M %g,%g %g,%g %g,%g Z" fill="%s" stroke="#0b2a55" stroke-width="0.8" '
                'stroke-linejoin="round"/>' % (tip + p1 + p2 + (color,)))
    sx, sy = (x0 + math.cos(ang) * L * 0.8, y0 + math.sin(ang) * L * 0.8) if both else (x0, y0)
    ex, ey = x1 - math.cos(ang) * L * 0.8, y1 - math.sin(ang) * L * 0.8
    out = ['<path d="M %g,%g %g,%g" stroke="#0b2a55" stroke-width="%g" stroke-linecap="round"/>' % (sx, sy, ex, ey, w + 1.6),
           '<path d="M %g,%g %g,%g" stroke="%s" stroke-width="%g" stroke-linecap="round"/>' % (sx, sy, ex, ey, color, w),
           head(x1, y1, ang)]
    if both:
        out.append(head(x0, y0, ang + math.pi))
    return out


def puck(cx, cy, s=1.0):
    """A SpaceMouse: silver base and a dark cap."""
    out = []
    out += ['<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="#000" opacity="0.35" filter="url(#blur)"/>'
            % (cx, cy + 25 * s, 33 * s, 9 * s)]
    # base
    out += ['<path d="M %g,%g L %g,%g A %g %g 0 0 0 %g,%g L %g,%g Z" fill="url(#metal)" stroke="#000" stroke-width="0.5"/>'
            % (cx - 30 * s, cy + 14 * s, cx - 30 * s, cy + 19 * s, 30 * s, 8 * s, cx + 30 * s, cy + 19 * s,
               cx + 30 * s, cy + 14 * s)]
    out += ellipse(cx, cy + 14 * s, 30 * s, 8 * s, '#d9d9d9', '#000', 0.5)
    # cap (truncated cone)
    out += ['<path d="M %g,%g L %g,%g A %g %g 0 0 0 %g,%g L %g,%g Z" fill="url(#cap)" stroke="#000" stroke-width="0.5"/>'
            % (cx - 16 * s, cy - 10 * s, cx - 21 * s, cy + 12 * s, 21 * s, 6 * s, cx + 21 * s, cy + 12 * s,
               cx + 16 * s, cy - 10 * s)]
    out += ellipse(cx, cy - 10 * s, 16 * s, 4.6 * s, '#4a4a4a', '#000', 0.5)
    out += ['<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="#ffffff" opacity="0.25"/>'
            % (cx - 4 * s, cy - 11 * s, 8 * s, 1.8 * s)]
    return out


def padlock(x, y, s=1.0, color='#f2a52b'):
    return ['<g transform="translate(%g %g) scale(%g)">'
            '<path d="M -5,-2 V -6 A 5 5 0 0 1 5,-6 V -2" fill="none" stroke="#1f1f1f" stroke-width="4.2"/>'
            '<path d="M -5,-2 V -6 A 5 5 0 0 1 5,-6 V -2" fill="none" stroke="#e8e8e8" stroke-width="2.2"/>'
            '<rect x="-8" y="-2" width="16" height="12" rx="2" fill="%s" stroke="#1f1f1f" stroke-width="1"/>'
            '<circle cx="0" cy="3" r="1.8" fill="#1f1f1f"/><path d="M 0,3 V 7" stroke="#1f1f1f" stroke-width="1.4"/>'
            '</g>' % (x, y, s, color)]


# ------------------------------------------------------------------------- icons
CX, CY, A, H = 52, 50, 21, 26          # default cube


def icon_showroom():
    out = backdrop(axes=False)
    out += beam([(30, -4), (58, -4), (88, 80), (8, 80)], 0.55)            # spot beam from above
    out += ellipse(48, 82, 38, 13, '#000', 'none', 0, 'opacity="0.35" filter="url(#blur)"')
    out += ['<path d="M 10,74 L 10,80 A 38 12 0 0 0 86,80 L 86,74 Z" fill="url(#metal)" stroke="#000" stroke-width="0.5"/>']
    out += ellipse(48, 74, 38, 12, '#e6e3ef', '#000', 0.5)
    out += cube(48, 50, 22, 26)
    out += arrow_arc(48, 74, 44, 15, 200, 330, '#f2a52b', 3.0)
    out += ['<path d="M 30,-2 L 58,-2 L 52,8 L 36,8 Z" fill="#3d3d3d" stroke="#000" stroke-width="0.6"/>']
    out += close_backdrop()
    return out


def icon_appearance():
    out = backdrop()
    out += floor_shadow(CX, CY, A, H)
    out += cube(CX, CY, A, H, faces=('#c9965a', '#e59a40', '#ffd7a8'), left_fill='url(#wood)')
    # colour drop
    out += ['<path d="M 82,58 C 82,58 72,72 72,79 A 10 10 0 0 0 92,79 C 92,72 82,58 82,58 Z" '
            'fill="#3d7cc9" stroke="#0b2a55" stroke-width="0.9"/>',
            '<ellipse cx="78.5" cy="77" rx="2.4" ry="3.6" fill="#fff" opacity="0.6"/>']
    out += close_backdrop()
    return out


def icon_shadows():
    out = backdrop()
    out += ['<path d="M 31,74 L 52,84 L 73,74 L 40,93 L 4,96 Z" fill="#202020" opacity="0.85" filter="url(#blur)"/>']
    out += floor_shadow(CX, CY, A, H, dx=-34, dy=20, op=0.9)
    out += cube(CX, CY, A, H)
    out += sun(84, 18, 8)
    out += close_backdrop()
    return out


def icon_ao():
    out = backdrop(axes=False)
    # a corner: back wall left, back wall right, floor
    out += ['<path d="M 52,10 L 8,30 L 8,72 L 52,52 Z" fill="#e9e6f1" stroke="#000" stroke-width="0.4"/>',
            '<path d="M 52,10 L 98,30 L 98,72 L 52,52 Z" fill="#d4cfe3" stroke="#000" stroke-width="0.4"/>',
            '<path d="M 52,52 L 8,72 L 52,96 L 98,72 Z" fill="#f4f2f8" stroke="#000" stroke-width="0.4"/>']
    # occlusion: dark soft bands along the edges of the corner and under the cube
    out += ['<path d="M 52,10 L 52,52 M 8,72 L 52,52 L 98,72" stroke="#1d1830" stroke-width="9" '
            'opacity="0.7" fill="none" filter="url(#soft)"/>']
    out += ['<path d="M 34,72 L 56,82 L 76,72 L 54,62 Z" fill="#1d1830" opacity="0.85" filter="url(#soft)"/>']
    out += cube(55, 56, 17, 18)
    out += close_backdrop()
    return out


def icon_catcher():
    out = backdrop(axes=False, grid=False)
    # an invisible ground: dashed outline only, and the soft shadow on it
    out += ['<path d="M 52,46 L 6,68 L 52,92 L 98,68 Z" fill="none" stroke="#ffffff" stroke-width="1.1" '
            'stroke-dasharray="3 2.4" opacity="0.95"/>']
    out += ['<ellipse cx="50" cy="71" rx="25" ry="8.5" fill="#141414" opacity="0.85" filter="url(#soft)"/>']
    out += cube(52, 34, 19, 22)
    out += close_backdrop()
    return out


def icon_turntable():
    out = backdrop(axes=False)
    out += ellipse(52, 82, 40, 12, '#000', 'none', 0, 'opacity="0.35" filter="url(#blur)"')
    out += ['<path d="M 12,72 L 12,78 A 40 12 0 0 0 92,78 L 92,72 Z" fill="url(#metal)" stroke="#000" stroke-width="0.5"/>']
    out += ellipse(52, 72, 40, 12, '#e6e3ef', '#000', 0.5)
    out += cube(52, 50, 19, 22)
    out += arrow_arc(52, 40, 44, 16, 160, 375, '#0a6fd6', 3.4)
    out += close_backdrop()
    return out


def icon_rig_three():
    out = backdrop()
    out += beam([(20, 22), (26, 16), (52, 46), (40, 58)], 0.8)
    out += beam([(86, 26), (92, 34), (70, 54), (62, 44)], 0.6)
    out += beam([(70, 8), (78, 12), (60, 30), (54, 24)], 0.5)
    out += floor_shadow(CX, CY + 6, A - 3, H - 4)
    out += cube(CX, CY + 6, A - 3, H - 4)
    out += lamp(19, 18, 45, 1.1)          # key
    out += lamp(90, 30, 145, 0.95)        # fill
    out += lamp(76, 7, 135, 0.8)          # rim
    out += close_backdrop()
    return out


def icon_rig_studio():
    out = backdrop()
    out += beam([(36, 10), (68, 10), (80, 48), (24, 48)], 0.7)
    out += beam([(10, 46), (14, 38), (36, 58), (30, 66)], 0.55)
    out += beam([(94, 40), (98, 48), (76, 66), (72, 58)], 0.55)
    out += floor_shadow(CX, CY + 8, A - 3, H - 4, dx=-10, dy=10)
    out += cube(CX, CY + 8, A - 3, H - 4)
    out += ['<rect x="34" y="4" width="36" height="7" rx="2" fill="#3d3d3d" stroke="#000" stroke-width="0.6"/>',
            '<rect x="37" y="9.5" width="30" height="2.6" rx="1" fill="#ffd36b"/>']
    out += lamp(10, 42, 40, 0.9)
    out += lamp(95, 43, 140, 0.9)
    out += close_backdrop()
    return out


def icon_rig_sun():
    out = backdrop()
    out += floor_shadow(CX, CY + 4, A, H - 2, dx=-30, dy=18, op=0.9)
    out += cube(CX, CY + 4, A, H - 2)
    out += ['<path d="M 14,70 A 44 44 0 0 1 92,38" fill="none" stroke="#ffffff" stroke-width="1.2" '
            'stroke-dasharray="3 2.5" opacity="0.9"/>']
    out += sun(82, 20, 9)
    out += close_backdrop()
    return out


def icon_spnav_rot():
    out = backdrop(axes=False, grid=False)
    out += puck(52, 54, 1.0)
    out += arrow_arc(52, 44, 40, 13, 200, 340, '#0a6fd6', 3.4)
    out += padlock(84, 80, 1.15)
    out += close_backdrop()
    return out


def icon_spnav_trans():
    out = backdrop(axes=False, grid=False)
    out += puck(52, 54, 1.0)
    out += straight_arrow(10, 86, 94, 30, '#2ea84a', 3.4, both=True)
    out += padlock(84, 80, 1.15)
    out += close_backdrop()
    return out


def icon_spnav_horizon():
    out = backdrop(axes=False, grid=False)
    out += puck(52, 56, 0.95)
    # a level: sky over ground inside a circle on the cap
    out += ['<clipPath id="lev"><circle cx="52" cy="22" r="11"/></clipPath>',
            '<g clip-path="url(#lev)"><rect x="38" y="8" width="28" height="14" fill="#7cc4f2"/>'
            '<rect x="38" y="22" width="28" height="14" fill="#9a6a3a"/></g>',
            '<circle cx="52" cy="22" r="11" fill="none" stroke="#1f1f1f" stroke-width="1.2"/>',
            '<path d="M 34,22 H 70" stroke="#ffffff" stroke-width="2.2"/>']
    out += padlock(84, 80, 1.15)
    out += close_backdrop()
    return out


def icon_spnav_orbit_selection():
    out = backdrop(axes=False, grid=False)
    out += puck(52, 72, 0.8)
    # an orbit around the selected object (FreeCAD's selection green): back half
    # behind it, front half with the arrow head in front, the pivot on top
    out += arrow_arc(52, 34, 38, 12, 185, 355, '#0a6fd6', 3.2, head=False)
    out += cube(52, 36, 14, 17, faces=('#1a8f1a', '#3fc43f', '#a8eca8'))
    out += arrow_arc(52, 34, 38, 12, 5, 165, '#0a6fd6', 3.2)
    out += ['<circle cx="52" cy="29.5" r="3" fill="#f2a52b" stroke="#1f1f1f" stroke-width="1"/>']
    out += close_backdrop()
    return out


def icon_settings():
    out = backdrop(axes=False)
    out += ['<ellipse cx="52" cy="88" rx="30" ry="7" fill="#000" opacity="0.3" filter="url(#blur)"/>']
    cx, cy, r1, r2, n = 52, 50, 34, 26, 8
    import math as _m
    pts = []
    for i in range(n * 2):
        a = _m.pi * i / n
        rr = r1 if i % 2 == 0 else r2
        for da in (-0.17, 0.17):
            pts.append((cx + rr * _m.cos(a + da), cy + rr * _m.sin(a + da)))
    d = 'M ' + ' '.join('%g,%g' % p for p in pts) + ' Z'
    out += ['<path d="%s M %g,%g a 13,13 0 1,0 26,0 a 13,13 0 1,0 -26,0 Z" fill="url(#sun)" fill-rule="evenodd" stroke="#6b3b00" stroke-width="1.4" stroke-linejoin="round"/>' % (d, cx - 13, cy)]
    out += close_backdrop()
    return out


def icon_panel():
    out = backdrop(axes=False)
    out += ['<ellipse cx="54" cy="90" rx="32" ry="6" fill="#000" opacity="0.3" filter="url(#blur)"/>',
            '<rect x="24" y="14" width="60" height="72" rx="8" fill="#2b3340" stroke="#0e1218" stroke-width="1.6"/>',
            '<rect x="29" y="19" width="50" height="11" rx="4" fill="url(#sun)"/>',
            '<rect x="29" y="35" width="50" height="46" rx="4" fill="#dfe6ee"/>']
    for i in range(5):
        y = 41 + i * 8
        out += ['<rect x="33" y="%d" width="16" height="3.5" rx="1.5" fill="#56606e"/>' % y,
                '<rect x="53" y="%d" width="22" height="3.5" rx="1.5" fill="#8a96a6"/>' % y]
    out += close_backdrop()
    return out


ICONS = {
    'ShowRoom.svg': icon_showroom,
    'Appearance.svg': icon_appearance,
    'ToggleShadows.svg': icon_shadows,
    'ToggleAmbientOcclusion.svg': icon_ao,
    'ToggleShadowCatcher.svg': icon_catcher,
    'Turntable.svg': icon_turntable,
    'RigThreePoint.svg': icon_rig_three,
    'RigStudio.svg': icon_rig_studio,
    'RigSun.svg': icon_rig_sun,
    'SpNav.svg': icon_spnav_rot,
    'SpNav_LockTrans.svg': icon_spnav_trans,
    'SpNav_LockHor.svg': icon_spnav_horizon,
    'SpNav_OrbitSel.svg': icon_spnav_orbit_selection,
    'Settings.svg': icon_settings,
    'FloatingPanel.svg': icon_panel,
}

if __name__ == '__main__':
    for name, fn in ICONS.items():
        body = fn()
        with open(os.path.join(OUT, name), 'w') as f:
            f.write(HEADER.replace('{tile}', TILE) + '\n'.join(body) + '\n' + FOOTER)
    print('written', len(ICONS))
