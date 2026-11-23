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
EASINGS = ['OutQuart', 'OutCubic', 'OutQuint', 'OutExpo', 'OutBack', 'InOutExpo', 'InOutCubic',
           'Linear']
EDGE = 6            # resize border, px
HIDE_DELAY = 1500   # ms outside the panel before autohide / roll up
GRACE = 3000        # ms a panel shown by a selection or a task stays before hiding

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
            lay = p.layout()
            self.index = lay.indexOf(widget)
            if isinstance(lay, QtWidgets.QGridLayout) and self.index >= 0:
                self.grid = lay.getItemPosition(self.index)

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
            elif isinstance(p.layout(), QtWidgets.QGridLayout):
                p.layout().addWidget(w, *getattr(self, 'grid', (0, 0, 1, 1)))
            elif hasattr(p.layout(), 'insertWidget'):
                p.layout().insertWidget(max(self.index, 0), w)
            elif p.layout() is not None:
                p.layout().addWidget(w)
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
        self.qml_page = self.prop_model = self.prop_bridge = None
        self._qml_failed = False
        self.tab = 'Data'
        self.hidden_side = None         # autohide: 'left' / 'right' while slid away
        self.rolled = False
        self.shown_until = 0
        self.had_dialog = False
        self._resize = None
        self._backdrop = None
        self._outside = 0

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(EDGE, EDGE + 2, EDGE, EDGE)
        lay.setSpacing(EDGE + 2)
        self.header = _Header(self)
        self.header.setCursor(QtCore.Qt.ArrowCursor)
        hl = QtWidgets.QHBoxLayout(self.header)
        hl.setContentsMargins(6, 4, 6, 4)
        hl.setSpacing(6)
        tabs = QtWidgets.QHBoxLayout()
        tabs.setSpacing(6)
        hl.addLayout(tabs, 1)               # ~80 %: Data, View, Task
        self.buttons = {}
        for name in ('Data', 'View', 'Task'):
            b = QtWidgets.QPushButton(name, self.header)
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
            b.setMinimumWidth(10)
            b.clicked.connect(lambda _=False, n=name: self.clicked_tab(n))
            tabs.addWidget(b)
            self.buttons[name] = b
        icons = QtWidgets.QHBoxLayout()
        icons.setSpacing(2)
        hl.addLayout(icons, 0)              # ~20 %: visibility and pin
        self.mode_button = QtWidgets.QToolButton(self.header)
        self.mode_button.clicked.connect(self.cycle_mode)
        icons.addWidget(self.mode_button)
        self.pin_button = QtWidgets.QToolButton(self.header)
        self.pin_button.setCheckable(True)
        self.pin_button.toggled.connect(self.set_pin)
        icons.addWidget(self.pin_button)
        lay.addWidget(self.header)

        self.card = QtWidgets.QFrame(self)
        self.card.setObjectName('SRCard')
        # the resize cursors belong to the border only, never to what is inside
        self.card.setCursor(QtCore.Qt.ArrowCursor)
        # its contents' minimum height must not stop the panel from rolling up smoothly
        self.card.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Ignored)
        cl = QtWidgets.QVBoxLayout(self.card)
        cl.setContentsMargins(0, 0, 0, 0)
        self.back = QtWidgets.QPushButton('◂  Back to the ShowRoom editor', self.card)
        self.back.setObjectName('SRBack')
        self.back.setCursor(QtCore.Qt.PointingHandCursor)
        self.back.clicked.connect(lambda: self.show_tab(self.tab))
        self.back.hide()
        cl.addWidget(self.back)
        self.stack = QtWidgets.QStackedWidget(self.card)
        cl.addWidget(self.stack)
        lay.addWidget(self.card, 1)
        self.empty = QtWidgets.QLabel('No task open', self.stack)
        self.empty.setAlignment(QtCore.Qt.AlignCenter)
        self.stack.addWidget(self.empty)

        self._style()
        self.anim = QtCore.QPropertyAnimation(self, b'pos', self)
        self.roll_anim = QtCore.QPropertyAnimation(self, b'size', self)
        self.roll_anim.finished.connect(self._rolled_end)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._tick)
        # the blurred background: grabbing the 3D view is costly, so it is done
        # only after something changed (camera, panel moved) and has settled,
        # plus a slow refresh for everything else (lights, colours...)
        self.blur_timer = QtCore.QTimer(self)
        self.blur_timer.setInterval(2500)
        self.blur_timer.timeout.connect(self.request_backdrop)
        self.blur_soon = QtCore.QTimer(self)
        self.blur_soon.setSingleShot(True)
        self.blur_soon.setInterval(250)
        self.blur_soon.timeout.connect(self._grab_backdrop)
        self._cam_sensor = self._cam_view = None
        host.installEventFilter(self)

    # -------------------------------------------------------------- set up
    def _style(self):
        """The same theme as ShowRoom's QML panels (bridge.make_theme)."""
        from dtpanels.bridge import make_theme
        t = make_theme()
        px = int(round(12 * t['s']))
        self.setStyleSheet(
            '#SRFloatingPanel { font-family: "%(family)s"; font-size: %(px)dpx; color: %(text)s; }'
            '#SRHeader { background: transparent; }'
            '#SRCard { background: transparent; border-radius: 10px; }'
            '#SRHeader QPushButton { border: 1px solid %(line)s; border-radius: 7px; padding: 4px 2px; margin: 0; min-width: 0px;'
            ' color: %(text)s; background: %(field)s; }'
            '#SRHeader QPushButton:checked { background: %(accent)s; border-color: %(accent)s;'
            ' color: %(accentText)s; font-weight: bold; }'
            '#SRHeader QToolButton { border: none; border-radius: 6px; color: %(muted)s;'
            ' padding: 2px 4px; font-size: %(icon)dpx; }'
            '#SRHeader QToolButton:hover { background: %(field)s; }'
            '#SRHeader QToolButton:checked { background: transparent; border: none; }'
            '#SRBack { border: none; border-radius: 7px; padding: 5px 8px; margin-bottom: 4px;'
            ' background: %(accent)s; color: %(accentText)s; font-weight: bold; text-align: left; }'
            '#SRCard QTreeView { background: transparent; border: none; gridline-color: %(card)s;'
            ' color: %(text)s; outline: 0; }'
            '#SRCard QTreeView::item { min-height: %(row)dpx; padding: 0 4px; border: none; }'
            '#SRCard QTreeView::item:selected { background: %(accent)s; color: %(accentText)s; }'
            '#SRCard QHeaderView::section { background: transparent; border: none; padding: 4px; }'
            '#SRCard QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }'
            '#SRCard QScrollBar::handle:vertical { background: %(line)s; border-radius: 3px; min-height: 24px; }'
            '#SRCard QScrollBar::add-line, #SRCard QScrollBar::sub-line { height: 0; }'
            '#SRCard QScrollBar::add-page, #SRCard QScrollBar::sub-page { background: none; }'
            '#SRCard QLineEdit, #SRCard QComboBox, #SRCard QAbstractSpinBox { border: 1px solid %(line)s;'
            ' border-radius: 6px; padding: 2px 6px; background: %(field)s; color: %(text)s; }'
            % dict(t, px=px, row=int(round(28 * t['s'])), icon=int(round(15 * t['s']))))
        self.icon_color, self.accent = QtGui.QColor(t['muted']), QtGui.QColor(t['accent'])
        # group rows: section titles like the QML cards (muted, bold) on the card colour
        self.group_colors = (QtGui.QColor(t['card']), QtGui.QColor(t['muted']))
        self.tint = QtGui.QColor(t['window'])
        self.task_qss = (
            'QScrollArea, QScrollArea > QWidget > QWidget, Gui--TaskView--TaskPanel, QSint--ActionPanel,'
            ' QSint--ActionGroup, Gui--TaskView--TaskBox, Gui--TaskView--TaskEditControl,'
            ' Gui--TaskView--TaskBox > QWidget { background: transparent; border: none; }'
            'QDialogButtonBox QPushButton { border: 1px solid %(line)s; border-radius: 7px;'
            ' padding: 5px 16px; color: %(text)s; background: %(field)s; font-family: "%(family)s"; }'
            'QDialogButtonBox QPushButton:default { background: %(accent)s; border-color: %(accent)s;'
            ' color: %(accentText)s; font-weight: bold; }' % t)
        self.border = QtGui.QColor(t['line'])

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
        if self.prop_bridge is not None:
            self.prop_bridge.stop()
        self.timer.stop()
        self.blur_timer.stop()
        self.blur_soon.stop()
        self._watch_camera(None)
        self.host.removeEventFilter(self)
        for b in (self.props, self.tasks):
            if b is not None:
                if b is self.props:
                    self._native_tabs(b.widget, True)
                    self._editor_look(b.widget, False)
                else:
                    b.widget.removeEventFilter(self)
                    b.widget.setStyleSheet('')
                    for w in b.widget.findChildren(QtWidgets.QWidget):
                        if w.metaObject().className() == 'QSint::TaskHeader':
                            w.show()
                b.give_back()
        self.props = self.tasks = None

    # -------------------------------------------------------------- tabs
    def show_tab(self, name, native=False):
        self.tab = name
        self.back.setVisible(native and name in ('Data', 'View') and self.qml_page is not None)
        for n, b in self.buttons.items():
            b.setChecked(n == name)
        if name == 'Task':
            has = self.tasks is not None and bool(Gui.Control.activeDialog())
            self.stack.setCurrentWidget(self.tasks.widget if has else self.empty)
        elif self._qml_page() is not None and not native:
            self.prop_model.tab = name
            self.update_target()
            self.stack.setCurrentWidget(self.qml_page)
        elif self.props is not None:
            self.stack.setCurrentWidget(self.props.widget)
            tabs = self._native_tabs(self.props.widget, False)
            if tabs is not None:
                texts = [tabs.tabText(i).replace('&', '').strip().lower() for i in range(tabs.count())]
                if name.lower() in texts:
                    tabs.setCurrentIndex(texts.index(name.lower()))
                elif tabs.count() == 2:
                    # translated FreeCAD: the property view always has View first, Data second
                    tabs.setCurrentIndex(0 if name == 'View' else 1)

    # -------------------------------------------------------------- QML properties
    def _qml_page(self):
        """ShowRoom's own Data / View editor (QML), made on first use."""
        if not prefs.get('QmlProperties'):
            return None
        if self.qml_page is None and not self._qml_failed:
            self._qml_failed = True
            try:
                from dtpanels import bridge as B
                from dtpanels.properties import PropertiesModel
                self.prop_model = PropertiesModel()
                self.prop_model.open_native = self._open_native
                self.prop_model.on_change = lambda: self.prop_bridge.refresh()
                self.prop_bridge = B.Bridge(self.prop_model)
                view = B._qml_widget(self.prop_bridge)
                if view is None:
                    self.prop_bridge.stop()
                    return None
                area = QtWidgets.QScrollArea(self.stack)
                area.setWidgetResizable(True)
                area.setFrameShape(QtWidgets.QFrame.NoFrame)
                area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
                area.setWidget(view)
                area.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
                view.setMinimumWidth(0)
                self.stack.addWidget(area)
                self.qml_page, self._qml_failed = area, False
            except Exception as error:
                App.Console.PrintWarning('ShowRoom: QML properties unavailable (%s)\n' % error)
                return None
        return self.qml_page

    def update_target(self):
        if self.prop_model is None:
            return
        sel = Gui.Selection.getSelection()
        obj = sel[0] if sel else None
        if obj is not self.prop_model.target or self.prop_model.tab != self.tab:
            self.prop_model.set_target(obj, self.tab if self.tab in ('Data', 'View') else None)
            self.prop_bridge._error = ''          # a message is about the object it came from
        self.prop_bridge.refresh()
        view = self.qml_page.widget() if self.qml_page is not None else None
        if view is not None:        # a much shorter page must not stay blank
            QtCore.QTimer.singleShot(60, view.update)

    def _open_native(self, name):
        """What the ShowRoom editor cannot edit: FreeCAD's own editor, on that property,
        with a button to come back."""
        def go():
            self.show_tab(self.tab, native=True)
            from dtpanels.properties import _words
            for tree in self.props.widget.findChildren(QtWidgets.QTreeView):
                if not tree.isVisible():
                    continue
                model = tree.model()
                hits = model.match(model.index(0, 0), QtCore.Qt.DisplayRole, _words(name), 1,
                                   QtCore.Qt.MatchExactly | QtCore.Qt.MatchRecursive)
                if hits:
                    tree.setCurrentIndex(hits[0])
                    tree.expand(hits[0])
                    tree.scrollTo(hits[0], QtWidgets.QAbstractItemView.PositionAtTop)
        QtCore.QTimer.singleShot(0, go)

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
        self.set_mode(VISIBILITY[(VISIBILITY.index(self.mode()) + 1) % 3])

    def set_pin(self, on):
        prefs.set('KeepOpenOnTask', on)
        self.pin_button.setIcon(_pin_icon(on, self.icon_color, self.accent))
        self.pin_button.setToolTip('Pinned: the panel stays open while a task is open (click to unpin)'
                                   if on else 'Not pinned: the panel may hide during tasks (click to pin)')

    def set_mode(self, m):
        prefs.set('PanelVisibility', m)
        self.apply_mode()

    def _easing(self):
        name = prefs.get('PanelEasing')
        curve = getattr(QtCore.QEasingCurve, name if name in EASINGS else 'OutQuart')
        ms = max(0, min(2000, prefs.get('PanelAnimMs')))
        for a in (self.anim, self.roll_anim):
            a.setEasingCurve(curve)
            a.setDuration(ms)

    def apply_mode(self):
        m = self.mode()
        nxt = VISIBILITY[(VISIBILITY.index(m) + 1) % 3]
        self.mode_button.setText({'Fixed': '▣', 'Rolled up': '▤', 'Autohide': '◧'}[m])
        self.mode_button.setToolTip('%s (click for %s)' % ({
            'Fixed': 'Fixed: always open', 'Rolled up': 'Rolled up: opens when the mouse is over it',
            'Autohide': 'Autohide: slides away, touch the screen edge to bring it back'}[m], nxt))
        self.pin_button.blockSignals(True)
        self.pin_button.setChecked(prefs.get('KeepOpenOnTask'))
        self.pin_button.blockSignals(False)
        self.set_pin(self.pin_button.isChecked())
        self._easing()
        if m != 'Autohide' and self.hidden_side:
            self.slide(False)
        self.roll(m == 'Rolled up')
        self.timer.start()
        if prefs.get('PanelBlur'):
            self.blur_timer.start()
            self.request_backdrop()
        else:
            self.blur_timer.stop()
            self._backdrop = None
            self.update()

    def roll(self, rolled):
        if rolled == self.rolled:
            return
        self.rolled = rolled
        g = self.geometry()
        lay = self.layout().contentsMargins()
        short = self.header.sizeHint().height() + lay.top() + lay.bottom()
        if rolled:
            if self.roll_anim.state() != QtCore.QAbstractAnimation.Running:
                self._full_height = g.height()
            end = short
        else:
            self.card.show()
            end = getattr(self, '_full_height', 420)
        self.roll_anim.stop()
        self.roll_anim.setStartValue(QtCore.QSize(g.width(), g.height()))
        self.roll_anim.setEndValue(QtCore.QSize(g.width(), end))
        self.roll_anim.start()

    def _rolled_end(self):
        if self.rolled:
            self.card.hide()

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
            end = self._placed().topLeft() if hasattr(self, 'wanted') else g.topLeft()
            self.hidden_side = None
            self.show()
            self.raise_()
        self.anim.stop()
        QtCore.QTimer.singleShot(int(self.anim.duration()) + 20, _tell_overlay)
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
    def _skin_tasks(self):
        """ShowRoom's own task panels (QML) without FreeCAD's grey header and
        frames, and with OK / Cancel in the QML style; other tasks untouched."""
        if self.tasks is None:
            return
        try:
            from dtpanels import bridge
            own = bool(Gui.Control.activeDialog()) and bridge.current() is not None
        except Exception:
            own = False
        dock = self.tasks.widget
        dock.setStyleSheet(self.task_qss if own else '')
        for w in dock.findChildren(QtWidgets.QWidget):
            if w.metaObject().className() == 'QSint::TaskHeader':
                w.setVisible(not own)

    def _task_shown(self):
        if self.tasks is None:
            return
        QtCore.QTimer.singleShot(50, self._skin_tasks)
        dock = self.tasks.widget
        if self.stack.indexOf(dock) < 0:        # taken back by FreeCAD's dock manager
            self.stack.addWidget(dock)
        if prefs.get('AutoTask') and Gui.Control.activeDialog():
            self.had_dialog = True
            self.reveal('Task')
        elif self.stack.currentWidget() is not dock:
            self.show_tab(self.tab)             # keep the current tab on top

    def _over_document(self):
        """False over the Start page (and web pages, or with no window open)."""
        try:
            sub = self.host.currentSubWindow() if isinstance(self.host, QtWidgets.QMdiArea) else None
            if sub is None:             # no window open at all
                return not isinstance(self.host, QtWidgets.QMdiArea)
            cls = sub.widget().metaObject().className()
            return not ('Start' in cls or 'WebView' in cls or 'Browser' in cls)
        except RuntimeError:
            return True

    def _tick(self):
        over = self._over_document()
        if over != (not self.isHidden()):
            self.setVisible(over)
            if over:
                self.raise_()
            _tell_overlay()
        if not over:
            return
        dialog = bool(Gui.Control.activeDialog())
        if self.tasks is not None and self.stack.indexOf(self.tasks.widget) < 0:
            self._task_shown()
        if dialog != self.had_dialog:
            self.had_dialog = dialog
            QtCore.QTimer.singleShot(50, self._skin_tasks)
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
                or _now() < self.shown_until
                or (prefs.get('KeepOpenOnTask') and dialog))
        if m == 'Autohide' and self.hidden_side:
            in_host = self.host.rect().contains(pos)
            at_edge = pos.x() <= 3 if self.hidden_side == 'left' else pos.x() >= self.host.width() - 4
            if in_host and at_edge:
                self.slide(False)
                # the panel may sit far from the edge: wait until the mouse gets there
                self.shown_until = _now() + 6000
                self.await_enter = True
            return
        if inside and getattr(self, 'await_enter', False):
            self.await_enter = False
            self.shown_until = 0
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
        self.request_backdrop()

    def save_geometry(self):
        """Only after the user moved or resized it.  A panel on the right half is
        remembered by its distance from the right edge, so that it stays there
        when the window or the docks change size."""
        g = self.geometry() if not self.hidden_side else QtCore.QRect(self._home, self.size())
        h = getattr(self, '_full_height', g.height()) if self.rolled else g.height()
        x = g.x()
        if g.center().x() > self.host.width() / 2:
            x = -(self.host.width() - g.right())        # negative: from the right edge
        self.wanted = (x, g.y(), g.width(), h)
        prefs.set('PanelGeometry', '%d,%d,%d,%d' % self.wanted)

    def _placed(self):
        """Where the remembered geometry falls in the current view area."""
        x, y, w, h = self.wanted
        W, H = self.host.width(), self.host.height()
        w, h = max(220, min(w, W)), max(160, min(h, H))
        if x < 0:
            x = W + x - w + 1
        return QtCore.QRect(max(0, min(x, W - w)), max(0, min(y, H - h)), w, h)

    def restore_geometry(self):
        try:
            self.wanted = tuple(int(v) for v in prefs.get('PanelGeometry').split(','))
            assert len(self.wanted) == 4
        except (ValueError, AssertionError):
            self.wanted = (-16, 16, 340, 560)
        self.place()

    def place(self):
        r = self._placed()
        if self.rolled:
            self._full_height = r.height()
            r.setHeight(self.height())
        if self.hidden_side:
            self._home = r.topLeft()
            x = -r.width() - 2 if self.hidden_side == 'left' else self.host.width() + 2
            self.setGeometry(x, r.y(), r.width(), r.height())
        else:
            self.setGeometry(r)

    def eventFilter(self, obj, ev):
        if self.tasks is not None and obj is self.tasks.widget and ev.type() == QtCore.QEvent.Show:
            # FreeCAD shows its task dock when a dialog opens: switch tab instead
            if self.stack.currentWidget() is not obj:
                QtCore.QTimer.singleShot(0, self._task_shown)
            return False
        if obj is self.host and ev.type() == QtCore.QEvent.Resize and self._resize is None \
                and hasattr(self, 'wanted'):
            self.place()                # never overwrites what the user chose
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
            if shape == QtCore.Qt.ArrowCursor:
                self.unsetCursor()
            else:
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
            self.request_backdrop()

    # -------------------------------------------------------------- blur
    def request_backdrop(self):
        """A new blurred background once things have been still for a moment."""
        if prefs.get('PanelBlur') and self.isVisible() and not self.hidden_side:
            self.blur_soon.start()

    def _watch_camera(self, view):
        """Re-blur after the camera moved (debounced), never during the move."""
        if view is self._cam_view:
            return
        if self._cam_sensor is not None:
            try:
                self._cam_sensor.detach()
            except Exception:
                pass
        self._cam_sensor, self._cam_view = None, view
        if view is None:
            return
        try:
            from pivy import coin
            self._cam_sensor = coin.SoNodeSensor(lambda *a: self.request_backdrop(), None)
            self._cam_sensor.attach(view.getCameraNode())
        except Exception:
            self._cam_sensor = None

    def _grab_backdrop(self):
        if not prefs.get('PanelBlur') or not self.isVisible() or self.hidden_side:
            return
        if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
            self.blur_soon.start()          # still navigating or dragging: later
            return
        try:
            active = Gui.ActiveDocument.ActiveView
            self._watch_camera(active)
            view = active.graphicsView()
            src = view.viewport() if hasattr(view, 'viewport') else view
            grab = src.grabFramebuffer() if hasattr(src, 'grabFramebuffer') else src.grab().toImage()
            ratio = grab.width() / max(1, src.width())
            top_left = src.mapFrom(self.host, self.pos()) if src.isAncestorOf(self) else \
                src.mapFromGlobal(self.mapToGlobal(QtCore.QPoint(0, 0)))
            rect = QtCore.QRect(top_left * ratio, self.size() * ratio)
            img = grab.copy(rect)
            # a cheap first reduction, then the smooth ones on a small picture
            img = img.scaled(max(1, img.width() // 4), max(1, img.height() // 4),
                             QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.FastTransformation)
            small = img.scaled(max(1, img.width() // 3), max(1, img.height() // 3),
                               QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            small = small.scaled(max(1, small.width() // 2 * 2), max(1, small.height() // 2 * 2),
                                 QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            self._backdrop = small.scaled(self.size(), QtCore.Qt.IgnoreAspectRatio,
                                          QtCore.Qt.SmoothTransformation)
        except Exception:
            self._backdrop = None
        self.update()

    def resizeEvent(self, ev):
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), 16, 16)
        self.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(ev)
        QtCore.QTimer.singleShot(0, _tell_overlay)

    def moveEvent(self, ev):
        super().moveEvent(ev)
        if self.anim.state() != QtCore.QAbstractAnimation.Running:
            QtCore.QTimer.singleShot(0, _tell_overlay)

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)
        p.setClipPath(path)
        tint = QtGui.QColor(self.tint)
        if self._backdrop is not None:
            p.drawImage(0, 0, self._backdrop)
            tint.setAlpha(215)
        p.fillPath(path, tint)
        p.setClipping(False)
        pen = QtGui.QPen(self.border)
        p.setPen(pen)
        p.drawPath(path)


def _pin_icon(on, color, accent):
    """A push pin: upright and filled when pinned, tilted outline when not."""
    c = (accent if on else color).name()
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           '<g transform="rotate(%d 12 12)" fill="%s" stroke="%s" stroke-width="1.6" '
           'stroke-linejoin="round" stroke-linecap="round">'
           '<path d="M8 3h8l-1.5 6 3.5 3.5H6L9.5 9z" fill-opacity="%s"/>'
           '<path d="M12 12.5V21" fill="none"/></g></svg>'
           % (0 if on else 40, c, c, '1' if on else '0'))
    pm = QtGui.QPixmap()
    pm.loadFromData(QtCore.QByteArray(svg.encode()), 'SVG')
    if not pm.isNull():
        pm = pm.scaled(36, 36, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    return QtGui.QIcon(pm)


def _now():
    return QtCore.QDateTime.currentMSecsSinceEpoch()


# ------------------------------------------------------------------ selection
class _Selection:
    def _shown(self, *args):
        if _panel is None:
            return
        QtCore.QTimer.singleShot(0, _panel.update_target)
        if not Gui.Control.activeDialog():
            _panel.reveal('Data' if _panel.tab == 'Task' else None)

    def _cleared(self, *args):
        if _panel is not None:
            QtCore.QTimer.singleShot(0, _panel.update_target)

    addSelection = setSelection = _shown
    removeSelection = clearSelection = _cleared


# ------------------------------------------------------------------ public
def _host():
    mw = Gui.getMainWindow()
    return mw.findChild(QtWidgets.QMdiArea) or mw.centralWidget()


def occupied(widget):
    """Where the floating panel is, in ``widget`` coordinates (None when it is away)."""
    p = _panel
    if p is None or p.isHidden() or p.hidden_side:
        return None
    top_left = widget.mapFromGlobal(p.mapToGlobal(QtCore.QPoint(0, 0)))
    return QtCore.QRect(top_left, p.size())


def _tell_overlay():
    try:
        from dtpanels import overlay
        if overlay._manager is not None:
            overlay._manager.replace()
    except Exception:
        pass


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
        _tell_overlay()


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
