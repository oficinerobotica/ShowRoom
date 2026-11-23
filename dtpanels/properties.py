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
    filter = ''

    def __init__(self):
        super().__init__(None)
        self.target = None
        self.tab = 'Data'
        self.open_native = None         # callback(name) from the floating panel
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
                out += self._placement(c, name, group, tip)
                continue
            row = self._row(c, name, _words(name), ptype, group, tip, readonly, expr)
            out += row if isinstance(row, list) else [row]
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
                doc.openTransaction('Edit %s' % label)
                try:
                    setattr(c, name, v)
                finally:
                    doc.commitTransaction()
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
        if kind in ('Material', 'MaterialList'):
            return self._material(c, name, label, base, kind == 'MaterialList', put)
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

    def _material(self, c, name, label, base, many, put):
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

        def setter(field):
            raw = put(lambda v: change(field, v))

            def go(v):
                current = first()
                old = hex_color(current.DiffuseColor) if field == 'DiffuseColor' else float(getattr(current, field))
                if (field == 'DiffuseColor' and old == v) or (field != 'DiffuseColor' and abs(old - float(v)) < 1e-6):
                    return
                raw(v)
            return go
        return [dict(base, name=name + '@color', label='%s · color' % label, kind='color', presets=presets,
                     get=lambda: hex_color(first().DiffuseColor), set=setter('DiffuseColor')),
                dict(base, name=name + '@shine', label='%s · shininess' % label, kind='number',
                     min=0, max=1, step=0.05, decimals=2, hardMin=0, hardMax=1,
                     get=lambda: float(first().Shininess), set=setter('Shininess'))]

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
        """Bind a property to an expression (empty text removes it)."""
        from PySide import QtWidgets
        obj = self.target
        current = dict(obj.ExpressionEngine or []).get(name, '')
        text, ok = QtWidgets.QInputDialog.getText(
            Gui.getMainWindow(), 'Expression', '%s =\n(empty: no expression)' % _words(name),
            QtWidgets.QLineEdit.Normal, current)
        if not ok or text.strip() == current:
            return
        doc = obj.Document
        doc.openTransaction('Expression %s' % name)
        try:
            obj.setExpression(name, text.strip() or None)
        finally:
            doc.commitTransaction()
        doc.recompute()
