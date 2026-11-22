# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""ShowRoom's own preferences (Preferences/Mod/ShowRoom), with their defaults."""
import FreeCAD as App

PATH = "User parameter:BaseApp/Preferences/Mod/ShowRoom"
GENERAL = "User parameter:BaseApp/Preferences/General"

RIGS = ['None', 'Sun', 'Three-point', 'Studio']
QUALITIES = ['Low', 'Medium', 'High']
GIZMO_SIZES = {'S': 0.8, 'M': 1.0, 'L': 1.25}


def _nav_default():
    from SceneFX import navigation
    return navigation.DEFAULT_MODE


DEFAULTS = {
    # startup
    'LoadAtStartup': True, 'StartInShowRoom': False,
    # new documents
    'AutoScene': True, 'StartRig': 'Three-point', 'AutoGrid': True, 'AutoGroundPlane': False,
    'AutoSceneOnOpen': False,
    # default scene
    'DefShadows': True, 'DefShadowQuality': 'High', 'DefShadowDarkness': 0.5,
    'DefShadowSoftness': 0.3, 'DefCatcher': False, 'DefAO': True, 'DefAOQuality': 'High',
    'DefAOIntensity': 1.0, 'DefWhileNavigating': None,
    # 3D view
    'InViewPanel': True, 'ShowGizmos': True, 'GizmoSize': 'M', 'SnapTarget': True,
    # panels and textures
    'FontScale': 1.0, 'UseQml': True, 'DefTileSize': 0.0,
    # floating properties panel
    'FloatingPanel': False, 'PanelVisibility': 'Fixed', 'PanelBlur': True, 'AutoTask': True,
    'PanelGeometry': '', 'PanelEasing': 'OutQuart', 'PanelAnimMs': 400, 'KeepOpenOnTask': True,
    # maintenance
    'WarnDisplayTools': True,
}

SCENE_KEYS = ['DefShadows', 'DefShadowQuality', 'DefShadowDarkness', 'DefShadowSoftness',
              'DefCatcher', 'DefAO', 'DefAOQuality', 'DefAOIntensity', 'DefWhileNavigating']


def default(name):
    value = DEFAULTS[name]
    return _nav_default() if name == 'DefWhileNavigating' else value


def group():
    return App.ParamGet(PATH)


def get(name):
    g, d = group(), default(name)
    if isinstance(d, bool):
        return g.GetBool(name, d)
    if isinstance(d, float):
        return g.GetFloat(name, d)
    if isinstance(d, int):
        return g.GetInt(name, d)
    return g.GetString(name, d)


def set(name, value):
    g, d = group(), default(name)
    if isinstance(d, bool):
        g.SetBool(name, bool(value))
    elif isinstance(d, float):
        g.SetFloat(name, float(value))
    elif isinstance(d, int):
        g.SetInt(name, int(value))
    else:
        g.SetString(name, str(value))


def gizmo_factor():
    return GIZMO_SIZES.get(get('GizmoSize'), 1.0)


def apply_start_workbench(on):
    """Make ShowRoom FreeCAD's start workbench, or give the previous one back."""
    general = App.ParamGet(GENERAL)
    current = general.GetString('AutoloadModule', '')
    if on and current != 'ShowRoomWorkbench':
        group().SetString('PreviousAutoload', current)
        general.SetString('AutoloadModule', 'ShowRoomWorkbench')
    elif not on and current == 'ShowRoomWorkbench':
        previous = group().GetString('PreviousAutoload', '')
        if previous:
            general.SetString('AutoloadModule', previous)
        else:
            general.RemString('AutoloadModule')


def reset_all():
    keep = group().GetBool('Migrated', False)
    group().Clear()
    if keep:
        group().SetBool('Migrated', True)
    apply_start_workbench(False)
