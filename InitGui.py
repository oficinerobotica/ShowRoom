# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""ShowRoom: lights, shadows, ambient occlusion and appearance for FreeCAD's 3D view."""
# FreeCAD runs this file with separate global and local namespaces: the functions
# below import what they need themselves.
import FreeCADGui


class ShowRoomWorkbench(Workbench):
    MenuText = "ShowRoom"
    ToolTip = "Lights, shadows, ambient occlusion, appearance and textures for the 3D view"

    def __init__(self):
        from Utils.resource_utils import iconPath
        self.__class__.Icon = iconPath("ShowRoom.svg")

    def Initialize(self):
        """Executed once, the first time the workbench is activated."""
        import showroom_toolbars
        everything = []
        for name, commands in showroom_toolbars.toolbarManager.Toolbars.items():
            self.appendToolbar(name, commands)
            if everything:
                everything.append(showroom_toolbars.SEPARATOR)
            everything += commands
        self.appendMenu("ShowRoom", everything)

    def ContextMenu(self, recipient):
        """Right click on objects with a shape: edit their appearance."""
        try:
            selection = FreeCADGui.Selection.getSelection()
            if selection and any(hasattr(o, 'Shape') for o in selection):
                self.appendContextMenu("", ["ShowRoom_Appearance"])
        except Exception:
            pass

    def Activated(self):
        import FreeCAD
        for module in ("SceneFX.textures", "dtpanels.overlay", "SceneFX.autoscene"):
            try:
                __import__(module, fromlist=["install"]).install()
            except Exception as error:
                FreeCAD.Console.PrintWarning("ShowRoom: %s: %s\n" % (module, error))

    def Deactivated(self):
        return

    def GetClassName(self):
        # mandatory for a workbench written in Python
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(ShowRoomWorkbench())


def _migratePreferences():
    """Bring over the settings of Display Tools, the add-on ShowRoom grew from (once)."""
    import FreeCAD
    try:
        new = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/ShowRoom")
        if new.GetBool("Migrated", False):
            return
        old = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/DisplayTools")
        for kind in ("Bool", "Int", "Float", "String", "Unsigned"):
            get, put = getattr(old, "Get" + kind), getattr(new, "Set" + kind)
            for name in getattr(old, "Get%ss" % kind)():
                put(name, get(name))
        new.SetBool("Migrated", True)
    except Exception:
        pass


def _warnDisplayTools():
    """Display Tools and ShowRoom share their modules: only one of them may be installed."""
    import os
    import FreeCAD
    if not FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/ShowRoom").GetBool(
            "WarnDisplayTools", True):
        return
    folders = [os.path.join(FreeCAD.getUserAppDataDir(), "Mod")]
    try:
        folders.append(os.path.join(FreeCAD.getHomePath(), "Mod"))
    except Exception:
        pass
    for mod in folders:
        try:
            names = os.listdir(mod)
        except OSError:
            continue
        for name in names:
            path = os.path.join(mod, name)
            if os.path.isfile(os.path.join(path, "displaytools_toolbars.py")) and \
                    not os.path.isfile(os.path.join(path, "showroom_toolbars.py")):
                FreeCAD.Console.PrintWarning(
                    "ShowRoom: the Display Tools add-on is installed too (%s). ShowRoom replaces "
                    "it and opens its documents: remove Display Tools.\n" % path)
                return


_migratePreferences()
_warnDisplayTools()



def _startServices():
    """Textures, the floating light panel and the scene of new documents (once).
    Self-contained: FreeCAD runs this file with separate namespaces."""
    import FreeCAD
    try:                            # before any QQuickWidget exists (Windows: Direct3D by default)
        from dtpanels import bridge
        bridge.quick_usable()
    except Exception:
        pass
    for module, label in (("SceneFX.textures", "textures"), ("dtpanels.overlay", "in-view light panel"),
                          ("SceneFX.autoscene", "automatic scene"),
                          ("dtpanels.floating", "floating properties panel")):
        try:
            __import__(module, fromlist=["install"]).install()
        except Exception as error:
            FreeCAD.Console.PrintWarning("ShowRoom: %s not available: %s\n" % (label, error))


def _loadAtStartup():
    import FreeCAD
    return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/ShowRoom").GetBool(
        "LoadAtStartup", True)


if _loadAtStartup():
    _startServices()
