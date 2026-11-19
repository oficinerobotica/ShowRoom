# SPDX-License-Identifier: LGPL-2.1-or-later
"""Temporal accumulation of the ambient occlusion (toggle: AOTemporal).

A temporal filter reads its own output of the previous frame.  Two
SoSceneTexture2 nodes reading each other would make the scene graph a
cycle, which Coin does not support, so an SoCallback does it in raw GL,
right after Coin binds the blurred AO (r = visibility, g = eye depth) to
unit 0:

1. each AO texel is reprojected into the previous frame with the current
   and previous camera matrices, read from GL so they are exactly Coin's;
2. where the depths agree it is blended with the history (weight 1/n,
   n frames, capped lower while the camera moves to limit lag) into the
   other of two history textures;
3. the result is bound to unit 0, where the composite shader reads it.

After each frame a one-shot sensor bumps the occlusion shader's dt_frame
uniform, so the next frame searches other slices: while the camera moves
the history adds them up (the per-frame budget is small, see
ambient_occlusion.TEMPORAL_QUALITY); once it stops only the AO and blur
passes re-render, with new noise, until STILL_FRAMES frames have
converged the picture.
"""
from __future__ import annotations

from typing import Any

from pivy import coin

from SceneFX import gl_util

#: frames of history while the camera moves (more: smoother, more lag)
MOVING_MAX = 4.0
#: frames of history once the camera stops
STILL_MAX = 24.0
#: extra frames rendered for progressive refinement while still
STILL_FRAMES = 24
#: relative depth mismatch that rejects the history
DEPTH_TOLERANCE = 0.02
#: how close two camera matrices must be to count as "not moving"
MATRIX_RTOL = 1e-6
MATRIX_ATOL = 1e-7
UNIFORMS = ('dt_cur', 'dt_hist', 'dt_invView', 'dt_prevView', 'dt_prevProj',
            'dt_proj', 'dt_maxCount', 'dt_tolerance')

VERTEX = """#version 120
varying vec2 dt_uv;
void main() {
    dt_uv = gl_Vertex.xy * 0.5 + 0.5;
    gl_Position = vec4(gl_Vertex.xy, 0.0, 1.0);
}
"""

FRAGMENT = """#version 120
uniform sampler2D dt_cur;    // r = visibility, g = eye depth
uniform sampler2D dt_hist;   // r, g as above, b = frames accumulated
uniform mat4 dt_invView;     // current eye -> world
uniform mat4 dt_prevView;    // world -> previous eye
uniform mat4 dt_prevProj;
uniform mat4 dt_proj;
uniform float dt_maxCount;
uniform float dt_tolerance;
varying vec2 dt_uv;

void main() {
    vec4 c = texture2D(dt_cur, dt_uv);
    if (c.g <= 0.0) { gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0); return; }

    float ze = -c.g;
    float wc = dt_proj[2][3] * ze + dt_proj[3][3];
    vec2 ndc = dt_uv * 2.0 - 1.0;
    vec3 eye = vec3(
        (ndc.x * wc - dt_proj[2][0] * ze - dt_proj[3][0]) / dt_proj[0][0],
        (ndc.y * wc - dt_proj[2][1] * ze - dt_proj[3][1]) / dt_proj[1][1],
        ze);

    vec4 pe = dt_prevView * (dt_invView * vec4(eye, 1.0));
    vec4 pc = dt_prevProj * pe;
    vec2 puv = pc.xy / pc.w * 0.5 + 0.5;

    float count = 1.0;
    float vis = c.r;
    if (all(greaterThan(puv, vec2(0.0))) && all(lessThan(puv, vec2(1.0)))) {
        vec4 h = texture2D(dt_hist, puv);
        float expected = -pe.z;
        if (h.g > 0.0 && abs(h.g - expected) < dt_tolerance * expected) {
            count = min(h.b + 1.0, dt_maxCount);
            vis = mix(h.r, c.r, 1.0 / count);
        }
    }
    gl_FragColor = vec4(vis, c.g, count, 1.0);
}
"""


#: set by a GL failure: the effect is rebuilt without the filter, at the
#: full per-frame budget its few slices a frame relied on
failed = False


def available() -> bool:
    """Whether the filter can run here (says why not, once)."""
    reason = ('disabled after a GL error' if failed
              else gl_util.missing_dependency())
    if reason is not None:
        gl_util.warn_once('temporal', 'temporal AO unavailable (%s)'
                          % reason)
    return reason is None


class Accumulator:
    """The temporal filter of one AO pipeline, in the view's GL context."""

    def __init__(self, width: int, height: int, frame: Any) -> None:
        self.width = width
        self.height = height
        self.frame = frame            # the occlusion shader's dt_frame
        self.frame.ref()
        self.disabled = False
        self.textures: list[int] = []
        self.gl_objects = gl_util.GLObjects()
        self.fbo = 0
        self.program = 0
        self.locations: dict[str, int] = {}
        self.index = 0
        self.previous: tuple[Any, Any] | None = None
        self.still = 0
        self.sensor = coin.SoOneShotSensor(self._next_frame, None)
        self.node = coin.SoCallback()
        self.node.setCallback(self._render, None)

    def _next_frame(self, data: Any, sensor: Any) -> None:
        if self.frame is not None:
            self.frame.value = self.frame.value.getValue() + 1.0

    def release(self) -> None:
        """Its effect is replaced: its GL objects go at the next frame."""
        self.sensor.unschedule()
        if self.frame is not None:
            self.frame.unref()
            self.frame = None
        gl_util.retire(self.gl_objects)
        self.gl_objects = gl_util.GLObjects()
        self.textures = []

    def _create(self, gl: Any) -> None:
        self.textures = []
        for _ in range(2):
            texture = gl_util.nearest_texture(gl)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA16F, self.width,
                            self.height, 0, gl.GL_RGBA, gl.GL_FLOAT, None)
            self.textures.append(texture)
        self.fbo = int(gl.glGenFramebuffers(1))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)   # empty history: 0 frames
        for texture in self.textures:
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,
                                      gl.GL_COLOR_ATTACHMENT0,
                                      gl.GL_TEXTURE_2D, texture, 0)
            if (gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                    != gl.GL_FRAMEBUFFER_COMPLETE):
                raise RuntimeError('history framebuffer incomplete')
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        self.program = gl_util.program(gl, VERTEX, FRAGMENT)
        self.locations = {name: gl.glGetUniformLocation(self.program, name)
                          for name in UNIFORMS}
        self.gl_objects = gl_util.GLObjects(
            gl_util.current_context(), list(self.textures), [self.fbo],
            [self.program])

    def _accumulate(self, gl: Any, current: int, view: Any, projection: Any,
                    moving: bool) -> int:
        """Blend this frame into the history; the texture it went to."""
        import numpy
        if not self.textures:
            self._create(gl)
        target = self.textures[self.index]
        previous_view, previous_projection = (self.previous
                                              or (view, projection))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                  gl.GL_TEXTURE_2D, target, 0)
        gl.glViewport(0, 0, self.width, self.height)
        for capability in (gl.GL_DEPTH_TEST, gl.GL_BLEND, gl.GL_CULL_FACE,
                           gl.GL_SCISSOR_TEST):
            gl.glDisable(capability)
        gl.glColorMask(True, True, True, True)
        gl.glUseProgram(self.program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, current)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.textures[1 - self.index])
        at = self.locations
        gl.glUniform1i(at['dt_cur'], 0)
        gl.glUniform1i(at['dt_hist'], 1)
        # GL keeps M column-major as M.T: inverse(M).T is inverse(M.T)
        gl.glUniformMatrix4fv(at['dt_invView'], 1, gl.GL_FALSE,
                              numpy.linalg.inv(view).astype(numpy.float32))
        gl.glUniformMatrix4fv(at['dt_prevView'], 1, gl.GL_FALSE,
                              previous_view)
        gl.glUniformMatrix4fv(at['dt_prevProj'], 1, gl.GL_FALSE,
                              previous_projection)
        gl.glUniformMatrix4fv(at['dt_proj'], 1, gl.GL_FALSE, projection)
        gl.glUniform1f(at['dt_maxCount'],
                       MOVING_MAX if moving else STILL_MAX)
        gl.glUniform1f(at['dt_tolerance'], DEPTH_TOLERANCE)
        gl_util.draw_quad(gl)
        return target

    def _moved(self, view: Any, projection: Any) -> bool:
        import numpy
        if self.previous is None:
            return True
        return not all(
            numpy.allclose(now, before, rtol=MATRIX_RTOL, atol=MATRIX_ATOL)
            for now, before in zip((view, projection), self.previous))

    def _render(self, data: Any, action: Any) -> None:
        global failed
        render = coin.SoGLRenderAction.getClassTypeId()
        if self.disabled or self.frame is None or not action.isOfType(
                render):
            return
        gl = gl_util.load()
        gl_util.clear_errors(gl)
        current = gl_util.bound(gl, 0)
        if current == 0:
            return
        view, projection = gl_util.matrices(gl)
        moving = self._moved(view, projection)
        try:
            with gl_util.preserved_state(gl):
                gl_util.collect(gl)
                result = self._accumulate(gl, current, view, projection,
                                          moving)
        except Exception as exc:  # noqa: BLE001 - called from Coin's render
            failed = True
            self.disabled = True
            gl_util.warn_once('temporal-gl',
                              'temporal AO disabled (%s)' % exc)
            return
        gl_util.bind(gl, 0, result)
        self.index = 1 - self.index
        self.previous = (view, projection)
        if moving:
            self.still = 0
            self.sensor.schedule()   # other slices next frame
        elif self.still < STILL_FRAMES:
            self.still += 1
            self.sensor.schedule()
