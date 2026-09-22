# TW1 PAR Editor

A GUI editor for Two Worlds 1 `.par` parameter files — the core data format that defines every NPC, weapon, spell, potion, and object in the game.

![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue) ![License: CC0](https://img.shields.io/badge/license-CC0-green) ![Platform: Windows/Linux/Mac](https://img.shields.io/badge/platform-Win%20%7C%20Linux%20%7C%20Mac-lightgrey)

## Features

- **Opens the game archives** - pick `WDFiles\Update16.wd`, the editor finds the par inside; saving writes a mod `.wd` into `Mods\`, the game archive is never touched (v1.6)
- **See what changed** - blue dot on changed entries, blue number and "was 80" on changed fields, a "Changed only" filter (v1.8)
- **The game's values** - with a mod open, the value from `Update16.wd` next to every field that differs; reset one field or a whole entry (v1.8)
- **Favourites, templates, jump box** - pin entries at the top of the tree; keep an entry as template for new ones with the next free name; Ctrl+P jumps to any entry by name (v1.8)
- **CSV tables** - a list, a category or a selection as table for Excel or LibreOffice, and back with a review of every change (v1.8)
- **Quick switching** - entries of the same sheet reuse the rows: a click takes 0.03 s instead of 0.8 s (v1.8)
- **Bulk edit and presets** - change one field in many entries at once (selection, list, category or search results): set, add, change by %, replace text; the field is picked by its SDK name, so field 34 is `initParamHP` for units and `wpDamColdMax` for weapons - the name decides; save the operation as a preset (v1.7)
- **Review before saving** - every change since opening with old and new value; untick a row and that field keeps its old value (v1.7)
- **Find references** - every entry that names this one in a text field, and one field across all entries (v1.7)
- **Drag and drop** - drop a `.par`, `.wd` or JSON export from Explorer onto the window (v1.7)
- **Error messages that help** - each error says what to try, links to the guide chapter and has a Report a bug button (v1.7)
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

1. Open `WDFiles\Update16.wd` of the game directly - the editor finds
   `Parameters\TwoWorlds.par` inside, no unpacking tool needed
2. Modify values or duplicate existing entries to create new objects
3. Save: the editor never writes into `WDFiles`. It asks for a new mod archive
   in `Mods\` (for example `MyParameters.wd`) that carries only the par, with
   the directory metadata of the original (flags `0x39`, resource
   `translateGameParams`, id 1536, same GUID - like the Kira mod ships it).
   Opening a mod `.wd` and saving swaps the par inside it and keeps every
   other file; the old archive goes to the tool's backup folder
   (`%LOCALAPPDATA%\TW1ParEditor\backup`), not into `Mods\`.
4. Start the game. The Mod Manager shows and toggles the mod.

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

### v1.8.0 (22.09.2026)

- **Change marks.** Entries that differ from the file as opened carry a blue
  dot in the tree (their list too); changed fields get a blue number and a
  small "was 80". **Changed only** in the toolbar hides the rest. Saving
  starts the marks again.
- **The game's values.** With a mod par open, the editor reads the game's
  `WDFiles\Update16.wd` in the background (found above the opened folder or
  in the usual Steam folders, or set under View) and shows "game 100" where
  a field differs. Right-click a field name > Reset to the game's value,
  right-click an entry > Reset to the game's values.
- **Favourites.** Right-click an entry > Add to favourites; the group sits at
  the top of the tree and is kept between sessions.
- **Entry templates.** Save an entry as template, then right-click a list of
  the same sheet > New entry from template. The name is the next free one,
  text fields with the old name get the new one. Duplicate suggests the next
  free name as well.
- **CSV export and import.** A list, a category or a selection as table
  (semicolon, one column per field name, array items split by ` | `).
  Importing shows every change in the review window first; empty cells are
  skipped, point and comma both work as decimal sign. One Ctrl+Z undoes it.
- **Jump box** (Ctrl+P): type part of a name, Enter jumps there.
- **Faster selection.** Entries with the same layout reuse the rows of the
  one before and keep the scroll position: 0.03 s per click instead of 0.8 s.
- Guide: new chapter Working faster.

### v1.7.1 (22.09.2026)

- Guide and examples use `initParamHP` for unit hit points: `maxHP` is 10
  in every unit, the value the game scales is `initParamHP` (wolf 80,
  skeleton 100). The bulk-edit chapter no longer claims a field sits at
  different numbers in different sheets - it is the other way round, one
  number means different fields.

### v1.7.0 (22.09.2026)

- **Bulk edit.** Ctrl+B, or right-click a list, a category or several
  selected entries (ctrl/shift-click). Pick a field by its SDK name - it is
  field 6 in one sheet and field 9 in another, the editor finds the right
  one per entry - then Set to / Add / Change by % / Replace text
  (`old=>new`). The preview lists every change with old and new value;
  ints are rounded, uint never goes below 0, arrays change item by item.
  One Ctrl+Z undoes the whole edit.
- **Bulk presets.** Save scope, field, operation and value under a name;
  Edit > Bulk presets calls it up with the preview ready. Lists and
  categories are stored by name, so a preset fits again next time.
- **Review changes before saving.** Saving shows every changed field since
  the file was opened; click a row or press Space to drop it, the field
  gets its old value back and the rest is saved. Edit > Review changes...
  shows the list any time; a checkbox in the Edit menu switches the
  question off.
- **Find references** (Ctrl+R): every entry that carries this entry's name
  in a text field. Right-click a field name > **Show in all entries**:
  that field with its value in every entry that has it. Double click jumps.
- **Drag and drop** of `.par`, `.wd` and JSON files from Explorer.
- **Error messages with tips.** Every error names what helps, has a
  **Read in the guide** button for the matching chapter and a
  **Report a bug...** button (preview first, nothing is sent without it).
- Help > test window: open test cases for this version, with the progress
  bar the other tools have.
- Guide: two new chapters, Bulk edit and presets / Review and references.

### v1.6.0 (18.09.2026)

- **Opens `.wd` archives.** Open `WDFiles\Update16.wd` (or any mod `.wd`)
  and the editor finds the `TwoWorlds.par` inside. The WDPackager, which
  crashes on 64-bit Windows, is no longer needed to edit parameters.
- **Saves as a mod.** A par from a game archive is saved as a new one-file
  `.wd` in `Mods\`; the game archive is never written. A par from a mod
  `.wd` is swapped in place, every other file of the archive is copied
  unchanged, the old archive lands in the tool's backup folder, outside
  `Mods\`.
- Works with buglord's
  [WD Repacker (Python)](https://github.com/buglord/Two-Worlds-1-Misc-Projects/tree/main/WD%20Repacker%20(Python)):
  a par saved loose keeps the two-stream layout whose first stream is the
  directory metadata (flags, resource, id, GUID), so `wdio.py pack -v 1`
  packs it with the right entry, and `wdio.py unpack -p` output opens here.
- Save As onto an existing `.wd` asks: swap only the par, or replace the
  whole archive.
- Fixes from a code review and a functional test run: no more data loss on
  Open / Close / DE-EN switch with a value still being typed; just viewing
  an entry no longer changes floats or empty string arrays; empty arrays
  get an input box; array items are range-checked; renaming to an existing
  name warns; a JSON import saves through Save As; the detail panel no
  longer leaks Tcl commands (about 60 per selected entry); nothing is ever
  written below a game's `WDFiles` folder, loose `.par` included.
- Compare & Merge reads `.wd` too and can save the merged par as a `.wd`.
- `--info` and `--export` accept a `.wd`.

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
