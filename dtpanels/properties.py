# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""Data / View properties of the selected object as a ShowRoom panel model.

Every property becomes a row of the shared QML panel (bridge.py): switches,
choices, numbers with units, colours, text.  What has no row of its own
(placement, links, vectors, materials...) or is bound to an expression is shown
as text with an "Edit" button that opens FreeCAD's own property editor."""
import os
import re
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from dtpanels.models import Model, hex_color, rgb

UNITS = {'Length': 'mm', 'Distance': 'mm', 'Angle': '°', 'Area': 'mm²', 'Volume': 'mm³',
         'Speed': 'mm/s', 'Force': 'N', 'Pressure': 'MPa', 'Acceleration': 'mm/s²', 'Mass': 'kg'}
_ICONS = {}

# small stroke icons telling the kind of each row (property editor, table rows)
KIND_ICONS = {
    'toggle': 'M3 7h18v10H3z M16 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0',
    'choice': 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
    'length': 'M3 15l12-12 6 6-12 12zM7 11l2 2M10 8l2 2M13 5l2 2',
    'angle': 'M4 20h16M4 20L16 6M10 20a7 7 0 0 0-2-5',
    'number': 'M9 4L7 20M17 4l-2 16M4 9h16M3 15h16',
    'text': 'M4 18L9 6l5 12M6 14h6M15 18v-6a2 2 0 0 1 4 0v6M15 15h4',
    'color': 'M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z',
    'link': 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
    'place': 'M12 12V4M12 12l7 4M12 12l-7 4',
    'shape': 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5',
    'more': 'M5 12h.01M12 12h.01M19 12h.01',
}
_KIND_URLS = {}


def _icon(kind):
    if kind not in _KIND_URLS:
        import base64
        try:
            from dtpanels.bridge import make_theme
            color = make_theme()['muted']
        except Exception:
            color = '#8a91a0'
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="48" height="48" '
               'fill="none" stroke="%s" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="%s"/></svg>' % (color, KIND_ICONS[kind]))
        _KIND_URLS[kind] = 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()
    return _KIND_URLS[kind]


def _icon_kind(ptype, row):
    kind = ptype.split('::')[-1].replace('Property', '')
    if 'Link' in kind:
        return 'link'
    if row['name'].endswith('@color') or kind == 'Color':
        return 'color'
    if kind in ('Bool',):
        return 'toggle'
    if kind == 'Enumeration':
        return 'choice'
    if kind == 'Angle' or row.get('unit') == '°':
        return 'angle'
    if kind in ('Length', 'Distance', 'Area', 'Volume') or row.get('unit') == 'mm':
        return 'length'
    if row.get('kind') == 'vector':
        return 'place'
    if row.get('kind') == 'number':
        return 'number'
    if kind in ('String', 'Font'):
        return 'text'
    if 'Shape' in kind:
        return 'shape'
    if ptype.startswith('Materials::'):
        return 'color'
    return 'more'


def _words(name):
    """FreeCAD shows 'ShapeAppearance' as 'Shape Appearance'."""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', name)


def _icon_file(obj):
    """The tree icon of ``obj`` as a PNG file (QML needs a URL)."""
    key = obj.TypeId + getattr(getattr(obj, 'Proxy', None), '__class__', type(None)).__name__
    if key in _ICONS:
        return _ICONS[key]
    path = ''
    try:
        from PySide import QtGui
        icon = obj.ViewObject.Icon if obj.ViewObject else QtGui.QIcon()
        if not icon.isNull():
            path = os.path.join(tempfile.gettempdir(), 'showroom_icon_%d.png' % (abs(hash(key)) % 10 ** 8))
            icon.pixmap(64, 64).save(path)
    except Exception:
        path = ''
    _ICONS[key] = path
    return path


class PropertiesModel(Model):
    """The properties of ``target`` (Data) or of its view provider (View)."""
    transaction = 'Edit property'
    searchable = True
    table = True            # the "table" rows of this editor (Settings, Properties panel)
    filter = ''

    def __init__(self):
        super().__init__(None)
        from Utils import prefs
        self.table = prefs.get('TableRows')
        self.target = None
        self.tab = 'Data'
        self.open_native = None         # callback(name) from the floating panel
        self.on_change = None           # callback after an expression was edited
        self.reselecting = False        # True while _reselect puts the selection back
        self._fx = None
        self.title = 'Nothing selected'
        self.icon = ''
        self._last = []

    # ------------------------------------------------------------------ target
    def set_target(self, obj, tab=None):
        self.target = obj
        if tab:
            self.tab = tab
        self.doc = obj.Document if obj is not None else None
        self.title = obj.Label if obj is not None else 'Nothing selected'
        self.icon = _icon_file(obj) if obj is not None else ''

    def container(self):
        obj = self.target
        if obj is None:
            return None
        return obj.ViewObject if self.tab == 'View' else obj

    def alive(self):
        return True

    def watched(self):
        return [self.target] if self.target is not None else []

    def subtitle(self):
        obj = self.target
        if obj is None:
            return 'Select an object in the tree or in the 3D view'
        return '%s · %s' % (obj.TypeId, self.tab)

    def _visible(self):
        c = self.container()
        if c is None:
            return []
        out = []
        for name in c.PropertiesList:
            try:
                mode = c.getEditorMode(name)
            except Exception:
                mode = []
            if 'Hidden' in mode:
                continue
            if name in ('ExpressionEngine', 'Proxy', 'Visibility') and self.tab == 'Data':
                continue
            out.append((name, 'ReadOnly' in mode))
        return out

    def hidden(self):
        text = self.filter.strip().lower()
        if not text:
            return []
        return [p['name'] for p in self._last if text not in p['label'].lower()
                and text not in p['name'].lower() and text not in p.get('section', '').lower()]

    def structure(self):
        return (id(self.target), self.tab, tuple(self._visible()),
                tuple(sorted(dict(getattr(self.target, 'ExpressionEngine', []) or []).keys()))
                if self.target is not None else ())

    # ------------------------------------------------------------------ rows
    def params(self):
        c = self.container()
        if c is None:
            return [dict(name='_none', label='Select an object to see its properties.', kind='note',
                         section='')]
        bound = dict(getattr(self.target, 'ExpressionEngine', []) or []) if self.tab == 'Data' else {}
        out = []
        for name, readonly in self._visible():
            try:
                group = c.getGroupOfProperty(name) or 'Base'
                ptype = c.getTypeIdOfProperty(name)
                tip = c.getDocumentationOfProperty(name)
            except Exception:
                continue
            expr = bound.get(name)
            if expr is None and any(k.startswith(name + '.') for k in bound):
                expr = '…'
            if ptype == 'App::PropertyPlacement' and expr is None and not readonly:
                out += [dict(r, icon=_icon('place')) for r in self._placement(c, name, group, tip)]
                continue
            row = self._row(c, name, _words(name), ptype, group, tip, readonly, expr)
            for r in row if isinstance(row, list) else [row]:
                r.setdefault('icon', _icon(_icon_kind(ptype, r)))
                if 'Link' in ptype and r.get('kind') == 'enum':
                    r['isLink'] = True
                out.append(r)
        self._last = out
        return out

    def _placement(self, c, name, group, tip):
        """Position and rotation (yaw, pitch, roll) on two compact rows."""
        doc = self.target.Document

        def edit(fn, label):
            def setter(v):
                pl = getattr(c, name)
                new = fn(pl, [float(x) for x in v])
                if new.isSame(pl, 1e-9) if hasattr(new, 'isSame') else new == pl:
                    return
                doc.openTransaction('Edit %s' % label)
                try:
                    setattr(c, name, new)
                finally:
                    doc.commitTransaction()
                doc.recompute()
            return setter

        def pos(pl, v):
            return App.Placement(App.Vector(*v), pl.Rotation)

        def rot(pl, v):
            r = App.Rotation()
            r.setYawPitchRoll(*v)
            return App.Placement(pl.Base, r)

        base = dict(section=group, tip=tip, kind='vector')
        label = _words(name)
        return [dict(base, name=name + '@pos', label='%s · position (mm)' % label, decimals=2,
                     get=lambda: list(getattr(c, name).Base), set=edit(pos, label)),
                dict(base, name=name + '@rot', label='%s · rotation (°)' % label, decimals=2,
                     components=['Yaw', 'Pitch', 'Roll'],
                     get=lambda: list(getattr(c, name).Rotation.getYawPitchRoll()),
                     set=edit(rot, label))]

    def _row(self, c, name, label, ptype, group, tip, readonly, expression):
        base = dict(name=name, label=label, section=group, tip=tip)
        kind = ptype.split('::')[-1].replace('Property', '')

        def native(text):
            return dict(base, kind='native', get=text, action='native:' + name,
                        readOnly=True, button='Edit')

        if expression is not None:
            row = native(lambda: '= %s' % expression)
            if expression != '…':
                row.update(button='fx', action='fx:' + name)
            return row
        if readonly:
            return dict(base, kind='text', readOnly=True, get=lambda: self._text(c, name))
        doc = self.target.Document

        def put(convert=lambda v: v):
            def setter(v):
                v = convert(v)
                if getattr(c, name) == v:
                    return
                self._undoable(doc, (id(c), name), 'Edit %s' % label, lambda: setattr(c, name, v))
                if self.tab == 'Data':
                    doc.recompute()
            return setter

        if kind == 'Bool':
            return dict(base, kind='bool', get=lambda: bool(getattr(c, name)), set=put())
        if kind == 'Enumeration':
            return dict(base, kind='enum', get=lambda: str(getattr(c, name)), set=put(),
                        options=list(c.getEnumerationsOfProperty(name) or []))
        if kind == 'Percent':
            return dict(base, kind='number', get=lambda: float(getattr(c, name)), set=put(int),
                        min=0, max=100, step=1, decimals=0, unit='%', hardMin=0, hardMax=100)
        if kind in ('Integer', 'IntegerConstraint'):
            return dict(base, kind='number', get=lambda: float(getattr(c, name)), set=put(int),
                        decimals=0, step=1, slider=False)
        if kind in ('Float', 'FloatConstraint', 'Precision') or kind in UNITS or kind == 'Quantity' \
                or kind.startswith('Quantity'):
            unit = UNITS.get(kind, '')

            def get():
                v = getattr(c, name)
                return float(getattr(v, 'Value', v))
            return dict(base, kind='number', get=get, set=put(float), decimals=3 if not unit else 2,
                        step=1, unit=unit, slider=False, fx='fx:' + name if self.tab == 'Data' else '')
        if kind == 'Color':
            return dict(base, kind='color', get=lambda: hex_color(getattr(c, name)),
                        set=put(rgb), presets=[])
        if kind in ('String', 'Font'):
            return dict(base, kind='text', get=lambda: str(getattr(c, name)), set=put(str))
        if kind in ('Vector', 'VectorDistance', 'Position', 'Direction'):
            return dict(base, kind='vector', decimals=3 if kind == 'Direction' else 2,
                        get=lambda: list(getattr(c, name)),
                        set=put(lambda v: App.Vector(*[float(x) for x in v])))
        if ptype.startswith('Materials::'):
            # the physical material (steel, PLA...): its name, then the colour the
            # object is shown with (Shape Appearance of the view)
            rows = [dict(base, kind='native', readOnly=True, button='Edit', action='native:' + name,
                         get=lambda: getattr(getattr(c, name), 'Name', '') or '')]
            vo = self._appearance_owner()
            if vo is not None and 'ShapeAppearance' in vo.PropertiesList:
                rows += self._material(vo, 'ShapeAppearance', 'Appearance', dict(base), True,
                                       self._putter(vo, 'Appearance', recompute=False),
                                       transparency=False)
            if vo is not None and 'Transparency' in vo.PropertiesList:
                # the View tab's own Transparency, here too to save a click
                put_view = self._putter(vo, 'Transparency', recompute=False)

                def to_int(v):
                    return int(round(float(v)))
                setter = put_view(to_int)
                setter.name = 'Transparency'
                rows.append(dict(base, name='View@Transparency', label='Transparency', kind='number',
                                 min=0, max=100, step=1, decimals=0, unit='%', hardMin=0, hardMax=100,
                                 get=lambda: float(vo.Transparency), set=setter))
            return rows
        if kind in ('Material', 'MaterialList'):
            # the material's transparency only where the view has no Transparency of its own
            return self._material(c, name, label, base, kind == 'MaterialList', put,
                                  transparency='Transparency' not in c.PropertiesList)
        if kind in ('Link', 'LinkChild', 'LinkGlobal', 'LinkHidden'):
            objs = [o for o in doc.Objects if o is not self.target]

            def get_link():
                v = getattr(c, name)
                return v.Name if v is not None else ''

            def to_obj(v):
                return doc.getObject(v) if v else None
            return dict(base, kind='enum', get=get_link, set=put(to_obj),
                        options=[''] + [o.Name for o in objs],
                        optionLabels=['(none)'] + [o.Label for o in objs])
        if kind == 'PartShape' or ptype.endswith('PropertyPartShape'):
            return dict(base, kind='text', readOnly=True, get=lambda: self._text(c, name))
        return native(lambda: self._text(c, name))

    def _rehighlight(self):
        """FreeCAD keeps the colours of a selected object (or face) in its
        selection highlight until the selection changes: a new appearance would
        only show after the next click in the view.  Selecting the same things
        again, once the edits pause, shows it at once."""
        from PySide import QtCore
        if getattr(self, '_highlight', None) is None:
            self._highlight = QtCore.QTimer()
            self._highlight.setSingleShot(True)
            self._highlight.setInterval(250)
            self._highlight.timeout.connect(self._reselect)
        self._highlight.start()

    def _reselect(self):
        sel = Gui.Selection.getSelectionEx('', 0)
        if not sel:
            return
        picks = [(s.DocumentName, s.ObjectName, list(s.SubElementNames)) for s in sel]
        self.reselecting = True
        try:
            Gui.Selection.clearSelection()
            for doc_name, obj_name, subs in picks:
                if subs:
                    for sub in subs:
                        Gui.Selection.addSelection(doc_name, obj_name, sub)
                else:
                    Gui.Selection.addSelection(doc_name, obj_name)
        finally:
            self.reselecting = False

    def _undoable(self, doc, key, title, change):
        """One undo step for a burst of changes to the same property (a slider
        being dragged): the first opens it, those within a second follow it."""
        import time
        now = time.monotonic()
        last = getattr(self, '_last_edit', (None, 0.0))
        self._last_edit = (key, now)
        if last[0] == key and now - last[1] < 1.0:
            change()
        else:
            doc.openTransaction(title)
            try:
                change()
            finally:
                doc.commitTransaction()
        if self.tab == 'View' or key[1] in ('ShapeAppearance', 'Transparency'):
            self._rehighlight()

    def _appearance_owner(self):
        """The view provider that really shows the target's colour: a feature
        inside a Body has its appearance hidden and follows the Body's."""
        obj = self.target
        vo = getattr(obj, 'ViewObject', None)
        try:
            if vo is not None and 'Hidden' in vo.getEditorMode('ShapeAppearance'):
                parent = obj.getParentGeoFeatureGroup()
                pvo = getattr(parent, 'ViewObject', None)
                if pvo is not None and 'ShapeAppearance' in pvo.PropertiesList:
                    return pvo
        except Exception:
            pass
        return vo

    def _putter(self, c, label, recompute):
        doc = self.target.Document

        def put(convert=lambda v: v):
            def setter(v):
                v = convert(v)
                self._undoable(doc, (id(c), setter.name), 'Edit %s' % label,
                               lambda: setattr(c, setter.name, v))
                if recompute:
                    doc.recompute()
            return setter
        return put

    def _material(self, c, name, label, base, many, put, transparency=True):
        """Colour (with quick picks) and shininess of a material; for a list (Shape
        Appearance) the change goes to every face."""
        from dtpanels.models import SHAPE_COLORS, LINE_COLORS
        presets = SHAPE_COLORS if 'Shape' in name else LINE_COLORS

        def first():
            v = getattr(c, name)
            return v[0] if many else v

        def change(field, value):
            mats = [m for m in getattr(c, name)] if many else [getattr(c, name)]
            for m in mats:
                if field == 'DiffuseColor':
                    alpha = m.DiffuseColor[3] if len(m.DiffuseColor) > 3 else 1.0
                    m.DiffuseColor = rgb(value) + (alpha,)
                else:
                    setattr(m, field, float(value))
            return mats if many else mats[0]

        def setter(field, scale=1.0):
            raw = put(lambda v: change(field, float(v) / scale if field != 'DiffuseColor' else v))
            raw.name = name

            def go(v):
                current = first()
                if field == 'DiffuseColor':
                    if hex_color(current.DiffuseColor) == v:
                        return
                elif abs(float(getattr(current, field)) * scale - float(v)) < 1e-6:
                    return
                raw(v)
            return go
        pre = '' if name == 'ShapeAppearance' else label.replace(' Material', '') + ' '

        def lab(word):
            text = pre + word
            return text[0].upper() + text[1:]
        return [dict(base, name=name + '@color', label=lab('color'), kind='color', presets=presets,
                     get=lambda: hex_color(first().DiffuseColor), set=setter('DiffuseColor')),
                dict(base, name=name + '@shine', label=lab('shininess'), kind='number',
                     min=0, max=1, step=0.05, decimals=2, hardMin=0, hardMax=1,
                     get=lambda: float(first().Shininess), set=setter('Shininess'))] + ([
                dict(base, name=name + '@transp', label=lab('transparency'), kind='number',
                     min=0, max=100, step=1, decimals=0, unit='%', hardMin=0, hardMax=100,
                     get=lambda: float(first().Transparency) * 100, set=setter('Transparency', 100.0))]
                if transparency else [])

    def _text(self, c, name):
        try:
            v = getattr(c, name)
        except Exception:
            return ''
        if hasattr(v, 'Label'):
            return v.Label
        if isinstance(v, (list, tuple)) and v and hasattr(v[0], 'Label'):
            return ', '.join(o.Label for o in v[:4]) + (' …' if len(v) > 4 else '')
        if hasattr(v, 'Base') and hasattr(v, 'Rotation'):
            b = v.Base
            return '(%.2f, %.2f, %.2f) mm' % (b.x, b.y, b.z)
        if hasattr(v, 'x') and hasattr(v, 'z'):
            return '(%.3g, %.3g, %.3g)' % (v.x, v.y, v.z)
        if isinstance(v, (list, tuple)) and len(v) > 1:
            return '%d values' % len(v)
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        text = str(getattr(v, 'UserString', v))
        if ' at 0x' in text or (text.startswith('<') and text.endswith('>')):
            return _words(type(v).__name__.replace('Py', ''))
        return text if len(text) < 60 else text[:57] + '…'

    def trigger(self, action):
        if action.startswith('native:') and self.open_native is not None:
            self.open_native(action[7:])
        elif action.startswith('fx:'):
            self._expression(action[3:])
        return None

    def _expression(self, name):
        """FreeCAD's own expression editor (with its suggestions), opened on the
        property: a bound QuantitySpinBox under the mouse receives "=" like a user
        typing it, and the result is applied as one undo step."""
        from PySide import QtCore, QtGui, QtWidgets
        obj = self.target
        mw = Gui.getMainWindow()
        box = Gui.UiLoader().createWidget('Gui::QuantitySpinBox', mw)
        binding = Gui.ExpressionBinding(box)
        binding.bind(obj, name)
        binding.setAutoApply(False)
        pos = mw.mapFromGlobal(QtGui.QCursor.pos())
        box.setGeometry(pos.x(), pos.y(), 1, 1)     # a dot under the mouse: the dialog opens there
        box.show()
        box.setFocus()
        QtWidgets.QApplication.sendEvent(box, QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, QtCore.Qt.Key_Equal, QtCore.Qt.NoModifier, '='))
        dialogs = [w for w in box.findChildren(QtWidgets.QDialog)
                   if w.metaObject().className().endswith('DlgExpressionInput')]
        self._fx = (box, binding)               # alive while the dialog is open

        before = dict(obj.ExpressionEngine or []).get(name)

        def done():
            """The dialog closed: hand what the spin box got to the property."""
            try:
                doc = obj.Document
                doc.openTransaction('Expression %s' % name)
                try:
                    binding.apply('Expression')
                finally:
                    if dict(obj.ExpressionEngine or []).get(name) == before:
                        doc.abortTransaction()      # cancelled: nothing to undo
                    else:
                        doc.commitTransaction()
                        doc.recompute()
            finally:
                self._fx = None
                timer.stop()
                box.hide()
                box.deleteLater()
                if self.on_change is not None:
                    self.on_change()

        def poll():
            try:
                open_ = dialogs[0].isVisible()
            except RuntimeError:            # deleted by the spin box after closing
                open_ = False
            if not open_:
                done()
        timer = QtCore.QTimer(box)
        timer.setInterval(150)
        timer.timeout.connect(poll)
        if not dialogs:
            done()
            raise RuntimeError("FreeCAD's expression editor did not open")
        timer.start()
