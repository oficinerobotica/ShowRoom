# Testing and checks

## Checks before handing over

ShowRoom has no CI yet. Run these on every Python file you added or
rewrote (older files are not held to them until they are rewritten):

```bash
ruff check --line-length 79 --select E,W,F,N,D2,D3,D4,I \
    --ignore D203,D213,D400,D401 <files>
pycodestyle --max-line-length 79 <files>
mypy --disallow-untyped-defs --ignore-missing-imports <files>
bandit -q <files>
for t in tests/test_*.py; do python "$t"; done
```

Package names that saved documents refer to (`SceneFX`, `CoinLights`)
stay as they are: ignore ruff's `N999` for them.

Bandit is what FreeCAD's Addon Report scores addons with, across the
whole repository. Fix findings rather than silencing them:
`contextlib.suppress(...)` for an exception deliberately ignored,
`unittest`'s `assert*` methods in tests. Where a finding is a false
positive, `# nosec B<id>  # reason` on the flagged line.

A `pyproject.toml` with these settings and a CI workflow running them
are the natural next step once there is code held to them.

## Kinds of test

- **Pure logic**: geometry, colour and layout modules import neither
  FreeCAD nor Coin, and are tested directly with `unittest` in
  `tests/test_<module>.py`.
  Most tests should be this kind; design modules so they can be.
- **Logic with stand-ins**: FreeCAD objects as `types.SimpleNamespace`
  with the attributes the code reads.
- **Headless FreeCAD**: `QT_QPA_PLATFORM=offscreen freecadcmd` for
  document behaviour. No 3D view there.
- **Running FreeCAD**: the only check for what the view shows and for
  crashes. Say when this wasn't done.

## Good tests here

- Test the behaviour a user would notice (the shadow moves away from the
  light, a hidden body casts nothing), not the implementation.
- A bug fix comes with the test that would have caught it.
- Per-feature test classes (`ShadowTests`, `LightTests`).

## Chasing a crash

Crashes in the 3D view are often heap corruption: the crash shows up
where the damaged memory is next touched, not where it was damaged, and
not every time.

1. **Repeat each configuration three times.** One run that doesn't crash
   proves nothing.
2. **Get both stacks.** Python's, written to a file so it survives:
   `import faulthandler; _fh = open('/tmp/fc_crash.txt', 'w');
   faulthandler.enable(file=_fh, all_threads=True)` in the console.
   The native one: `gdb -q -ex run -ex "bt 40" --args freecad` (for an
   AppImage, its path; on Arch, `DEBUGINFOD_URLS` for symbols).
3. **Bisect by removing, not by adding fixes.** Turn effects off one at a
   time, then take nodes out of the live graph from the console, until
   the crash goes away three times in a row.
4. **For corruption, use a memory checker** (valgrind) rather than more
   bisection: it reports the first bad write.
5. Record what was learned in [pitfalls](pitfalls.md).
