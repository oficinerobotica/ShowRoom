# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
import FreeCAD

from Utils.resource_utils import iconPath
from SpaceNav import orbit_selection, sketch_lock, spacenav_commands

TOOLBAR = 'ShowRoom SpaceMouse'
NOTE = "\n(Built-in SpaceMouse support only; ignored when the 3Dconnexion driver is in control)"


def _wanted_state(checked, current):
    """New state of a toggle, whoever triggered it.

    A click on the toolbar button passes the button's new state, which
    differs from the current one.  A SpaceMouse button (Customize > Spaceball
    Buttons) runs the command with 1 every time, and so does a shortcut on
    some FreeCAD versions: when what is passed is the current state already,
    it is a request to toggle.
    """
    if checked is None or bool(checked) == bool(current):
        return not current
    return bool(checked)


class _LockCommand:
    """Checkable command: checked = the axes are locked."""
    toolbarName = TOOLBAR
    parameter = None
    what = ""

    def Activated(self, checked=None):
        locked = _wanted_state(checked, spacenav_commands.isLocked(self.parameter))
        spacenav_commands.setLocked(self.parameter, locked)
        spacenav_commands.sync_button(self.commandName, locked)
        FreeCAD.Console.PrintLog("ShowRoom: SpaceMouse %s %s\n"
                                 % (self.what, "locked" if locked else "unlocked"))

    def IsActive(self):
        return True

    def resources(self, text, tip, icon):
        return {'MenuText': text, 'ToolTip': tip + NOTE, 'Pixmap': iconPath(icon),
                'Checkable': spacenav_commands.isLocked(self.parameter)}


class SpToolsLockRot(_LockCommand):
    commandName = 'ShowRoom_SpaceNavLockRotation'
    parameter = 'Rotations'
    what = "rotation"

    def GetResources(self):
        return self.resources("Lock SpaceMouse rotation",
                              "The SpaceMouse only pans and zooms", 'SpNav.svg')


class SpToolsLockTrans(_LockCommand):
    commandName = 'ShowRoom_SpaceNavLockTranslation'
    parameter = 'Translations'
    what = "translation"

    def GetResources(self):
        return self.resources("Lock SpaceMouse translation",
                              "The SpaceMouse only rotates", 'SpNav_LockTrans.svg')


class SpToolsLockHorizon(_LockCommand):
    commandName = 'ShowRoom_SpaceNavLockHorizon'
    parameter = 'RollEnable'
    what = "roll (horizon)"

    def GetResources(self):
        return self.resources("Lock SpaceMouse horizon",
                              "The SpaceMouse does not roll the view: the horizon stays level",
                              'SpNav_LockHor.svg')


class SpToolsOrbitSelection:
    """Checkable command: checked = the SpaceMouse rotates around the selection."""
    toolbarName = TOOLBAR
    commandName = 'ShowRoom_SpaceNavOrbitSelection'

    def GetResources(self):
        return {'MenuText': "Rotate around selection",
                'ToolTip': "The SpaceMouse rotates the view around the centre of the selected "
                           "objects or faces (nothing selected: as usual); selecting\n"
                           "something brings it to the middle of the view and keeps it there\n"
                           "(rotation and zoom only while something is selected).\n"
                           "Sets the navigation rotation mode to \"Window center\" while on" + NOTE,
                'Pixmap': iconPath('SpNav_OrbitSel.svg'),
                'Checkable': orbit_selection.isOn()}

    def Activated(self, checked=None):
        on = _wanted_state(checked, orbit_selection.isOn())
        orbit_selection.setOn(on)
        spacenav_commands.sync_button(self.commandName, on)
        FreeCAD.Console.PrintLog("ShowRoom: SpaceMouse rotate around selection %s\n"
                                 % ("on" if on else "off"))

    def IsActive(self):
        return True


import showroom_toolbars     # noqa: E402
showroom_toolbars.toolbarManager.registerCommand(SpToolsLockRot())
showroom_toolbars.toolbarManager.registerCommand(SpToolsLockTrans())
showroom_toolbars.toolbarManager.registerCommand(SpToolsLockHorizon())
showroom_toolbars.toolbarManager.registerCommand(SpToolsOrbitSelection())
orbit_selection.install()    # the option may have been left on (no-op if already running)
sketch_lock.install()
