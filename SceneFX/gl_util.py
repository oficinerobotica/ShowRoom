# SPDX-License-Identifier: LGPL-2.1-or-later
"""Raw OpenGL helpers shared by the ambient occlusion callbacks.

Coin owns the GL state; a callback that draws on its own must leave that
state exactly as it found it.  ``preserved_state`` saves and restores what
Coin's lazy state tracking does not see (framebuffers, program, active
texture unit) around everything ``glPushAttrib`` covers.

GL objects can only be deleted in the context that made them, from inside
a frame.  A helper whose effect is replaced ``retire``s them; ``collect``,
run by every helper callback, deletes those of the current context.
"""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

#: a full-screen quad in clip space
QUAD = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
#: errors other code left behind: cleared, or our own checks would trip
STALE_ERRORS = 16
_reported: set[str] = set()


@dataclass
class GLObjects:
    """GL objects made by one helper, in one context."""

    context: int = 0
    textures: list[int] = field(default_factory=list)
    framebuffers: list[int] = field(default_factory=list)
    programs: list[int] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.textures or self.framebuffers or self.programs)


#: GL objects of replaced effects, waiting for a frame in their context
_retired: list[GLObjects] = []


def _configure() -> None:
    """Turn off PyOpenGL's checks, before its GL module is first loaded.

    By default PyOpenGL calls glGetError after every GL call: a driver
    round trip that can stall the GPU, on every call of every frame.  The
    helpers check for errors where it matters.  Loaded first by other code,
    PyOpenGL keeps that code's choice.
    """
    import OpenGL
    OpenGL.ERROR_CHECKING = False
    OpenGL.ERROR_LOGGING = False


def load() -> Any:
    """PyOpenGL's GL module (raises ImportError where it is missing)."""
    _configure()
    from OpenGL import GL
    return GL


def missing_dependency() -> str | None:
    """Why the GL helpers cannot run here, or None if they can."""
    with contextlib.suppress(ImportError):
        _configure()
    for package in ('OpenGL.GL', 'numpy'):
        try:
            __import__(package)
        except ImportError as exc:
            return '%s: %s' % (package, exc)
    return None


def warn_once(key: str, message: str) -> None:
    """One line in the Report view per key and session."""
    if key in _reported:
        return
    _reported.add(key)
    with contextlib.suppress(ImportError):
        import FreeCAD
        FreeCAD.Console.PrintWarning('ShowRoom: %s\n' % message)


def current_context() -> int:
    """The current GL context, as a number to compare; 0 if none."""
    from OpenGL import contextdata
    return int(contextdata.getContext() or 0)


def retire(objects: GLObjects) -> None:
    """Queue ``objects`` for deletion at the next frame in their context."""
    if objects:
        _retired.append(objects)


def collect(gl: Any) -> None:
    """Delete the retired objects that belong to the current context."""
    if not _retired:
        return
    context = current_context()
    for objects in [o for o in _retired if o.context == context]:
        _retired.remove(objects)
        if objects.textures:
            gl.glDeleteTextures(objects.textures)
        if objects.framebuffers:
            gl.glDeleteFramebuffers(len(objects.framebuffers),
                                    objects.framebuffers)
        for program in objects.programs:
            gl.glDeleteProgram(program)


def clear_errors(gl: Any) -> None:
    """Drop GL errors left by others."""
    for _ in range(STALE_ERRORS):
        if gl.glGetError() == gl.GL_NO_ERROR:
            return


def program(gl: Any, vertex: str, fragment: str) -> int:
    """A linked GLSL program; RuntimeError with the log if it fails."""
    def shader(kind: int, source: str) -> int:
        handle = gl.glCreateShader(kind)
        gl.glShaderSource(handle, source)
        gl.glCompileShader(handle)
        if not gl.glGetShaderiv(handle, gl.GL_COMPILE_STATUS):
            raise RuntimeError(gl.glGetShaderInfoLog(handle))
        return int(handle)

    handle = gl.glCreateProgram()
    shaders = (shader(gl.GL_VERTEX_SHADER, vertex),
               shader(gl.GL_FRAGMENT_SHADER, fragment))
    for part in shaders:
        gl.glAttachShader(handle, part)
    gl.glLinkProgram(handle)
    # flagged now, freed with the program
    for part in shaders:
        gl.glDeleteShader(part)
    if not gl.glGetProgramiv(handle, gl.GL_LINK_STATUS):
        raise RuntimeError(gl.glGetProgramInfoLog(handle))
    return int(handle)


def nearest_texture(gl: Any) -> int:
    """A new texture with nearest filtering, clamped, bound to unit 0."""
    texture = int(gl.glGenTextures(1))
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST),
                        (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                        (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE),
                        (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
        gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
    return texture


def draw_quad(gl: Any) -> None:
    """Draw the full-screen quad with the current program."""
    gl.glBegin(gl.GL_QUADS)
    for x, y in QUAD:
        gl.glVertex2f(x, y)
    gl.glEnd()


def bind(gl: Any, unit: int, texture: int) -> None:
    """Bind ``texture`` on ``unit``, leaving the active unit as it was."""
    active = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    gl.glActiveTexture(active)


def bound(gl: Any, unit: int) -> int:
    """The texture bound on ``unit``, leaving the active unit as it was."""
    active = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    texture = int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D))
    gl.glActiveTexture(active)
    return texture


@contextlib.contextmanager
def preserved_state(gl: Any) -> Iterator[None]:
    """Everything a callback changes is put back on the way out."""
    draw = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
    read = int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING))
    current = int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM))
    active = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))
    gl.glPushAttrib(gl.GL_ALL_ATTRIB_BITS)
    try:
        yield
    finally:
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read)
        gl.glUseProgram(current)
        gl.glPopAttrib()
        gl.glActiveTexture(active)


def matrices(gl: Any) -> tuple[Any, Any]:
    """Modelview and projection as GL holds them (column-major)."""
    import numpy
    view = numpy.array(gl.glGetFloatv(gl.GL_MODELVIEW_MATRIX),
                       dtype=numpy.float32).reshape(4, 4)
    projection = numpy.array(gl.glGetFloatv(gl.GL_PROJECTION_MATRIX),
                             dtype=numpy.float32).reshape(4, 4)
    return view, projection
