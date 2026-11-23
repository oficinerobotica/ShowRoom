# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Base classes shared by the point, directional and spot light objects.

How a light is put on screen
----------------------------
* The Coin light node (``coinLight``) is *not* part of the view provider's own
  scene graph: a light inside a view provider only lights that view provider.
  ``SceneFX.view_rig`` inserts the light nodes of a document at the right place
  of every 3D view showing it, and keeps them there across undo/redo, new
  views, document loading, ...
* The gizmo (Gizmos package) is an ordinary display mode node of the view
  provider, so FreeCAD shows/hides/deletes it by itself.
* The FreeCAD properties are the single source of truth.  Dragging the gizmo
  writes the properties, and the properties drive both light and gizmo.
"""
import math

import FreeCAD
from pivy import coin

from Utils import view_utils

# limits of the (hidden, kept for older files) Scale property
SCALE_LIMITS = (5, 1000000, 5)
INTENSITY_LIMITS = (0.0, 1.0, 0.1)
# FreeCAD's headlight is already at full strength: an extra light at 1.0 burns the scene out
DEFAULT_INTENSITY = 0.6
EPS = 1e-6


def _constraint(obj, name, limits):
    """(Re)apply the limits of a constraint property: they are not stored in the file."""
    try:
        setattr(obj, name, (getattr(obj, name),) + tuple(limits))
    except Exception:
        pass


def hideLegacy(obj):
    """Properties of the old Coin manipulators: kept so that older files load,
    hidden because the gizmo no longer uses them (it has a constant size on
    screen and draws the sun from the model)."""
    for name in ('Scale', 'GizmoPosition'):
        if name in obj.PropertiesList:
            try:
                obj.setEditorMode(name, 2)
            except Exception:
                pass


class UniversalLight:
    type = 'coinLight'
    isDisplayToolsLight = True
    canCastShadows = False

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        pl = obj.PropertiesList

        if 'Color' not in pl:
            obj.addProperty("App::PropertyColor", "Color", "Light",
                            "The color of the light").Color = (1.0, 0.94, 0.91)
        if 'Intensity' not in pl:
            obj.addProperty("App::PropertyFloatConstraint", "Intensity", "Light",
                            "The intensity of the light").Intensity = (DEFAULT_INTENSITY,) + INTENSITY_LIMITS
        if 'ShowManipulator' not in pl:
            obj.addProperty("App::PropertyBool", "ShowManipulator", "Manipulator",
                            "Show the gizmo of the light in the 3D view").ShowManipulator = _show_gizmos()
        if 'Scale' not in pl:
            obj.addProperty("App::PropertyIntegerConstraint", "Scale", "Manipulator",
                            "Size of the manipulator").Scale = (5,) + SCALE_LIMITS
            hideLegacy(obj)
        if self.canCastShadows and 'CastShadows' not in pl:
            obj.addProperty("App::PropertyBool", "CastShadows", "Light",
                            "This light casts shadows when shadows are enabled "
                            "in the scene configuration").CastShadows = self.defaultCastShadows

    defaultCastShadows = False

    def onDocumentRestored(self, obj):
        self.setProperties(obj)
        _constraint(obj, 'Intensity', INTENSITY_LIMITS)
        _constraint(obj, 'Scale', SCALE_LIMITS)
        hideLegacy(obj)

    def execute(self, obj):
        pass

    # the proxy has no state of its own to store in the document
    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class ViewProviderUniversalLight:
    displayMode = "UniversalLight"

    def __init__(self, vobj):
        vobj.Proxy = self

    # ------------------------------------------------------------------ setup
    def attach(self, vobj):
        from Gizmos.light_gizmo import LightGizmo
        self.ViewObject = vobj
        self.Object = vobj.Object

        self.coinLight = self.createLightInstance()
        self.gizmo = LightGizmo(self)
        try:
            from Gizmos import interaction
            interaction.watch_extent(vobj.Object.Document)    # place the icons around the model
        except Exception:
            pass

        self.root = coin.SoSeparator()
        self.root.addChild(self.gizmo.root)
        vobj.addDisplayMode(self.root, self.displayMode)

        self.updateAll()
        self.requestSync()

    def createLightInstance(self):
        raise NotImplementedError()

    def getDisplayModes(self, vobj):
        return [self.displayMode]

    def getDefaultDisplayMode(self):
        return self.displayMode

    def setDisplayMode(self, mode):
        return mode

    def attached(self):
        return getattr(self, 'coinLight', None) is not None

    def requestSync(self):
        from SceneFX import view_rig
        try:
            view_rig.schedule_sync(self.Object.Document)
        except ReferenceError:
            pass

    # ------------------------------------------------------- property -> scene
    GIZMO_PROPERTIES = ('Location', 'Direction', 'Target', 'CutOffAngle', 'Azimuth', 'Elevation',
                        'ShowManipulator')

    def updateData(self, obj, prop):
        if not self.attached():
            return
        if prop == 'Color':
            self.updateColor()
        elif prop == 'Intensity':
            self.updateIntensity()
        elif prop == 'Location':
            self.updateLocation()
        elif prop == 'Direction':
            self.updateDirection()
            self.lightMoved()
        elif prop == 'CutOffAngle':
            self.updateCutOffAngle()
        elif prop == 'DropOffRate':
            self.updateDropOffRate()
        elif prop == 'CastShadows':
            self.requestSync()
        if prop in self.GIZMO_PROPERTIES:
            self.gizmo.update()

    def onChanged(self, vobj, prop):
        if prop == 'Visibility' and self.attached():
            self.updateLightVisibility()
            self.lightMoved()

    def lightMoved(self):
        """The shadow catcher is drawn from the direction of the light."""
        from SceneFX import view_rig
        try:
            view_rig.light_moved(self.Object.Document)
        except ReferenceError:
            pass

    def updateAll(self):
        self.updateColor()
        self.updateIntensity()
        self.updateLocation()
        self.updateDirection()
        self.updateCutOffAngle()
        self.updateDropOffRate()
        self.updateLightVisibility()
        self.gizmo.update()

    def updateColor(self):
        color = self.Object.Color
        self.coinLight.color.setValue(coin.SbColor(color[0], color[1], color[2]))

    def updateIntensity(self):
        self.coinLight.intensity.setValue(float(self.Object.Intensity))

    def updateLocation(self):
        if hasattr(self.Object, 'Location'):
            loc = self.Object.Location
            self.coinLight.location.setValue(loc.x, loc.y, loc.z)

    def updateDirection(self):
        if not hasattr(self.Object, 'Direction'):
            return
        d = FreeCAD.Vector(self.Object.Direction)
        if d.Length < EPS:
            return   # a null direction is meaningless, keep the previous one
        d.normalize()
        self.coinLight.direction.setValue(coin.SbVec3f(d.x, d.y, d.z))

    def cutOffAngleRadians(self):
        value = self.Object.CutOffAngle
        degrees = float(getattr(value, 'Value', value))
        # Coin's cut-off angle is the half angle of the cone, at most 90 degrees
        return math.radians(min(max(degrees, 1.0), 90.0))

    def updateCutOffAngle(self):
        if hasattr(self.Object, 'CutOffAngle'):
            self.coinLight.cutOffAngle.setValue(self.cutOffAngleRadians())

    def updateDropOffRate(self):
        if hasattr(self.Object, 'DropOffRate'):
            self.coinLight.dropOffRate.setValue(min(max(float(self.Object.DropOffRate), 0.0), 1.0))

    def updateLightVisibility(self):
        self.coinLight.on.setValue(bool(self.ViewObject.Visibility))

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

    # ---------------------------------------------------------------- cleanup
    def onDelete(self, vobj, subelements):
        # The light node is taken out of the views by the next sync (and put
        # back by it if the deletion is undone).
        self.requestSync()
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def sceneExtent(doc):
    """(center, size) of what is shown, to give new lights a sensible place and gizmo size."""
    view = view_utils.first_view(doc)
    box = view_utils.scene_bound_box(view, doc) if view is not None else None
    if box is None:
        return FreeCAD.Vector(0, 0, 0), 0.0
    center = FreeCAD.Vector((box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2)
    size = FreeCAD.Vector(box[3] - box[0], box[4] - box[1], box[5] - box[2]).Length
    return center, size


def _show_gizmos():
    from Utils import prefs
    return prefs.get('ShowGizmos')


def addToScene(obj):
    """Put a new light in the scene configuration folder of its document."""
    import create_scene_config
    create_scene_config.getSceneFolder(obj.Document, create=True).addObject(obj)
