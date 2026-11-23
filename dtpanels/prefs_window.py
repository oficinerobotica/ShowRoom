# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""ShowRoom's preferences in a floating QML window (sections on the right),
modelled on FreeCAD's own Preferences dialog.  Same model as the task panel
(models.SettingsModel); nothing is saved before Apply or OK."""
import base64
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from dtpanels import bridge as B

# section icons: stroke paths on a 24 px grid
ICONS = {
    'Startup': 'M5 12h14M13 6l6 6-6 6',
    'New documents': 'M7 3h7l4 4v14H7zM14 3v4h4',
    'Default scene': 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5',
    '3D view': 'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12zM12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z',
    'Panels': 'M4 4h16v16H4zM4 9h16M9 9v11',
    'Properties panel': 'M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M14 4v4M8 10v4M16 16v4',
    'Textures': 'M4 4h7v7H4zM13 13h7v7h-7zM13 4h7v7h-7zM4 13h7v7H4z',
    'Maintenance': 'M14.5 5.5a4 4 0 0 0-5 5L4 16v4h4l5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5z',
}
HINTS = {
    'Startup': 'What happens when FreeCAD starts',
    'New documents': 'The scene every new file gets',
    'Default scene': 'Shadows and ambient occlusion of a new scene',
    '3D view': 'Gizmos and navigation',
    'Panels': 'How the ShowRoom panels look',
    'Properties panel': 'The floating Data / View / Task panel',
    'Textures': 'Images on shapes',
    'Maintenance': 'Export, factory defaults',
}

_window = None


def _icon_url(path, color):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="48" height="48" fill="none" '
           'stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="%s"/></svg>'
           % (color, path))
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()


class PrefsBridge(B.Bridge):
    currentChanged = QtCore.Signal()
    pendingChanged = QtCore.Signal()

    def __init__(self, model, window):
        super().__init__(model)
        self._current = 'Default scene'
        self.window = window
        t = self._theme
        self._icons = {k: dict(normal=_icon_url(v, t['muted']), active=_icon_url(v, t['accent']))
                       for k, v in ICONS.items()}

    current = QtCore.Property(str, lambda self: self._current, notify=currentChanged)
    icons = QtCore.Property("QVariant", lambda self: self._icons, constant=True)
    hints = QtCore.Property("QVariant", lambda self: HINTS, constant=True)

    def _pending(self):
        m = self.model
        return sum(1 for k, v in m.values.items() if v != m.prefs.get(k))
    pending = QtCore.Property(int, _pending, notify=pendingChanged)

    def refresh(self):
        super().refresh()
        self.pendingChanged.emit()

    @QtCore.Slot(str, "QVariant")
    def setValue(self, name, value):
        super().setValue(name, value)
        self.pendingChanged.emit()

    @QtCore.Slot(str)
    def select(self, title):
        self._current = title
        self.currentChanged.emit()

    @QtCore.Slot(int, int)
    def moveBy(self, dx, dy):
        self.window.move_by(dx, dy)

    @QtCore.Slot(str)
    def resetParam(self, name):
        if name in self.model.values:
            self.model.values[name] = self.model.prefs.default(name)
            self.refresh()

    @QtCore.Slot(str)
    def resetSection(self, title):
        for p in self.model.params():
            if p.get('section') == title and p['name'] in self.model.values:
                self.model.values[p['name']] = self.model.prefs.default(p['name'])
        self.refresh()

    @QtCore.Slot()
    def apply(self):
        self.model.on_close(True)
        self.refresh()

    @QtCore.Slot()
    def ok(self):
        self.model.on_close(True)
        QtCore.QTimer.singleShot(0, self.window.close_window)

    @QtCore.Slot()
    def cancel(self):
        QtCore.QTimer.singleShot(0, self.window.close_window)


class PrefsWindow(QtWidgets.QWidget):
    def __init__(self):
        mw = Gui.getMainWindow()
        super().__init__(mw)
        from dtpanels.models import SettingsModel
        self.model = SettingsModel()
        self.bridge = PrefsBridge(self.model, self)
        th = self.bridge.theme
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = B.QtQuickWidgets.QQuickWidget(self)
        self.view.setResizeMode(B.QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
        # transparent outside the rounded window: the corners show FreeCAD, not a square
        self.view.setAttribute(QtCore.Qt.WA_AlwaysStackOnTop, True)
        self.view.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.view.setClearColor(QtCore.Qt.transparent)
        self.view.rootContext().setContextProperty('bridge', self.bridge)
        self.view.setSource(QtCore.QUrl.fromLocalFile(os.path.join(B.QML, 'PrefsWindow.qml')))
        if self.view.status() != B.QtQuickWidgets.QQuickWidget.Ready:
            errors = '; '.join(e.toString() for e in self.view.errors())
            raise RuntimeError(errors or 'QML not ready')
        lay.addWidget(self.view)
        s = th['s']
        w, h = int(720 * s), int(500 * s)
        w, h = min(w, int(mw.width() * 0.7)), min(h, int(mw.height() * 0.75))
        self.resize(w, h)
        self.move((mw.width() - w) // 2, max(40, (mw.height() - h) // 2))
        QtGui.QShortcut(QtGui.QKeySequence('Escape'), self, activated=self.close_window)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+F'), self,
                        activated=lambda: self.view.rootObject().focusSearch())
        mw.installEventFilter(self)

    def move_by(self, dx, dy):
        mw = self.parentWidget()
        x = max(0, min(self.x() + dx, mw.width() - self.width()))
        y = max(0, min(self.y() + dy, mw.height() - self.height()))
        self.move(x, y)

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Resize:
            self.move_by(0, 0)
        return False

    def close_window(self):
        global _window
        try:
            self.parentWidget().removeEventFilter(self)
        except RuntimeError:
            pass
        self.bridge.stop()
        self.hide()
        self.deleteLater()
        _window = None


def show():
    """Open (or bring forward) the preferences window; False when QML cannot run."""
    global _window
    if _window is not None:
        _window.show()
        _window.raise_()
        return True
    if not B.quick_usable() or not App.ParamGet(B.PREFS).GetBool('UseQml', True):
        return False
    try:
        _window = PrefsWindow()
    except Exception as error:
        App.Console.PrintWarning('ShowRoom: preferences window unavailable (%s)\n' % error)
        _window = None
        return False
    _window.show()
    _window.raise_()
    _window.activateWindow()
    return True
