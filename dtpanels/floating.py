# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Floating properties panel over the 3D view.

FreeCAD's own property editor and task view are moved into a frameless panel
that floats over the MDI area, with Data / View / Task tabs, a blurred
background, resizing, and three visibility modes (fixed, rolled up, autohide).
Turning the panel off puts both widgets back where they came from."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from Utils import prefs

VISIBILITY = ['Fixed', 'Rolled up', 'Autohide']
EDGE = 6            # resize border, px
HIDE_DELAY = 700    # ms outside the panel before autohide / roll up
GRACE = 1500        # ms a panel shown by a selection or a task stays before hiding

_panel = None
_observer = None


# ------------------------------------------------------------------ native widgets
def _find(cls_name):
    mw = Gui.getMainWindow()
    found = [w for w in mw.findChildren(QtWidgets.QWidget)
             if w.metaObject().className() == cls_name]
    visible = [w for w in found if w.isVisible()]
    return (visible or found or [None])[0]


class _Borrowed:
    """A native widget taken from its place, and how to give it back."""

    def __init__(self, widget):
        # FreeCAD finds its task view through the dock that holds it: take the dock along
        dock = widget.parentWidget()
        if isinstance(dock, QtWidgets.QDockWidget):
            mw = Gui.getMainWindow()
            self.widget, self.parent, self.kind = dock, mw, 'maindock'
            area = mw.dockWidgetArea(dock)
            self.area = area if area != QtCore.Qt.NoDockWidgetArea else QtCore.Qt.RightDockWidgetArea
            self.floating = dock.isFloating()
            self.dock_visible, self.title = dock.isVisible(), dock.titleBarWidget()
            dock.setTitleBarWidget(QtWidgets.QWidget(dock))
            return
        self.widget = widget
        self.parent = widget.parentWidget()
        self.kind, self.index, self.label, self.icon = 'layout', 0, '', QtGui.QIcon()
        p = self.parent
        tabs = p.parentWidget() if isinstance(p, QtWidgets.QStackedWidget) else None
        if isinstance(tabs, QtWidgets.QTabWidget):
            self.kind, self.parent = 'tab', tabs
            self.index = tabs.indexOf(widget)
            self.label, self.icon = tabs.tabText(self.index), tabs.tabIcon(self.index)
        elif isinstance(p, QtWidgets.QSplitter):
            self.kind, self.index = 'splitter', p.indexOf(widget)
            self.sizes = p.sizes()
        elif isinstance(p, QtWidgets.QDockWidget):
            self.kind = 'dock'
            self.dock_visible = p.isVisible()
        elif p is not None and p.layout() is not None:
            self.index = p.layout().indexOf(widget)

    def give_back(self):
        w, p = self.widget, self.parent
        if p is None:
            return
        try:
            if self.kind == 'maindock':
                w.setTitleBarWidget(self.title)
                p.addDockWidget(self.area, w)
                w.setFloating(self.floating)
                w.setVisible(self.dock_visible)
                return
            if self.kind == 'tab':
                p.insertTab(self.index, w, self.icon, self.label)
            elif self.kind == 'splitter':
                p.insertWidget(self.index, w)
                p.setSizes(self.sizes)
            elif self.kind == 'dock':
                p.setWidget(w)
                p.setVisible(self.dock_visible)
            elif p.layout() is not None:
                p.layout().insertWidget(max(self.index, 0), w)
            else:
                w.setParent(p)
            w.show()
        except RuntimeError:        # the old home was deleted meanwhile
            pass


# ------------------------------------------------------------------ the panel
class _Header(QtWidgets.QFrame):
    """Tab buttons; dragging its empty part moves the panel."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setObjectName('SRHeader')
        self._drag = None

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            self._drag = (ev.globalPos(), self.panel.pos())

    def mouseMoveEvent(self, ev):
        if self._drag is not None:
            start, origin = self._drag
            self.panel.move_to(origin + ev.globalPos() - start)

    def mouseReleaseEvent(self, ev):
        if self._drag is not None:
            self._drag = None
            self.panel.save_geometry()

    def enterEvent(self, ev):
        self.panel.hovered()


class FloatingPanel(QtWidgets.QFrame):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setObjectName('SRFloatingPanel')
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        self.props = self.tasks = None
        self.tab = 'Data'
        self.hidden_side = None         # autohide: 'left' / 'right' while slid away
        self.rolled = False
        self.shown_until = 0
        self.had_dialog = False
        self._resize = None
        self._backdrop = None
        self._outside = 0

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(EDGE, EDGE, EDGE, EDGE)
        lay.setSpacing(EDGE)
        self.header = _Header(self)
        hl = QtWidgets.QHBoxLayout(self.header)
        hl.setContentsMargins(6, 4, 6, 4)
        hl.setSpacing(4)
        self.buttons = {}
        for name in ('Data', 'View', 'Task'):
            b = QtWidgets.QPushButton(name, self.header)
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self.clicked_tab(n))
            hl.addWidget(b)
            self.buttons[name] = b
        hl.addStretch(1)
        self.mode_button = QtWidgets.QToolButton(self.header)
        self.mode_button.setToolTip('Visibility: fixed, rolled up, autohide')
        self.mode_button.clicked.connect(self.cycle_mode)
        hl.addWidget(self.mode_button)
        lay.addWidget(self.header)

        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName('SRCard')
        cl = QtWidgets.QVBoxLayout(self.card)
        cl.setContentsMargins(4, 4, 4, 4)
        self.stack = QtWidgets.QStackedWidget(self.card)
        cl.addWidget(self.stack)
        lay.addWidget(self.card, 1)
        self.empty = QtWidgets.QLabel('No task open', self.stack)
        self.empty.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.empty)

        self._style()
        self.anim = QtCore.QPropertyAnimation(self, b'pos', self)
        self.anim.setDuration(180)
        self.anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._tick)
        self.blur_timer = QtCore.QTimer(self)
        self.blur_timer.setInterval(400)
        self.blur_timer.timeout.connect(self._grab_backdrop)
        host.installEventFilter(self)

    # -------------------------------------------------------------- set up
    def _style(self):
        pal = QtWidgets.QApplication.palette()
        dark = pal.color(QtGui.QPalette.Window).lightness() < 128
        head = 'rgba(255,255,255,18)' if dark else 'rgba(0,0,0,14)'
        card = pal.color(QtGui.QPalette.Base).name()
        accent = pal.color(QtGui.QPalette.Highlight).name()
        text = pal.color(QtGui.QPalette.WindowText).name()
        base = pal.color(QtGui.QPalette.Base)
        alt = (base.lighter(108) if dark else base.darker(103)).name()
        mid = pal.color(QtGui.QPalette.Mid).name()
        hl = pal.color(QtGui.QPalette.Highlight)
        k = 0.22 if dark else 0.14         # group rows: the base tinted with the accent colour
        group_bg = QtGui.QColor(int(base.red() * (1 - k) + hl.red() * k),
                                int(base.green() * (1 - k) + hl.green() * k),
                                int(base.blue() * (1 - k) + hl.blue() * k)).name()
        self.setStyleSheet(
            '#SRHeader { background: %s; border-radius: 8px; }'
            '#SRCard { background: %s; border-radius: 8px; }'
            '#SRHeader QPushButton { border: none; border-radius: 6px; padding: 4px 12px; color: %s; background: transparent; }'
            '#SRHeader QPushButton:checked { background: %s; color: white; font-weight: bold; }'
            '#SRHeader QToolButton { border: none; color: %s; padding: 2px 6px; }'
            '#SRCard QTreeView { background: transparent; border: none; gridline-color: %s;'
            ' show-decoration-selected: 1; outline: 0; }'
            '#SRCard QTreeView::item { min-height: 26px; padding: 0 4px; border: none; }'
            '#SRCard QTreeView::item:selected { background: %s; color: white; border-radius: 5px; }'
            '#SRCard QHeaderView::section { background: transparent; border: none; padding: 4px; }'
            '#SRCard QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }'
            '#SRCard QScrollBar::handle:vertical { background: %s; border-radius: 3px; min-height: 24px; }'
            '#SRCard QScrollBar::add-line, #SRCard QScrollBar::sub-line { height: 0; }'
            '#SRCard QScrollBar::add-page, #SRCard QScrollBar::sub-page { background: none; }'
            '#SRCard QLineEdit, #SRCard QComboBox, #SRCard QAbstractSpinBox { border: 1px solid %s;'
            ' border-radius: 5px; padding: 1px 4px; background: %s; }'
            % (head, card, text, accent, text, alt, accent, mid, mid, card))
        self.group_colors = (QtGui.QColor(group_bg),
                             QtGui.QColor(accent).lighter(140) if dark else QtGui.QColor(accent).darker(120))
        self.tint = pal.color(QtGui.QPalette.Window)

    def adopt(self):
        """Take the property editor and the task view (when FreeCAD has them)."""
        if self.props is None:
            w = _find('Gui::PropertyView')
            if w is not None:
                self.props = _Borrowed(w)
                self.stack.addWidget(w)
                self._native_tabs(w, False)
                self._editor_look(w, True)
        if self.tasks is None:
            w = _find('Gui::TaskView::TaskView')
            if w is not None:
                self.tasks = _Borrowed(w)
                self.stack.addWidget(self.tasks.widget)
                self.tasks.widget.installEventFilter(self)
        self.show_tab(self.tab)
        return self.props is not None

    def _editor_look(self, view, ours):
        names = ('groupBackground', 'groupTextColor')
        for ed in view.findChildren(QtWidgets.QTreeView):
            if ours:
                ed._sr_saved = [ed.property(n) for n in names]
                for n, c in zip(names, self.group_colors):
                    ed.setProperty(n, QtGui.QBrush(c) if n == 'groupBackground' else c)
                ed.setIndentation(12)
            elif hasattr(ed, '_sr_saved'):
                for n, c in zip(names, ed._sr_saved):
                    if c is not None:
                        ed.setProperty(n, c)
            ed.viewport().update()

    def _native_tabs(self, view, visible):
        tabs = view.findChild(QtWidgets.QTabWidget)
        if tabs is not None:
            tabs.tabBar().setVisible(visible)
        return tabs

    def release(self):
        self.timer.stop()
        self.blur_timer.stop()
        self.host.removeEventFilter(self)
        for b in (self.props, self.tasks):
            if b is not None:
                if b is self.props:
                    self._native_tabs(b.widget, True)
                    self._editor_look(b.widget, False)
                else:
                    b.widget.removeEventFilter(self)
                b.give_back()
        self.props = self.tasks = None

    # -------------------------------------------------------------- tabs
    def show_tab(self, name):
        self.tab = name
        for n, b in self.buttons.items():
            b.setChecked(n == name)
        if name == 'Task':
            has = self.tasks is not None and bool(Gui.Control.activeDialog())
            self.stack.setCurrentWidget(self.tasks.widget if has else self.empty)
        elif self.props is not None:
            self.stack.setCurrentWidget(self.props.widget)
            tabs = self._native_tabs(self.props.widget, False)
            if tabs is not None:
                for i in range(tabs.count()):
                    if tabs.tabText(i).replace('&', '') == name:
                        tabs.setCurrentIndex(i)

    def clicked_tab(self, name):
        if self.mode() == 'Rolled up' and not self.rolled and name == self.tab:
            self.roll(True)
        else:
            self.roll(False)
            self.show_tab(name)

    # -------------------------------------------------------------- modes
    def mode(self):
        m = prefs.get('PanelVisibility')
        return m if m in VISIBILITY else 'Fixed'

    def cycle_mode(self):
        prefs.set('PanelVisibility', VISIBILITY[(VISIBILITY.index(self.mode()) + 1) % 3])
        self.apply_mode()

    def apply_mode(self):
        m = self.mode()
        self.mode_button.setText({'Fixed': '▣', 'Rolled up': '▤', 'Autohide': '◧'}[m])
        if m != 'Autohide' and self.hidden_side:
            self.slide(False)
        self.roll(m == 'Rolled up')
        self.timer.start()
        if prefs.get('PanelBlur'):
            self.blur_timer.start()
            self._grab_backdrop()
        else:
            self.blur_timer.stop()
            self._backdrop = None
            self.update()

    def roll(self, rolled):
        if rolled == self.rolled:
            return
        self.rolled = rolled
        g = self.geometry()
        if rolled:
            self._full_height = g.height()
            self.card.hide()
            self.resize(g.width(), self.header.sizeHint().height() + 2 * EDGE)
        else:
            self.card.show()
            self.resize(g.width(), getattr(self, '_full_height', 420))

    def side(self):
        return 'left' if self.geometry().center().x() < self.host.width() / 2 else 'right'

    def slide(self, away):
        """Autohide: slide out of view towards the nearer edge, or back in."""
        if away == bool(self.hidden_side):
            return
        g = self.geometry()
        if away:
            self._home = g.topLeft()
            self.hidden_side = self.side()
            x = -g.width() - 2 if self.hidden_side == 'left' else self.host.width() + 2
            end = QtCore.QPoint(x, g.y())
        else:
            end = getattr(self, '_home', g.topLeft())
            self.hidden_side = None
            self.show()
            self.raise_()
        self.anim.stop()
        self.anim.setStartValue(g.topLeft())
        self.anim.setEndValue(end)
        self.anim.start()

    def reveal(self, tab=None):
        """Bring the panel up for a selection or a task (autohide / rolled up)."""
        if tab:
            self.show_tab(tab)
        m = self.mode()
        if m == 'Autohide':
            self.slide(False)
        elif m == 'Rolled up':
            self.roll(False)
        self.shown_until = _now() + GRACE

    def hovered(self):
        if self.mode() == 'Rolled up':
            self.roll(False)

    # -------------------------------------------------------------- polling
    def _task_shown(self):
        if self.tasks is None:
            return
        dock = self.tasks.widget
        if self.stack.indexOf(dock) < 0:        # taken back by FreeCAD's dock manager
            self.stack.addWidget(dock)
        if prefs.get('AutoTask') and Gui.Control.activeDialog():
            self.had_dialog = True
            self.reveal('Task')
        elif self.stack.currentWidget() is not dock:
            self.show_tab(self.tab)             # keep the current tab on top

    def _tick(self):
        dialog = bool(Gui.Control.activeDialog())
        if self.tasks is not None and self.stack.indexOf(self.tasks.widget) < 0:
            self._task_shown()
        if dialog != self.had_dialog:
            self.had_dialog = dialog
            if prefs.get('AutoTask'):
                if dialog:
                    self.reveal('Task')
                else:
                    self.show_tab('Data')
            elif self.tab == 'Task':
                self.show_tab('Task')
        m = self.mode()
        if m == 'Fixed':
            return
        pos = self.host.mapFromGlobal(QtGui.QCursor.pos())
        inside = self.geometry().adjusted(-4, -4, 4, 4).contains(pos)
        busy = (QtWidgets.QApplication.activePopupWidget() is not None
                or QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton
                or _now() < self.shown_until)
        if m == 'Autohide' and self.hidden_side:
            in_host = self.host.rect().contains(pos)
            at_edge = pos.x() <= 3 if self.hidden_side == 'left' else pos.x() >= self.host.width() - 4
            if in_host and at_edge:
                self.slide(False)
                self.shown_until = _now() + 400
            return
        if inside or busy:
            self._outside = 0
            return
        self._outside += self.timer.interval()
        if self._outside >= HIDE_DELAY:
            self._outside = 0
            if m == 'Autohide':
                self.slide(True)
            elif m == 'Rolled up':
                self.roll(True)

    # -------------------------------------------------------------- geometry
    def move_to(self, p):
        x = max(0, min(p.x(), self.host.width() - self.width()))
        y = max(0, min(p.y(), self.host.height() - self.height()))
        self.move(x, y)
        self._grab_backdrop()

    def save_geometry(self):
        g = self.geometry() if not self.hidden_side else QtCore.QRect(self._home, self.size())
        h = getattr(self, '_full_height', g.height()) if self.rolled else g.height()
        prefs.set('PanelGeometry', '%d,%d,%d,%d' % (g.x(), g.y(), g.width(), h))

    def restore_geometry(self):
        try:
            x, y, w, h = [int(v) for v in prefs.get('PanelGeometry').split(',')]
        except ValueError:
            w, h = 340, min(560, max(300, self.host.height() - 40))
            x, y = self.host.width() - w - 16, 16
        w, h = max(220, min(w, self.host.width())), max(160, min(h, self.host.height()))
        self.setGeometry(max(0, min(x, self.host.width() - w)), max(0, min(y, self.host.height() - h)), w, h)

    def eventFilter(self, obj, ev):
        if self.tasks is not None and obj is self.tasks.widget and ev.type() == QtCore.QEvent.Show:
            # FreeCAD shows its task dock when a dialog opens: switch tab instead
            if self.stack.currentWidget() is not obj:
                QtCore.QTimer.singleShot(0, self._task_shown)
            return False
        if obj is self.host and ev.type() == QtCore.QEvent.Resize and not self.hidden_side:
            g = self.geometry()
            self.move(max(0, min(g.x(), self.host.width() - g.width())),
                      max(0, min(g.y(), self.host.height() - g.height())))
        return False

    def _edges(self, pos):
        r = self.rect()
        e = set()
        if pos.x() < EDGE:
            e.add('l')
        if pos.x() > r.width() - EDGE:
            e.add('r')
        if not self.rolled and pos.y() > r.height() - EDGE:
            e.add('b')
        if not self.rolled and pos.y() < EDGE:
            e.add('t')
        return e

    def mousePressEvent(self, ev):
        e = self._edges(ev.pos())
        if e and ev.button() == QtCore.Qt.LeftButton:
            self._resize = (e, ev.globalPos(), self.geometry())

    def mouseMoveEvent(self, ev):
        if self._resize is None:
            e = self._edges(ev.pos())
            shape = QtCore.Qt.ArrowCursor
            if e in ({'l', 'b'}, {'r', 't'}):
                shape = QtCore.Qt.SizeBDiagCursor
            elif e in ({'r', 'b'}, {'l', 't'}):
                shape = QtCore.Qt.SizeFDiagCursor
            elif e & {'l', 'r'}:
                shape = QtCore.Qt.SizeHorCursor
            elif e:
                shape = QtCore.Qt.SizeVerCursor
            self.setCursor(shape)
            return
        e, start, g = self._resize
        d = ev.globalPos() - start
        x, y, w, h = g.x(), g.y(), g.width(), g.height()
        if 'r' in e:
            w = g.width() + d.x()
        if 'l' in e:
            w = g.width() - d.x()
            x = g.right() + 1 - max(220, w)
        if 'b' in e:
            h = g.height() + d.y()
        if 't' in e:
            h = g.height() - d.y()
            y = g.bottom() + 1 - max(160, h)
        w, h = max(220, w), max(160, h)
        self.setGeometry(QtCore.QRect(x, y, w, h).intersected(self.host.rect()))

    def mouseReleaseEvent(self, ev):
        if self._resize is not None:
            self._resize = None
            self.save_geometry()
            self._grab_backdrop()

    # -------------------------------------------------------------- blur
    def _grab_backdrop(self):
        if not prefs.get('PanelBlur') or not self.isVisible() or self.hidden_side:
            return
        try:
            view = Gui.ActiveDocument.ActiveView.graphicsView()
            src = view.viewport() if hasattr(view, 'viewport') else view
            grab = src.grabFramebuffer() if hasattr(src, 'grabFramebuffer') else src.grab().toImage()
            ratio = grab.width() / max(1, src.width())
            top_left = src.mapFrom(self.host, self.pos()) if src.isAncestorOf(self) else \
                src.mapFromGlobal(self.mapToGlobal(QtCore.QPoint(0, 0)))
            rect = QtCore.QRect(top_left * ratio, self.size() * ratio)
            img = grab.copy(rect)
            small = img.scaled(max(1, img.width() // 12), max(1, img.height() // 12),
                               QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            small = small.scaled(max(1, small.width() // 2 * 2), max(1, small.height() // 2 * 2),
                                 QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            self._backdrop = small.scaled(self.size(), QtCore.Qt.IgnoreAspectRatio,
                                          QtCore.Qt.SmoothTransformation)
        except Exception:
            self._backdrop = None
        self.update()

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.setClipPath(path)
        tint = QtGui.QColor(self.tint)
        if self._backdrop is not None:
            p.drawImage(0, 0, self._backdrop)
            tint.setAlpha(150)
        p.fillPath(path, tint)
        p.setClipping(False)
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 60))
        p.setPen(pen)
        p.drawPath(path)


def _now():
    return QtCore.QDateTime.currentMSecsSinceEpoch()


# ------------------------------------------------------------------ selection
class _Selection:
    def _shown(self, *args):
        if _panel is not None and not Gui.Control.activeDialog():
            _panel.reveal('Data' if _panel.tab == 'Task' else None)

    addSelection = setSelection = _shown


# ------------------------------------------------------------------ public
def _host():
    mw = Gui.getMainWindow()
    return mw.findChild(QtWidgets.QMdiArea) or mw.centralWidget()


def enabled():
    return prefs.get('FloatingPanel')


def start():
    """Create the panel (once) and take FreeCAD's property editor and task view."""
    global _panel, _observer
    if _panel is not None:
        _panel.apply_mode()
        return _panel
    host = _host()
    if host is None:
        return None
    panel = FloatingPanel(host)
    if not panel.adopt():
        panel.release()
        panel.deleteLater()
        App.Console.PrintWarning("ShowRoom: FreeCAD's property editor was not found; "
                                 "the floating panel needs it.\n")
        return None
    _panel = panel
    panel.restore_geometry()
    panel.show()
    panel.raise_()
    panel.apply_mode()
    if _observer is None:
        _observer = _Selection()
        Gui.Selection.addObserver(_observer)
    return panel


def stop():
    global _panel, _observer
    if _observer is not None:
        Gui.Selection.removeObserver(_observer)
        _observer = None
    if _panel is not None:
        _panel.save_geometry()
        _panel.release()
        _panel.hide()
        _panel.deleteLater()
        _panel = None


def apply_prefs():
    if enabled():
        start()
    else:
        stop()


def toggle():
    prefs.set('FloatingPanel', not enabled())
    apply_prefs()


def install():
    """At startup: open the panel once the main window is complete."""
    if App.GuiUp and enabled():
        QtCore.QTimer.singleShot(1500, apply_prefs)
