# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""The scene configuration: a tree folder holding the lights and helpers of a
document, plus the per-document settings of the viewport effects."""
import FreeCAD

from Utils.resource_utils import iconPath

SCENE_TYPE = 'SceneConfiguration'

SHADOW_QUALITIES = ['Low', 'Medium', 'High']
AO_QUALITIES = ['Low', 'Medium', 'High']

UNIT_LIMITS = (0.0, 1.0, 0.05)
AO_INTENSITY_LIMITS = (0.0, 4.0, 0.1)

#: ambient occlusion options that need PyOpenGL: (property, tip)
AO_TOGGLES = (
    ('AOTemporal', 'Accumulate ambient occlusion over frames: smoother, and '
                   'it keeps refining while the view is still. Needs PyOpenGL'),
)
#: properties of earlier versions, dropped when a document is opened
RETIRED_PROPERTIES = ('AODepthReuse',)

EFFECT_PROPERTIES = ('Shadows', 'ShadowDarkness', 'ShadowSoftness', 'ShadowQuality',
                     'AmbientOcclusion', 'AOIntensity', 'AORadius', 'AOQuality',
                     'AOTemporal',
                     'WhileNavigating', 'NavigationResumeDelay', 'ShadowCatcher')


def _enumeration(obj, name, values):
    """Give an enumeration saved by an older version today's values."""
    try:
        if list(obj.getEnumerationsOfProperty(name)) == list(values):
            return
        chosen = getattr(obj, name)
        setattr(obj, name, list(values))
        if chosen in values:
            setattr(obj, name, chosen)
    except Exception:
        pass


def _constraint(obj, name, limits):
    try:
        setattr(obj, name, (getattr(obj, name),) + tuple(limits))
    except Exception:
        pass


class CreateSceneConfig(object):
    type = SCENE_TYPE

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        pl = obj.PropertiesList
        if 'Shadows' not in pl:
            obj.addProperty("App::PropertyBool", "Shadows", "Shadows",
                            "Real-time shadows in the 3D view, cast by the directional and spot "
                            "lights that have CastShadows enabled").Shadows = False
        if 'ShadowDarkness' not in pl:
            obj.addProperty("App::PropertyFloatConstraint", "ShadowDarkness", "Shadows",
                            "How dark the shadows are").ShadowDarkness = (0.5,) + UNIT_LIMITS
        if 'ShadowSoftness' not in pl:
            obj.addProperty("App::PropertyFloatConstraint", "ShadowSoftness", "Shadows",
                            "Blur of the shadow borders").ShadowSoftness = (0.3,) + UNIT_LIMITS
        if 'ShadowQuality' not in pl:
            obj.addProperty("App::PropertyEnumeration", "ShadowQuality", "Shadows",
                            "Resolution of the shadow maps. High needs a decent graphics card")
            obj.ShadowQuality = SHADOW_QUALITIES
            obj.ShadowQuality = 'High'
        if 'ShadowCatcher' not in pl:
            obj.addProperty("App::PropertyBool", "ShadowCatcher", "Shadows",
                            "Soft shadow of the model on an invisible ground, at the lowest "
                            "point of the scene. Works with or without real-time shadows; "
                            "uses ShadowDarkness, ShadowSoftness and ShadowQuality"
                            ).ShadowCatcher = False
        if 'TurntablePeriod' not in pl:
            obj.addProperty("App::PropertyFloat", "TurntablePeriod", "Turntable",
                            "Seconds the turntable takes for one full turn "
                            "(negative = the other way)").TurntablePeriod = 15.0
        if 'AmbientOcclusion' not in pl:
            obj.addProperty("App::PropertyBool", "AmbientOcclusion", "Ambient Occlusion",
                            "Screen space ambient occlusion: darkens creases, holes and contact "
                            "areas in the 3D view").AmbientOcclusion = False
        if 'AOIntensity' not in pl:
            obj.addProperty("App::PropertyFloatConstraint", "AOIntensity", "Ambient Occlusion",
                            "Strength of the darkening").AOIntensity = (1.0,) + AO_INTENSITY_LIMITS
        if 'AORadius' not in pl:
            obj.addProperty("App::PropertyLength", "AORadius", "Ambient Occlusion",
                            "Distance within which surfaces occlude each other. "
                            "0 = automatic, from the size of the scene").AORadius = 0.0
        if 'AOQuality' not in pl:
            obj.addProperty("App::PropertyEnumeration", "AOQuality", "Ambient Occlusion",
                            "Number of samples and resolution of the effect")
            obj.AOQuality = AO_QUALITIES
            obj.AOQuality = 'High'
        missing = [name for name, _tip in AO_TOGGLES if name not in pl]
        if missing:
            # on where they can run: no warnings for what was never asked
            from SceneFX import gl_util
            default = gl_util.missing_dependency() is None
            for name, tip in AO_TOGGLES:
                if name in missing:
                    obj.addProperty("App::PropertyBool", name,
                                    "Ambient Occlusion", tip)
                    setattr(obj, name, default)
        if 'WhileNavigating' not in pl:
            from SceneFX import navigation
            obj.addProperty("App::PropertyEnumeration", "WhileNavigating", "Performance",
                            "What to do with the effects while the view is rotated, panned or "
                            "zoomed. Pausing them keeps navigation fluid on heavy models")
            obj.WhileNavigating = navigation.MODES
            obj.WhileNavigating = navigation.DEFAULT_MODE
        if 'NavigationResumeDelay' not in pl:
            obj.addProperty("App::PropertyIntegerConstraint", "NavigationResumeDelay", "Performance",
                            "Milliseconds the view has to stay still before the paused effects "
                            "come back").NavigationResumeDelay = (250, 0, 5000, 50)

    def onDocumentRestored(self, obj):
        for name in RETIRED_PROPERTIES:
            if name in obj.PropertiesList:
                obj.removeProperty(name)
        self.setProperties(obj)
        from SceneFX import navigation
        _enumeration(obj, 'WhileNavigating', navigation.MODES)
        _constraint(obj, 'ShadowDarkness', UNIT_LIMITS)
        _constraint(obj, 'ShadowSoftness', UNIT_LIMITS)
        _constraint(obj, 'AOIntensity', AO_INTENSITY_LIMITS)
        _constraint(obj, 'NavigationResumeDelay', (0, 5000, 50))

    def onChanged(self, obj, prop):
        if prop in EFFECT_PROPERTIES and FreeCAD.GuiUp:
            from SceneFX import view_rig
            view_rig.schedule_sync(obj.Document)

    def execute(self, obj):
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class ViewProviderCreateSceneFolder:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from SceneFX import view_rig
        view_rig.schedule_sync(vobj.Object.Document)

    def onDelete(self, vobj, subelements):
        # deleting the configuration switches the effects off
        from SceneFX import view_rig
        view_rig.schedule_sync(vobj.Object.Document)
        return True

    # ------------------------------------------------------------ task panel
    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        from dtpanels import bridge
        return bridge.show_for(vobj.Object) is not None

    def unsetEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        import FreeCADGui
        FreeCADGui.Control.closeDialog()
        return True

    def doubleClicked(self, vobj):
        """Double click in the tree: edit in the task panel, as in Part Design."""
        from dtpanels import bridge
        bridge.edit(vobj.Object)
        return True

    def setupContextMenu(self, vobj, menu):
        action = menu.addAction("Display effects…")
        action.triggered.connect(lambda: self.doubleClicked(vobj))

    def getIcon(self):
        return iconPath('FolderTreeIcon.svg')

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def isSceneFolder(obj):
    return getattr(getattr(obj, 'Proxy', None), 'type', None) == SCENE_TYPE


def getSceneFolder(doc=None, create=False):
    """The scene configuration of ``doc`` (there is one per document)."""
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    for obj in doc.Objects:
        if isSceneFolder(obj):
            return obj
    return createSceneFolder(doc) if create else None


def createSceneFolder(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    obj = doc.addObject("App::DocumentObjectGroupPython", "SceneFolder")
    CreateSceneConfig(obj)
    if FreeCAD.GuiUp:
        ViewProviderCreateSceneFolder(obj.ViewObject)
    return obj


if __name__ == "__main__":
    createSceneFolder()
