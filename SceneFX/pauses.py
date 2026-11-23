# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""When the viewport effects step aside for FreeCAD's own tools.

Two kinds of pause, each for a reason found on real GPUs:

* **Sketch pause** (``navigation._editing``): real-time shadows and ambient
  occlusion leave the scene while a sketch is being created, selected or
  edited, and while "Create sketch"'s plane choice or an attachment panel is
  open.  Coin's shadow pass crashes on the nodes Sketcher adds and removes,
  and ambient occlusion makes the origin planes impossible to pick.
* **Feature panel** (``feature_panel()``): while another workbench's task
  panel is open (Pad, Pocket, Thickness...) its preview is in the scene.  The
  shadow catcher, which redraws the model into a texture, turns the whole view
  black on some drivers when it meets that preview, so it waits; and the
  model's bound box is not measured again (view_rig.model_box), so switching
  the preview on and off does not change the brightness of the view.

view_rig calls ``install`` once with a function that brings every document
in line, and ``poll`` from its watch timer.
"""
import FreeCAD

from SceneFX import navigation

PICK_PANELS = ('TaskFeaturePick', 'TaskAttacher')
RESUME_CHECK_MS = 500

_resync = None          # view_rig.resync_all
_timer = None           # checks when the sketch pause can end
_observers = None
_feature_open = False   # feature_panel() at the last poll


# --------------------------------------------------------------------- tests
def is_sketch(obj):
    try:
        return obj.isDerivedFrom('Sketcher::SketchObject')
    except Exception:
        return False


def feature_panel():
    """A task panel that is not one of ShowRoom's is open."""
    import FreeCADGui
    try:
        if not FreeCADGui.Control.activeDialog():
            return False
        from dtpanels import bridge
        return bridge.current() is None
    except Exception:
        return False


def pick_panel():
    """"Create sketch"'s plane choice or an attachment panel is on screen."""
    import FreeCADGui
    if not FreeCADGui.Control.activeDialog():
        return False
    try:
        from PySide import QtWidgets
        for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
            if w.metaObject().className().split('::')[-1] in PICK_PANELS and w.isVisible():
                return True
    except Exception:
        pass
    return False


def sketch_busy():
    """A sketch is in edit or selected, or a pick panel is open."""
    import FreeCADGui
    try:
        for name in FreeCAD.listDocuments():
            gdoc = FreeCADGui.getDocument(name)
            vp = gdoc.getInEdit() if gdoc is not None else None
            if vp is not None and is_sketch(getattr(vp, 'Object', None)):
                return True
        if pick_panel():
            return True
        return any(is_sketch(o) for o in FreeCADGui.Selection.getSelection())
    except Exception:
        return False


# -------------------------------------------------------------- sketch pause
def pause():
    """Start the sketch pause right away, then check regularly when it can end."""
    global _timer
    if not navigation._editing:
        navigation.editing(True)
        _bring_in_line()
    if _timer is None:
        from PySide import QtCore
        import FreeCADGui
        _timer = QtCore.QTimer(FreeCADGui.getMainWindow())
        _timer.setInterval(RESUME_CHECK_MS)
        _timer.timeout.connect(_resume_if_idle)
    _timer.start()


def _resume_if_idle():
    if not sketch_busy():
        _timer.stop()
        navigation.editing(False)
        _bring_in_line()


def _bring_in_line():
    if _resync is not None:
        _resync()


def created(obj):
    """A new object: a sketch pauses before Sketcher opens it for editing."""
    if is_sketch(obj):
        pause()


def poll():
    """From view_rig's watch timer: task panels opening and closing."""
    global _feature_open
    if not navigation._editing and pick_panel():
        pause()
    now = feature_panel()
    if now != _feature_open:
        _feature_open = now
        _bring_in_line()


# ------------------------------------------------------------------ observers
class _EditObserver:
    """Edit mode starts and ends. Never add slotChangedObject here: see textures.py."""

    def slotInEdit(self, vobj):
        if is_sketch(getattr(vobj, 'Object', None)):
            pause()

    def slotResetEdit(self, vobj):
        pause()                 # ends at the next check if nothing else holds it


class _SketchSelection:
    def _check(self, *args):
        import FreeCADGui
        if any(is_sketch(o) for o in FreeCADGui.Selection.getSelection()):
            pause()

    addSelection = setSelection = _check


def install(resync):
    global _resync, _observers
    _resync = resync
    if _observers is None:
        import FreeCADGui
        _observers = (_EditObserver(), _SketchSelection())
        FreeCADGui.addDocumentObserver(_observers[0])
        FreeCADGui.Selection.addObserver(_observers[1])
