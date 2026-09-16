# TW1 PAR Editor

A GUI editor for Two Worlds 1 `.par` parameter files — the core data format that defines every NPC, weapon, spell, potion, and object in the game.

![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue) ![License: CC0](https://img.shields.io/badge/license-CC0-green) ![Platform: Windows/Linux/Mac](https://img.shields.io/badge/platform-Win%20%7C%20Linux%20%7C%20Mac-lightgrey)

## Features

- **Full PAR parsing** — reads and writes the binary PAR format byte-perfectly (zlib-compressed dual-stream wrapper included)
- **2055 SDK field names** — from the official `TwoWorlds.xls` SDK spreadsheet (39 sheets), resolved per list by the entry names, so every field carries the right name (v1.4)
- **1178 tooltip descriptions** — hover over any field name to see what it does
- **Groups and live filter** — Player, NPCs, Enemies, Weapons, Game Parameters ... as a dropdown and as the tree; type to filter by name, sheet or text field (v1.4)
- **Dark theme, DE/EN, guide on first start** — same look as the other TW1 tools (v1.4)
- **Editable fields** — change int32, uint32, float32, and string values directly in the GUI
- **Duplicate / Rename / Delete entries** — right-click any entry in the tree to clone, rename, or remove it. Duplicating auto-increments names and updates mesh paths (v1.2)
- **Add new entries** — right-click a list node to add a blank entry with matching field structure (v1.2)
- **Compare & Merge** — compare two PAR files field-by-field, see differences color-coded, and selectively merge changes from one into the other. Supports an optional unmodified PAR as baseline reference (v1.3)
- **JSON export/import** — convert PAR to human-readable JSON (with labels) and back
- **Label system** — right-click to rename/add labels, persisted to `~/tw1_par_labels.json`
- **Validation** — roundtrip-tested on the original `TwoWorlds.par` (602 lists, 5087 entries, byte-identical)

## Quick Start

```
python tw1_par_editor.py
```

Or double-click `START_PAR_EDITOR.bat` on Windows.

**Requirements:** Python 3.6+ with tkinter (included in standard Python on Windows).

## Files

| File | Description |
|------|-------------|
| `tw1_par_editor.py` | Main editor script (GUI + parser + writer) |
| `theme.py` | Dark theme shared by the TW1 tools |
| `guidebook.py` | Guide window (F1): chapters, search, reference tables generated from the code |
| `categories.py` | The groups (Player, NPCs, Enemies ...) and which SDK sheet belongs where |
| `updater.py` + `version.py` | Update check on start and self-update from GitHub Releases |
| `tw1_sdk_fields.json` | 39 SDK sheets with their field names, entry-to-sheet map |
| `tw1_sdk_labels.json` + `tw1_sdk_descriptions.json` | Tooltip descriptions (joined by field name) |
| `START_PAR_EDITOR.bat` | Windows launcher for the script version |
| `build_par_editor_exe.bat` | PyInstaller one-file build (`dist\TW1_PAR_Editor.exe`) |
| `selftest_exe.bat` | Starts the built exe in selftest mode and prints its line |
| `par_editor_settings.json` | Language, guide, original PAR path (auto-created) |

Or take the exe from the Releases page — no Python needed. The script version wants all files in one folder.

## Usage

See [GUIDE.md](GUIDE.md) for a detailed usage guide.

**Open:** File → Open PAR (or Ctrl+O) — supports both raw and zlib-compressed `.par` files

**Navigate:** Tree on the left shows Groups → SDK sheets → Entries. Pick a group in the Category dropdown or type in the filter box. Click an entry to see its fields on the right.

**Edit:** Change values in the input fields, then File → Save (Ctrl+S).

**Manage entries:** Right-click an entry → Duplicate / Rename / Delete. Right-click a list node → Add New Entry. Duplicating auto-suggests the next name and updates string fields referencing the old name.

**Labels:** SDK labels appear in cyan. Hover for German tooltip. Right-click to rename. Click `···` on unlabeled fields to add a name.

**Compare & Merge:** Switch to the "Compare & Merge" tab to compare two PAR files. Load a Source PAR (your working file), an Input PAR (the file with changes to merge), and optionally an unmodified Original PAR as baseline. Click Compare to see all differences, select the changes you want, and click Merge.

**Export:** File → Export JSON — creates a labeled, human-readable JSON version.

## PAR Format

See [PAR_FORMAT.md](PAR_FORMAT.md) for the complete reverse-engineered binary specification.

## Entry Categories

The PAR format groups entries by field count. Each category maps to an SDK sheet:

| Fields | SDK Sheet | Examples |
|--------|-----------|----------|
| 6 | SoundPack | SND_MENU_GO, SND_SWORD_01 |
| 16 | SimplePassives | HUGEGATE, QUD_FIREPLACE |
| 26 | BasicUnits | MO_RABBIT_01, MO_BIRD_01 |
| 53 | MagicCard | MAGIC_LIGHTING, MAGIC_HEAL |
| 65 | Units / ShopUnits | MO_WOLF_01, NPC_Q_005 |
| 67 | Weapon | WP_SWORD_01, WP_BOW_01 |
| 77 | Traps | TRAP_HOLD_01, TRAP_FIRE_01 |
| 101 | PotionArtefacts | POTION_HEALING_01 |
| 121 | Heroes | HEROSINGLE, HERO1 |

See `classmask.h` for the class type hierarchy used in the `classID` field.

## Mesh Field Syntax

The `mesh` field (field index 1) in SimplePassives, Passives, and other object entries supports a powerful extended syntax that goes beyond simple file paths. The engine uses this syntax to define mesh variants, texture overrides, and LOD ranges — all within a single string field.

### Basic Format

```
<path>.vdf
```

Example: `Houses\VILLAGE 02\STABLE_02_04.vdf`

### Mesh Variants with Range Notation

```
<path>_0[1-4].vdf
```

This defines multiple mesh variants in a single entry. `STAIRS_02_0[1-4].vdf` expands to four meshes: `STAIRS_02_01.vdf`, `STAIRS_02_02.vdf`, `STAIRS_02_03.vdf`, `STAIRS_02_04.vdf`. In the Two Worlds Editor, these variants can be cycled through via right-click on the placed object. This is useful for objects that share the same parameters but have different visual appearances (e.g. different house styles, fence sections, stair variants).

### Texture Overrides

```
<path>.vdf:<texture1>.dds
```

Appending `:texture.dds` after the VDF path overrides the default texture embedded in the VDF file. This allows reusing the same 3D model with different textures without duplicating the mesh file.

### Multiple Texture Variants

```
<path>.vdf:<texture1>.dds|<texture2>.dds
```

The `|` separator defines additional texture variants. These correspond to the `#mesh2`, `#mesh3` columns visible in the SDK spreadsheet (`TwoWorlds.xls`). In the SDK spreadsheet, these appear as separate columns for readability, but in the PAR binary they are stored as a single concatenated string.

### Combined Example

```
Houses\TOWN 02\STAIRS_02_0[1-4].vdf:STAIRS_02.dds|STAIRS_04.dds
```

This single string defines:
- **4 mesh variants** (STAIRS_02_01 through STAIRS_02_04) — right-click to cycle
- **2 texture sets** (STAIRS_02.dds and STAIRS_04.dds) — alternative skins

### SDK Spreadsheet Mapping

The SDK spreadsheet (`TwoWorlds.xls`) splits this compound string across multiple columns for readability:

| PAR Field | Spreadsheet Column | Content |
|-----------|-------------------|---------|
| field[1] (before `:`) | `mesh` | VDF file path (with optional `[n-m]` range) |
| field[1] (after `:`, before `|`) | `#mesh2` | First texture override |
| field[1] (after `|`) | `#mesh3` | Second texture override |

These are **not separate PAR fields** — they are all part of the single `mesh` string in field index 1.

## Building Mods

1. Extract `TwoWorlds.par` from the game's WD archives
2. Open in the editor, modify values or duplicate existing entries to create new objects
3. Save and repack into a `.wd` file for the `WDFiles` folder

**Adding new objects (e.g. a new road sign):**
1. Find a similar entry (e.g. `ROADSIGN_L_13`)
2. Right-click → Duplicate → name it `ROADSIGN_L_14`
3. Adjust mesh path and parameters
4. Save, add matching VDF/MTR to the WD archive, update `EditorDef.txt`

## Credits

- **Reality Pump Studios** — Two Worlds game engine and SDK
- PAR format reverse-engineered from binary analysis and SDK correlation
- Field labels extracted from `TwoWorlds.xls` (SDK)
- Class hierarchy from `classmask.h` (SDK)

## License

MIT

## Changelog

### v1.5.0 (16.09.2026)

- **Guide window** (Help > Guide, F1): eight chapters in English and German,
  search, reference tables generated from the code (groups, sheets with
  field counts, field types) with a source line under each. Gold `?` marks
  next to the tree, the filter, the fields and the compare tab open the
  matching chapter.
- **Updates from GitHub:** the tool checks for a newer release on start
  (switchable in Help) and updates itself: download, SHA-256 check against
  the release digest, swap after the tool has closed, old exe kept as
  `.old`. The exe is now called `TW1_PAR_Editor.exe` so the updater finds
  it in every release.
- **Undo / Redo** (Ctrl+Z / Ctrl+Y) for field edits, duplicate, rename,
  delete and add. Global shortcuts let the keys through while you type.
- **File > Restore backup** brings a copy from `_backup\` back.
- Status bar always visible (also at small window sizes), "unsaved changes"
  marker, one line under the header that says why a value is red, grey
  example in the empty filter box, empty state with an Open button, the
  language switch keeps file, selection and tab.
- Selftest mode: `PAR_EDITOR_SELFTEST=<file>` writes one line and quits
  (`selftest_exe.bat`).


### v1.4 (16.09.2026)

- **Field names are right now.** Labels come from the SDK sheet of each list
  (`tw1_sdk_fields.json`, 39 sheets, 2055 names), resolved by the entry names
  of the list. The old count-based lookup mislabelled 414 of 609 lists — nine
  sheet pairs share a field count (Traps/MagicClub 77, Units/ShopUnits 65,
  BasicUnits/BasicUnitsAnimations 26 ...). Measured against the par the game
  actually runs (`Update16.wd`): 608 of 609 lists resolve with the exact
  column count. The old 1.0 layout in `Parameters.wd` gets a warning.
- **Live filter** instead of a jump-only search: the tree shows only matching
  entries while you type — by entry name, sheet name (`traps`, `units`) or any
  text field such as the mesh path. Several words must all match
  (`units wolf`). Enter/F3 jumps through the matches, Esc clears, Ctrl+F focuses.
- **Sheet names in the tree** (`Units (MO_WOLF_01...) [7]`) instead of `List 453`.
- **Invalid input is no longer dropped silently**: red border while the text
  is not a valid value, status line says which field kept its old value, and
  Save refuses until it is fixed. Integers accept `0x` hex, floats a comma.
- **Backup on save**: the file on disk goes to `_backup\<name>.<timestamp>.par`
  before it is overwritten (once per file and session).
- `START_PAR_EDITOR.bat` starts the right file again (it pointed at a name that
  did not exist in the DE folder), Ctrl+E / Ctrl+I are bound as documented.

### v1.4 — look and groups (16.09.2026, same day)

- **Same design as the other TW1 tools** (PY_TOOL_DESIGN.md): dark warm
  theme from `theme.py`, dark title bar, dark menu bar with popup menus,
  `DE · EN` switch top right (takes effect immediately), guide on first
  start (Help > Start guide), links in the Help menu and About dialog.
  Config in `par_editor_settings.json` next to the script (as exe under
  `%LOCALAPPDATA%\TW1ParEditor`).
- **Groups instead of one long list.** The tree is grouped into Player,
  NPCs, Enemies, Animals & Mounts, Weapons & Missiles, Armour & Equipment,
  Magic & Effects, Potions & Items, Objects & Buildings, Traps, Sounds &
  Voices, Meshes & Animations, Game Parameters. Below a group sit the SDK
  sheets with their entries. The **Category** dropdown shows one group only;
  the text filter works inside it. Units are split by the first entry name:
  CITIZEN, SOLDIER, BARTENDER, NPC_ ... are NPCs, the rest enemies.
