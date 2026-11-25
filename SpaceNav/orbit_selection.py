# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""SpaceMouse: rotate around the selection.

FreeCAD's built-in SpaceMouse support rotates the view around the centre of
the window (with the "Window center" rotation mode), or around the point the
last mouse drag started from, or around the whole scene.  None of these is the
selection, and Python cannot set FreeCAD's rotation centre.  So the rotation is
corrected after the fact:

* When something is selected the active view slides (sideways only, in a
  quarter of a second) until the selection is in its middle, and the focal
  point is put at the selection's depth.
* While something is selected the SpaceMouse's sideways and up/down axes
  are switched off in FreeCAD's own SpaceMouse settings (Spaceball Motion):
  the selection stays in the middle, only rotating and zooming are left.
  With nothing selected (or in a sketch) they are on as usual.
* An immediate sensor on the camera of the active 3D view sees every move
  of the camera.  FreeCAD rotated it around the focal point (the centre of
  the window); the camera is moved so that the centre of the selection is
  what stays still, and any sideways movement is taken out.  Moves made while
  a mouse button is down (mouse orbit, pan, the navigation cube) are left
  alone.

The correction is exact only when FreeCAD rotates around the focal point, i.e.
with Preferences > Display > Navigation > Rotation mode = "Window center".
While the option is on that mode is set (and the previous one given back when
it is switched off); if the mode is changed by hand meanwhile, nothing is
corrected.

With the official 3Dconnexion driver (NavLib, Windows and macOS) the driver
rotates around its own pivot, which this does not change; the driver has its
own "rotate around selection" setting.
"""
import FreeCAD
from pivy import coin

from Utils import view_utils

PREFS = "User parameter:BaseApp/Preferences/Mod/ShowRoom"
VIEW_PREFS = "User parameter:BaseApp/Preferences/View"
PARAM = "SpaceMouseOrbitSelection"
SAVED_MODE = "SpaceMouseOrbitPreviousRotationMode"
WINDOW_CENTER = 0
CENTER_PARAM = "SpaceMouseCenterSelection"
LOCK_PAN_PARAM = "SpaceMouseLockPan"
MOTION_PREFS = "User parameter:BaseApp/Spaceball/Motion"
ALL_AXES = ("PanLREnable", "PanUDEnable", "ZoomEnable")
SAVED_PREFIX = "SpaceMouseOrbitPrevious"
MIN_DEPTH = 1.0                 # mm: closest the camera gets to the selection
CENTER_MS = 250                 # how long the view takes to centre the selection

_service = None


# ------------------------------------------------------------------ settings
def isOn():
    return FreeCAD.ParamGet(PREFS).GetBool(PARAM, False)


def centers():
    """Option: selecting something brings it to the middle of the view."""
    return FreeCAD.ParamGet(PREFS).GetBool(CENTER_PARAM, True)


def locks_pan():
    """Option: no SpaceMouse panning while rotating around the selection."""
    return FreeCAD.ParamGet(PREFS).GetBool(LOCK_PAN_PARAM, True)


def setOn(on):
    FreeCAD.ParamGet(PREFS).SetBool(PARAM, bool(on))
    apply_prefs()


def apply_prefs():
    """Bring everything in line with the settings (toggle or settings panel)."""
    if isOn():
        _force_window_center()
        _start()
    else:
        _stop()
        _restore_rotation_mode()
    update_pan()


def install():
    """Called at startup: bring the option back if it was left on, and give
    back anything a crash left switched off."""
    apply_prefs()


def update_pan():
    """Pan axes off only while rotating around something that is selected."""
    _restore_pan()          # first: the right axes, should "Flip Y/Z" have changed
    if _service is not None and locks_pan() and not _editing_sketch() \
            and _service.current_pivot() is not None:
        _disable_pan()


def _disable_pan():
    """Switch off the SpaceMouse's sideways and up/down axes (zoom stays).

    FreeCAD reads these settings (Tools > Customize > Spaceball Motion) at
    every motion event, so the cap's push sideways is simply dropped.  The
    previous values are kept to give them back (_restore_pan).
    """
    motion = FreeCAD.ParamGet(MOTION_PREFS)
    saved = FreeCAD.ParamGet(PREFS)
    for name in _pan_axes(motion):
        key = SAVED_PREFIX + name
        if saved.GetInt(key, -1) < 0:
            saved.SetInt(key, int(motion.GetBool(name, True)))
        motion.SetBool(name, False)


def _pan_axes(motion):
    """The settings that switch off the view's left/right and up/down moves.

    With "Flip Y/Z" FreeCAD swaps the settings along with the axes: the one
    called "Zoom" then governs up/down and "Pan up/down" governs the zoom.
    """
    if motion.GetBool("FlipYZ", False):
        return ("PanLREnable", "ZoomEnable")
    return ("PanLREnable", "PanUDEnable")


def _restore_pan():
    motion = FreeCAD.ParamGet(MOTION_PREFS)
    saved = FreeCAD.ParamGet(PREFS)
    for name in ALL_AXES:
        key = SAVED_PREFIX + name
        value = saved.GetInt(key, -1)
        if value >= 0:
            motion.SetBool(name, bool(value))
            saved.RemInt(key)


def _rotation_mode():
    return FreeCAD.ParamGet(VIEW_PREFS).GetInt("RotationMode", WINDOW_CENTER)


def _force_window_center():
    mode = _rotation_mode()
    if mode != WINDOW_CENTER:
        FreeCAD.ParamGet(PREFS).SetInt(SAVED_MODE, mode)
        FreeCAD.ParamGet(VIEW_PREFS).SetInt("RotationMode", WINDOW_CENTER)
        FreeCAD.Console.PrintMessage(
            "ShowRoom: rotate around selection needs the rotation mode \"Window center\"; "
            "the previous mode comes back when the option is switched off.\n")


def _restore_rotation_mode():
    group = FreeCAD.ParamGet(PREFS)
    saved = group.GetInt(SAVED_MODE, -1)
    if saved >= 0:
        if _rotation_mode() == WINDOW_CENTER:
            FreeCAD.ParamGet(VIEW_PREFS).SetInt("RotationMode", saved)
        group.RemInt(SAVED_MODE)


def _start():
    global _service
    if _service is None:
        try:
            _service = _Service()
        except Exception as error:
            _service = None
            FreeCAD.Console.PrintWarning("ShowRoom: rotate around selection: %s\n" % error)
            return
    _service.watch_active_view()


def _stop():
    global _service
    if _service is not None:
        _service.close()
        _service = None


def _editing_sketch():
    """A sketch is open for editing: the sketcher has its own view, leave it alone."""
    from SpaceNav import sketch_lock
    return sketch_lock.editing_sketch()


# ------------------------------------------------------------------ pivot
def _shape_box(obj, sub):
    """Global bounding box of a selected object or sub-element (None if no shape)."""
    try:
        import Part
        shape = Part.getShape(obj, sub, needSubElement=True)
    except Exception:
        return None
    if shape is None or shape.isNull():
        return None
    box = shape.BoundBox
    return box if box.isValid() else None


def selection_center():
    """Centre of the bounding box of what is selected, as a SbVec3f (None: nothing)."""
    import FreeCADGui
    box = None
    points = []
    for sel in FreeCADGui.Selection.getSelectionEx('', 0):
        found = False
        for sub in (sel.SubElementNames or ('',)):
            b = _shape_box(sel.Object, sub)
            if b is None:
                continue
            found = True
            if box is None:
                box = FreeCAD.BoundBox(b)
            else:
                box.add(b)
        if not found:
            points += list(sel.PickedPoints)
    for p in points:
        if box is None:
            box = FreeCAD.BoundBox(p, p)
        else:
            box.add(p)
    if box is None:
        return None
    c = box.Center
    return coin.SbVec3f(c.x, c.y, c.z)


# ------------------------------------------------------------------ service
class _SelectionObserver:
    def __init__(self, service):
        self.service = service

    def addSelection(self, doc, obj, sub, pos):
        self.service.selection_changed()

    def removeSelection(self, doc, obj, sub):
        self.service.selection_changed()

    def setSelection(self, doc):
        self.service.selection_changed()

    def clearSelection(self, doc):
        self.service.selection_changed()


def _pose(camera):
    return (coin.SbVec3f(*camera.position.getValue().getValue()),
            coin.SbRotation(*camera.orientation.getValue().getValue()),
            camera.focalDistance.getValue())


class _Service:
    def __init__(self):
        import FreeCADGui
        from PySide import QtCore, QtWidgets
        self.QtWidgets = QtWidgets
        self.pivot = None
        self.pivot_dirty = True
        self.camera = None
        self.pose = None            # camera pose after the last move we saw
        self.busy = False
        self.sensor = coin.SoNodeSensor(self._camera_changed, None)
        self.sensor.setPriority(0)  # immediate: right after the camera moved
        self.slide = None
        self.slide_clock = QtCore.QElapsedTimer()
        self.slide_timer = QtCore.QTimer()
        self.slide_timer.setInterval(15)
        self.slide_timer.timeout.connect(self._slide_step)
        self.settle_timer = QtCore.QTimer()
        self.settle_timer.setSingleShot(True)
        self.settle_timer.setInterval(0)
        self.settle_timer.timeout.connect(self._selection_settled)
        self.observer = _SelectionObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        self.mdi = None
        try:
            self.mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
            if self.mdi is not None:
                self.mdi.subWindowActivated.connect(self._view_activated)
        except Exception:
            self.mdi = None

    def close(self):
        import FreeCADGui
        self.settle_timer.stop()
        self.slide_timer.stop()
        self.slide = None
        self.sensor.detach()
        self.camera = None
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        if self.mdi is not None:
            try:
                self.mdi.subWindowActivated.disconnect(self._view_activated)
            except Exception:
                pass

    # -------------------------------------------------------------- views
    def _view_activated(self, *args):
        self.watch_active_view()

    def _active_view(self):
        import FreeCADGui
        try:
            view = FreeCADGui.ActiveDocument.ActiveView
            if view.getCameraNode() is not None:
                return view
        except Exception:
            pass
        return None

    def watch_active_view(self):
        """Keep the sensor on the camera of the active 3D view."""
        view = self._active_view()
        camera = view.getCameraNode() if view is not None else None
        if view_utils.same_node(camera, self.camera):
            return camera
        self.sensor.detach()
        self.camera = camera
        self.pose = None
        if camera is not None:
            self.pose = _pose(camera)
            self.sensor.attach(camera)
        return camera

    # -------------------------------------------------------------- pivot
    def selection_changed(self):
        self.pivot_dirty = True
        # several notifications come for one click: act once, afterwards
        self.settle_timer.start()

    def _selection_settled(self):
        update_pan()
        if centers() and not _editing_sketch():
            self._center_selection()

    def current_pivot(self):
        if self.pivot_dirty:
            try:
                self.pivot = selection_center()
            except Exception as error:
                FreeCAD.Console.PrintLog("ShowRoom: selection centre: %s\n" % error)
                self.pivot = None
            self.pivot_dirty = False
        return self.pivot

    # ------------------------------------------------------------ centring
    def _center_selection(self):
        """Slide the active view so that the selection is in the middle of it."""
        camera = self.watch_active_view()
        pivot = self.current_pivot()
        if pivot is None or camera is None:
            return
        direction = camera.orientation.getValue().multVec(coin.SbVec3f(0, 0, -1))
        to_pivot = pivot - camera.position.getValue()
        depth = to_pivot.dot(direction)
        if depth < MIN_DEPTH:
            return          # behind the camera or too close: leave the view alone
        self._move(camera, None, depth)
        # the sideways part only: the distance to the model does not change
        self.slide = (camera, to_pivot - direction * depth, 0.0)
        self.slide_clock.restart()
        self.slide_timer.start()

    def _slide_step(self):
        if self.slide is None:
            self.slide_timer.stop()
            return
        camera, shift, done = self.slide
        t = min(self.slide_clock.elapsed() / float(CENTER_MS), 1.0)
        eased = 1.0 - (1.0 - t) ** 3
        try:
            # small steps added to wherever the camera is: a SpaceMouse
            # moving it at the same time is not fought against
            self._move(camera, camera.position.getValue() + shift * (eased - done), None)
        except Exception:
            t = 1.0
        self.slide = None if t >= 1.0 else (camera, shift, eased)

    def _move(self, camera, position, focal_distance):
        """Change the camera without reacting to it ourselves."""
        self.busy = True
        try:
            if position is not None:
                camera.position.setValue(position)
            if focal_distance is not None:
                camera.focalDistance.setValue(focal_distance)
        finally:
            self.busy = False
        if view_utils.same_node(camera, self.camera):
            self.pose = _pose(camera)

    # -------------------------------------------------------------- motion
    def _mouse_down(self):
        buttons = self.QtWidgets.QApplication.mouseButtons()
        try:
            return int(buttons) != 0
        except TypeError:           # PySide6 flags without int()
            return bool(buttons)

    def _camera_changed(self, data, sensor):
        if self.busy:
            return
        camera = self.camera
        if camera is None:
            return
        previous, self.pose = self.pose, _pose(camera)
        if previous is None or self.slide is not None:
            return
        p0, r0, fd0 = previous
        p1, r1, _fd1 = self.pose
        if p1.equals(p0, 1e-9) and r1.equals(r0, 1e-9):
            return          # clipping planes and the like: not a move
        if _rotation_mode() != WINDOW_CENTER or self._mouse_down() or _editing_sketch():
            return
        pivot = self.current_pivot()
        if pivot is None:
            return
        new_position = coin.SbVec3f(*p1.getValue())
        if not r1.equals(r0, 1e-9):
            # FreeCAD kept the old focal point C still; keep the pivot P still
            # instead: p' = p1 + (P - C) - M (P - C), M = rotation r0 -> r1
            focal = p0 + r0.multVec(coin.SbVec3f(0, 0, -1)) * fd0
            offset = pivot - focal
            turned = r1.multVec(r0.inverse().multVec(offset))
            new_position = new_position + offset - turned
        direction = r1.multVec(coin.SbVec3f(0, 0, -1))
        depth = (pivot - new_position).dot(direction)
        if not locks_pan():
            self._move(camera, new_position, depth if depth > MIN_DEPTH else None)
            return
        if depth < MIN_DEPTH:
            depth = MIN_DEPTH   # zooming in stops just short of the selection
        # no sideways or up/down movement: the selection stays in the middle of
        # the view, only the distance to it (the zoom) is left to the SpaceMouse
        self._move(camera, pivot - direction * depth, depth)
