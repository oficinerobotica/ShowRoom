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

    def __init__(self):
        super().__init__(None)
        self.target = None
        self.tab = 'Data'
        self.open_native = None         # callback(name) from the floating panel
        self.title = 'Nothing selected'
        self.icon = ''

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
            out.append(self._row(c, name, _words(name), ptype, group, tip, readonly,
                                 bound.get(name)))
        return out

    def _row(self, c, name, label, ptype, group, tip, readonly, expression):
        base = dict(name=name, label=label, section=group, tip=tip)
        kind = ptype.split('::')[-1].replace('Property', '')

        def native(text):
            return dict(base, kind='native', get=text, action='native:' + name,
                        readOnly=True, button='Edit')

        if expression is not None:
            return native(lambda: '= %s' % expression)
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
                        step=1, unit=unit, slider=False)
        if kind == 'Color':
            return dict(base, kind='color', get=lambda: hex_color(getattr(c, name)),
                        set=put(rgb), presets=[])
        if kind in ('String', 'Font'):
            return dict(base, kind='text', get=lambda: str(getattr(c, name)), set=put(str))
        return native(lambda: self._text(c, name))

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
        return None
