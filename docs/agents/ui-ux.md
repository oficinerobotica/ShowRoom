# UI and UX

ShowRoom should feel like a well-made part of FreeCAD: quiet, quick,
predictable, and never in the way of modelling.

## The 3D view comes first

- **Effects never slow modelling.** An effect that is expensive pauses
  or simplifies itself while the camera moves (`SceneFX/navigation.py`)
  and while things are dragged, and comes back when they stop.
- **Effects never get in the way.** Effect geometry is unpickable,
  ignored by fit-all, and drawn behind the model it belongs to.
- **Degrade honestly.** If an effect can't run on this system or this
  model, it turns itself off and says why once in the Report view, rather
  than drawing something wrong (a black slab where a shadow should be).
- Look right in FreeCAD's light and dark themes, in perspective and
  orthographic views.

## Feedback and responsiveness

- **Every control responds at once**: hover, press and release are drawn
  immediately. A switch or selector changes visually *first*; the work it
  triggers starts a frame later.
- **Widget state never waits on computation.** Scene syncs, bakes and
  recomputes happen after the frame that shows the change.
- Animations are short (~90–150 ms) and never animate a colour through
  `"transparent"` (that is transparent *black*); animate opacity instead.

## Desktop conventions

- Arrow cursor on buttons, switches, rows and chips. Pointing hand only on
  text links.
- Double-click opens an object for editing (the scene folder opens its
  panel). Escape backs out of the innermost thing (popup, panel), never
  two at once. Return applies; Escape in a field reverts.
- One user action, one undo step.
- Mouse wheel over a number steps it (fine; with the modifier, coarse).

## Keyboard

- Tab order is reading order: left to right, then top to bottom. Every
  value control takes Tab focus.
- Focus is drawn by a ring in the accent colour for keyboard focus only;
  hover is a separate, plainly visible cue.

## Controls

- **Switches, not checkboxes**, for on/off settings.
- **Segmented control** for a few choices (Low / Medium / High);
  **dropdown** for longer lists.
- Labels are short; explanation goes in a tooltip.
- A value that can't be changed in the current mode is hidden, not shown
  disabled, unless seeing it helps (then read-only).

## Information

- Every state has a non-colour cue. Interactive borders ≥ 3:1 contrast,
  text ≥ 4.5:1.
- Plain words in messages: what happened and what to do.
