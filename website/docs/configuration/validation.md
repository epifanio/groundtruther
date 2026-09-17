# Validation & troubleshooting

GroundTruther checks your configuration **one key at a time**. This page explains
what that means in practice, where the findings appear, and how to read the
messages it produces.

## Degrade, don't veto

Older versions validated the configuration as a single object: one stale path
made the *whole* file invalid, the plugin fell back to a set of empty strings,
and it then crashed reading an empty path — for a data source that was perfectly
fine. An external drive remounting under a different label was enough to take the
plugin down entirely.

Now each key is graded on its own:

| Severity | Which keys | What happens |
|---|---|---|
| **Error** | `HabCam.imagepath`, `HabCam.imagemetadata` — and only these | GroundTruther genuinely cannot run. It opens the Settings dialog once so you can fix it; if the problem survives, it shows a dialog naming the offending key and the value it saw. |
| **Warning** | Every other key, when it is **set but unusable** | The one feature that uses the key is disabled. Everything else runs normally. |
| *(silent)* | Every optional key, when it is **unset** | Nothing is reported. A partly configured install is a normal, supported state. |

The plugin then runs on a *degraded* copy of your settings in which **only the
failing keys are blanked**. A stale image path does not disable the query
builder; an unreadable soundings file does not disable the video player.

!!! info "The wrong key can't hurt the right one"
    This is the single most important thing to know when troubleshooting: if a
    feature is missing, the cause is almost always **its own** setting, not a
    neighbouring one.

## Where the findings appear

In the QGIS **message log** (*View → Panels → Log Messages*), tab
**`GroundTruther`**. Every finding is one line:

```
config: HabCam.imageannotation: file does not exist: '/data/hrs1508/detections.csv' — the feature using it is disabled
config: Roughness.epsg: below the minimum 1024: 619
```

Errors are logged at **Critical**, warnings at **Warning**. The log is written at
plugin start and again every time you save the Settings dialog, so it always
reflects the current file.

Fatal problems additionally raise a dialog:

```
GroundTruther cannot start with the current configuration.
Open Settings (wizard icon) and fix:
  • HabCam.imagepath: directory does not exist: '/run/media/epinux/SURVEY/imgs_jpg' (the drive may not be mounted)
```

## The unmounted-drive case

This is the failure that motivated the whole validation model, and it has its own
hint. Any missing path under `/run/media`, `/media`, `/mnt` or `/Volumes` gets
the suffix **"(the drive may not be mounted)"**:

```
config: HabCam.imagepath: directory does not exist: '/run/media/epinux/SURVEY/imgs_jpg' (the drive may not be mounted)
```

Plug the drive back in, or remount it, and reopen the plugin — nothing else needs
to change. If the drive comes back under a *different* label, the path really has
changed and you have to update it in Settings.

## Message → cause → fix

These are the exact reason strings the validator produces.

| Message | Cause | Fix |
|---|---|---|
| `not set` | A required key (`HabCam.imagepath` / `HabCam.imagemetadata`) is missing, `null`, or an empty string. | Set it in **Settings**. |
| `directory does not exist: '…'` | A `dir` key points nowhere. | Correct the path, or mount the volume. |
| `file does not exist: '…'` | A `file` key points nowhere. | Correct the path; check the file was not moved or renamed. |
| `… does not exist: '…' (the drive may not be mounted)` | As above, on removable media. | Mount the drive. See [above](#the-unmounted-drive-case). |
| `not a directory: '…'` | A `dir` key points at a *file*. | Point it at the containing folder. |
| `not a file: '…'` | A `file` key points at a *directory*. | Point it at the file itself. |
| `not readable: '…'` | The path exists but your user has no read permission. | Fix ownership/permissions on the file or its parents. |
| `parent directory does not exist: '…'` | `Session.groundtruther_project` names a file in a folder that does not exist. The file itself need not exist — it is created on first save. | Create the folder, or choose a path inside an existing one. |
| `not a valid http(s) URL: '…'` | A `url` key is missing its scheme or host — `api.fastgis.eu` instead of `https://api.fastgis.eu`. | Include the scheme. Only `http` and `https` are accepted. |
| `expected a path, got int: 5` | A path key holds a bare number (commonly an unquoted YAML value). | Quote it, or re-save from the Settings dialog. |
| `expected an integer, got str: 'utm19'` | A numeric key holds text. | Use the number alone — `32619`, not `EPSG:32619`. |
| `below the minimum 1024: 619` | `Roughness.epsg` is out of range. | Use a full EPSG code (`32619`), not a UTM zone number. |
| `above the maximum 999999: …` | `Roughness.epsg` is implausibly large. | Check for a typo. |
| `expected true or false, got str: 'maybe'` | A boolean key holds something unrecognised. YAML's `yes`/`no`/`on`/`off`/`1`/`0` *are* accepted. | Use `true` or `false`. |
| `expected a mapping of settings, got list` | A whole section is malformed — usually YAML indentation. | Compare against [`config.example.yaml`](https://github.com/epifanio/groundtruther/blob/master/config/config.example.yaml). |
| `no configuration loaded (missing or unparseable config.yaml)` | The file is absent or is not valid YAML. | Copy the example file and edit it; a YAML parse error is logged with its line number. |

## Symptom → setting

Working the other way round — a feature is missing and you want to know which key
to look at:

| Symptom | Look at |
|---|---|
| The plugin refuses to start / opens Settings immediately | `HabCam.imagepath`, `HabCam.imagemetadata` |
| Images browse but no detection boxes appear | `HabCam.imageannotation` |
| The query builder has no soundings | `Mbes.soundings` |
| The 3-D view shows a gridded point cloud instead of your DEM | `Mbes.reference_surface` |
| Report export fails | `Export.kmldir` |
| The GRASS toolbox is greyed out or every call fails | `Processing.grass_api_endpoint`, `Processing.grass_api_key` |
| GRASS calls return 401 / 403 | `Processing.grass_api_key` — a *wrong* key is not caught locally |
| The roughness panel says "roughness service not configured" | `Processing.grass_api_endpoint` + `Processing.grass_api_key`, or `Roughness.base_url` / `Roughness.direct_url` |
| Roughness computes but nothing is added to the map | `Roughness.georeference` (and the Georef tab, which overrides it) |
| Georeferenced rasters land in the wrong place | `Roughness.epsg` — must match your survey's UTM zone |
| The video plays but the map does not follow | `Video.videometadata` |
| UI state is not restored between sessions | `Session.groundtruther_project` |

## Values are read defensively

Beyond the startup check, every consumer coerces its value at the point of use:
a key that is absent, `null`, or holds junk yields the documented default instead
of raising. That is why a broken `Roughness.epsg` degrades to `32619` rather than
crashing the image loader that projects the USBL position with it.

The practical consequence: **a warning in the log is a real finding even when
nothing visibly broke.** Read the log after changing settings.
