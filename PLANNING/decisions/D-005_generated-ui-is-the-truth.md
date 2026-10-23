---
id: D-005
date: 2026-10-23
status: accepted
decided-by: epifanio (standing choice in CLAUDE.md; recorded by plan-adopt-groundtruther, 2026-10-23)
lanes: U
---
**Decision.** The generated `pygui/Ui_*.py` files are the truth for the UI, not `qtui/*.ui`.
**Never run `compile_ui.sh` wholesale.** Hand-edit the generated `.py`, or regenerate a single `.ui`
you have verified is current. New Settings widgets are added **programmatically** in `ConfigDialog`,
not to `qtui/app_settings_ui.ui`.

**Why.** The 12 `.ui` files in `qtui/` are stale: video widgets and others were hand-added straight
to the generated `.py` and the `.ui` was never updated, so regenerating silently drops them —
quietly, with the tests still passing. `app_settings_ui.ui` and `grassapi_settings_ui.ui` are
known-stale. `qtui/*.py` is git-ignored, which is why the generated `.py` under `pygui/` is what is
actually committed and reviewed.

**Binds.** Lane U. Not machine-checkable (it is about an action, not a textual signature), so it
lives here and in `CLAUDE.md`. A plan that wants the `.ui` files to become the truth again must
first make one of them current and prove it, in its own plan, and supersede this record.
