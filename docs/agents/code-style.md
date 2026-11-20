# Code style

## Priorities

1. Stability: nothing ShowRoom does may crash FreeCAD.
2. Performance: the view must stay smooth on large models.
3. Readability: a newcomer can follow it without the history.
4. Pythonic idiom.

When these conflict, present the options and let the maintainer choose.

## Python

- Python 3.11, `from __future__ import annotations` in every module.
- **Fully typed.** mypy runs with `disallow_untyped_defs`. FreeCAD and
  pivy objects are `Any`; don't invent stubs for them.
- 79 columns. ruff (`E W F N D2 D3 D4 I`) and pycodestyle must pass.
- Qt and FreeCAD dictate camelCase for overrides, slots, properties,
  signals and proxy methods (`onChanged`, `setEdit`, `slotCreatedObject`);
  mark those `# noqa: N802`. Package names that saved documents refer to (`SceneFX`,
  `CoinLights`) stay as they are.
- Names carry the meaning: `light_slopes(direction)`,
  `scene_bound_box(view)`, `document_lights(doc)`. Prefer a well-named
  small function to a comment.
- **Comments are rare.** Write one only where the code can't say it: a
  FreeCAD, Coin or Qt behaviour being worked around, a non-obvious reason,
  a unit. Never narrate what the next line does.
- **Docstrings:** a one-line summary saying what the thing *is* or gives
  ("(sx, sy): how far a shadow moves in x and y per unit of height.").
  Module docstrings
  explain the idea in a short paragraph, and any crash the design avoids.
- **No magic numbers.** Name them as module constants with a `#:` comment
  when the reason isn't obvious (`SYNC_DELAY_MS = 30`, `MIN_SLOPE = 0.25`).
- Fewer lines when clarity doesn't suffer: comprehensions, early returns,
  tables (dicts) instead of if-chains, numpy instead of Python loops over
  geometry.
- `except Exception:` only at a boundary FreeCAD or Qt calls into (an
  observer slot, a timer callback, a command), with
  `# noqa: BLE001 - <why>` and a line in the Report view
  (`FreeCAD.Console.PrintError("ShowRoom: ...\n")`). Never silently
  swallow in logic; `contextlib.suppress(...)` for an exception that is
  deliberately ignored.
- Imports of FreeCAD, FreeCADGui, pivy, PySide and workbench modules
  (`Part`) go inside the function that needs them, so modules import and
  test headlessly. Pure computation (geometry, colour, layout) lives in
  modules that import neither.
- ShowRoom's own preferences go through `Utils/prefs.py` (`prefs.get`,
  with a default in `DEFAULTS`). A document's effect settings are
  properties of its scene folder (`create_scene_config.py`). Never call
  `App.ParamGet` for ShowRoom's values elsewhere.

## QML

- Panels live in `dtpanels/qml`; Python reaches them only through the
  bridge objects in `dtpanels/bridge.py`, and models in
  `dtpanels/models.py`. QML holds no FreeCAD logic.
- A short `//` header comment says what the component is and how to use
  it. Inline comments only for workarounds.
- Colours, sizes and fonts come from the theme the bridge provides, in
  light and dark. No hex literals, no hard-coded pixel sizes that should
  scale with the font.
- Prefer drawing small primitives to `QtQuick.Controls`; where a Control
  is used it is `QtQuick.Controls.Basic`, fully restyled.
- `property` names don't repeat a parent's name (it shadows it and reads
  as a binding loop).

## Text a user reads

- Short labels in FreeCAD's own terms where FreeCAD has one ("Body",
  "Sketch"); tooltips may be full sentences.
- ShowRoom is not translated yet. Keep user text in one place per panel
  (the models) and build no sentence from fragments, so translation can be
  added later.
