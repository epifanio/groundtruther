---
id: D-006
date: 2026-09-24
status: accepted
decided-by: epifanio (standing choice in CLAUDE.md; recorded by plan-adopt-groundtruther, 2026-10-23)
lanes: D, C, U
enforced-by: tests/unit/test_settings_docs.py
---
**Decision.** User-facing documentation is the MkDocs Material site in `website/`, published to
<https://epifanio.github.io/groundtruther/>. `help/` is a retired Plugin Builder Sphinx stub —
**do not add documentation there.** Adding a feature means adding its tool page **and** its config
keys to `website/docs/configuration/settings-reference.md`.

**Why.** One home for user docs, checked by `mkdocs build --strict -f website/mkdocs.yml` (§5.2
rule 4), which catches broken internal links and pages missing from the nav. `help/` survives only
because `Makefile` and `pb_tool.cfg` expect `help/build/html` to exist; it holds four files
(`Makefile`, `make.bat`, `source/conf.py`, `source/index.rst`) and a pointer at the site.
`docs/grass_fastgis.md` and `docs/photogrammetric_ribbon.md` are agent-facing deep dives and stay
out of the site deliberately.

**Binds.** Every lane that changes behaviour a user can see. The config-key half is enforced:
`tests/unit/test_settings_docs.py` and `tests/unit/test_config_check.py` fail if a key is added in
`config_model.py` or `config_check.SPEC` without its row in the settings reference (§5.2 rule 3).
Merging a `website/` change **publishes it** (`WORKFLOW.md` §8), so review the rendered page.
