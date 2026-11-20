# Changelog

## ShowRoom 1.1.7

- Windows: QML panels were empty ("Failed to get a QRhi"): Qt Quick now draws with OpenGL like the 3D view; where that is not possible the classic widget panels are used.

## ShowRoom 1.1.6

- Effects pause only for Create sketch's plane choice, attachment panels and sketch editing; Pad, Pocket and other task panels keep them.

## ShowRoom 1.1.5

Fixed
- With ambient occlusion on, the origin planes could not be picked (no plane for a new sketch).
  While a task panel of another workbench is open (Create sketch, attachment, features) or a
  sketch is busy, the effects pause and come back afterwards.

Changed
- Settings panel: ambient occlusion comes before shadows in the default scene.

## ShowRoom 1.1.4

Fixed
- Same as 1.0.3: no shadow node in the scene while a sketch is busy (the real fix of the sketch
  crash), and gizmos for lights in opened files.

## ShowRoom 1.1.3

Fixed
- With the shadow catcher on, FreeCAD crashed when a sketch was created or opened for editing:
  the catcher now pauses together with the shadows while a sketch is selected or edited.

## ShowRoom 1.1.1

Fixed
- FreeCAD crashed when a sketch was opened for editing with shadows on (now the default in new
  documents): shadows pause as soon as a sketch is created or selected and while an object is
  in edit mode, and come back afterwards.
- A document created by Part Design's *Create body* (or *Create part*) did not get the scene.

## ShowRoom 1.1.0

New
- *ShowRoom settings…* (gear, last toolbar button): startup, what every new document starts
  with (scene, lights, grid), the default scene (shadows, catcher, ambient occlusion,
  navigation), gizmos, panels, textures, export and reset.
- New documents get the scene, three-point lights and the dynamic grid by default, without
  being marked as modified. Documents created by scripts and opened files are left alone.

## ShowRoom 1.0.1

Fixed
- With ShowRoom installed, Part objects lost `ViewObject.DiffuseColor`, which broke other
  add-ons that read it (for example SheetMetal's *Make Wall*). The texture watcher used a GUI
  document observer that FreeCAD calls while a view provider is still being built; handing
  that view provider to Python gave it the generic wrapper for good. Textures now follow the
  display mode with a Coin sensor instead.

## ShowRoom 1.0.0

First release under the new name. ShowRoom continues Display Tools 1.7.1 and opens its documents.

New
- Name, workbench, menu and toolbars are now *ShowRoom*; commands are `ShowRoom_…`.
- The scene icon opens the scene settings in the task panel (it creates the scene
  configuration the first time); the separate *Display effects panel* command is gone.
- New scenes: shadow and ambient occlusion quality High, shadow darkness 50 %.
- New icons for the workbench, appearance, effects, rigs, turntable and SpaceMouse locks, in
  the style of the scene icon (source: `tools/icons/gen.py`).
- Preferences are copied from Display Tools on the first start; a warning appears if Display
  Tools is installed too.

Changed
- Licence: LGPL-2.1-or-later, like FreeCAD (Display Tools was MIT; see NOTICE.md).

# Display Tools (previous name)

## 1.7.1

Fixed
- The sun icon jumped the first time it was clicked: its circle around the model was only
  measured on selection. It now follows the model (recompute, show/hide, undo, opening).

## 1.7.0

New
- *Appearance…* replaces *Texture…* and *Remove texture*: one task panel for color,
  transparency, shininess, display mode, lighting, draw style, lines, points and texture
  (with a *None* tile). OK keeps, Cancel puts everything back. Also in the right-click menu.
- Directional light task panel: *Morning*, *Noon*, *Evening*.

Fixed
- Picking another texture in the panel did not change the image on screen (FreeCAD keeps the
  new image under the old file name).
- *Remove texture* closed the panel, and reopening it laid the default wood again.

## 1.6.0

New
- Light gizmos replace Coin's manipulators: constant-size icons, and when a light is selected,
  handles drawn over the model (spot: axis arrows, target that snaps to the surface, cone grip;
  sun: compass and elevation arc; point: drop line). Hover highlight, one undo step per drag,
  Esc cancels, double click opens the task panel. Not tinted by shadows or ambient occlusion.
- Floating QML panel in the 3D view for the selected light (pin, close, *All options…*),
  with a compass for the sun and quick presets. Preference `InViewPanel`.
- Spot lights have a `Target`: moving the light keeps it aimed at the same point.

Changed
- `Scale` and `GizmoPosition` are no longer used and are hidden in old files.

## 1.5.0

New
- QML task panels for lights, dynamic grid, display effects and textures, opened by double
  clicking the object in the tree or at creation, with OK / Cancel as in Part Design. Same
  components as the Plastic add-on; Qt Widgets fallback when Qt Quick is missing.

Fixed
- With more than about 5 lights switched on and shadows on, Coin's shadow shader failed to
  compile (more than 8 OpenGL lights). The lights beyond the limit are now left out, with a
  message.
- Texture gallery: the chosen image is recognised although FreeCAD renames the copy it keeps.

## 1.4.0

New
- Textures: an image per object, box projected (`TextureImage`, `TextureScale`,
  `TextureRotation`), stored in the document. Six tileable materials included.
  Hovered and selected faces are highlighted over the image, in FreeCAD's own colors.

## 1.3.0

New
- Light rigs: three-point, studio, sun. `Azimuth` / `Elevation` on directional lights.
- Shadow catcher (`ShadowCatcher`): soft shadow on an invisible ground.
- Display effects task panel, also opened by double clicking the scene configuration
  in the tree or from its context menu.
- Turntable (`TurntablePeriod`).

Fixed
- With shadows on, directional and spot lights with `CastShadows` off cast shadows anyway
  (blocky ones), and through the code path that could crash FreeCAD: Coin turns every light
  found inside its shadow group into a shadow caster. They are now kept outside of it.

## 1.2.0

New
- Effects are paused while the view is navigated (`WhileNavigating`,
  `NavigationResumeDelay` on the scene configuration).

## 1.1.0

Compatibility
- Works on FreeCAD 26.3. There `getSceneGraph()` returns a new root node, with the view's
  own lights in a separate group: lights inserted at fixed child positions ended up *after*
  the model and lit nothing. The lights are now placed by looking at what the scene graph
  really contains, which also keeps FreeCAD 1.0 / 1.1 working.
- Qt6 / PySide6: `Utils.qtutils` imports through FreeCAD's `PySide` shim only.
- Proxies define `dumps` / `loads` (the names FreeCAD uses with Python 3.11+).

New
- Real-time shadows (Coin shadow group), with a `CastShadows` switch on directional and
  spot lights.
- Screen space ambient occlusion.
- Dynamic grid: `ZOffset`, `CenterOnScene`, `GroundPlane`, `GroundColor`.
- Spot light: `DropOffRate`. Directional light: `GizmoPosition`.
- SpaceMouse lock rotation / translation / horizon are implemented.
- "Display Tools" menu; every command creates one undo step.

Fixed
- Dynamic grid not always at the lowest point of the scene: it reacted to a visibility
  change before the view had applied it, only counted solids with a volume, and ignored
  the placement of containers (Part, Body, Link). The bottom of the scene is now measured
  on the 3D view itself, a moment after the change.
- Grid not placed when created, lines overshooting when `Size` is not a multiple of
  `Spacing`, `Placement` rotation ignored, grid inflating *Fit all*.
- Opening a saved document raised "Property ... already exists" for every light, after
  which lights and grid were no longer recognised (duplicate scene folders, ...).
- Lights, manipulators and grid were added to whatever 3D view happened to be active:
  wrong document when loading files, missing in a second view, never back after
  undoing a deletion, drawn twice in the active view.
- Manipulator drawn away from its light as soon as `Scale` was not the default.
- Directional light created with a null direction; spot cut-off accepted up to 180°
  (Coin's limit is 90°).
- "Not yet implemented" printed at every start; debug output flooding the console and
  report view.
- `package.xml`: icon path with the wrong case (no icon in the Addon Manager on Linux),
  licence not matching the LICENSE file.

- Crash (segmentation fault in `SoSeparator::GLRenderInPath`) with ambient occlusion or
  shadows on, e.g. when selecting a group in the tree. The off-screen passes rendered the
  whole selection root, FreeCAD's "selection on top" included, with the view's own render
  action: paths queued for the end of the frame got the wrong root. The passes now render
  only the view providers' roots, with transparency off, and ambient occlusion is drawn in
  the end-of-frame phase.
- Grid cut off by the camera clipping planes (it was left out of the view's bounding box).
- Shadow maps of directional lights are fitted to the model, not to grid and gizmos.

Changed
- Grid and light manipulators count again for *Fit all*.
- Commands are prefixed `DisplayTools_` (they are global in FreeCAD; names such as
  `Separator` or `Dynamic_Grid` could clash with other addons). Custom toolbars that
  used the old names need the buttons added again.
- New lights start at intensity 0.6 instead of 1.0.
- The scene folder no longer creates the unused, hidden `Lights` part.
- Removed the unfinished `CoinLights/manipulator.py`, backup files and the test command.
