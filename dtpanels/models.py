# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (c) 2025-2026 OficineRobotica
"""What each ShowRoom panel shows and edits (see bridge.py for the format)."""
import math
import os

import FreeCAD as App

from Utils import view_utils
from Utils.resource_utils import iconPath, resources_path

TEXTURES_DIR = os.path.join(resources_path, 'Textures')

LIGHT_COLORS = ['#ffffff', '#fff2dc', '#ffe0b3', '#dce8ff', '#ffd2a6']
GRID_COLORS = ['#808080', '#b0b0b0', '#5a5a5a', '#3d7bd6']
GROUND_COLORS = ['#d9d9d9', '#f2f2f2', '#9a9a9a', '#e8e0d0']


# ------------------------------------------------------------------------------ helpers
def num(obj, name):
    value = getattr(obj, name)
    return float(getattr(value, 'Value', value))


def hex_color(color):
    return '#%02x%02x%02x' % tuple(int(round(max(0.0, min(1.0, c)) * 255)) for c in color[:3])


def rgb(hex_text):
    hex_text = hex_text.lstrip('#')
    return tuple(int(hex_text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def nice(value):
    """Round up to 1, 2 or 5 times a power of ten."""
    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 5, 10):
        if value <= step * power + 1e-9:
            return step * power
    return 10 * power


def param(name, label, kind, section, get, set, **extra):
    p = dict(name=name, label=label, kind=kind, section=section, get=get, set=set)
    p.update(extra)
    return p


def prop(obj, name, label, kind, section, **extra):
    """A parameter bound to the property ``name`` of ``obj``."""
    if kind == 'color':
        def get():
            return hex_color(getattr(obj, name))

        def put(value):
            setattr(obj, name, rgb(value))
    elif kind in ('number', 'int', 'compass'):
        def get():
            return num(obj, name)

        def put(value):
            if abs(num(obj, name) - float(value)) > 1e-9:
                setattr(obj, name, value)
    else:
        def get():
            value = getattr(obj, name)
            return str(value) if kind == 'enum' else value

        def put(value):
            if getattr(obj, name) != value:
                setattr(obj, name, value)
    if kind == 'enum' and 'options' not in extra:
        extra['options'] = list(obj.getEnumerationsOfProperty(name))
    extra.setdefault('tip', obj.getDocumentationOfProperty(name))
    return param(name, label, kind, section, get, put, **extra)


def scene_extent(doc):
    """(center, size, lowest z) of the model shown in the first view of ``doc``."""
    view = view_utils.first_view(doc)
    box = view_utils.scene_bound_box(view, doc) if view is not None else None
    if box is None:
        return App.Vector(0, 0, 0), 0.0, 0.0
    center = App.Vector((box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2)
    size = App.Vector(box[3] - box[0], box[4] - box[1], box[5] - box[2]).Length
    return center, size, box[2]


def view_axes(doc):
    """(direction the view looks in, up direction of the view)."""
    view = view_utils.first_view(doc)
    forward, up = App.Vector(-1, 1, -1), App.Vector(0, 0, 1)
    if view is not None:
        try:
            forward = App.Vector(view.getViewDirection())
            up = view.getCameraOrientation().multVec(App.Vector(0, 1, 0))
        except Exception:
            pass
    forward.normalize()
    return forward, up


def fmt_len(value):
    return ('%.1f mm' % value) if abs(value) < 1000 else ('%.2f m' % (value / 1000.0))


class Model:
    """Common defaults."""
    title = ''
    icon = ''
    transaction = 'Edit'
    edited = None

    def __init__(self, doc):
        self.doc = doc

    def alive(self):
        return self.doc is not None and self.doc.Name in App.listDocuments()

    def subtitle(self):
        return ''

    def hidden(self):
        return []

    def info(self):
        return []

    def actions(self):
        return []

    def active_actions(self):
        return []

    def hint(self):
        return ''

    def galleries(self):
        return {}

    def watched(self):
        return []

    def structure(self):
        return None

    def trigger(self, name):
        return None

    def browse(self, name):
        return None

    def edit(self, name):
        return None

    def on_close(self, accepted):
        pass


def _object_alive(obj):
    try:
        return obj.Document is not None and obj.Name is not None and \
            obj.Document.getObject(obj.Name) is obj
    except Exception:
        return False


# ------------------------------------------------------------------------------ effects
def lights_of(doc):
    return [o for o in doc.Objects if getattr(getattr(o, 'Proxy', None), 'isDisplayToolsLight', False)]


class EffectsModel(Model):
    title = 'Scene settings'
    icon = iconPath('CreateCustomScene.svg')
    transaction = 'Edit scene settings'

    def __init__(self, cfg):
        super().__init__(cfg.Document)
        self.cfg = cfg
        self.edited = cfg

    def alive(self):
        return _object_alive(self.cfg)

    def subtitle(self):
        return self.doc.Label

    def structure(self):
        return tuple(o.Name for o in lights_of(self.doc))

    def watched(self):
        return [self.cfg] + lights_of(self.doc)

    def params(self):
        c = self.cfg
        _, size, _ = scene_extent(self.doc)
        ps = [
            prop(c, 'Shadows', 'Real-time shadows', 'bool', 'Shadows'),
            prop(c, 'ShadowCatcher', 'Shadow on an invisible ground', 'bool', 'Shadows'),
            prop(c, 'ShadowDarkness', 'Darkness', 'number', 'Shadows', min=0, max=1, step=0.05,
                 hardMin=0, hardMax=1),
            prop(c, 'ShadowSoftness', 'Softness', 'number', 'Shadows', min=0, max=1, step=0.05,
                 hardMin=0, hardMax=1),
            prop(c, 'ShadowQuality', 'Quality', 'enum', 'Shadows'),
            prop(c, 'AmbientOcclusion', 'Ambient occlusion', 'bool', 'Ambient occlusion'),
            prop(c, 'AOIntensity', 'Intensity', 'number', 'Ambient occlusion', min=0, max=4, step=0.1,
                 hardMin=0, hardMax=4),
            prop(c, 'AORadius', 'Radius', 'number', 'Ambient occlusion', min=0,
                 max=nice(max(size, 1.0) * 0.25), step=nice(max(size, 1.0) * 0.25) / 100,
                 unit='mm', special='Auto', hardMin=0),
            prop(c, 'AOQuality', 'Quality', 'enum', 'Ambient occlusion'),
        ]
        lights = lights_of(self.doc)
        if lights:
            for light in lights:
                ps.append(self._light_row(light))
        else:
            ps.append(param('nolights', 'No lights yet: add a rig with the buttons above, or a '
                            'single light from the toolbar.', 'note', 'Lights', None, None))
        ps += [
            prop(c, 'WhileNavigating', 'While navigating', 'enum', 'Performance and turntable',
                 optionLabels=['Keep', 'Pause AO', 'Pause all']),
            prop(c, 'NavigationResumeDelay', 'Resume after', 'number', 'Performance and turntable',
                 min=0, max=2000, step=50, unit='ms', decimals=0, cast='int', hardMin=0, hardMax=5000),
            prop(c, 'TurntablePeriod', 'One turn in', 'number', 'Performance and turntable',
                 min=-60, max=60, step=1, unit='s', decimals=0),
        ]
        return ps

    def _light_row(self, light):
        def get():
            return dict(on=bool(light.ViewObject.Visibility), intensity=float(light.Intensity),
                        cast=bool(getattr(light, 'CastShadows', False)),
                        canCast=hasattr(light, 'CastShadows'), color=hex_color(light.Color))

        def put(value, field):
            if field == 'on':
                light.ViewObject.Visibility = bool(value)
            elif field == 'intensity':
                light.Intensity = max(0.0, min(1.0, float(value)))
            elif field == 'cast' and hasattr(light, 'CastShadows'):
                light.CastShadows = bool(value)
        return param('light:' + light.Name, light.Label, 'light', 'Lights', get, put,
                     tip='Light on/off, intensity, shadows. "…" edits the light.')

    def hidden(self):
        c = self.cfg
        out = []
        if not (c.Shadows or c.ShadowCatcher):
            out += ['ShadowDarkness', 'ShadowSoftness', 'ShadowQuality']
        if not c.AmbientOcclusion:
            out += ['AOIntensity', 'AORadius', 'AOQuality']
        return out

    def info(self):
        lights = lights_of(self.doc)
        on = [l for l in lights if l.ViewObject.Visibility]
        casters = [l for l in on if getattr(l, 'CastShadows', False)]
        shadow_status = 'none'
        if self.cfg.Shadows:
            shadow_status = 'ok' if casters else 'warn'
        return [dict(label='Lights on', value='%d of %d' % (len(on), len(lights)), status='none', gauge=-1),
                dict(label='Shadow casters', value=str(len(casters)) if casters or not self.cfg.Shadows
                     else 'none: no shadows', status=shadow_status, gauge=-1)]

    def actions(self):
        return [dict(name='rig:three', label='Three-point lights'),
                dict(name='rig:studio', label='Studio lights'),
                dict(name='rig:sun', label='Sun'),
                dict(name='turntable', label='Turntable')]

    def active_actions(self):
        from SceneFX import turntable
        return ['turntable'] if turntable.is_running() else []

    def hint(self):
        return 'OK keeps the changes, Cancel puts everything back as it was.'

    def trigger(self, name):
        from CoinLights import rigs
        if name == 'rig:three':
            rigs.createThreePoint(self.doc)
        elif name == 'rig:studio':
            rigs.createStudio(self.doc)
        elif name == 'rig:sun':
            rigs.createSun(self.doc)
        elif name == 'turntable':
            from SceneFX import turntable
            view = view_utils.first_view(self.doc)
            if view is not None:
                turntable.toggle(view, self.doc)
        return None

    def edit(self, name):
        light = self.doc.getObject(name.partition(':')[2])
        return ('edit', light) if light is not None else None


# ------------------------------------------------------------------------------- lights
class LightModel(Model):
    transaction = 'Edit light'

    TITLES = {'PointLight': 'Point light', 'DirectionalLight': 'Directional light',
              'SpotLight': 'Spot light'}
    ICONS = {'PointLight': 'CreatePointLight.svg', 'DirectionalLight': 'CreateDirectionalLight.svg',
             'SpotLight': 'CreateSpotLight.svg'}

    def __init__(self, obj):
        super().__init__(obj.Document)
        self.obj = obj
        self.edited = obj
        self.kind = obj.Proxy.type
        self.title = self.TITLES.get(self.kind, 'Light')
        self.icon = iconPath(self.ICONS.get(self.kind, 'CreatePointLight.svg'))

    def alive(self):
        return _object_alive(self.obj)

    def subtitle(self):
        return self.obj.Label

    def watched(self):
        import create_scene_config
        cfg = create_scene_config.getSceneFolder(self.doc)
        return [self.obj] + ([cfg] if cfg is not None else [])

    def params(self):
        o = self.obj
        ps = [prop(o, 'Color', 'Color', 'color', 'Light', presets=LIGHT_COLORS),
              prop(o, 'Intensity', 'Intensity', 'number', 'Light', min=0, max=1, step=0.05,
                   hardMin=0, hardMax=1)]
        if hasattr(o, 'CastShadows'):
            ps.append(prop(o, 'CastShadows', 'Casts shadows', 'bool', 'Light'))
        if self.kind == 'DirectionalLight':
            ps += [prop(o, 'Azimuth', 'Comes from (azimuth)', 'number', 'Direction', min=0, max=360,
                        step=1, unit='°', decimals=0),
                   prop(o, 'Elevation', 'Height above horizon', 'number', 'Direction', min=-90,
                        max=90, step=1, unit='°', decimals=0, hardMin=-90, hardMax=90)]
        if hasattr(o, 'Location'):
            def get_loc():
                v = o.Location
                return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]

            def set_loc(value):
                o.Location = App.Vector(*value)
            ps.append(param('Location', 'Position', 'vector', 'Position', get_loc, set_loc,
                            unit='mm', decimals=1, tip=o.getDocumentationOfProperty('Location')))
        if self.kind == 'SpotLight':
            from CoinLights.directional_light import DirectionalLight as D

            def angles():
                a = D.anglesOf(o.Direction) or (0.0, 0.0)
                return (a[0] if a[0] is not None else 0.0), a[1]

            def set_aim(which):
                def put(value):
                    az, el = angles()
                    if which == 'az':
                        az = float(value)
                    else:
                        el = max(-90.0, min(90.0, float(value)))
                    o.Direction = D.directionOf(az, el)
                return put
            ps += [param('AimAzimuth', 'Comes from (azimuth)', 'number', 'Aim',
                         lambda: angles()[0] % 360.0, set_aim('az'), min=0, max=360, step=1,
                         unit='°', decimals=0, tip='Compass direction the spot shines from'),
                   param('AimElevation', 'Height above horizon', 'number', 'Aim',
                         lambda: angles()[1], set_aim('el'), min=-90, max=90, step=1, unit='°',
                         decimals=0, tip='How steeply the spot shines down'),
                   prop(o, 'CutOffAngle', 'Cone half angle', 'number', 'Cone', min=1, max=90,
                        step=1, unit='°', decimals=0, hardMin=1, hardMax=90),
                   prop(o, 'DropOffRate', 'Fade towards the border', 'number', 'Cone', min=0,
                        max=1, step=0.05, hardMin=0, hardMax=1)]
        ps.append(prop(o, 'ShowManipulator', 'Show the gizmo in the 3D view', 'bool', 'Gizmo'))
        return ps

    def hidden(self):
        return []

    def info(self):
        import create_scene_config
        cfg = create_scene_config.getSceneFolder(self.doc)
        if not hasattr(self.obj, 'CastShadows'):
            shadows = dict(label='Shadows', value='not for point lights', status='none', gauge=-1)
        elif not self.obj.CastShadows:
            shadows = dict(label='Shadows', value='off', status='none', gauge=-1)
        elif cfg is not None and cfg.Shadows:
            shadows = dict(label='Shadows', value='cast', status='ok', gauge=-1)
        else:
            shadows = dict(label='Shadows', value='scene shadows off', status='warn', gauge=-1)
        state = 'on' if self.obj.ViewObject.Visibility else 'off (hidden)'
        return [dict(label='Light', value=state, status='none' if self.obj.ViewObject.Visibility else 'warn',
                     gauge=-1), shadows]

    SUN = {'morning': (100.0, 18.0), 'noon': (180.0, 62.0), 'evening': (260.0, 14.0)}

    def actions(self):
        acts = [dict(name='view', label='From the view', primary=True)]
        if self.kind == 'SpotLight':
            acts.append(dict(name='aim', label='Aim at the model'))
        elif self.kind == 'DirectionalLight':
            acts += [dict(name='morning', label='Morning'), dict(name='noon', label='Noon'),
                     dict(name='evening', label='Evening')]
        return acts

    def active_actions(self):
        if self.kind != 'DirectionalLight':
            return []
        az, el = num(self.obj, 'Azimuth') % 360.0, num(self.obj, 'Elevation')
        return [n for n, (a, e) in self.SUN.items() if abs(a - az) < 0.5 and abs(e - el) < 0.5]

    def hint(self):
        if self.kind == 'SpotLight':
            return 'In the 3D view: drag the blue target onto the model, the orange grip opens the cone.'
        if self.kind == 'DirectionalLight':
            return 'In the 3D view: drag the blue grip around the compass and the orange one up the arc.'
        return 'In the 3D view: drag the icon, or an arrow to move along one axis.'

    def trigger(self, name):
        o = self.obj
        if name in self.SUN and self.kind == 'DirectionalLight':
            o.Azimuth, o.Elevation = self.SUN[name]
            return None
        center, size, _ = scene_extent(self.doc)
        forward, up = view_axes(self.doc)
        if name == 'view':
            if self.kind == 'DirectionalLight':
                o.Direction = forward
            else:
                distance = max(size, 10.0)
                o.Location = center - forward * distance + up * (0.4 * distance)
                if self.kind == 'SpotLight':
                    o.Target = center
        elif name == 'aim' and self.kind == 'SpotLight':
            if (center - o.Location).Length > 1e-9:
                o.Target = center
        return None


# --------------------------------------------------------------------------------- grid
class GridModel(Model):
    title = 'Dynamic grid'
    icon = iconPath('CreateDynamicGrid.svg')
    transaction = 'Edit grid'

    def __init__(self, obj):
        super().__init__(obj.Document)
        self.obj = obj
        self.edited = obj

    def alive(self):
        return _object_alive(self.obj)

    def subtitle(self):
        return self.obj.Label

    def watched(self):
        return [self.obj]

    def params(self):
        o = self.obj
        size = max(num(o, 'Size'), 10)

        def get_z():
            return o.Placement.Base.z

        def set_z(value):
            pl = o.Placement
            pl.Base.z = float(value)
            o.Placement = pl
        return [
            prop(o, 'Size', 'Size', 'number', 'Grid', min=10, max=max(1000, nice(size * 2)), step=10,
                 unit='mm', decimals=0, cast='int', hardMin=1),
            prop(o, 'Spacing', 'Spacing', 'number', 'Grid', min=1, max=max(100, nice(size / 5)), step=1,
                 unit='mm', decimals=0, cast='int', hardMin=1),
            prop(o, 'Style', 'Style', 'enum', 'Grid', tip='The compass rose has north on +Y, '
                 'like the sun compass of the lights'),
            prop(o, 'Color', 'Line color', 'color', 'Grid', presets=GRID_COLORS),
            prop(o, 'Dynamic', 'Follow the bottom of the model', 'bool', 'Placement'),
            prop(o, 'ZOffset', 'Gap below the model', 'number', 'Placement', min=-50, max=50, step=0.5,
                 unit='mm', decimals=1, tip='Negative = below the lowest point'),
            prop(o, 'CenterOnScene', 'Centered under the model', 'bool', 'Placement'),
            param('Height', 'Height', 'number', 'Placement', get_z, set_z, min=-500, max=500, step=1,
                  unit='mm', decimals=1, tip='Height of the grid when it does not follow the model'),
            prop(o, 'GroundPlane', 'Solid ground (receives shadows)', 'bool', 'Ground'),
            prop(o, 'GroundColor', 'Ground color', 'color', 'Ground', presets=GROUND_COLORS),
        ]

    def hidden(self):
        out = ['Height'] if self.obj.Dynamic else ['ZOffset', 'CenterOnScene']
        if not self.obj.GroundPlane:
            out.append('GroundColor')
        return out

    def info(self):
        center, size, bottom = scene_extent(self.doc)
        if size <= 0:
            return []
        return [dict(label='Model bottom', value=fmt_len(bottom), status='none', gauge=-1),
                dict(label='Model size', value=fmt_len(size), status='none', gauge=-1)]

    def actions(self):
        return [dict(name='fit', label='Fit to the model', primary=True)]

    def hint(self):
        return 'The grid cannot be picked in the 3D view: select it in the tree.'

    def trigger(self, name):
        if name == 'fit':
            from HelperTools import dynamic_grid
            dynamic_grid.fit_to_model(self.obj)
        return None


# ----------------------------------------------------------------------------- textures
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp')


def _images_in(folder):
    out = []
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith(IMAGE_EXT))
    except OSError:
        names = []
    for name in names:
        stem = os.path.splitext(name)[0].replace('_', ' ').replace('-', ' ')
        label = ''.join((' ' + ch if ch.isupper() and i and stem[i - 1].islower() else ch)
                        for i, ch in enumerate(stem))
        out.append((os.path.join(folder, name), label))
    return out


def user_texture_dir():
    return App.ParamGet('User parameter:BaseApp/Preferences/Mod/ShowRoom').GetString('UserTextureDir', '')


def bundled_textures():
    """ShowRoom's textures, then the ones in the user's own folder (Settings, Textures)."""
    out = _images_in(TEXTURES_DIR)
    folder = user_texture_dir()
    if folder and os.path.isdir(folder) and os.path.normpath(folder) != os.path.normpath(TEXTURES_DIR):
        out += _images_in(folder)
    return out


VIEW_PROPERTIES = ('DisplayMode', 'ShapeAppearance', 'ShapeColor', 'Transparency', 'Lighting',
                   'DrawStyle', 'LineColor', 'LineWidth', 'PointColor', 'PointSize')


class AppearanceModel(Model):
    """Colour, transparency, lines, points and texture of the selected objects."""
    title = 'Appearance'
    icon = iconPath('Appearance.svg')
    transaction = 'Appearance'

    def __init__(self, owners):
        super().__init__(owners[0].Document)
        self.owners = owners
        # view properties are not always undone with the transaction: keep them for Cancel
        self.saved = [(o, {n: _copy(getattr(o.ViewObject, n)) for n in VIEW_PROPERTIES
                           if n in o.ViewObject.PropertiesList}) for o in owners]

    def alive(self):
        return all(_object_alive(o) for o in self.owners)

    def subtitle(self):
        labels = [o.Label for o in self.owners]
        return ', '.join(labels[:3]) + (' +%d' % (len(labels) - 3) if len(labels) > 3 else '')

    def watched(self):
        return list(self.owners)

    # ------------------------------------------------------------------- texture
    def _textured(self):
        from SceneFX import textures
        return [o for o in self.owners if textures.image_of(o)]

    def structure(self):
        return bool(self._textured())

    def _current(self):
        """The image as an option name: the bundled file it came from, the stored copy or ''."""
        from SceneFX import textures
        owner = self.owners[0]
        path = textures.image_of(owner)
        if not path:
            return ''
        source = getattr(owner, 'TextureSource', '') or os.path.basename(path)
        for bundled, _ in bundled_textures():
            if os.path.basename(bundled) == source:
                return bundled
        return path

    def galleries(self):
        items = [dict(name='', label='None', url='')]
        items += [dict(name=path, label=label, url=_url(path)) for path, label in bundled_textures()]
        current = self._current()
        if current and all(item['name'] != current for item in items):
            items.append(dict(name=current, label='Custom', url=_url(current)))
        return {'Texture': items}

    def _set_texture(self, value):
        from SceneFX import textures
        for owner in self.owners:
            if value:
                textures.apply(owner, value)
            else:
                textures.clear(owner)

    # ------------------------------------------------------------------- view props
    def _view(self, name):
        return [o.ViewObject for o in self.owners if name in o.ViewObject.PropertiesList]

    def _vparam(self, name, label, kind, section, **extra):
        views = self._view(name)
        if not views:
            return None
        first = views[0]

        def get():
            value = getattr(first, name)
            if kind == 'color':
                return hex_color(value)
            if kind == 'enum':
                return str(value)
            return float(getattr(value, 'Value', value))

        def put(value):
            for vo in views:
                if kind == 'color':
                    value_ = rgb(value)
                elif kind == 'int' or extra.get('cast') == 'int':
                    value_ = int(round(float(value)))
                elif kind == 'number':
                    value_ = float(value)
                else:
                    value_ = value
                if getattr(vo, name) != value_:
                    setattr(vo, name, value_)
        if kind == 'enum' and 'options' not in extra:
            extra['options'] = list(first.getEnumerationsOfProperty(name))
        extra.setdefault('tip', first.getDocumentationOfProperty(name) or '')
        return param(name, label, kind, section, get, put, **extra)

    def _material_param(self, name, label, kind, **extra):
        """A field of the shape material (all faces), falling back to ShapeColor."""
        views = self._view('ShapeAppearance')
        legacy = self._view('ShapeColor') if not views else []
        if not views and not legacy:
            return None

        def get():
            if views:
                material = views[0].ShapeAppearance[0]
                value = getattr(material, name)
                return hex_color(value) if kind == 'color' else float(value)
            return hex_color(legacy[0].ShapeColor) if kind == 'color' else 0.0

        def put(value):
            if views:
                for vo in views:
                    materials = list(vo.ShapeAppearance)
                    for m in materials:
                        if kind == 'color':
                            alpha = m.DiffuseColor[3] if len(m.DiffuseColor) > 3 else 1.0
                            setattr(m, name, rgb(value) + (alpha,))
                        else:
                            setattr(m, name, float(value))
                    vo.ShapeAppearance = materials
            elif kind == 'color':
                for vo in legacy:
                    vo.ShapeColor = rgb(value)
        if legacy and kind != 'color':
            return None
        return param('Material' + name, label, kind, 'Shape', get, put, **extra)

    def params(self):
        ps = [self._material_param('DiffuseColor', 'Color', 'color', presets=SHAPE_COLORS),
              self._vparam('Transparency', 'Transparency', 'number', 'Shape', min=0, max=100,
                           step=5, unit='%', decimals=0, cast='int', hardMin=0, hardMax=100),
              self._material_param('Shininess', 'Shininess', 'number', min=0, max=1, step=0.05,
                                   hardMin=0, hardMax=1,
                                   tip='0 = matte, 1 = small sharp highlights'),
              self._vparam('DisplayMode', 'Display mode', 'enum', 'Shape'),
              self._vparam('Lighting', 'Lighting', 'enum', 'Shape'),
              self._vparam('DrawStyle', 'Draw style', 'enum', 'Lines and points', collapsed=True),
              self._vparam('LineColor', 'Line color', 'color', 'Lines and points',
                           presets=LINE_COLORS),
              self._vparam('LineWidth', 'Line width', 'number', 'Lines and points', min=0.5,
                           max=8, step=0.5, decimals=1, hardMin=0.1),
              self._vparam('PointColor', 'Point color', 'color', 'Lines and points',
                           presets=LINE_COLORS),
              self._vparam('PointSize', 'Point size', 'number', 'Lines and points', min=1, max=12,
                           step=1, decimals=0, hardMin=0.5),
              param('Texture', 'Texture', 'gallery', 'Texture', self._current, self._set_texture,
                    browseLabel='Your image…',
                    tip='Click a material, "None" to take it away, or "Your image…"')]
        textured = self._textured()
        if textured:
            first = textured[0]

            def setter(name):
                def put(value):
                    for owner in self._textured():
                        if abs(num(owner, name) - float(value)) > 1e-9:
                            setattr(owner, name, value)
                return put
            scale = max(num(first, 'TextureScale'), 1.0)
            ps += [param('TextureScale', 'Size of one tile', 'number', 'Texture',
                         lambda: num(first, 'TextureScale'), setter('TextureScale'), min=1,
                         max=max(200, nice(scale * 3)), step=1, unit='mm', decimals=1,
                         hardMin=0.01),
                   param('TextureRotation', 'Rotation', 'number', 'Texture',
                         lambda: num(first, 'TextureRotation'), setter('TextureRotation'), min=0,
                         max=360, step=5, unit='°', decimals=0),
                   param('projection', 'Box projection: each face takes the image from the axis '
                         'it faces most, at real size. Shown in the Flat Lines and Shaded modes.',
                         'note', 'Texture', None, None)]
        return [p for p in ps if p is not None]

    def info(self):
        textured = self._textured()
        out = [dict(label='Objects', value=str(len(self.owners)), status='none', gauge=-1)]
        if textured:
            from PySide import QtGui
            image = QtGui.QImageReader(textured[0].TextureImage).size()
            size = '%d × %d px' % (image.width(), image.height()) if image.isValid() else '?'
            out.append(dict(label='Texture', value=size, status='none', gauge=-1))
        else:
            out.append(dict(label='Texture', value='none', status='none', gauge=-1))
        return out

    def actions(self):
        acts = [dict(name='reset', label='Default look')]
        if self._textured():
            acts.insert(0, dict(name='fit', label='Texture size from the object'))
        return acts

    def hint(self):
        return 'Changes show right away; OK keeps them, Cancel puts everything back.'

    def trigger(self, name):
        from SceneFX import textures
        if name == 'fit':
            for owner in self._textured():
                owner.TextureScale = textures.default_scale(owner)
        elif name == 'reset':
            view = App.ParamGet("User parameter:BaseApp/Preferences/View")
            packed = view.GetUnsigned('DefaultShapeColor', 0xCCCCCC00)
            color = '#%02x%02x%02x' % ((packed >> 24) & 255, (packed >> 16) & 255, (packed >> 8) & 255)
            line = view.GetUnsigned('DefaultShapeLineColor', 0x191919FF)
            line_hex = '#%02x%02x%02x' % ((line >> 24) & 255, (line >> 16) & 255, (line >> 8) & 255)
            defaults = {'MaterialDiffuseColor': color, 'Transparency': 0, 'Lighting': 'Two side',
                        'DrawStyle': 'Solid', 'LineColor': line_hex, 'PointColor': line_hex,
                        'LineWidth': view.GetInt('DefaultShapeLineWidth', 2),
                        'PointSize': view.GetInt('DefaultShapePointSize', 2), 'Texture': ''}
            for p in self.params():
                if p['name'] in defaults and 'set' in p:
                    p['set'](defaults[p['name']])
        return None

    def browse(self, name):
        import FreeCADGui
        from PySide import QtWidgets
        path = QtWidgets.QFileDialog.getOpenFileName(
            FreeCADGui.getMainWindow(), 'Choose the texture image', os.path.expanduser('~'),
            'Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)')[0]
        if path:
            self._set_texture(path)
        return None

    def on_close(self, accepted):
        from SceneFX import textures
        if accepted:
            # "None" leaves empty texture properties: tidy them away
            for owner in self.owners:
                if 'TextureImage' in owner.PropertiesList and not textures.image_of(owner):
                    textures.remove(owner)
            return
        for owner, values in self.saved:
            if not _object_alive(owner):
                continue
            for name, value in values.items():
                try:
                    if getattr(owner.ViewObject, name) != value:
                        setattr(owner.ViewObject, name, value)
                except Exception:
                    pass


SHAPE_COLORS = ['#cccccc', '#e59a40', '#3d7cc9', '#c94a3d', '#4f9d5a', '#2b2b2b']
LINE_COLORS = ['#191919', '#ffffff', '#3d7cc9', '#c94a3d']


def _copy(value):
    try:
        return [m for m in value] if isinstance(value, (list, tuple)) and value and \
            hasattr(value[0], 'DiffuseColor') else value
    except Exception:
        return value


def _url(path):
    from PySide import QtCore
    return QtCore.QUrl.fromLocalFile(path).toString()


# ----------------------------------------------------------------------------- dispatch
def model_for(obj):
    proxy = getattr(obj, 'Proxy', None)
    kind = getattr(proxy, 'type', None)
    if getattr(proxy, 'isDisplayToolsLight', False):
        return LightModel(obj)
    if kind == 'DynamicGrid':
        return GridModel(obj)
    if kind == 'SceneConfiguration':
        return EffectsModel(obj)
    return None


# ------------------------------------------------------------------------------ settings
class _NoDocument:
    """The settings panel edits preferences, not a document: no transaction."""
    Name = '__ShowRoomSettings__'

    def openTransaction(self, *args):
        pass

    def commitTransaction(self):
        pass

    def abortTransaction(self):
        pass

    def recompute(self):
        pass


class SettingsModel(Model):
    """ShowRoom's preferences, kept in the panel until OK."""
    title = 'ShowRoom settings'
    icon = iconPath('Settings.svg')
    transaction = 'ShowRoom settings'

    def __init__(self):
        from Utils import prefs
        super().__init__(_NoDocument())
        self.prefs = prefs
        self.values = {name: prefs.get(name) for name in prefs.DEFAULTS}

    def alive(self):
        return True

    def subtitle(self):
        return 'Saved in your preferences, for every document'

    searchable = True
    filter = ''

    def hidden(self):
        text = self.filter.strip().lower()
        if not text:
            return []
        return [p['name'] for p in self.params()
                if text not in p['label'].lower() and text not in p.get('section', '').lower()]

    def _p(self, name, label, kind, section, **extra):
        extra.setdefault('default', self.prefs.default(name))

        def get():
            value = self.values[name]
            return float(value) if kind == 'number' else value

        def put(value):
            self.values[name] = type(self.prefs.default(name))(value) \
                if not isinstance(self.prefs.default(name), bool) else bool(value)
        return param(name, label, kind, section, get, put, **extra)

    def params(self):
        from SceneFX import navigation
        from dtpanels.floating import EASINGS
        P = self._p
        unit = dict(min=0, max=1, step=0.05, hardMin=0, hardMax=1)
        return [
            P('LoadAtStartup', 'Load ShowRoom when FreeCAD starts', 'bool', 'Startup',
              tip='Lights, textures and the scene work in every file without opening the '
                  'workbench. Takes effect at the next start'),
            P('StartInShowRoom', 'Open FreeCAD in the ShowRoom workbench', 'bool', 'Startup'),
            P('AutoScene', 'Add the scene to every new document', 'bool', 'New documents'),
            P('StartRig', 'Starting lights', 'enum', 'New documents', options=self.prefs.RIGS),
            P('AutoGrid', 'Dynamic grid', 'bool', 'New documents'),
            P('DefGridStyle', 'Grid style', 'enum', 'New documents', options=['Grid', 'Compass rose'],
              tip='Also used by Create dynamic grid'),
            P('AutoGroundPlane', 'Ground plane under the grid', 'bool', 'New documents'),
            P('AutoSceneOnOpen', 'Also add it to opened files without a scene', 'bool',
              'New documents', tip='Files that have a scene always keep their own'),
            P('DefAO', 'Ambient occlusion', 'bool', 'Default scene'),
            P('DefAOQuality', 'AO quality', 'enum', 'Default scene', options=self.prefs.QUALITIES),
            P('DefAOIntensity', 'AO intensity', 'number', 'Default scene', min=0, max=2,
              step=0.05, hardMin=0, hardMax=2),
            P('DefShadows', 'Shadows', 'bool', 'Default scene'),
            P('DefShadowQuality', 'Shadow quality', 'enum', 'Default scene',
              options=self.prefs.QUALITIES),
            P('DefShadowDarkness', 'Shadow darkness', 'number', 'Default scene', **unit),
            P('DefShadowSoftness', 'Shadow softness', 'number', 'Default scene', **unit),
            P('DefCatcher', 'Shadow catcher', 'bool', 'Default scene'),
            P('DefWhileNavigating', 'While navigating', 'enum', 'Default scene',
              options=list(navigation.MODES)),
            P('InViewPanel', 'Floating light panel', 'bool', '3D view'),
            P('ShowGizmos', 'Show light gizmos on new lights', 'bool', '3D view'),
            P('GizmoSize', 'Gizmo size', 'enum', '3D view', options=list(self.prefs.GIZMO_SIZES),
              tip='Applies to the documents opened from now on'),
            P('SnapTarget', 'Snap the spot target to surfaces', 'bool', '3D view'),
            P('FontScale', 'Text size', 'number', 'Panels', min=0.8, max=1.4, step=0.05,
              decimals=2, hardMin=0.5, hardMax=2, tip='Applies to the panels opened next'),
            P('UseQml', 'QML panels', 'bool', 'Panels',
              tip='Off: classic widget panels, for FreeCAD builds without Qt Quick'),
            P('FloatingPanel', 'Floating properties panel (Data, View, Task)', 'bool',
              'Properties panel', tip="Moves FreeCAD's property editor and task view into a "
              'panel over the 3D view'),
            P('PanelVisibility', 'Visibility', 'enum', 'Properties panel',
              options=['Fixed', 'Rolled up', 'Autohide'],
              tip='Autohide: slides away, comes back when the mouse touches the screen edge '
                  'on its side, when something is selected or when a task opens'),
            P('SectionStyle', 'Section style', 'enum', 'Panels', options=['Flat', 'Inset', 'Outset', 'Outline'],
              tip='How the sections of the ShowRoom panels look; panels opened afterwards use it'),
            P('QmlProperties', "ShowRoom's own Data / View editor (switches, sliders)", 'bool',
              'Properties panel', tip="Off: FreeCAD's property editor"),
            P('TableRows', 'Table layout: type icons, lines between rows, clearer states', 'bool',
              'Properties panel', tip='For the Data / View editor; it applies when the panel opens'),
            P('KeepOpenOnTask', 'Keep it open while a task is open', 'bool', 'Properties panel'),
            P('PanelEasing', 'Animation', 'enum', 'Properties panel',
              options=list(EASINGS),
              tip='Out curves start fast and slow down at the end: the most natural'),
            P('PanelAnimMs', 'Animation time', 'number', 'Properties panel', min=0, max=1500,
              step=50, unit='ms', decimals=0, cast='int', hardMin=0, hardMax=2000),
            P('PanelBlur', 'Blurred background', 'bool', 'Properties panel'),
            P('AutoTask', 'Autotask: show the Task tab when a task opens', 'bool',
              'Properties panel', tip='Pad, Pocket, sketch editing...'),
            P('DefTileSize', 'Texture tile size (0 = from the object)', 'number', 'Textures',
              min=0, max=200, step=1, unit='mm', decimals=0, hardMin=0),
            P('UserTextureDir', 'Your texture folder', 'text', 'Textures', button='Choose…',
              action='browse:UserTextureDir',
              tip='Its images (jpg, png, webp...) appear in the texture gallery after the bundled ones'),
            P('WarnDisplayTools', 'Warn when Display Tools is installed', 'bool', 'Maintenance'),
        ]

    def info(self):
        return []

    def actions(self):
        acts = [dict(name='factory', label='Factory defaults'),
                dict(name='export', label='Export settings…'),
                dict(name='reset', label='Reset all')]
        if App.ActiveDocument is not None:
            acts.insert(0, dict(name='current', label='Use the current scene'))
        return acts

    def hint(self):
        return 'OK saves the settings; Cancel leaves them as they were.'

    def browse(self, name):
        if name == 'UserTextureDir':
            import FreeCADGui
            from PySide import QtWidgets
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                FreeCADGui.getMainWindow(), 'Your texture folder', self.values.get(name) or os.path.expanduser('~'))
            if folder:
                self.values[name] = folder
        return None

    def trigger(self, name):
        prefs = self.prefs
        if name == 'current':
            import create_scene_config
            cfg = create_scene_config.getSceneFolder(App.ActiveDocument)
            if cfg is not None:
                for prop, key in (('Shadows', 'DefShadows'), ('ShadowQuality', 'DefShadowQuality'),
                                  ('ShadowDarkness', 'DefShadowDarkness'),
                                  ('ShadowSoftness', 'DefShadowSoftness'),
                                  ('ShadowCatcher', 'DefCatcher'), ('AmbientOcclusion', 'DefAO'),
                                  ('AOQuality', 'DefAOQuality'), ('AOIntensity', 'DefAOIntensity'),
                                  ('WhileNavigating', 'DefWhileNavigating')):
                    if prop in cfg.PropertiesList:
                        value = getattr(cfg, prop)
                        self.values[key] = type(prefs.default(key))(
                            str(value) if isinstance(prefs.default(key), str) else value)
        elif name == 'factory':
            for key in prefs.SCENE_KEYS:
                self.values[key] = prefs.default(key)
        elif name == 'reset':
            self.values = {key: prefs.default(key) for key in prefs.DEFAULTS}
        elif name == 'export':
            import FreeCADGui
            from PySide import QtWidgets
            path = QtWidgets.QFileDialog.getSaveFileName(
                FreeCADGui.getMainWindow(), 'Export ShowRoom settings', 'ShowRoom.FCParam',
                'FreeCAD parameters (*.FCParam)')[0]
            if path:
                self._save()
                prefs.group().Export(path)
        return None

    def _save(self):
        for key, value in self.values.items():
            self.prefs.set(key, value)

    def on_close(self, accepted):
        if not accepted:
            return
        self._save()
        self.prefs.apply_start_workbench(self.values['StartInShowRoom'])
        try:
            from dtpanels import floating
            floating.apply_prefs()
        except Exception as error:
            App.Console.PrintWarning("ShowRoom: floating panel: %s\n" % error)
        if self.values['LoadAtStartup'] or self.values['AutoScene'] or self.values['AutoSceneOnOpen']:
            from SceneFX import autoscene
            autoscene.install()


def open_settings():
    import FreeCADGui
    from dtpanels import bridge
    try:
        from dtpanels import prefs_window
        if prefs_window.show():
            return None
    except Exception as error:
        App.Console.PrintWarning("ShowRoom: %s\n" % error)
    if FreeCADGui.Control.activeDialog():
        App.Console.PrintWarning("ShowRoom: close the open task panel first.\n")
        return None
    return bridge.open_panel(SettingsModel(), created=True)
