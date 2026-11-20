# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Floating panel over the 3D view for the selected light.

When exactly one light is selected, a small QML card appears in the top right
corner of the 3D view (under the navigation cube) with the essentials of that
light: intensity, colour, shadows, cone or sun position, quick actions.
"All options…" opens the full task panel.

* pin: the card stays, showing the last light, when the selection changes;
* close: hides it until another light is selected;
* it steps aside while a task panel is open.

Edits made in the card are grouped into one undo step per burst of changes
(a slider drag is one step).  Preference ``InViewPanel`` (bool, default true)
in Mod/ShowRoom switches the card off; without Qt Quick there is none.
"""
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from dtpanels import QML, models
from dtpanels.bridge import Bridge, PREFS, QtQuickWidgets, edit, quick_usable

WIDTH = 330
TOP = 150           # below the navigation cube
MARGIN = 14
COMMIT_MS = 700


# ------------------------------------------------------------------------ model
class QuickLightModel(models.LightModel):
    """The essentials of a light, for the floating card."""
    transaction = 'Edit light'

    def params(self):
        o = self.obj
        P = models.prop
        ps = [P(o, 'Intensity', 'Intensity', 'number', 'Light', min=0, max=1, step=0.05,
                hardMin=0, hardMax=1),
              P(o, 'Color', 'Color', 'color', 'Light', presets=models.LIGHT_COLORS)]
        if hasattr(o, 'CastShadows'):
            ps.append(P(o, 'CastShadows', 'Casts shadows', 'bool', 'Light'))
        if self.kind == 'SpotLight':
            ps += [P(o, 'CutOffAngle', 'Cone half angle', 'number', 'Cone', min=1, max=90, step=1,
                     unit='°', decimals=0, hardMin=1, hardMax=89),
                   P(o, 'DropOffRate', 'Soft edge', 'number', 'Cone', min=0, max=1, step=0.05,
                     hardMin=0, hardMax=1)]
        elif self.kind == 'DirectionalLight':
            ps = [P(o, 'Azimuth', 'Comes from', 'compass', 'Position'),
                  P(o, 'Elevation', 'Height above horizon', 'number', 'Position', min=0, max=90,
                    step=1, unit='°', decimals=0, hardMin=-90, hardMax=90)] + ps
        else:
            def get_h():
                return round(o.Location.z - models.scene_extent(self.doc)[2], 1)

            def set_h(value):
                v = App.Vector(o.Location)
                v.z = models.scene_extent(self.doc)[2] + float(value)
                o.Location = v
            ps.append(models.param('Height', 'Height over the model', 'number', 'Position', get_h,
                                   set_h, min=0, max=max(200, models.nice(get_h() * 2)), step=1,
                                   unit='mm', decimals=0))
        return ps

    def info(self):
        return []

    def subtitle(self):
        o = self.obj
        if not hasattr(o, 'CastShadows'):
            return '%s · no shadows' % o.Label
        return '%s · %s' % (o.Label, 'casts shadows' if o.CastShadows else 'no shadows')

    def actions(self):
        if self.kind == 'SpotLight':
            return [dict(name='aim', label='Aim at the model', primary=True),
                    dict(name='view', label='From the view')]
        if self.kind == 'DirectionalLight':
            return [dict(name='view', label='From the view', primary=True),
                    dict(name='morning', label='Morning'), dict(name='noon', label='Noon'),
                    dict(name='evening', label='Evening')]
        return [dict(name='above', label='Above the model', primary=True),
                dict(name='camera', label='At the camera')]

    def hint(self):
        return 'Double click for every option'

    def trigger(self, name):
        o = self.obj
        if name == 'full':
            return ('edit', o)
        if name in self.SUN:
            return super().trigger(name)
        center, size, _ = models.scene_extent(self.doc)
        if name == 'above':
            o.Location = center + App.Vector(0, 0, max(size, 10.0) * 0.9)
            return None
        if name == 'camera':
            view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
            cam = view.getCameraNode().position.getValue() if hasattr(view, 'getCameraNode') else None
            if cam is not None:
                o.Location = App.Vector(cam[0], cam[1], cam[2])
            return None
        return super().trigger(name)


# ----------------------------------------------------------------------- bridge
class OverlayBridge(Bridge):
    pinnedChanged = QtCore.Signal()

    def __init__(self, model, manager):
        self.manager = manager
        self._txn = False
        super().__init__(model)
        self._commit = QtCore.QTimer(self)
        self._commit.setSingleShot(True)
        self._commit.setInterval(COMMIT_MS)
        self._commit.timeout.connect(self.commit)

    def _begin(self):
        """Group a burst of edits into one undo step (none while a task panel holds one)."""
        if Gui.Control.activeDialog():
            return
        if not self._txn:
            self.model.doc.openTransaction(self.model.transaction)
            self._txn = True
        self._commit.start()

    def commit(self):
        if self._txn:
            self._txn = False
            try:
                self.model.doc.commitTransaction()
            except Exception:
                pass

    @QtCore.Slot(str, "QVariant")
    def setValue(self, name, value):
        if self.alive():
            self._begin()
        super().setValue(name, value)

    @QtCore.Slot(str)
    def trigger(self, action):
        if action != 'full' and self.alive():
            self._begin()
        super().trigger(action)

    pinned = QtCore.Property(bool, lambda self: self.manager.pinned, notify=pinnedChanged)

    @QtCore.Slot()
    def togglePin(self):
        self.manager.pinned = not self.manager.pinned
        self.pinnedChanged.emit()

    @QtCore.Slot()
    def close(self):
        self.manager.dismiss()

    def stop(self):
        self.commit()
        super().stop()


# ---------------------------------------------------------------------- manager
class _Manager:
    def __init__(self):
        self.view_widget = None
        self.quick = None
        self.bridge = None
        self.obj_key = None
        self.pinned = False
        self.dismissed = None
        self.timer = QtCore.QTimer()
        self.timer.setInterval(400)
        self.timer.timeout.connect(self._watch)

    # ---------------------------------------------------------------- show/hide
    def enabled(self):
        return App.ParamGet(PREFS).GetBool("InViewPanel", True) and quick_usable()

    def selection_changed(self):
        if not self.enabled():
            self.hide()
            return
        light = None
        try:
            sel = Gui.Selection.getSelection()
        except Exception:
            sel = []
        if len(sel) == 1 and getattr(getattr(sel[0], 'Proxy', None), 'isDisplayToolsLight', False):
            light = sel[0]
        if light is None:
            self.dismissed = None
            if not self.pinned:
                self.hide()
            return
        key = (light.Document.Name, light.Name)
        if key == self.dismissed:
            return
        if key != self.obj_key or self.quick is None:
            self.show(light)

    def dismiss(self):
        self.dismissed = self.obj_key
        self.pinned = False
        QtCore.QTimer.singleShot(0, self.hide)

    def _host(self, doc):
        view = None
        try:
            gdoc = Gui.getDocument(doc.Name)
            active = gdoc.ActiveView
            if hasattr(active, 'graphicsView'):
                view = active
        except Exception:
            pass
        if view is None:
            from Utils import view_utils
            view = view_utils.first_view(doc)
        return view

    def show(self, light):
        self.hide()
        if Gui.Control.activeDialog():
            return
        view = self._host(light.Document)
        if view is None:
            return
        host = view.graphicsView()
        bridge = OverlayBridge(QuickLightModel(light), self)
        quick = QtQuickWidgets.QQuickWidget(host)
        quick.setAttribute(QtCore.Qt.WA_AlwaysStackOnTop, True)
        quick.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        quick.setClearColor(QtCore.Qt.transparent)
        quick.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
        quick.rootContext().setContextProperty("bridge", bridge)
        quick.setSource(QtCore.QUrl.fromLocalFile(os.path.join(QML, "OverlayPanel.qml")))
        if quick.status() != QtQuickWidgets.QQuickWidget.Ready:
            for err in quick.errors():
                App.Console.PrintWarning("ShowRoom QML: %s\n" % err.toString())
            bridge.stop()
            quick.deleteLater()
            return
        bridge.setParent(quick)
        bridge.handOver.connect(self._hand_over)
        bridge.heightChanged.connect(lambda h: QtCore.QTimer.singleShot(0, lambda: self._place(h)))
        self.quick, self.bridge, self.view_widget = quick, bridge, host
        self.obj_key = (light.Document.Name, light.Name)
        self._height = int(quick.rootObject().property("contentHeight") or 300)
        self._filter = _ResizeFilter(self, host)
        host.installEventFilter(self._filter)
        self._place(self._height)
        quick.show()
        quick.raise_()
        self.timer.start()

    def _place(self, height=None):
        if self.quick is None:
            return
        if height is not None:
            self._height = int(height) + 2
        host = self.view_widget
        s = self.bridge.theme.get("s", 1.0) if self.bridge else 1.0
        w = int(WIDTH * s)
        h = min(self._height, max(host.height() - TOP - MARGIN, 120))
        self.quick.setGeometry(max(host.width() - w - MARGIN, 0), TOP, w, h)

    def hide(self):
        self.timer.stop()
        quick, bridge = self.quick, self.bridge
        self.quick = self.bridge = None
        self.obj_key = None
        if bridge is not None:
            bridge.stop()
        if quick is not None:
            try:
                self.view_widget.removeEventFilter(self._filter)
            except Exception:
                pass
            quick.hide()
            quick.deleteLater()
        self.view_widget = None

    def _hand_over(self, result):
        if result and result[0] == 'edit':
            obj = result[1]
            self.hide()
            QtCore.QTimer.singleShot(0, lambda: edit(obj))

    def _watch(self):
        """Step aside for task panels; disappear with the light or its view."""
        if self.quick is None:
            self.timer.stop()
            return
        if Gui.Control.activeDialog() or self.bridge is None or not self.bridge.alive():
            self.hide()
            return
        try:
            self.view_widget.isVisible()
        except RuntimeError:            # the view was closed
            self.quick = None
            self.hide()

    def current(self):
        return self.bridge


class _ResizeFilter(QtCore.QObject):
    def __init__(self, manager, parent):
        super().__init__(parent)
        self.manager = manager

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0, self.manager._place)
        return False


_manager = None


class _SelectionObserver:
    def _changed(self, *args):
        QtCore.QTimer.singleShot(0, manager().selection_changed)

    addSelection = removeSelection = setSelection = _changed

    def clearSelection(self, *args):
        manager().dismissed = None          # a closed card comes back on the next selection
        self._changed()


_observer = None


def manager():
    global _manager
    if _manager is None:
        _manager = _Manager()
    return _manager


def install():
    """Start following the selection (once)."""
    global _observer
    if _observer is not None or not App.GuiUp:
        return
    _observer = _SelectionObserver()
    Gui.Selection.addObserver(_observer)
