---
id: D-009
date: 2026-10-24
status: accepted
decided-by: epifanio, 2026-10-24 ("Queue a planning session to promote 'no pandas datetimes in gt/' to a decision record."); the three questions below carry this session's recommendation and are accepted as written when this PR merges
lanes: U, C, P
enforce: (?<!\x60)pd\.(read_parquet|to_datetime|to_timedelta)\( in gt/
enforce: (?<!\x60)pd\.(read_parquet|to_datetime|to_timedelta)\( in pygui/
enforce: (?<!\x60)pd\.(read_parquet|to_datetime|to_timedelta)\( in mixins/
enforce: (?<!\x60)pd\.(read_parquet|to_datetime|to_timedelta)\( in scripts/
enforce: (?<!\x60)pd\.(read_parquet|to_datetime|to_timedelta)\( in *.py
---
**Decision.** Plugin code never lets pandas build a `datetime64` or `timedelta64`. Temporal data is
carried as **object dtype holding plain `datetime.datetime` / `datetime.timedelta`**, with the dtype
spelled out at every hand-off, and Arrow data reaches pandas through `gt/pandas_safe.py`
(`read_parquet`, `arrow_table_to_dataframe`, `object_series`, `parse_datetimes`,
`elapsed_seconds`) — never `pd.read_parquet`, `pd.to_datetime`, `pd.to_timedelta` or
`Table.to_pandas()` on a timestamp or duration column. Unconditional, on every platform and every
QGIS build. `gt/pandas_safe.py` is the one home for the reasoning and the helpers.

**Why.** In QGIS **4.2.1** on macOS, pandas' datetime C extension is broken — a pandas/numpy C-API
ABI mismatch in QGIS's own bundle (pandas 3.0.3 against numpy 2.5.0). It does not raise: it
SIGSEGVs the whole application (exit 139, no exception, nothing in the QGIS log), in pandas' own
`get_datetime_metadata_from_dtype`. An **empty** `datetime64` array is enough, so **the fault
cannot be probed for at runtime — the probe is the crash** (which is also why `gt/deps_check.py`
can report a missing module but can never report a broken pandas), and `pd.ArrowDtype` is a trap
that stores fine and dies when one element is read back. The real hazard is pandas' type
*inference*: the `DataFrame`/`Series` constructors and `set_index` infer `datetime64` from an
object-dtype array of datetimes, so "do not call `pd.to_datetime`" would be far too narrow a rule.
Measurements and the crash frame: [`../TODO_mac-install-test.md`](../TODO_mac-install-test.md) §5
and §6.2; the call sites fixed behind the helpers are PR #73 (`master` `e9a0d47`), PR #81
(`de84a58`) and PR #100 (`0155844`).

The rule is nevertheless **not a description of every build.** Measured by this session on
2026-10-24 against `/Applications/QGIS-final-4_2_3.app` (QGIS **4.2.3**: Python 3.12.11, pandas
**3.0.5**, numpy **2.5.2**, pyarrow **25.0.1**), in the signed harness of
[`../../CLAUDE.md`](../../CLAUDE.md), each case its own process run with `-u` and its exit status
read un-piped — **all nine returned cleanly, exit 0**:

| Case | 4.2.1 (quoted, §5) | 4.2.3 (measured 2026-10-24) |
|---|---|---|
| `pd.Series(np.array([], dtype="datetime64[us]"))` | SIGSEGV | exit 0 — `datetime64[us]`, len 0 |
| `pd.to_datetime(["2015-01-01"])` | SIGSEGV | exit 0 — `DatetimeIndex` |
| `pq.read_table(test_imagemetadata.pq).to_pandas()` | SIGSEGV | exit 0 — (5900, 38), `DatetimeIndex` `datetime64[us]`, first label `Timestamp('2015-06-19 18:11:42.496000')` |
| `pd.DataFrame([row])`, `row` named by object `datetime.datetime` labels | SIGSEGV (§6.2) | exit 0 — (1, 2) |
| `pd.to_timedelta([1, 2], unit="s")` | SIGSEGV | exit 0 — `timedelta64[s]` |
| `pd.Series(arrow, dtype=pd.ArrowDtype(pa.timestamp("us")))`, then `.iloc[0]` | SIGSEGV on the element read | exit 0 — `Timestamp` |
| `set_index` on an object-dtype datetime column | the inference that crashes | exit 0 — `DatetimeIndex` |
| `pd.read_parquet(test_imagemetadata.pq)` | SIGSEGV | exit 0 — (5900, 38), `DatetimeIndex` |

**QGIS 4.2.1 is no longer installed on this Mac** (`/Applications` holds only
`QGIS-final-4_2_3.app`), so its column above is **quoted from `TODO_mac-install-test.md` §5, not
re-measured.** What 4.2.3 shows is that the fault is a property of **one bundle's build**, not of
pandas 3, macOS or the plugin — and that nothing in the plugin can tell which bundle it is running
in.

So the rule stays unconditional, for three reasons that outlive the version: the plugin declares
`qgisMinimumVersion=4.0` and users on 4.2.1 exist; the safe readers are **correct and cheap on both
builds** (`arrow_table_to_dataframe` is Arrow→Python, and `temporal="epoch_us"` read 20.6 M MBES
soundings in 1.5 s), so nothing is paid for the caution; and a version gate would have to be a
runtime probe, which cannot exist. A platform or version branch would also leave the macOS path
untested, since Linux CI exercises only the other side of it.

**Binds.** Lanes U, C and P: `gt/`, `pygui/`, `mixins/`, `scripts/` and the root-level modules.
`tests/` is deliberately **out of scope** — `tests/unit/test_pandas_safe.py` poisons
`pd.read_parquet` and `pd.to_datetime` by name and `tests/unit/test_config_check.py` quotes
`pd.read_parquet("")`, so enforcing there would fail CI on the suites that defend this decision.
The `enforce` regex is **a grep that catches the obvious half only**: it matches the three banned
calls written out, and cannot see inference through a `DataFrame`/`Series` constructor or
`set_index`, which is the real hazard. `Table.to_pandas()` is deliberately **not** in the regex:
`gt/pandas_safe.py:253` calls it on the safe columns on purpose and `pygui/querybuilder_gui.py`
calls it on **cudf** objects, where it means something else entirely. The `(?<!\x60)` lookbehind is
what keeps the regex off the prose: `gt/pandas_safe.py`, `gt/image_manager.py` and
`pygui/querybuilder_gui.py` all name these calls inside ``` `` ``` to say *not* to use them. The
real guards remain `tests/unit/test_pandas_safe.py` and
`tests/unit/test_image_metadata_panel.py`, which assert the *shape* of the call and that no
`datetime64`/`timedelta64` dtype reaches the result — on Linux the same code is harmless, so CI can
pin nothing else.

**Asked, with this session's recommendation; your merge accepts them as written.** A different
answer is a new record that supersedes this one, not an edit (`decisions/README.md`).

1. **Scope** — recommend the wider one, written above: every hand-written module, not `gt/` alone.
   The crash does not care which directory it is in, and `pygui/` and `scripts/` had call sites of
   their own (PR #81).
2. **`enforce` or not** — recommend the five lines above, with the limits stated plainly. Verified
   by this session against the tree at `master` `d6f09e9` in both directions: clean as it stands,
   and a `pd.read_parquet(` planted in `gt/image_manager.py` is reported as D4.
3. **Permanent or expiring** — recommend **permanent**, with a stated review trigger rather than an
   expiry, since no code can tell which bundle it is in. **Review trigger:** the owner dropping
   support for QGIS 4.2.1 (`metadata.txt` `qgisMinimumVersion` moving past it). That, and nothing
   less, is what would make relaxing this rule safe — and it is the owner's call, not a
   measurement.
