# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""SpaceMouse axis locks.

FreeCAD's built-in ("legacy", spacenav based) SpaceMouse support reads its
settings from the parameter group below at every motion event, so flipping the
parameters takes effect immediately.  They are the same settings as in
Tools > Customize > Spaceball Motion.

Not covered: when FreeCAD talks to the official 3Dconnexion driver through
NavLib (Windows and macOS with the driver installed, i.e. "Legacy SpaceMouse
devices" switched off in the navigation preferences), the driver owns the axis
handling and these parameters are ignored.
"""
import FreeCAD

MOTION_GROUP = "User parameter:BaseApp/Spaceball/Motion"


def _group():
    return FreeCAD.ParamGet(MOTION_GROUP)


def isLocked(parameter):
    return not _group().GetBool(parameter, True)


def setLocked(parameter, locked):
    _group().SetBool(parameter, not locked)


def sync_button(command_name, state):
    """Show a state on a command's toolbar button and menu entry: a SpaceMouse
    button, or ShowRoom itself, runs or changes things without touching them."""
    try:
        import FreeCADGui
        for action in FreeCADGui.Command.get(command_name).getAction():
            if action.isCheckable() and action.isChecked() != state:
                blocked = action.blockSignals(True)
                action.setChecked(state)
                action.blockSignals(blocked)
    except Exception:
        pass


def toggle(parameter):
    locked = not isLocked(parameter)
    setLocked(parameter, locked)
    return locked
