# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Real-time ground truth ambient occlusion for the 3D view.

Four passes, built from stock Coin nodes:

1. *depth*: eye depth and facet normal of every pixel, drawn into a float
   texture;
2. *occlusion*: ground truth AO (Jimenez et al. 2016, structured like
   Intel's XeGTAO): horizons searched along a few slices per pixel, the
   visible arc between them integrated exactly;
3. *blur*: depth-aware 4x4 blur at AO resolution, which averages away the
   4x4 interleaved noise of the occlusion pass;
4. *composite*: depth-aware upsample, blended black over the picture.

A temporal filter (temporal_ao) may sit between blur and composite.
Each pass re-renders only when its scene notifies a change, so a still
view costs only the composite.  A level-of-detail switch holds a cheap
"Interactive" pipeline that navigation shows while the camera moves.

Crash to avoid: a scene texture renders with the view's own render
action, and nodes that queue paths for the end of the frame (selection on
top, annotations, transparent objects) would queue paths starting at our
node; Coin replays them from the root of the first one and walks off a
child list.  So the depth pass holds only the view providers' roots, draws
everything opaque, and the effect sits in an SoAnnotation.
"""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

from pivy import coin

from Utils import view_utils


def _optional(name: str) -> ModuleType | None:
    """A SceneFX helper module, or None where it cannot be imported."""
    try:
        return importlib.import_module('SceneFX.' + name)
    except ImportError:
        return None


temporal_ao = _optional('temporal_ao')

ROOT_NAME = 'DisplayToolsAO'
#: on/off switch, flipped by navigation while the camera moves
SWITCH_NAME = ROOT_NAME + 'Switch'
#: child 0: chosen quality, child 1: INTERACTIVE
LOD_SWITCH_NAME = ROOT_NAME + 'LOD'

#: quality -> (slices, steps per side, depth scale, AO scale);
#: depth fetches per AO pixel = 2 * slices * steps
QUALITY = {
    'Interactive': (2, 3, 0.5, 0.5),
    'Low': (2, 4, 1.0, 0.5),
    'Medium': (3, 4, 1.0, 1.0),
    'High': (4, 6, 1.0, 1.0),
}
#: the same per frame where temporal accumulation runs: the slices turn
#: each frame and the history adds them up, so one or two slices a frame
#: give the look of four or more once settled
TEMPORAL_QUALITY = {
    'Interactive': (1, 3, 0.5, 0.5),
    'Low': (1, 3, 1.0, 0.5),
    'Medium': (1, 4, 1.0, 1.0),
    'High': (2, 4, 1.0, 1.0),
}
INTERACTIVE = 'Interactive'
DEFAULT_QUALITY = 'Medium'

#: largest sampling disc, as a fraction of the view: a smaller one shrinks
#: the radius of a zoomed-in part to a thin line along its contacts
MAX_SCREEN_RADIUS = 0.2
#: visibility ** (intensity * POWER): deepens creases, open faces stay 1
POWER = 1.5
#: how far the passes' quads reach on every axis, in model units: Coin
#: culls a shape whose bounds miss the view, so the quad's bounds must
#: hold any view (kilometres, in millimetres)
QUAD_REACH = 1e9
#: SoSceneTexture2 sizes are 16 bit
MAX_TEXTURE = 8192
MIN_TEXTURE = 8

DEPTH_VERTEX = """#version 120
varying vec3 dt_eye;
void main() {
    vec4 eye = gl_ModelViewMatrix * gl_Vertex;
    dt_eye = eye.xyz;
    gl_ClipVertex = eye;            // keep FreeCAD's clipping planes
    gl_Position = ftransform();
}
"""

# The facet normal, not the smooth vertex normal: only it agrees with the
# depth samples, and the mismatch shows as stripes along the facets.
DEPTH_FRAGMENT = """#version 120
varying vec3 dt_eye;
void main() {
    vec3 n = normalize(cross(dFdx(dt_eye), dFdy(dt_eye)));
    if (n.z < 0.0) n = -n;
    gl_FragColor = vec4(-dt_eye.z, n);  // r = depth (0: background)
}
"""

# The quad's corners may lie far out (see _quad): only their signs place
# it, over the whole viewport.
QUAD_VERTEX = """#version 120
varying vec2 dt_uv;
void main() {
    vec2 corner = sign(gl_Vertex.xy);
    dt_uv = corner * 0.5 + 0.5;
    gl_Position = vec4(corner, 0.0, 1.0);
}
"""

# Samples snap to texel centres, which moves them off their slice; on a
# sloped face such a point sits above the true horizon and fakes
# occlusion, so each offset is projected back into the slice plane.
GTAO_FRAGMENT = """#version 120
#define DT_DIRS %(dirs)d
#define DT_STEPS %(steps)d
#define DT_PI 3.14159265
#define DT_HALF_PI 1.57079633
#define P00 gl_ProjectionMatrix[0][0]
#define P11 gl_ProjectionMatrix[1][1]
#define P20 gl_ProjectionMatrix[2][0]
#define P21 gl_ProjectionMatrix[2][1]
#define P23 gl_ProjectionMatrix[2][3]
#define P30 gl_ProjectionMatrix[3][0]
#define P31 gl_ProjectionMatrix[3][1]
#define P33 gl_ProjectionMatrix[3][3]
uniform sampler2D dt_depthTex;
uniform vec2 dt_texel;
uniform vec2 dt_size;
uniform float dt_radius;
uniform float dt_intensity;
uniform float dt_frame;
varying vec2 dt_uv;

vec3 eyePos(vec2 uv, float d) {
    float ze = -d;
    float wc = P23 * ze + P33;
    vec2 ndc = uv * 2.0 - 1.0;
    return vec3((ndc.x * wc - P20 * ze - P30) / P00,
                (ndc.y * wc - P21 * ze - P31) / P11, ze);
}

vec2 snap(vec2 uv) { return (floor(uv * dt_size + 0.01) + 0.5) * dt_texel; }

float horizon(vec2 uv, vec2 dir, vec3 C, vec3 V, vec3 axis,
              float invR2, float jitter, float minT) {
    float best = -1.0;
    for (int j = 0; j < DT_STEPS; j++) {
        float t = (float(j) + jitter) / float(DT_STEPS);
        t = minT + (1.0 - minT) * t * t;
        vec2 quv = snap(uv + dir * t);
        float qd = texture2D(dt_depthTex, quv).r;
        vec3 S = eyePos(quv, qd) - C;
        S -= axis * dot(S, axis);
        float ll = dot(S, S);
        if (qd <= 0.0 || ll < 1e-12) continue;
        float c = dot(S, V) * inversesqrt(ll);
        float w = clamp(1.0 - ll * invR2, 0.0, 1.0);
        best = max(best, mix(-1.0, c, w));
    }
    return best;
}

void main() {
    vec2 cuv = snap(dt_uv);
    vec4 c = texture2D(dt_depthTex, cuv);
    if (c.r <= 0.0) { gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0); return; }
    vec3 C = eyePos(cuv, c.r);
    vec3 n = c.gba;
    vec3 V = (P33 > 0.5) ? vec3(0.0, 0.0, 1.0) : normalize(-C);
    if (dot(n, V) < 0.0) n = -n;

    float wc = P23 * C.z + P33;
    vec2 ruv = dt_radius * 0.5 * vec2(P00, P11) / max(wc, 1e-6);
    float scale = min(1.0, %(max_radius)s / max(ruv.x, ruv.y));
    ruv *= scale;
    if (max(ruv.x * dt_size.x, ruv.y * dt_size.y) < 1.5) {
        gl_FragColor = vec4(1.0, c.r, 0.0, 1.0);
        return;
    }
    float R = dt_radius * scale;
    float invR2 = 1.0 / (R * R);

    vec2 cell = mod(floor(gl_FragCoord.xy), 4.0);
    float n1 = fract(mod((cell.x * 4.0 + cell.y) * 7.0, 16.0) / 16.0
                     + dt_frame * 0.618034);
    float n2 = fract(mod((cell.y * 4.0 + cell.x) * 5.0 + 3.0, 16.0) / 16.0
                     + dt_frame * 0.381966);
    float jitter = 0.25 + 0.5 * n2;

    float vis = 0.0;
    for (int i = 0; i < DT_DIRS; i++) {
        float phi = (float(i) + n1) * DT_PI / float(DT_DIRS);
        vec2 omega = vec2(cos(phi), sin(phi));
        vec3 dir = vec3(omega, 0.0);
        vec3 orthoDir = dir - dot(dir, V) * V;
        vec3 axis = normalize(cross(orthoDir, V));
        vec3 projN = n - axis * dot(n, axis);
        float projLen = length(projN);
        float cosN = clamp(dot(projN, V) / max(projLen, 1e-6), 0.0, 1.0);
        float nAng = sign(dot(orthoDir, projN)) * acos(cosN);

        vec2 stepUV = omega * ruv;
        float minT = clamp(1.0 / length(stepUV * dt_size), 0.0, 0.5);
        float hc0 = horizon(dt_uv, stepUV, C, V, axis, invR2, jitter, minT);
        float hc1 = horizon(dt_uv, -stepUV, C, V, axis, invR2, jitter, minT);
        float h0 = -acos(clamp(hc1, -1.0, 1.0));
        float h1 = acos(clamp(hc0, -1.0, 1.0));
        h0 = nAng + max(h0 - nAng, -DT_HALF_PI);
        h1 = nAng + min(h1 - nAng, DT_HALF_PI);
        float sinN = sin(nAng);
        float arc0 = (cosN + 2.0 * h0 * sinN - cos(2.0 * h0 - nAng)) * 0.25;
        float arc1 = (cosN + 2.0 * h1 * sinN - cos(2.0 * h1 - nAng)) * 0.25;
        vis += projLen * (arc0 + arc1);
    }
    vis = clamp(vis / float(DT_DIRS), 0.0, 1.0);
    float visibility = pow(vis, max(dt_intensity, 0.0) * %(power)s);
    gl_FragColor = vec4(visibility, c.r, 0.0, 1.0);
}
"""

BLUR_FRAGMENT = """#version 120
uniform sampler2D dt_aoTex;
uniform vec2 dt_aoTexel;
uniform float dt_radius;
varying vec2 dt_uv;

void main() {
    vec4 c = texture2D(dt_aoTex, dt_uv);
    if (c.g <= 0.0) { gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0); return; }
    float inv = 1.0 / dt_radius;
    float sum = 0.0;
    float weight = 0.0;
    for (int x = -2; x < 2; x++) {
        for (int y = -2; y < 2; y++) {
            vec2 uv = clamp(dt_uv + vec2(float(x), float(y)) * dt_aoTexel,
                            0.5 * dt_aoTexel, 1.0 - 0.5 * dt_aoTexel);
            vec4 s = texture2D(dt_aoTex, uv);
            float w = step(1e-6, s.g)
                      * max(0.0, 1.0 - abs(s.g - c.g) * inv) + 1e-4;
            sum += w * s.r;
            weight += w;
        }
    }
    gl_FragColor = vec4(sum / weight, c.g, 0.0, 1.0);
}
"""

COMPOSITE_FRAGMENT = """#version 120
uniform sampler2D dt_aoTex;
uniform sampler2D dt_depthTex;
uniform vec2 dt_aoSize;
uniform vec2 dt_depthSize;
uniform float dt_radius;
varying vec2 dt_uv;

void main() {
    vec2 duv = (floor(dt_uv * dt_depthSize) + 0.5) / dt_depthSize;
    float z = texture2D(dt_depthTex, duv).r;
    if (z <= 0.0) discard;
    vec2 p = dt_uv * dt_aoSize - 0.5;
    vec2 base = floor(p);
    vec2 f = p - base;
    vec2 half_texel = 0.5 / dt_aoSize;
    float inv = 1.0 / dt_radius;
    float sum = 0.0;
    float weight = 0.0;
    for (int x = 0; x < 2; x++) {
        for (int y = 0; y < 2; y++) {
            vec2 o = vec2(float(x), float(y));
            vec2 uv = clamp((base + o + 0.5) / dt_aoSize,
                            half_texel, 1.0 - half_texel);
            vec4 s = texture2D(dt_aoTex, uv);
            vec2 b = mix(1.0 - f, f, o);
            float depth_w = step(1e-6, s.g)
                            * max(0.0, 1.0 - abs(s.g - z) * inv) + 1e-3;
            float w = b.x * b.y * depth_w;
            sum += w * s.r;
            weight += w;
        }
    }
    gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0 - sum / max(weight, 1e-6));
}
"""

#: The GL helpers of each effect, by its root's address: their Python
#: callbacks must live as long as their nodes, and ``release`` frees them.
_helpers: dict[int, list[Any]] = {}


def _use_temporal(wanted: bool) -> bool:
    return wanted and temporal_ao is not None and temporal_ao.available()


def available() -> bool:
    """Whether this Coin build has every node the effect is made of."""
    needed = ('SoSceneTexture2', 'SoShaderProgram', 'SoFragmentShader',
              'SoVertexShader', 'SoShaderParameter1f', 'SoShaderParameter2f',
              'SoShaderParameter1i', 'SoTextureUnit', 'SoDepthBuffer',
              'SoTransparencyType')
    return (all(hasattr(coin, name) for name in needed)
            and hasattr(coin.SoSceneTexture2, 'RGBA32F'))


def signature(width: int, height: int, camera: Any, scene: Any,
              radius: float, intensity: float, quality: str,
              temporal: bool = False) -> str:
    """Everything the node tree depends on: a new signature, a rebuild.

    The effective toggle is part of it, so temporal AO that failed is
    rebuilt without it at the next sync.
    """
    flags = 'T' if _use_temporal(temporal) else ''
    return 'gtao|%s|%dx%d|%x|%x|%.6g|%.4g|%s' % (
        flags, width, height, view_utils.node_address(camera),
        view_utils.node_address(scene), radius, intensity, quality)


def current_signature(root: Any) -> str | None:
    """The signature the effect under ``root`` was built with."""
    info = view_utils.find_child(root, ROOT_NAME + 'Info')
    return info.string.getValue().getString() if info is not None else None


def _program(vertex: str, fragment: str, parameters: list[Any]) -> Any:
    vs = coin.SoVertexShader()
    vs.sourceType = coin.SoShaderObject.GLSL_PROGRAM
    vs.sourceProgram = vertex
    fs = coin.SoFragmentShader()
    fs.sourceType = coin.SoShaderObject.GLSL_PROGRAM
    fs.sourceProgram = fragment
    for i, parameter in enumerate(parameters):
        fs.parameter.set1Value(i, parameter)
    program = coin.SoShaderProgram()
    program.shaderObject.set1Value(0, vs)
    program.shaderObject.set1Value(1, fs)
    return program


def _float(name: str, value: float) -> Any:
    parameter = coin.SoShaderParameter1f()
    parameter.name = name
    parameter.value = float(value)
    return parameter


def _vec2(name: str, x: float, y: float) -> Any:
    parameter = coin.SoShaderParameter2f()
    parameter.name = name
    parameter.value = coin.SbVec2f(float(x), float(y))
    return parameter


def _sampler(name: str, unit: int) -> Any:
    parameter = coin.SoShaderParameter1i()
    parameter.name = name
    parameter.value = unit
    return parameter


def _quad(reach: float = QUAD_REACH) -> Any:
    """A pass's full-screen quad, ``reach`` out from the origin.

    Its shader places it, but Coin culls a shape by its bounds: a unit quad
    at the origin was skipped with the origin out of view or behind the
    camera (a model far from it, zoomed in), and the pass with it.  Reaching
    QUAD_REACH out on every axis, its bounds hold any view.
    """
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, 4, [
        (-reach, -reach, -reach), (reach, -reach, -reach),
        (reach, reach, reach), (-reach, reach, reach)])
    face = coin.SoFaceSet()
    face.numVertices.setValue(4)
    group = coin.SoGroup()
    group.addChild(coords)
    group.addChild(face)
    return group


def _framed_quad() -> Any:
    """The composite's quad, framed by a camera of its own.

    It is drawn in the view's scene, where a far-reaching quad would stretch
    "fit all", and a unit quad under the view's camera is culled with the
    origin out of view.  This camera always sees it; the composite shader
    does not use the view's projection.
    """
    camera = coin.SoOrthographicCamera()
    camera.viewportMapping = coin.SoCamera.LEAVE_ALONE
    camera.position = (0, 0, 1)
    camera.height = 2.0
    camera.aspectRatio = 1.0
    camera.nearDistance = 0.5
    camera.farDistance = 1.5
    group = coin.SoGroup()
    group.addChild(camera)
    group.addChild(_quad(reach=1.0))
    return group


def _separator() -> Any:
    """A separator Coin never culls: its quads are placed by shaders."""
    separator = coin.SoSeparator()
    separator.renderCulling = coin.SoSeparator.OFF
    return separator


def _depth(enabled: bool) -> Any:
    """Depth test and write switch.

    A scene texture renders (and clears) its buffers with the depth
    settings in force where it sits: with writing off its depth buffer is
    never cleared.  So the "off" node of a quad always follows the texture
    nodes that quad reads.
    """
    node = coin.SoDepthBuffer()
    node.test = enabled
    node.write = enabled
    return node


def _hide_lines() -> Any:
    """An all-zero line pattern forced below: edges stay out of the AO."""
    style = coin.SoDrawStyle()
    style.linePattern = 0
    for name in ('style', 'pointSize', 'lineWidth'):
        style.getField(name).setIgnored(True)
    style.setOverride(True)
    return style


def _no_transparency() -> Any:
    """Everything opaque, drawn at once: nothing is queued for later."""
    node = coin.SoTransparencyType()
    node.value = coin.SoTransparencyType.NONE
    node.setOverride(True)
    return node


def _texture(width: int, height: int, kind: Any, scene: Any) -> Any:
    texture = coin.SoSceneTexture2()
    texture.size = coin.SbVec2s(width, height)
    texture.type = kind
    texture.backgroundColor = coin.SbVec4f(0, 0, 0, 0)
    texture.transparencyFunction = coin.SoSceneTexture2.NONE
    texture.wrapS = coin.SoSceneTexture2.CLAMP
    texture.wrapT = coin.SoSceneTexture2.CLAMP
    texture.scene = scene
    return texture


def _unit(index: int) -> Any:
    unit = coin.SoTextureUnit()
    unit.unit = index
    return unit


def _scaled(value: int, scale: float) -> int:
    return max(int(value * scale), MIN_TEXTURE)


def _packed_format() -> Any:
    """Half floats where Coin has them: (visibility, depth) needs no more."""
    return getattr(coin.SoSceneTexture2, 'RGBA16F',
                   coin.SoSceneTexture2.RGBA32F)


def _depth_pass(width: int, height: int, camera: Any, scene: Any) -> Any:
    depth_scene = _separator()
    # off then on: SoAnnotation turns depth testing off behind Coin's back,
    # a change of value is what makes Coin turn it on again for real
    depth_scene.addChild(_depth(False))
    depth_scene.addChild(_depth(True))
    depth_scene.addChild(_no_transparency())
    depth_scene.addChild(camera)
    depth_scene.addChild(_hide_lines())
    depth_scene.addChild(_program(DEPTH_VERTEX, DEPTH_FRAGMENT, []))
    depth_scene.addChild(scene)
    return _texture(width, height, coin.SoSceneTexture2.RGBA32F, depth_scene)


def _composite_body() -> Any:
    body = view_utils.skip_bounding_group()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    light_model = coin.SoLightModel()
    light_model.model = coin.SoLightModel.BASE_COLOR
    draw_style = coin.SoDrawStyle()
    draw_style.style = coin.SoDrawStyle.FILLED
    blend = coin.SoTransparencyType()
    blend.value = coin.SoTransparencyType.BLEND
    material = coin.SoMaterial()
    material.diffuseColor = (0, 0, 0)
    material.transparency = 0.5   # only there to make Coin enable blending
    for node in (pick, light_model, draw_style, blend, material):
        body.addChild(node)
    return body


def _pipeline(width: int, height: int, camera: Any, scene: Any,
              radius: float, intensity: float, quality: str,
              temporal: bool, helpers: list[Any]) -> Any:
    """Depth, occlusion, blur and composite for one quality level."""
    budget = TEMPORAL_QUALITY if temporal else QUALITY
    dirs, steps, depth_scale, ao_scale = budget.get(
        quality, budget[DEFAULT_QUALITY])
    dw, dh = _scaled(width, depth_scale), _scaled(height, depth_scale)
    aw, ah = _scaled(width, ao_scale), _scaled(height, ao_scale)

    depth_tex = _depth_pass(dw, dh, camera, scene)

    frame = _float('dt_frame', 0.0)
    occlusion = GTAO_FRAGMENT % {'dirs': dirs, 'steps': steps,
                                 'max_radius': repr(MAX_SCREEN_RADIUS),
                                 'power': repr(POWER)}
    ao_scene = _separator()
    for node in [camera, _unit(0), depth_tex, _depth(False),
                 _program(QUAD_VERTEX, occlusion,
                          [_sampler('dt_depthTex', 0),
                           _vec2('dt_texel', 1.0 / dw, 1.0 / dh),
                           _vec2('dt_size', dw, dh),
                           _float('dt_radius', radius),
                           _float('dt_intensity', intensity),
                           frame]),
                 _quad()]:
        ao_scene.addChild(node)
    ao_tex = _texture(aw, ah, _packed_format(), ao_scene)

    blur_scene = _separator()
    for node in (_unit(0), ao_tex, _depth(False),
                 _program(QUAD_VERTEX, BLUR_FRAGMENT,
                          [_sampler('dt_aoTex', 0),
                           _vec2('dt_aoTexel', 1.0 / aw, 1.0 / ah),
                           _float('dt_radius', radius)]),
                 _quad()):
        blur_scene.addChild(node)
    blur_tex = _texture(aw, ah, _packed_format(), blur_scene)

    body = _composite_body()
    body.addChild(_unit(1))
    body.addChild(depth_tex)
    body.addChild(_unit(0))
    body.addChild(blur_tex)
    if temporal and temporal_ao is not None:
        accumulator = temporal_ao.Accumulator(aw, ah, frame)
        helpers.append(accumulator)
        body.addChild(accumulator.node)
    body.addChild(_depth(False))
    body.addChild(_program(QUAD_VERTEX, COMPOSITE_FRAGMENT,
                           [_sampler('dt_aoTex', 0),
                            _sampler('dt_depthTex', 1),
                            _vec2('dt_aoSize', aw, ah),
                            _vec2('dt_depthSize', dw, dh),
                            _float('dt_radius', radius)]))
    body.addChild(_framed_quad())
    return body


def build(width: int, height: int, camera: Any, scene: Any, radius: float,
          intensity: float, quality: str, temporal: bool = False) -> Any:
    """Node tree of the effect, to be added right after the scene."""
    shrink = min(1.0, MAX_TEXTURE / max(width, height, 1))
    width = _scaled(width, shrink)
    height = _scaled(height, shrink)

    root = coin.SoAnnotation()
    root.setName(ROOT_NAME)
    root.renderCulling = coin.SoSeparator.OFF
    root.pickCulling = coin.SoSeparator.OFF

    info = coin.SoInfo()
    info.setName(ROOT_NAME + 'Info')
    info.string = signature(width, height, camera, scene, radius, intensity,
                            quality, temporal)
    root.addChild(info)

    switch = coin.SoSwitch()
    switch.setName(SWITCH_NAME)
    switch.whichChild = coin.SO_SWITCH_ALL
    root.addChild(switch)

    lod = coin.SoSwitch()
    lod.setName(LOD_SWITCH_NAME)
    lod.whichChild = 0
    switch.addChild(lod)
    temporal = _use_temporal(temporal)
    helpers: list[Any] = []
    for level in (quality, INTERACTIVE):
        if level == INTERACTIVE and quality == INTERACTIVE:
            lod.addChild(lod.getChild(0))
        else:
            lod.addChild(_pipeline(width, height, camera, scene, radius,
                                   intensity, level, temporal, helpers))
    if helpers:
        _helpers[view_utils.node_address(root)] = helpers
    return root


def release(root: Any) -> None:
    """Free the GL objects of the effect under ``root``, being replaced.

    They go at the next frame drawn in their view's GL context.
    """
    for helper in _helpers.pop(view_utils.node_address(root), []):
        helper.release()
