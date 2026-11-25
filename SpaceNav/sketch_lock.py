# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""SpaceMouse: no rotation while a sketch is being edited.

A sketch is drawn on its plane: rotating the view away from it only gets in
the way.  While the option is on, the rotation lock (the "Rotations" setting
of Tools > Customize > Spaceball Motion, the same as the Lock SpaceMouse
rotation button) is switched on when a sketch opens for editing and given back
as it was when the sketch is closed.  Panning and zooming keep working.

FreeCAD has no Python notification for "edit mode started", so a light timer
looks at the document in edit a few times per second.  Built-in SpaceMouse
support only, like the other SpaceMouse options.
"""
import FreeCAD

from SpaceNav import spacenav_commands

PREFS = "User parameter:BaseApp/Preferences/Mod/ShowRoom"
PARAM = "SpaceMouseSketchNoRotation"
SAVED = "SpaceMouseSketchPreviousRotationLock"     # -1: not in a sketch
INTERVAL_MS = 300
LOCK_COMMAND = 'ShowRoom_SpaceNavLockRotation'

_timer = None


def isOn():
    return FreeCAD.ParamGet(PREFS).GetBool(PARAM, False)


def editing_sketch():
    """The object being edited is a sketch."""
    try:
        import FreeCADGui
        doc = FreeCADGui.ActiveDocument
        vp = doc.getInEdit() if doc is not None else None
        obj = getattr(vp, 'Object', None)
        return obj is not None and obj.isDerivedFrom('Sketcher::SketchObject')
    except Exception:
        return False


def _sketch_changed():
    """Rotate around the selection steps aside in a sketch: its pan lock too."""
    from SpaceNav import orbit_selection
    orbit_selection.update_pan()


def _check():
    group = FreeCAD.ParamGet(PREFS)
    saved = group.GetInt(SAVED, -1)
    inside = isOn() and editing_sketch()
    if inside and saved < 0:
        group.SetInt(SAVED, int(spacenav_commands.isLocked('Rotations')))
        spacenav_commands.setLocked('Rotations', True)
        spacenav_commands.sync_button(LOCK_COMMAND, True)
        _sketch_changed()
    elif not inside and saved >= 0:
        group.RemInt(SAVED)
        spacenav_commands.setLocked('Rotations', bool(saved))
        spacenav_commands.sync_button(LOCK_COMMAND, bool(saved))
        _sketch_changed()


def apply_prefs():
    """Start or stop watching, according to the setting."""
    global _timer
    if isOn():
        if _timer is None:
            from PySide import QtCore
            _timer = QtCore.QTimer()
            _timer.setInterval(INTERVAL_MS)
            _timer.timeout.connect(_check)
        _timer.start()
    elif _timer is not None:
        _timer.stop()
    _check()            # also gives the lock back after a crash inside a sketch


def install():
    apply_prefs()
