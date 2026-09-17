# MBES soundings

`Mbes.soundings` — the per-beam multibeam table the
[Acoustic Query Builder](../tools/query-builder.md) selects from and plots.

- **Format:** Apache **Parquet** (read with `pandas.read_parquet`, or
  `cudf.read_parquet` when `Processing.gpu_avaibility` is on).
- **One row per beam per ping.** These files are large — the reference dataset
  has **14 526 619 rows**.
- **Reference file:** `mbes_2015_multilevel.parquet` — 14.5 M rows, 18 columns.

---

## Geometry

The query builder reads its coordinate columns **by name from editable text
fields**, so you can point it at differently named columns without changing any
code. The defaults match the table below.

| Column | Query-builder field | dtype | Units | Meaning |
|---|---|---|---|---|
| `Easting` | **Easting** (`xutm`) | float64 | m | Projected easting of the sounding. Used for point-in-polygon selection against the sampling shape and as the X axis of the 3-D surface. |
| `Northing` | **Northing** (`yutm`) | float64 | m | Projected northing. |
| `Longitude` | **Longitude** | float64 | ° WGS-84 | Geographic position. |
| `Latitude` | **Latitude** | float64 | ° WGS-84 | Geographic position. |
| `Depth` | *(fixed name)* | float64 | m, positive down | Sounding depth. The 3-D viewer plots it **negated** (`Z = −Depth`) so the seabed renders the right way up. |

!!! warning "All four coordinate fields must exist"
    On load, the query builder checks that the four named columns are present.
    If any is missing it logs `validate_fields: missing columns […]` to the
    `GroundTruther` message-log tab and the spatial tools stay disabled. The
    **UTM zone** field beside them (default `19`) is used when building the
    projection for the query — it is free text and falls back to `19` if blanked.

## Backscatter

GroundTruther supports two soundings schemas, and detects which one you have
from the column names alone
(`gt/mbes_fields.py` · `detect_backscatter_fields`).

**Multi-level schema** (the reference file) — the successive stages of the
BSWG-2015 Ch. 6 backscatter-processing chain, each in decibels:

| Column | Stage |
|---|---|
| `BS_raw_dB` | The raw recorded backscatter level, before any compensation. |
| `BS_RL_dB` | Received level. |
| `BS_TL_dB` | Transmission-loss compensated. |
| `BS_area_dB` | Ensonified-area normalised. |
| `BS_AVG_dB` | Angular-response corrected (`mbbackangle`, referenced to 30°). **The most processed level, and the default selection.** |

**Legacy schema** (`mbes_2015.parquet`) — a single processed pair:

| Column | Stage |
|---|---|
| `Backscatter Value` | Uncorrected. |
| `Corrected Backscatter Value` | Angular-response corrected — the legacy equivalent of `BS_AVG_dB`. |

The authoritative definitions of the chain stages are in the dataset's own
README; GroundTruther only needs the names.

### How the default is chosen

The **backscatter field** combo box is filled by scanning your columns against
this preference list and keeping the ones that are present, in this order:

```
Corrected Backscatter Value → BS_AVG_dB → BS_area_dB → BS_TL_dB
→ BS_RL_dB → BS_raw_dB → Backscatter Value
```

The **first match becomes the default selection** — i.e. the most corrected
level available. Any other column whose name starts with `BS_` or contains
"backscatter" (case-insensitive) is appended after the known ones, so a schema
GroundTruther has never seen still offers its backscatter columns rather than
none. If nothing matches, a warning naming your actual columns is written to the
message log and the combo stays empty.

Your current selection is preserved across data reloads when the column still
exists.

## Beam geometry

| Column | dtype | Units | Meaning |
|---|---|---|---|
| `True Angle` | float64 | ° | Beam incidence angle at the seabed, **signed**: negative = port, positive = starboard. This is the X axis of the angular-response plot and the column the port/starboard filter acts on. Range in the reference file ≈ ±85°. |
| `Nominal Angle` | float64 | ° | The nominal (uncorrected) beam angle. Narrower range than `True Angle` (≈ ±60° in the reference file). Not read by the plugin. |
| `Beam Number` | int32 | — | Beam index within the ping, `0…511` in the reference file. Not read by the plugin. |
| `Beam Flag` | int16 | — | Per-sounding quality/rejection flag from the processing software. **All zero throughout the reference file**, so its value encoding cannot be read off the data. Not read by the plugin — GroundTruther does not filter on it, so pre-filter rejected soundings yourself if your file flags any. |

### The beam filter

The query builder's four mutually exclusive radio buttons work purely on
`True Angle`:

| Button | Effect |
|---|---|
| **Raw** (default) | All beams, unchanged. |
| **L** | Port only — keeps `True Angle < 0`. |
| **R** | Starboard only — keeps `True Angle > 0`. |
| **Fold** | Replaces `True Angle` with its absolute value, overlaying both sides on one angular axis. |

## Ping identity and time

| Column | dtype | Units | Meaning |
|---|---|---|---|
| `Ping Time` | float64 | s | Ping timestamp as Unix epoch seconds — verified identical to `datetime`. |
| `datetime` | datetime64[us] | — | The same instant as a timestamp. |
| `Ping Number` | int64 | — | Sequential ping counter. |
| `line` | string | — | Survey line identifier. **Read by the plugin**: the two grouped density plots (*Group Norm* and *Group Scaled*) colour and fill by this column, so each survey line gets its own curve. Values in the reference file look like `170_001_1942` — day-of-year, line number, start time (day 170 and 171 of 2015 are indeed 19 and 20 June) — but the encoding is the survey's own and nothing in GroundTruther parses it. |

---

## Bringing your own soundings

| You must provide | Notes |
|---|---|
| Easting / Northing / Longitude / Latitude | Under any names — set them in the query builder's four coordinate fields. |
| `Depth` | Name is fixed. Positive down. |
| `True Angle` | Name is fixed. Signed, port negative. |
| At least one backscatter column | Either a known name from the list above, or any `BS_*` / `*backscatter*` name. |
| `line` | Only needed for the two grouped density plots. |

Everything else is optional. Keep the file in Parquet — the point-in-polygon
selection is `numba`-compiled over the raw column arrays, and a CSV of this size
would not be workable.
