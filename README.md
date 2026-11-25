<div align="center">

# ShowRoom for FreeCAD

**Present your models right in the 3D view:** lights you place by hand, real-time shadows,
a shadow on an invisible ground, ambient occlusion, materials and textures, a turntable.
No rendering, no export: it is the live view you model in.

<img src="Resources/ReadmeResources/Lights.jpg" alt="ShowRoom: a spot light with its gizmo and floating panel" width="820">

### Support the Development

<p align="center">
  <a href="https://liberapay.com/oficinerobotica/">
    <img src="https://img.shields.io/badge/Liberapay-Support_Development-yellow?style=for-the-badge&logo=liberapay" alt="Support via Liberapay">
  </a>
  <a href="https://www.patreon.com/oficinerobotica">
    <img src="https://img.shields.io/badge/Patreon-Become_a_Patron-red?style=for-the-badge&logo=patreon" alt="Support via Patreon">
  </a>
  <a href="https://www.youtube.com/@OficineRobotica">
    <img src="https://img.shields.io/badge/YouTube-Subscribe-red?style=for-the-badge&logo=youtube" alt="YouTube Channel">
  </a>
</p>

---

</div>

ShowRoom is the new name of **Display Tools**, rewritten and much extended. It opens the
documents made with Display Tools as they are (see [Coming from Display Tools](#coming-from-display-tools)).

<p align="center">
  <img src="Resources/ReadmeResources/ToolBar.png" alt="ShowRoom toolbars" width="820">
</p>

## Contents

* [Scene settings](#scene-settings)
* [Lights and their gizmos](#lights-and-their-gizmos)
* [Light rigs](#light-rigs)
* [Shadows](#shadows) · [Shadow catcher](#shadow-catcher) · [Ambient occlusion](#ambient-occlusion)
* [Appearance and textures](#appearance-and-textures)
* [Turntable](#turntable) · [Fluid navigation](#fluid-navigation)
* [Dynamic grid](#dynamic-grid) · [SpaceMouse axis locks](#spacemouse-axis-locks)
* [Task panels](#task-panels) · [ShowRoom settings](#showroom-settings) · [Installation](#installation) · [License](#license)

## Features

### Scene settings

<p align="center">
  <img src="Resources/ReadmeResources/SceneSettings.jpg" alt="Scene settings task panel" width="560">
</p>

Click the **scene icon** (*Scene settings…*, first button of the toolbar) to open the scene
settings in the task panel. The first time, it creates the **scene configuration** of the
document (`SceneFolder` in the tree), which holds the lights and the grid; Cancel takes it
away again. Afterwards the same click, or a double click on `SceneFolder`, opens its panel:

* shadows, shadow on an invisible ground, ambient occlusion, with their quality;
* every light of the document with on/off, intensity and shadows (the "…" button opens that
  light's own panel);
* light rigs, turntable and the navigation settings.

New scenes start with shadow and ambient occlusion quality on **High** and the shadow
darkness at **50 %**.

### Lights and their gizmos

Point, directional and spot lights are document objects: they are saved with the file and can
be hidden. Each one has a **gizmo** in the 3D view: an icon that keeps the same size on
screen and, when the light is selected, handles to place and aim it.

* **Spot**: drag the icon to move the light, an arrow to move along one axis, the blue target
  onto the model (it snaps to the surface) to aim it, the orange grip on the rim to open or
  close the cone. The cone is drawn as a faint warm beam.
* **Directional (sun)**: a compass around the model; drag the blue grip around it to change
  where the sun comes from, the orange one up the arc to raise or lower it.
* **Point**: drag the icon or an arrow; a drop line shows where it stands over the ground.

Every drag is one undo step, Esc cancels it, a double click on the icon opens the task panel.
The handles follow the properties (`Location`, `Target`, `Direction`, `CutOffAngle`,
`Azimuth`, `Elevation`) and the other way round. The gizmos are not tinted by shadows or
ambient occlusion.

<p align="center">
  <img src="Resources/ReadmeResources/Sun.jpg" alt="The sun gizmo and its floating panel" width="820">
</p>

**Floating panel**: when one light is selected, a small card appears in the top right corner
of the 3D view with intensity, color and shadows, plus the cone (spot), a compass and the
*Morning*, *Noon* and *Evening* presets (sun) or the height over the model (point). The pin
keeps it open when the selection changes, *All options…* opens the task panel. It can be
switched off with the boolean parameter `InViewPanel` in `BaseApp/Preferences/Mod/ShowRoom`.

| Property | Lights | Meaning |
| --- | --- | --- |
| `Color`, `Intensity` | all | FreeCAD's headlight is already at full strength, so new lights start at 0.6 |
| `Location` | point, spot | position of the light |
| `Target` | spot | point the spot is aimed at; moving the light keeps it aimed there |
| `Direction` | directional, spot | direction the light travels in |
| `Azimuth`, `Elevation` | directional | where the sun comes from (0° = from +Y, 90° = from +X) and its height above the horizon, linked both ways to `Direction` |
| `CutOffAngle`, `DropOffRate` | spot | half angle of the cone (1° to 90°) and falloff towards its border |
| `CastShadows` | directional, spot | the light casts shadows when shadows are enabled |
| `ShowManipulator` | all | show the gizmo in the 3D view |

FreeCAD's own headlight stays on and is added to these lights. If the picture is too bright,
lower *Preferences > Display > Light sources*. OpenGL handles 8 lights at once and FreeCAD
uses up to 3 of them: beyond that, the extra lights switched on are left out (shadow casters
are kept first) and a message in the report view names them.

### Light rigs

The **Light rigs** drop-down adds a ready-made set in one click:

* *Three-point lighting*: key light (casting the shadows), fill and rim, placed for the way the
  view looks at the model at that moment;
* *Studio lighting*: a soft light from above and two side lights;
* *Sun*: one directional light.

### Shadows

*Toggle shadows* switches real-time shadows on for the active document. They are cast by the
directional and spot lights that have `CastShadows` set; if there is none, a directional light
named `Sun` is added. Point lights cannot cast shadows.

| Property (scene configuration) | Meaning |
| --- | --- |
| `Shadows` | on / off |
| `ShadowDarkness` | 0 = invisible, 1 = the light is fully blocked (new scenes: 0.5) |
| `ShadowSoftness` | blur of the shadow borders |
| `ShadowQuality` | Low / Medium / High: shadow map of 1024 / 2048 / 4096 pixels (new scenes: High) |

### Shadow catcher

*Toggle shadow catcher* (`ShadowCatcher`) shows the soft shadow of the model on an
**invisible ground** at the lowest point of the scene, without a floor object. It follows the
first visible light with `CastShadows` (straight from above if there is none), uses
`ShadowDarkness`, `ShadowSoftness` and `ShadowQuality`, and works with or without the
real-time shadows. It is redrawn only when the model or the light changes, so it costs
nothing while navigating. Lights lower than about 15° above the horizon are treated as if they
were at 15°.

### Ambient occlusion

*Toggle ambient occlusion* darkens creases, holes and the places where objects touch, which
makes shapes much easier to read.

| Property (scene configuration) | Meaning |
| --- | --- |
| `AmbientOcclusion` | on / off |
| `AOIntensity` | strength of the darkening |
| `AORadius` | distance within which surfaces occlude each other; 0 = automatic (6 % of the size of the scene) |
| `AOQuality` | Low / Medium / High: samples per pixel and resolution (new scenes: High) |

### Appearance and textures

<p align="center">
  <img src="Resources/ReadmeResources/Appearance.jpg" alt="Appearance task panel" width="560">
</p>

**Appearance…** (toolbar, or right click on objects) edits the look of the selected objects in
one task panel; changes show right away, OK keeps them, Cancel puts everything back:

* **Shape**: color with presets, transparency, shininess, display mode, lighting (one or two
  sides);
* **Lines and points**: draw style, line color and width, point color and size;
* **Texture**: *None*, a gallery of materials (wood, brushed metal, concrete, carbon fibre,
  plastic grain, checker) or *Your image…* (any PNG or JPG), with the size of one tile and the
  rotation. *Texture size from the object* picks a size for you, *Default look* puts FreeCAD's
  default colors back.

The texture image is copied into the document, so the file can be moved or shared. The object
gets three properties:

| Property | Meaning |
| --- | --- |
| `TextureImage` | the image |
| `TextureScale` | size of one repetition of the image, in mm |
| `TextureRotation` | rotation of the image on the faces |

The image is laid with a box projection: every face takes it from the axis it faces most, at
real size, with no unwrapping. That suits materials; on round shapes a seam shows where the
projection changes side. Selecting a PartDesign feature textures its Body, and the texture
follows the Tip. Textures show in the *Flat Lines* and *Shaded* modes, replace the object's
own color and transparency, are one per object (not per face) and do not apply to meshes yet.
They work with shadows, the shadow catcher and ambient occlusion, and come back when a
document is opened even before the workbench is activated.

### Turntable

*Toggle turntable* slowly rotates the view around the model about the Z axis, with the effects
kept on: made for screen recordings. `TurntablePeriod` is the number of seconds per turn
(negative turns the other way).

### Fluid navigation

While a view is rotated, panned or zoomed its effects are paused, and come back a moment after
it stops. Editing the model or dragging a light is not navigation: shadows stay live.

| Property (scene configuration) | Meaning |
| --- | --- |
| `WhileNavigating` | *Pause all effects* (default), *Pause ambient occlusion* (shadows stay), *Keep effects* |
| `NavigationResumeDelay` | milliseconds the view has to stay still before the effects return (250) |

Good to know about shadows and ambient occlusion:

* they redraw the scene once more per frame (once per shadow casting light), so on heavy models
  the view gets slower: they are per document and off until you switch them on;
* they need a graphics card with OpenGL 2.1 shaders and floating point textures (anything from
  the last 15 years);
* shadows get blocky when zooming far into a small detail of a large scene: raise
  `ShadowQuality`, or hide what is not needed;
* ambient occlusion treats transparent objects as opaque;
* images saved with *Tools > Save image* are rendered by FreeCAD without the two effects:
  take a screenshot of the view instead.

### Dynamic grid

<p align="center">
  <img src="Resources/ReadmeResources/DynamicGrid.jpg" alt="Dynamic grid" width="800">
</p>

A reference grid with adjustable `Size`, `Spacing` and `Color` per document. With `Dynamic` on
it keeps itself at the lowest point of what is visible in the 3D view: every kind of object
counts (solids, meshes, objects inside Parts, Bodies and Links, ...), hidden objects do not.
`ZOffset` leaves a gap, `CenterOnScene` keeps it centered under the model, `GroundPlane` adds
a solid floor that catches the shadows.

The grid cannot be picked in the 3D view (select it in the tree). It is part of what *Fit all*
frames, like any object: FreeCAD derives the camera clipping planes from the same box, and
leaving the grid out of it made the grid get cut off. Keep `Size` in proportion to the model.

### SpaceMouse axis locks

<p align="center">
  <img src="Resources/ReadmeResources/SpaceMouse.jpg" alt="SpaceMouse tools" width="800">
</p>

Three toggles: lock rotation (pan and zoom only), lock translation (rotate only), lock horizon
(no roll). They flip the settings of *Tools > Customize > Spaceball Motion*, so they work with
FreeCAD's built-in SpaceMouse support (the default on Linux). When FreeCAD uses the official
3Dconnexion driver instead (Windows and macOS with the driver installed) the driver handles the
axes and the locks have no effect.

A fourth toggle, **Rotate around selection**, makes the SpaceMouse rotate the view around the
centre of what is selected (objects, faces, edges or vertices; with nothing selected the view
rotates as usual). Selecting something slides the view until the selection is in its middle,
and it stays there: the SpaceMouse then only rotates and zooms (its sideways and up/down axes
are switched off in *Spaceball Motion* while something is selected, and back on otherwise).
Panning with the mouse still works; the next SpaceMouse move brings the selection back.
It needs FreeCAD's rotation mode *Window center* (Preferences > Display > Navigation): the
toggle sets it while on and gives the previous mode back when switched off. Same limit as the
locks: with the official 3Dconnexion driver use the driver's own "rotate around selection"
setting instead.

*ShowRoom settings > SpaceMouse* has the options: rotate around the selection (the same as the
button), bring the selection to the middle of the view, keep it there (rotate and zoom only),
and **no rotation while editing a sketch**: the rotation lock switches on when a sketch opens
and goes back as it was when it closes; panning and zooming keep working.

### Task panels

Every object of the workbench is edited in the task panel, as in Part Design: **double click**
it in the tree (or create it: the panel opens right away). OK keeps the changes, Cancel puts
everything back, including the object itself if it was just created; the whole session is one
undo step.

* *Light*: color with presets, intensity, shadows, position, azimuth / elevation, cone, gizmo.
  *From the view* places the light where you are looking from; for the sun also *Morning*,
  *Noon* and *Evening*.
* *Dynamic grid*: size, spacing, colors, following the model, ground plane. *Fit to the model*
  sizes it for you.
* *Scene settings* and *Appearance*: see above.

The panels are written in QML and take colors and font from the FreeCAD theme. If Qt Quick is
missing from a FreeCAD build, an equivalent widget panel is used instead. Text size:
`FontScale` in `Preferences/Mod/ShowRoom` (parameter editor); `UseQml` = false forces the
widget panels.

### ShowRoom settings

The last toolbar button (*ShowRoom settings…*, a gear) opens ShowRoom's own settings in the task
panel, with or without a document open. OK saves them in `Preferences/Mod/ShowRoom`, Cancel
leaves them as they were.

* **Startup**: load ShowRoom when FreeCAD starts (textures, lights and the scene work in every
  file without opening the workbench), open FreeCAD in the ShowRoom workbench.
* **New documents**: add the scene to every new document, with starting lights (none, sun,
  three-point, studio), the dynamic grid and its ground plane; optionally also to opened files
  that have no scene. Files that have a scene always keep their own.
* **Default scene**: shadows (quality, darkness, softness), shadow catcher, ambient occlusion
  (quality, intensity) and the navigation mode every new scene starts with. *Use the current
  scene* copies them from the active document, *Factory defaults* puts them back.
* **3D view**: floating light panel, gizmos on new lights, gizmo size, snapping of the spot
  target to surfaces.
* **Panels and textures**: text size, QML or widget panels, a fixed texture tile size.
* **Maintenance**: the Display Tools warning, *Export settings…*, *Reset all*.

## Coming from Display Tools

* Remove the `DisplayTools` folder from `Mod` before installing ShowRoom: the two share their
  modules, and ShowRoom warns in the report view if it finds both.
* Documents made with Display Tools open as they are: lights, grid, scene configuration and
  textures keep working.
* The preferences are copied from `Preferences/Mod/DisplayTools` to `Preferences/Mod/ShowRoom`
  the first time ShowRoom starts.
* The commands are now called `ShowRoom_…` (toolbars you customized with the old
  `DisplayTools_…` commands need them added again). *Texture…* and *Remove texture* became
  *Appearance…*; *Display effects panel* is now the scene icon.

## Installation

Copy or clone this repository into the `Mod` folder of your FreeCAD user data directory as
`ShowRoom`, then restart FreeCAD. On Linux with FreeCAD 26.3:

```sh
git clone https://github.com/oficinerobotica/ShowRoom ~/.local/share/FreeCAD/v26-3/Mod/ShowRoom
```

(Windows: `%APPDATA%\FreeCAD\v26-3\Mod\ShowRoom`, macOS:
`~/Library/Application Support/FreeCAD/v26-3/Mod/ShowRoom`.) The folder can also be added in
the Addon Manager as a custom repository.

**Requirements:** FreeCAD 1.0 or newer. Tested on FreeCAD 1.1, 26.3 and the 27.1 development
builds.

## Developer

OficineRobotica

## License

ShowRoom is free software, released under the GNU Lesser General Public License version 2.1 or
(at your option) any later version, like FreeCAD. See [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md) for the history of the code (it started as Display Tools, under the MIT
licence) and of the artwork.
