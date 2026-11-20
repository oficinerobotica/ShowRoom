# Architecture

## Packages

```
InitGui.py, Init.py   workbench registration; heavy setup deferred until
                      the workbench is activated
create_*.py           commands and the document objects they create
                      (scene folder, lights, effects, textures, settings)
showroom_toolbars.py  toolbar and menu registry
CoinLights/           light objects: directional, spot, point, rigs
Gizmos/               on-screen light handles and their interaction
HelperTools/          dynamic grid
SceneFX/              the effects in the 3D view
  view_rig.py         keeps every view of a document in line with its
                      lights and scene settings (see its docstring)
  shadows.py          real-time shadows (Coin's SoShadowGroup)
  shadow_catcher.py   shadow on an invisible ground
  ambient_occlusion.py
  textures.py, navigation.py, turntable.py, autoscene.py
SpaceNav/             SpaceMouse locks
Utils/                prefs, view_utils (scene graph helpers), Qt helpers,
                      resource paths   (imports nothing else of ShowRoom)
dtpanels/             QML panels: bridge, models, overlay, qml/
tools/                developer tools (icon generator)
tests/                headless tests (to be added with the first module
                      that has pure logic to test)
```

- `Utils` imports nothing else of ShowRoom. Effects import `Utils`, never
  each other's internals; `view_rig` is the one place that composes them.
- A new effect is a package or module in `SceneFX/` with a small public
  surface (`sync(...)`, `forget_except(...)`), called from `view_rig`.
- Pure computation is kept apart from FreeCAD and Coin, in modules that
  import neither, so it can be tested headlessly.

## The scene graph

`view_rig.sync_document` is idempotent: it looks at what the document
holds now and what each view holds now, and fixes the difference. It runs
again, a moment later, whenever something that matters may have changed.
There is no other bookkeeping to keep in step.

- **Add beside, don't reach inside.** A new effect adds its own nodes at
  the top of the view's scene and finds them again by name. It never
  traverses, measures or re-parents FreeCAD's view-provider nodes from
  Python, and never holds them in a second parent (see
  [pitfalls](pitfalls.md)). The current shadows, shadow catcher and
  ambient occlusion still do some of this; they pause around sketch
  editing and plane picking instead (1.1.6).
- **Read the document, not the view.** Geometry an effect needs (shapes,
  bounding boxes, placements) comes from the document objects, triangulated
  coarsely with `Shape.tessellate`, which reuses the view's mesh.
- **Nothing off screen.** No `SoSceneTexture2` or `SoOffscreenRenderer`
  for a new effect: both fail or crash on some systems. Bake on the CPU
  (numpy) into a plain `SoTexture2`. Ambient occlusion and the shadow
  catcher still use scene textures.
- **An effect that is off leaves no node.** Switching it off removes its
  nodes; switching it on adds them again.

## Patterns to reuse

- **Rebuild and compare, not incremental mutation:** compute a key of
  what an effect depends on; redo the work only when the key changes.
- **Deferred work through timers parented to the main window** (or an
  owner), never a static `QTimer.singleShot` on a bound method.
- **Coarse while dragging, fine when settled:** changes closer together
  than a short interval get a cheap result now and a full one once they
  stop.
- **Feature detection, not version numbers:** a property or method
  FreeCAD lacks is skipped (`getattr`/`hasattr`), so one code path serves
  several FreeCAD versions.
- **Reload-safe:** new long-lived objects (observers, timers) need a
  teardown path and must survive the module being reloaded.

## Where to put things

- A new effect: `SceneFX/`, called from `view_rig`, its settings as scene
  folder properties, its controls in the scene panel model.
- A new panel or control: `dtpanels/qml` and its model, reached through
  the bridge.
- A constraint the code works around: one paragraph in the module's
  docstring, and an entry in [pitfalls](pitfalls.md) if it can bite
  elsewhere.
