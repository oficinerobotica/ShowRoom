# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
import FreeCADGui  # noqa: F401

from Utils.resource_utils import iconPath

TOOLBAR = 'ShowRoom settings'


class SettingsCommand:
    toolbarName = TOOLBAR
    commandName = 'ShowRoom_Settings'

    def GetResources(self):
        return {'MenuText': "ShowRoom settings…",
                'ToolTip': "ShowRoom's own settings in the task panel: startup, what every new "
                           "document starts with, the default scene, gizmos, panels",
                'Pixmap': iconPath('Settings.svg')}

    def Activated(self):
        from dtpanels import models
        models.open_settings()

    def IsActive(self):
        return True


class FloatingPanelCommand:
    toolbarName = TOOLBAR
    commandName = 'ShowRoom_FloatingPanel'

    def GetResources(self):
        return {'MenuText': "Floating properties panel",
                'ToolTip': "FreeCAD's properties (Data, View) and task panel in a panel "
                           "floating over the 3D view. Click again to put them back",
                'Pixmap': iconPath('FloatingPanel.svg')}

    def Activated(self, *args):
        from dtpanels import floating
        floating.toggle()

    def IsActive(self):
        return True


import showroom_toolbars     # noqa: E402
showroom_toolbars.toolbarManager.registerCommand(SettingsCommand())
showroom_toolbars.toolbarManager.registerCommand(FloatingPanelCommand())
