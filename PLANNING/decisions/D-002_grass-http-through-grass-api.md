---
id: D-002
date: 2026-10-23
status: accepted
decided-by: epifanio (standing choice in CLAUDE.md; recorded by plan-adopt-groundtruther, 2026-10-23)
lanes: U, C
enforce: requests in mixins/
enforce: requests in pygui/
---
**Decision.** All GRASS/FastGIS HTTP goes through `gt/grass_api.py`, which raises `GrassApiError`.
No mixin and no dialog makes its own HTTP call.

**Why.** One client means one place for the base URL, the API key, timeouts, error translation and
retries, and it is the reason the GRASS layer can be unit-tested without a server
(`tests/unit/test_grass_api.py`). A mixin that called `requests` directly would duplicate the key
handling and bypass `GrassApiError`, so a failure would surface as a raw traceback in the QGIS log
instead of a handled message.

**Binds.** Lanes U and C. `mixins/` and `pygui/` were clean of `requests` at `master` d7affe8
(2026-10-23) and the `enforce` lines keep them so. `ioutils.py` imports `requests` at line 6 for
non-GRASS downloads and is deliberately outside the scope; a new GRASS call there would still be
wrong. Widening the scope beyond these two directories needs a new record.
