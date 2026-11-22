# Coin, Qt, QML and FreeCAD pitfalls

Each of these has broken ShowRoom, or the projects it learned from,
before.

## Coin inside FreeCAD

- **Don't draw shadow maps from FreeCAD's view-provider nodes.** The
  real-time shadows render their maps from the view providers' roots held
  in a second parent group ("mirrors"). With shadows on, FreeCAD crashed
  in `SoSeparator::GLRenderInPath` when Part Design opened a sketch, or
  reported `malloc(): unsorted double linked list corrupted`. Bisected in
  a running FreeCAD 27.1: the `SoShadowGroup` around the selection root
  alone did not crash; the maps drawn from the mirrored roots did. 1.1.6
  pauses the effects around sketch editing and plane picking. A new
  effect reads geometry from the document (`Shape.tessellate`,
  `BoundBox`, `getGlobalPlacement`) and draws from its own nodes.
- **Don't run Coin actions on FreeCAD's nodes from Python** (bounding
  box, search) or hold them in a second parent. Not proven harmful on its
  own, but it shares the mirrors' risk and is never needed: the document
  has the same information.
- **Don't draw an effect on a copy of the model.** A copy outside
  FreeCAD's scene doesn't follow what FreeCAD does to the real model:
  Sketcher's section clip plane, clipping planes, display modes,
  transparency, selection highlighting. Tried for real-time shadows: the
  part Sketcher cut away was drawn as a dark ghost. An effect on the model
  itself must shade FreeCAD's own geometry (Coin's `SoShadowGroup`).
- **No `SoSceneTexture2` in the view, no `SoOffscreenRenderer`.** A
  scene texture renders with the view's own render action: paths queued
  for the end of the frame from inside it (selection on top, annotations,
  transparent objects) start at our node and Coin replays them off the
  end of a child list (see `SceneFX/ambient_occlusion.py`). Bake on the
  CPU into a plain `SoTexture2` instead.
- **An empty texture is not invisible.** A textured face whose texture
  has no image yet draws in its material colour: keep it in a switch that
  is off until the image is set.
- **`SoOffscreenRenderer.render()` can fail.** It returned false in a
  FreeCAD 27.1 AppImage on Linux: no off-screen GL context. Never rely on
  it; if used, check its result and fall back.
- **Don't change the graph from inside a redraw.** Transparent shapes
  and annotations are drawn at the end of the frame from saved paths; a
  graph reshaped in between leaves those paths pointing at the wrong
  children.
- A Gui observer with `slotChangedObject` breaks Python view providers;
  use the App observer (see `SceneFX/textures.py`).
- pivy has no Python classes for some nodes (the shadow nodes): create
  them from their type names and set fields through the generic field
  interface (`Utils/view_utils.new_node`, `set_field`).
- Changing a field notifies and redraws: compare before setting
  (`shadows._set_float`).

## Qt and PySide

- **No Python exception may escape a Qt callback** (slot, timer, event
  filter): it can terminate the process. Guard the boundary and report to
  the Report view.
- **`QTimer.singleShot` with a bound method or lambda outlives its
  object.** After a reload it fires into a deleted wrapper. Use a `QTimer`
  parented to the main window or an owner.
- PySide6 enums are `enum.Enum`: use `.value`, not `int()`.
- FreeCAD imports PySide as `PySide`; import from there.

## QML

- **Never destroy a QML object from inside its own signal handler.** It
  calls `qFatal` and FreeCAD exits. Defer with `Qt.callLater`.
- A `MouseArea` that accepts presses takes an exclusive grab.
- `TapHandler.tapped` fires again on a double tap; use `singleTapped` and
  `doubleTapped` when both mean something.
- A popup that closes on focus loss must outlive the click on it.

## FreeCAD

- **`setEdit` nests an event loop**, and Part Design's sketch creation
  shows and hides objects (`Show.TempoVis`) while its dialog is open. Any
  effect that resyncs on visibility changes runs in the middle of it: keep
  that sync cheap and safe.
- A selection inside a Body is filed under the Body (`("Body", "Pad.")`).
- Objects inside a hidden Body or Part are not shown even if their own
  `Visibility` is true: walk `getParentGeoFeatureGroup()`.
- A shape's points from `tessellate` are in the shape's placement, not
  the document's: apply `getGlobalPlacement() * Placement.inverse()`.
- Workbench commands don't exist until their Gui module is imported.
- Prefer detection (`hasattr`) to version checks; FreeCAD versions differ.
