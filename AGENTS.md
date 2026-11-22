# Working on ShowRoom with an AI coding assistant

ShowRoom is a FreeCAD addon that presents models in the live 3D view:
lights with gizmos, real-time shadows, a shadow catcher, ambient
occlusion, appearance and textures, a turntable, a dynamic grid. It is
written entirely in Python on FreeCAD's Coin scene graph, with Qt Quick
(QML) panels, and needs no change to FreeCAD itself.

These files tell an assistant, or a new contributor, how code here is
written, how the interface behaves, and what has already gone wrong.

Read this file first, then the guide for the task at hand:

| Task | Read |
|---|---|
| Any change | [workflow](docs/agents/workflow.md), [code style](docs/agents/code-style.md) |
| New module, moving code, scene graph work | [architecture](docs/agents/architecture.md) |
| Anything a user sees or touches | [UI and UX](docs/agents/ui-ux.md) |
| Coin, Qt, QML, FreeCAD API work | [pitfalls](docs/agents/pitfalls.md) |
| Before you say "done" | [testing and checks](docs/agents/testing.md) |

Deeper records: `CHANGELOG.md` (what changed and why, per version), the
module docstrings of `SceneFX/` (each effect explains its own design and
the crashes it avoids).

## The rules that matter most

1. **Never crash FreeCAD.** A display effect is optional; FreeCAD and the
   user's work are not. Prefer an effect that quietly turns itself off,
   with a line in the Report view, to one that can take FreeCAD down.
2. **Addon, not fork.** Never require a change to FreeCAD. New effects add
   their own nodes beside FreeCAD's and never reshape, traverse or mirror
   FreeCAD's nodes (the older effects that do are known risks, see
   [pitfalls](docs/agents/pitfalls.md)); put back anything borrowed; leave
   no trace when an effect is switched off or ShowRoom is removed.
3. **Qt Quick first.** New interface is QML in `dtpanels/qml`. QtWidgets
   only where FreeCAD requires a widget (a task dialog's form, a
   preferences page), kept as thin as possible.
4. **The interface never waits.** Every control shows hover, press and
   its new state at once; heavy work (bakes, scene syncs) follows on a
   later event-loop turn.
5. **Short, self-explanatory code.** Names over comments; comments only
   for what the code cannot say (usually *why*). No magic numbers. Fewer
   lines when it costs no clarity. Fully typed.
6. **Priorities when they conflict:** stability, then performance, then
   readability, then Pythonic idiom. If an optimisation costs readability
   or lines, present the trade-off and let the maintainer decide.
7. **The maintainer runs git.** Do not commit, push, merge or switch
   branches. Suggest a commit message instead.
8. **A fix that didn't work is reverted** before the next attempt. Never
   stack speculative fixes; find the cause first (see
   [testing](docs/agents/testing.md), "Chasing a crash").
9. **Say what was and wasn't verified.** Headless tests are not a running
   FreeCAD; say which one you used.
