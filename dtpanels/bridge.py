# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Generic task panel: bridge between a panel model and its QML (or widget) form.

A *model* (see models.py) describes what the panel edits:

    title, subtitle(), icon               header
    doc, transaction                      the document, the undo step's name
    edited                                object put in edit mode (or None)
    params()                              list of parameter dicts, see below
    hidden(), info(), actions(), active_actions(), hint(), galleries()
    watched()                             objects whose changes refresh the panel
    structure()                           a change of this value rebuilds the sections
    trigger(name)                         action buttons; may return ("close",) or
                                          ("edit", obj) to hand over to another panel
    browse(param_name)

A parameter is a dict with name, label, kind, section and the usual limits,
plus ``get()`` and ``set(value, field)`` callables.  Kinds: number, int, bool,
enum, color, vector, gallery, light, note.

The whole panel session is one transaction: OK commits it, Cancel undoes it,
as in Part Design.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from dtpanels import QML

try:
    from PySide6 import QtQuickWidgets
except Exception:                   # pragma: no cover - older Qt bindings
    try:
        from PySide2 import QtQuickWidgets
    except Exception:
        QtQuickWidgets = None

import os


_quick_ok = None


def quick_usable():
    """Qt Quick must draw with the same graphics API as FreeCAD's window (OpenGL).
    On Windows Qt 6 defaults to Direct3D, and the QML panels stay empty ("Failed
    to get a QRhi"): ask for OpenGL before the first QQuickWidget is created.  If
    that is no longer possible (created earlier by something else), the classic
    widget panels are used."""
    global _quick_ok
    if _quick_ok is None:
        _quick_ok = QtQuickWidgets is not None
        if _quick_ok:
            try:
                from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
                api = QSGRendererInterface.GraphicsApi
                if QQuickWindow.graphicsApi() not in (api.OpenGL, api.OpenGLRhi):
                    QQuickWindow.setGraphicsApi(api.OpenGL)
                _quick_ok = QQuickWindow.graphicsApi() in (api.OpenGL, api.OpenGLRhi)
            except Exception:
                pass                # PySide2 / Qt 5: always OpenGL
            if not _quick_ok:
                App.Console.PrintLog("ShowRoom: Qt Quick cannot use OpenGL here, using widget panels\n")
    return _quick_ok

PREFS = "User parameter:BaseApp/Preferences/Mod/ShowRoom"
_new = set()


# ------------------------------------------------------------------ theme (as in Plastic)
def _probe(cls, parent):
    """Font and (when the widget paints an opaque one) background colour of a FreeCAD widget
    as actually styled. Returns (colour or None, QFontInfo, text colour)."""
    w = cls(parent)
    try:
        w.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
        w.resize(48, 32)
        w.ensurePolished()
        info = QtGui.QFontInfo(w.font())
        img = QtGui.QImage(48, 32, QtGui.QImage.Format_ARGB32)
        img.fill(QtCore.Qt.transparent)
        w.render(img, QtCore.QPoint(), QtGui.QRegion(), QtWidgets.QWidget.DrawChildren)
        c = img.pixelColor(24, 24)
        return (c if c.alpha() == 255 else None), info, QtGui.QColor(w.palette().color(w.foregroundRole()))
    finally:
        w.deleteLater()


def make_theme():
    """Colours and font sizes matching the running FreeCAD theme."""
    pal = QtWidgets.QApplication.palette()
    try:
        pal = Gui.getMainWindow().palette()
    except Exception:
        pass
    win, txt = QtGui.QColor(pal.color(QtGui.QPalette.Window)), QtGui.QColor(pal.color(QtGui.QPalette.WindowText))
    base, accent = QtGui.QColor(pal.color(QtGui.QPalette.Base)), QtGui.QColor(pal.color(QtGui.QPalette.Highlight))
    font = QtGui.QFontInfo(QtWidgets.QApplication.font())
    try:
        mw = Gui.getMainWindow()
        bg, font, fg = _probe(QtWidgets.QLabel, mw)
        if bg is not None and abs(bg.lightness() - fg.lightness()) >= 80:
            win, txt = bg, fg          # stylesheet theme that paints its own backgrounds
        styled = _probe(QtWidgets.QLineEdit, mw)[0]
        if styled is not None:
            base = styled
    except Exception:
        pass
    if abs(txt.lightness() - win.lightness()) < 80:      # unreadable pair: fall back to contrast
        txt = QtGui.QColor("#f2f2f2" if win.lightness() < 128 else "#1a1a1a")
    try:
        raw = App.ParamGet("User parameter:BaseApp/Preferences/Themes").GetUnsigned("ThemeAccentColor1", 0)
        if raw:
            accent = QtGui.QColor((raw >> 24) & 255, (raw >> 16) & 255, (raw >> 8) & 255)
    except Exception:
        pass
    px = font.pixelSize() if font.pixelSize() > 0 else 13
    scale = max(0.9, px / 12.0) * max(0.5, App.ParamGet(PREFS).GetFloat("FontScale", 1.0))
    dark = win.lightness() < 128

    def mix(a, b, k):
        return QtGui.QColor(int(a.red() + (b.red() - a.red()) * k), int(a.green() + (b.green() - a.green()) * k),
                            int(a.blue() + (b.blue() - a.blue()) * k)).name()
    usable = abs(base.lightness() - win.lightness()) > 6 and abs(base.lightness() - txt.lightness()) >= 110
    field = base.name() if usable else mix(win, txt, 0.11)
    card = mix(win, QtGui.QColor("#000000" if dark else "#ffffff"), 0.30 if dark else 0.80)
    field = mix(QtGui.QColor(card), txt, 0.07 if not dark else 0.1)    # fields stand out on the cards
    return dict(dark=dark, window=win.name(), text=txt.name(), s=scale, family=font.family(),
                # sections a step lighter than the panel (darker on a dark theme)
                card=card, field=field, line=mix(win, txt, 0.22),
                muted=mix(win, txt, 0.6), wall=mix(win, txt, 0.3),
                accent=accent.name(), accentText="#ffffff" if accent.lightness() < 150 else "#101010",
                ok="#2e9e6b" if not dark else "#4cc38a", warn="#c98a12" if not dark else "#e6b043",
                bad="#d6453d" if not dark else "#f0736b",
                sectionStyle=App.ParamGet(PREFS).GetString("SectionStyle", "Flat"),
                bevelLight=mix(win, QtGui.QColor("#ffffff"), 0.85 if not dark else 0.25),
                bevelDark=mix(win, QtGui.QColor("#000000"), 0.2 if not dark else 0.5))


# ------------------------------------------------------------------------------- bridge
def _public(p):
    """The part of a parameter dict QML gets to see (no callables)."""
    out = dict(name=p["name"], label=p.get("label", p["name"]), kind=p["kind"],
               min=float(p.get("min", 0)), max=float(p.get("max", 100)), step=float(p.get("step", 1)),
               unit=p.get("unit", ""), tip=p.get("tip", ""), decimals=int(p.get("decimals", 2)),
               options=list(p.get("options", [])), special=p.get("special", ""),
               presets=list(p.get("presets", [])), browseLabel=p.get("browseLabel", "Browse…"),
               shadowLabel=p.get("shadowLabel", "Shadows"), slider=bool(p.get("slider", True)),
               readOnly=bool(p.get("readOnly", False)), button=p.get("button", ""),
               action=p.get("action", ""), fx=p.get("fx", ""), components=list(p.get("components", [])))
    labels = list(p.get("optionLabels", out["options"]))
    # an enumeration with more values than labels (a file from an older version)
    out["optionLabels"] = [labels[i] if i < len(labels) else str(o) for i, o in enumerate(out["options"])]
    return out


class Bridge(QtCore.QObject):
    valuesChanged = QtCore.Signal()
    feedbackChanged = QtCore.Signal()
    stateChanged = QtCore.Signal()
    sectionsChanged = QtCore.Signal()
    heightChanged = QtCore.Signal(float)
    handOver = QtCore.Signal(object)        # ("close",) or ("edit", obj)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self._error = ""
        self._closed = False
        self._collapsed = {}
        self._theme = make_theme()
        self._build()
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(30)
        self._refresh_timer.timeout.connect(self.refresh)
        self._observer = _DocObserver(self)
        App.addDocumentObserver(self._observer)

    def _build(self):
        self._params = {}
        sections, index = [], {}
        for p in self.model.params():
            self._params[p["name"]] = p
            title = p.get("section", "")
            if title not in index:
                index[title] = dict(title=title, params=[],
                                    collapsed=self._collapsed.get(title, bool(p.get("collapsed", False))))
                sections.append(index[title])
            index[title]["params"].append(_public(p))
        self._sections = sections
        self._structure = self.model.structure()

    def alive(self):
        if self._closed:
            return False
        try:
            return self.model.alive()
        except Exception:
            return False

    def _safe(self, fn, default):
        if not self.alive():
            return default
        try:
            return fn()
        except Exception:
            return default

    # -- properties read by QML ------------------------------------------------------------
    def _get_values(self):
        out = {}
        if not self.alive():
            return out
        for name, p in self._params.items():
            if "get" in p:
                try:
                    out[name] = p["get"]()
                except Exception:
                    pass
        return out

    sections = QtCore.Property("QVariant", lambda self: self._sections, notify=sectionsChanged)
    theme = QtCore.Property("QVariant", lambda self: self._theme, constant=True)
    title = QtCore.Property(str, lambda self: self.model.title, notify=stateChanged)
    iconUrl = QtCore.Property(str, lambda self: QtCore.QUrl.fromLocalFile(self.model.icon).toString()
                              if self.model.icon else "", notify=stateChanged)
    subtitle = QtCore.Property(str, lambda self: self._safe(self.model.subtitle, ""), notify=stateChanged)
    values = QtCore.Property("QVariant", _get_values, notify=valuesChanged)
    hidden = QtCore.Property("QVariant", lambda self: self._safe(self.model.hidden, []), notify=valuesChanged)
    info = QtCore.Property("QVariant", lambda self: self._safe(self.model.info, []), notify=feedbackChanged)
    actions = QtCore.Property("QVariant", lambda self: self._safe(self.model.actions, []), notify=stateChanged)
    activeActions = QtCore.Property("QVariant", lambda self: self._safe(self.model.active_actions, []),
                                    notify=stateChanged)
    galleries = QtCore.Property("QVariant", lambda self: self._safe(self.model.galleries, {}),
                                notify=valuesChanged)
    hint = QtCore.Property(str, lambda self: self._safe(self.model.hint, ""), notify=stateChanged)
    error = QtCore.Property(str, lambda self: self._error, notify=stateChanged)
    searchable = QtCore.Property(bool, lambda self: bool(getattr(self.model, "searchable", False)),
                                 constant=True)

    # -- slots -----------------------------------------------------------------------------
    @QtCore.Slot(float)
    def setContentHeight(self, h):
        self.heightChanged.emit(h)

    @QtCore.Slot(str, "QVariant")
    def setValue(self, name, value):
        if not self.alive():
            return
        base, _, field = name.partition("/")
        p = self._params.get(base)
        if p is None or "set" not in p:
            return
        try:
            if p["kind"] == "int" or p.get("cast") == "int":
                value = int(round(float(value)))
            elif p["kind"] in ("number", "compass"):
                value = float(value)
                if "hardMin" in p:
                    value = max(p["hardMin"], value)
                if "hardMax" in p:
                    value = min(p["hardMax"], value)
            elif p["kind"] == "bool":
                value = bool(value)
            elif p["kind"] == "vector":
                value = [float(v) for v in value]
            p["set"](value, field) if field else p["set"](value)
            self._error = ""
        except Exception as exc:
            self._error = str(exc)
        self.refresh()

    @QtCore.Slot(str, bool)
    def setCollapsed(self, title, collapsed):
        self._collapsed[title] = collapsed

    @QtCore.Slot(str)
    def setFilter(self, text):
        self.model.filter = text
        self.valuesChanged.emit()

    @QtCore.Slot(str)
    def pickColor(self, name):
        p = self._params.get(name)
        if p is None or not self.alive():
            return
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(p["get"]()), Gui.getMainWindow(),
                                                p.get("label", ""))
        if color.isValid():
            self.setValue(name, color.name())

    @QtCore.Slot(str)
    def trigger(self, action):
        if not self.alive():
            return
        try:
            if action.startswith("browse:"):
                result = self.model.browse(action[7:])
            elif action.startswith("edit:"):
                result = self.model.edit(action[5:])
            else:
                result = self.model.trigger(action)
            self._error = ""
        except Exception as exc:
            self._error = str(exc)
            result = None
        if result:
            self.handOver.emit(result)
            return
        self.refresh()

    # -- updates ---------------------------------------------------------------------------
    def schedule_refresh(self):
        if not self._closed:
            self._refresh_timer.start()

    def refresh(self):
        if not self.alive():
            return
        try:
            structure = self.model.structure()
        except Exception:
            structure = self._structure
        if structure != self._structure:
            self._build()
            self.sectionsChanged.emit()
        self.valuesChanged.emit()
        self.feedbackChanged.emit()
        self.stateChanged.emit()

    def stop(self):
        if self._closed:
            return
        self._closed = True
        try:
            App.removeDocumentObserver(self._observer)
        except Exception:
            pass
        try:
            self._refresh_timer.stop()
        except RuntimeError:
            pass


class _DocObserver:
    """Refresh the panel when what it shows changes elsewhere (gizmo, property editor, undo)."""

    def __init__(self, bridge):
        self.bridge = bridge

    def _touch(self, doc):
        try:
            if doc is self.bridge.model.doc or doc.Name == self.bridge.model.doc.Name:
                self.bridge.schedule_refresh()
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        try:
            if obj in self.bridge.model.watched():
                self.bridge.schedule_refresh()
        except Exception:
            pass

    def slotCreatedObject(self, obj):
        self._touch(obj.Document)

    def slotDeletedObject(self, obj):
        self._touch(obj.Document)


# ------------------------------------------------------------------------------ QML form
def _qml_widget(bridge):
    if not App.ParamGet(PREFS).GetBool("UseQml", True) or not quick_usable():
        return None
    try:
        view = QtQuickWidgets.QQuickWidget()
        view.setResizeMode(QtQuickWidgets.QQuickWidget.SizeRootObjectToView)
        view.setClearColor(QtGui.QColor(bridge.theme["window"]))
        view.rootContext().setContextProperty("bridge", bridge)
        view.setSource(QtCore.QUrl.fromLocalFile(os.path.join(QML, "TaskPanel.qml")))
        if view.status() != QtQuickWidgets.QQuickWidget.Ready:
            for err in view.errors():
                App.Console.PrintWarning("ShowRoom QML: %s\n" % err.toString())
            view.deleteLater()
            return None
    except Exception as exc:
        App.Console.PrintWarning("ShowRoom: QML panel unavailable (%s), using widgets\n" % exc)
        return None
    view.setMinimumWidth(int(260 * bridge.theme["s"]))
    # The bridge must outlive the QML scene: as a child of the view it is destroyed after the
    # root item, so bindings never see a null "bridge" while the panel closes.
    bridge.setParent(view)
    # Never resize from inside a QML binding: that re-enters the renderer in the middle of a frame.
    pending = {"h": int(view.rootObject().property("contentHeight") or 400) + 2}
    timer = QtCore.QTimer(view)
    timer.setSingleShot(True)
    timer.setInterval(0)

    def apply():
        if view.height() != pending["h"]:
            view.setFixedHeight(pending["h"])

    def request(h):
        pending["h"] = int(h) + 2
        timer.start()
    timer.timeout.connect(apply)
    bridge.heightChanged.connect(request)
    view.setFixedHeight(pending["h"])
    return view


# ------------------------------------------------------------------------ widget fallback
class _WidgetForm(QtWidgets.QWidget):
    """Qt Widgets fallback with the same content as the QML panel."""

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.lay = QtWidgets.QVBoxLayout(self)
        self.hint = QtWidgets.QLabel()
        self.hint.setWordWrap(True)
        self.lay.addWidget(self.hint)
        row = QtWidgets.QHBoxLayout()
        self.buttons = row
        self.lay.addLayout(row)
        self.body = QtWidgets.QWidget()
        self.lay.addWidget(self.body)
        self.info = QtWidgets.QLabel()
        self.info.setTextFormat(QtCore.Qt.RichText)
        self.lay.addWidget(self.info)
        self.err = QtWidgets.QLabel()
        self.err.setWordWrap(True)
        self.err.setStyleSheet("color:#e05a52")
        self.lay.addWidget(self.err)
        self.lay.addStretch(1)
        bridge.valuesChanged.connect(self.sync)
        bridge.feedbackChanged.connect(self.sync_info)
        bridge.stateChanged.connect(self.sync_info)
        bridge.sectionsChanged.connect(self.rebuild)
        self.rebuild()

    def rebuild(self):
        while self.buttons.count():
            item = self.buttons.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for a in self.bridge.actions:
            b = QtWidgets.QPushButton(a["label"])
            b.clicked.connect(lambda _=False, n=a["name"]: self.bridge.trigger(n))
            self.buttons.addWidget(b)
        old = self.body
        self.body = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(self.body)
        lay.setContentsMargins(0, 0, 0, 0)
        self.editors = {}
        for sec in self.bridge.sections:
            box = QtWidgets.QGroupBox(sec["title"])
            form = QtWidgets.QFormLayout(box)
            for p in sec["params"]:
                w = self._editor(p)
                w.setToolTip(p["tip"])
                self.editors[p["name"]] = (p, w)
                if p["kind"] in ("note", "light", "gallery"):
                    form.addRow(w)
                else:
                    form.addRow(p["label"], w)
            lay.addWidget(box)
        self.lay.replaceWidget(old, self.body)
        old.deleteLater()
        self.sync()
        self.sync_info()

    def _editor(self, p):
        name, kind, b = p["name"], p["kind"], self.bridge
        if kind == "bool":
            w = QtWidgets.QCheckBox()
            w.toggled.connect(lambda v: b.setValue(name, v))
        elif kind == "enum":
            w = QtWidgets.QComboBox()
            for o, l in zip(p["options"], p["optionLabels"]):
                w.addItem(l, o)
            w.activated.connect(lambda i: b.setValue(name, w.itemData(i)))
        elif kind == "int":
            w = QtWidgets.QSpinBox()
            w.setRange(int(p["min"]), int(p["max"]))
            w.valueChanged.connect(lambda v: b.setValue(name, v))
        elif kind == "color":
            w = QtWidgets.QPushButton()
            w.clicked.connect(lambda: b.pickColor(name))
        elif kind == "vector":
            w = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            w.spins = []
            for i in range(3):
                s = QtWidgets.QDoubleSpinBox()
                s.setRange(-1e7, 1e7)
                s.setDecimals(p["decimals"])
                s.editingFinished.connect(lambda: b.setValue(name, [x.value() for x in w.spins]))
                h.addWidget(s)
                w.spins.append(s)
        elif kind == "gallery":
            w = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            w.combo = QtWidgets.QComboBox()
            w.combo.activated.connect(lambda i: b.setValue(name, w.combo.itemData(i)))
            browse = QtWidgets.QPushButton(p["browseLabel"])
            browse.clicked.connect(lambda: b.trigger("browse:" + name))
            h.addWidget(w.combo, 1)
            h.addWidget(browse)
        elif kind == "light":
            w = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            w.on = QtWidgets.QCheckBox(p["label"])
            w.on.toggled.connect(lambda v: b.setValue(name + "/on", v))
            w.intensity = QtWidgets.QDoubleSpinBox()
            w.intensity.setRange(0, 1)
            w.intensity.setSingleStep(0.05)
            w.intensity.valueChanged.connect(lambda v: b.setValue(name + "/intensity", v))
            w.cast = QtWidgets.QCheckBox(p["shadowLabel"])
            w.cast.toggled.connect(lambda v: b.setValue(name + "/cast", v))
            edit = QtWidgets.QPushButton("…")
            edit.clicked.connect(lambda: b.trigger("edit:" + name))
            for x in (w.on, w.intensity, w.cast, edit):
                h.addWidget(x)
        elif kind == "note":
            w = QtWidgets.QLabel(p["label"])
            w.setWordWrap(True)
        else:
            w = QtWidgets.QDoubleSpinBox()
            w.setDecimals(p["decimals"])
            w.setRange(-1e7, 1e7)
            w.setSingleStep(p["step"])
            w.setSuffix(" " + p["unit"] if p["unit"] else "")
            if p["special"]:
                w.setSpecialValueText(p["special"])
                w.setMinimum(0)
            w.valueChanged.connect(lambda v: b.setValue(name, v))
        return w

    def sync(self):
        values, hidden = self.bridge.values, self.bridge.hidden
        galleries = self.bridge.galleries
        for name, (p, w) in self.editors.items():
            v = values.get(name)
            w.blockSignals(True)
            try:
                kind = p["kind"]
                if kind == "bool":
                    w.setChecked(bool(v))
                elif kind == "enum":
                    w.setCurrentIndex(max(0, w.findData(v)))
                elif kind == "color":
                    w.setStyleSheet("background:%s" % v)
                elif kind == "vector" and v is not None:
                    for s, x in zip(w.spins, v):
                        s.blockSignals(True)
                        s.setValue(x)
                        s.blockSignals(False)
                elif kind == "gallery":
                    w.combo.blockSignals(True)
                    w.combo.clear()
                    for item in galleries.get(name, []):
                        w.combo.addItem(item["label"], item["name"])
                    w.combo.setCurrentIndex(max(0, w.combo.findData(v)))
                    w.combo.blockSignals(False)
                elif kind == "light" and v:
                    for x, val in ((w.on, v["on"]), (w.cast, v["cast"])):
                        x.blockSignals(True)
                        x.setChecked(bool(val))
                        x.blockSignals(False)
                    w.cast.setVisible(bool(v["canCast"]))
                    w.intensity.blockSignals(True)
                    w.intensity.setValue(v["intensity"])
                    w.intensity.blockSignals(False)
                elif kind not in ("note",) and v is not None:
                    w.setValue(v)
            finally:
                w.blockSignals(False)
            w.setVisible(name not in hidden)

    def sync_info(self):
        colors = {"ok": "#3fb27f", "warn": "#e0a030", "bad": "#e05a52"}
        rows = ["<tr><td>%s&nbsp;&nbsp;</td><td style='color:%s'><b>%s</b></td></tr>"
                % (i["label"], colors.get(i["status"], "inherit"), i["value"]) for i in self.bridge.info]
        self.info.setText("<table>%s</table>" % "".join(rows))
        self.hint.setText(self.bridge.hint)
        self.err.setText(self.bridge.error)


# ---------------------------------------------------------------------------- task panel
class TaskPanel:
    def __init__(self, model, created):
        self.model = model
        self.doc = model.doc
        self.created = created
        self.bridge = Bridge(model)
        self.form = _qml_widget(self.bridge) or _WidgetForm(self.bridge)
        self.is_qml = not isinstance(self.form, _WidgetForm)
        if not self.is_qml:
            self.bridge.setParent(self.form)
        self.form.setWindowTitle(model.title)
        self.form.setWindowIcon(QtGui.QIcon(model.icon))
        self.bridge.handOver.connect(self._hand_over)
        self._done = False

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True

    def isAllowedAlterDocument(self):
        return True

    def _leave_edit(self):
        if self.model.edited is None:
            return
        try:
            gdoc = Gui.getDocument(self.doc.Name)
            if gdoc.getInEdit() is not None:
                gdoc.resetEdit()
        except Exception:
            pass

    def accept(self):
        if self._done:
            return True
        self._done = True
        self.bridge.stop()
        try:
            self.model.on_close(True)
        except Exception:
            pass
        self.doc.commitTransaction()
        self._leave_edit()
        self.doc.recompute()
        return True

    def reject(self):
        if self._done:
            return True
        self._done = True
        self.bridge.stop()
        try:
            self.model.on_close(False)
        except Exception:
            pass
        # abort before leaving edit mode: resetEdit() would commit the open transaction
        self.doc.abortTransaction()
        self._leave_edit()
        self.doc.recompute()
        return True

    def _hand_over(self, result):
        """An action asked to close the panel (keeping the changes), maybe to edit something else."""
        def go():
            self.accept()
            Gui.Control.closeDialog()
            if result[0] == "edit":
                QtCore.QTimer.singleShot(0, lambda: edit(result[1]))
        QtCore.QTimer.singleShot(0, go)


_current = [None]


def current():
    """The open ShowRoom panel (for tests and scripts)."""
    panel = _current[0]
    if panel is not None and not panel._done:
        return panel
    return None


def mark_new(obj):
    """``obj`` was just created in an open transaction: Cancel will delete it."""
    _new.add((obj.Document.Name, obj.Name))


def open_panel(model, created=False):
    """Show the task panel of ``model``; one transaction for the whole session."""
    if not created:
        model.doc.openTransaction(model.transaction)
    panel = TaskPanel(model, created)
    _current[0] = panel
    Gui.Control.showDialog(panel)
    return panel


def show_for(obj):
    """Open the panel of one of our objects (called by its view provider's setEdit)."""
    from dtpanels import models
    key = (obj.Document.Name, obj.Name)
    created = key in _new
    _new.discard(key)
    model = models.model_for(obj)
    if model is None:
        return None
    return open_panel(model, created)


def edit(obj):
    """Put one of our objects in edit mode, as a double click in the tree does."""
    if Gui.Control.activeDialog():
        App.Console.PrintWarning("ShowRoom: close the open task panel first.\n")
        return False
    gdoc = Gui.getDocument(obj.Document.Name)
    gdoc.setEdit(obj, 0)
    return True
