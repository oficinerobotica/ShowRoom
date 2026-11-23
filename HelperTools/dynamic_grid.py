# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""A reference grid that can follow the bottom of the scene.

With ``Dynamic`` on, the grid sits at the lowest point of what the 3D view
shows.  That point is measured on the scene graph of the view itself, which is
what makes it reliable:

* everything visible counts, whatever its type (solids, shells, meshes,
  sketches, links, ...), and nothing hidden does -- including objects hidden
  through their group, Part or Body;
* objects inside Parts, Bodies and Links are taken where they really are, not
  where their local placement says;
* the measure is taken a moment *after* a change, when the view has caught up
  with the document (a visibility change is not yet applied to the view while
  the document signals it).
"""
import FreeCAD
from pivy import coin

from Utils import view_utils
from Utils.resource_utils import iconPath

GRID_TYPE = 'DynamicGrid'
SIZE_LIMITS = (1, 10 ** 6, 5)
MAX_LINES = 2000            # per direction; more than this only freezes the view
UPDATE_DELAY_MS = 60
EPS = 1e-6

# properties of other objects whose change never moves the bottom of the scene
IGNORED_PROPERTIES = ('Label', 'Label2', 'ExpressionEngine', 'Proxy', '_GroupTouched')


def isGrid(obj):
    return getattr(getattr(obj, 'Proxy', None), 'type', None) == GRID_TYPE


class DynamicGrid:
    type = GRID_TYPE

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        pl = obj.PropertiesList
        if 'Placement' not in pl:
            obj.addProperty("App::PropertyPlacement", "Placement", "Base",
                            "Position and orientation of the grid")
        if 'Color' not in pl:
            obj.addProperty("App::PropertyColor", "Color", "Grid", "Grid color").Color = (0.5, 0.5, 0.5)
        if 'Size' not in pl:
            obj.addProperty("App::PropertyIntegerConstraint", "Size", "Grid",
                            "Length of the side of the grid").Size = (100,) + SIZE_LIMITS
        if 'Spacing' not in pl:
            obj.addProperty("App::PropertyIntegerConstraint", "Spacing", "Grid",
                            "Distance between the grid lines").Spacing = (10,) + SIZE_LIMITS
        if 'Dynamic' not in pl:
            obj.addProperty("App::PropertyBool", "Dynamic", "Grid",
                            "Keep the grid at the lowest point of the visible scene").Dynamic = True
        if 'ZOffset' not in pl:
            obj.addProperty("App::PropertyDistance", "ZOffset", "Grid",
                            "Dynamic grid: distance from the lowest point of the scene "
                            "(negative = below it)").ZOffset = 0.0
        if 'CenterOnScene' not in pl:
            obj.addProperty("App::PropertyBool", "CenterOnScene", "Grid",
                            "Dynamic grid: also keep the grid centered under the scene").CenterOnScene = False
        if 'GroundPlane' not in pl:
            obj.addProperty("App::PropertyBool", "GroundPlane", "Ground",
                            "Draw a solid plane under the grid. It receives the shadows "
                            "when shadows are enabled").GroundPlane = False
        if 'GroundColor' not in pl:
            obj.addProperty("App::PropertyColor", "GroundColor", "Ground",
                            "Color of the ground plane").GroundColor = (0.85, 0.85, 0.85)

    def onDocumentRestored(self, obj):
        self.setProperties(obj)
        for name in ('Size', 'Spacing'):
            try:
                setattr(obj, name, (getattr(obj, name),) + SIZE_LIMITS)
            except Exception:
                pass
        schedule_update(obj.Document)

    def execute(self, obj):
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class ViewProviderDynamicGrid:
    displayMode = "DynamicGrid"

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.ViewObject = vobj
        self.Object = vobj.Object

        self.transform = coin.SoTransform()
        self.grid_color = coin.SoBaseColor()
        self.ground_color = coin.SoMaterial()
        self.geometry = coin.SoSeparator()

        # The grid is a visual aid: it must not be picked instead of the model.
        # It does stay in the bounding box of the view: FreeCAD computes the
        # camera clipping planes from it, and leaving the grid out cut it off.
        holder = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        holder.addChild(pick)
        holder.addChild(self.transform)
        holder.addChild(self.geometry)

        self.root = coin.SoSeparator()
        self.root.addChild(holder)
        vobj.addDisplayMode(self.root, self.displayMode)

        self.rebuildGrid()
        self.updateColor()
        self.updateGridLocation()
        ensure_hooks()
        schedule_update(self.Object.Document)

    def attached(self):
        return getattr(self, 'geometry', None) is not None

    # ------------------------------------------------------------- geometry
    def gridExtent(self):
        """(half side, spacing): the lines run from -half to +half, a multiple of the spacing."""
        size = max(int(self.Object.Size), 1)
        spacing = max(int(self.Object.Spacing), 1)
        steps = max((size // 2) // spacing, 1)
        if steps > MAX_LINES // 2:
            FreeCAD.Console.PrintWarning(
                "ShowRoom: grid limited to %d lines per side, increase Spacing.\n" % MAX_LINES)
            steps = MAX_LINES // 2
        return steps, spacing

    def rebuildGrid(self):
        steps, spacing = self.gridExtent()
        half = steps * spacing
        self.geometry.removeAllChildren()

        # ground plane (lit, so that it can show the shadows), pushed back a
        # little so that the lines are not z-fighting with it
        self.ground_switch = coin.SoSwitch()
        ground = coin.SoSeparator()
        offset = coin.SoPolygonOffset()
        offset.factor = 2.0
        offset.units = 2.0
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE      # lit from both sides
        normal = coin.SoNormal()
        normal.vector.setValue(0, 0, 1)
        binding = coin.SoNormalBinding()
        binding.value = coin.SoNormalBinding.OVERALL
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 4, [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)])
        face = coin.SoFaceSet()
        face.numVertices.setValue(4)
        for node in (offset, hints, self.ground_color, normal, binding, coords, face):
            ground.addChild(node)
        self.ground_switch.addChild(ground)
        self.geometry.addChild(self.ground_switch)

        # lines keep their own color whatever the lighting of the scene
        lines = coin.SoSeparator()
        light_model = coin.SoLightModel()
        light_model.model = coin.SoLightModel.BASE_COLOR
        lines.addChild(light_model)

        points = []
        counts = []
        for i in range(-steps, steps + 1):
            if i == 0:
                continue      # the axes are drawn below, in their own colors
            v = i * spacing
            points += [(-half, v, 0), (half, v, 0), (v, -half, 0), (v, half, 0)]
            counts += [2, 2]
        if points:
            grid_coords = coin.SoCoordinate3()
            grid_coords.point.setValues(0, len(points), points)
            grid_lines = coin.SoLineSet()
            grid_lines.numVertices.setValues(0, len(counts), counts)
            lines.addChild(self.grid_color)
            lines.addChild(grid_coords)
            lines.addChild(grid_lines)

        style = coin.SoDrawStyle()
        style.lineWidth = 2
        lines.addChild(style)
        for color, ends in (((1, 0, 0), [(-half, 0, 0), (half, 0, 0)]),      # X axis: red
                            ((0, 1, 0), [(0, -half, 0), (0, half, 0)])):     # Y axis: green
            axis_color = coin.SoBaseColor()
            axis_color.rgb.setValue(*color)
            axis_coords = coin.SoCoordinate3()
            axis_coords.point.setValues(0, 2, ends)
            axis_line = coin.SoLineSet()
            axis_line.numVertices.setValue(2)
            for node in (axis_color, axis_coords, axis_line):
                lines.addChild(node)
        self.geometry.addChild(lines)
        self.updateGround()

    # -------------------------------------------------------------- updates
    def getDisplayModes(self, vobj):
        return [self.displayMode]

    def getDefaultDisplayMode(self):
        return self.displayMode

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if not self.attached():
            return
        if prop == 'Placement':
            self.updateGridLocation()
        elif prop in ('Color', 'GroundColor'):
            self.updateColor()
        elif prop in ('Size', 'Spacing'):
            self.rebuildGrid()
        elif prop == 'GroundPlane':
            self.updateGround()
        elif prop in ('Dynamic', 'ZOffset', 'CenterOnScene'):
            schedule_update(obj.Document)

    def onChanged(self, vobj, prop):
        pass    # visibility is handled by FreeCAD: the grid is a regular display mode

    def updateColor(self):
        c = self.Object.Color
        self.grid_color.rgb.setValue(c[0], c[1], c[2])
        # (a grid saved by an older version gets this property only once loading is over)
        g = getattr(self.Object, 'GroundColor', (0.85, 0.85, 0.85))
        self.ground_color.diffuseColor.setValue(g[0], g[1], g[2])
        self.ground_color.ambientColor.setValue(g[0] * 0.3, g[1] * 0.3, g[2] * 0.3)

    def updateGround(self):
        show = bool(getattr(self.Object, 'GroundPlane', False))
        self.ground_switch.whichChild.setValue(coin.SO_SWITCH_ALL if show else coin.SO_SWITCH_NONE)

    def updateGridLocation(self):
        placement = self.Object.Placement
        base = placement.Base
        q = placement.Rotation.Q
        self.transform.translation.setValue(base.x, base.y, base.z)
        self.transform.rotation.setValue(q[0], q[1], q[2], q[3])

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

    def onDelete(self, vobj, subelements):
        return True

    def getIcon(self):
        return iconPath('Grid.svg')

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


# ------------------------------------------------------------ dynamic placement
def place_grid(grid, box):
    """Move ``grid`` under the scene bounding box ``box``. Returns True if it moved."""
    if box is None:
        return False            # empty scene: stay where we are
    placement = grid.Placement
    base = FreeCAD.Vector(placement.Base)
    offset = getattr(grid, 'ZOffset', 0.0)
    base.z = box[2] + float(getattr(offset, 'Value', offset))
    if getattr(grid, 'CenterOnScene', False):
        base.x = (box[0] + box[3]) / 2.0
        base.y = (box[1] + box[4]) / 2.0
    scale = max(1.0, abs(base.x), abs(base.y), abs(base.z))
    if base.isEqual(placement.Base, EPS * scale):
        return False
    grid.Placement = FreeCAD.Placement(base, placement.Rotation)
    return True


def update_document(doc):
    """Re-place the dynamic grids of ``doc`` under what its 3D view shows now."""
    try:
        grids = [o for o in doc.Objects if isGrid(o) and getattr(o, 'Dynamic', False)]
    except ReferenceError:
        return
    if not grids:
        return
    view = view_utils.first_view(doc)
    if view is None:
        return
    box = view_utils.scene_bound_box(view, doc)
    for grid in grids:
        place_grid(grid, box)


_pending = set()
_timer = None
_bridge = None
_observer = None


def _run_pending():
    names = list(_pending)
    _pending.clear()
    documents = FreeCAD.listDocuments()
    for name in names:
        doc = documents.get(name)
        if doc is not None:
            try:
                update_document(doc)
            except Exception as error:
                FreeCAD.Console.PrintError("ShowRoom: grid update failed: %s\n" % error)


def schedule_update(doc):
    """Re-place the grids of ``doc`` shortly; many calls in a row cost one update."""
    if not FreeCAD.GuiUp or doc is None:
        return
    ensure_hooks()
    try:
        _pending.add(doc.Name)
    except ReferenceError:
        return
    _bridge.wake.emit()


class _SceneObserver:
    """Whatever may change the extent of the scene re-places the grids."""

    def _touch(self, obj):
        try:
            if isGrid(obj):
                return
            schedule_update(obj.Document)
        except ReferenceError:
            pass

    def slotCreatedObject(self, obj):
        self._touch(obj)

    def slotDeletedObject(self, obj):
        self._touch(obj)

    def slotChangedObject(self, obj, prop):
        if prop not in IGNORED_PROPERTIES:
            self._touch(obj)

    def slotRecomputedDocument(self, doc):
        schedule_update(doc)

    def slotUndoDocument(self, doc):
        schedule_update(doc)

    def slotRedoDocument(self, doc):
        schedule_update(doc)

    def slotFinishRestoreDocument(self, doc):
        schedule_update(doc)

    # The thumbnail saved in the file is a picture of the view: no grid in it.
    def slotStartSaveDocument(self, doc, filename):
        self._hidden = []
        for obj in doc.Objects:
            try:
                sw = obj.ViewObject.SwitchNode if isGrid(obj) and obj.ViewObject else None
            except Exception:
                sw = None
            if sw is not None and sw.whichChild.getValue() >= 0:
                self._hidden.append((sw, sw.whichChild.getValue()))
                sw.whichChild.setValue(-1)

    def slotFinishSaveDocument(self, doc, filename):
        for sw, child in getattr(self, '_hidden', []):
            try:
                sw.whichChild.setValue(child)
            except Exception:
                pass
        self._hidden = []


def ensure_hooks():
    global _timer, _bridge, _observer
    if _bridge is not None or not FreeCAD.GuiUp:
        return
    import FreeCADGui
    from PySide import QtCore

    class Bridge(QtCore.QObject):
        wake = QtCore.Signal()

    _bridge = Bridge(FreeCADGui.getMainWindow())
    _timer = QtCore.QTimer(_bridge)
    _timer.setSingleShot(True)
    _timer.setInterval(UPDATE_DELAY_MS)
    _timer.timeout.connect(_run_pending)
    # restarting the timer on every change is what debounces the updates; the
    # signal makes it safe to be told about changes from a recompute thread
    _bridge.wake.connect(_timer.start)

    _observer = _SceneObserver()
    FreeCAD.addDocumentObserver(_observer)


def createDynamicGrid(doc=None):
    import create_scene_config
    doc = doc or FreeCAD.ActiveDocument
    obj = doc.addObject("App::FeaturePython", "DynamicGrid")
    DynamicGrid(obj)
    if FreeCAD.GuiUp:
        ViewProviderDynamicGrid(obj.ViewObject)
    create_scene_config.getSceneFolder(doc, create=True).addObject(obj)
    return obj


if __name__ == "__main__":
    createDynamicGrid()
