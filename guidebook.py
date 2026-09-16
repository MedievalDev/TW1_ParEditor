"""Guide window: Help > Guide, F1 (PY_TOOL_DESIGN.md section 6.2).

Chapter tree on the left, text on the right, search field on top, German
and English. Every table that maps names to numbers is generated from the
same data the tool uses (categories.py, tw1_sdk_fields.json, TYPE_NAMES),
with a source line under it, so guide and tool never drift apart.

Imports of the main module happen inside the functions: tw1_par_editor
imports this module, so a top-level import would be circular.
"""

import re
import tkinter as tk
from tkinter import ttk

import theme
import categories as C


def _lang():
    import tw1_par_editor as M
    return M._LANG


def _l(de, en):
    return de if _lang() == 'de' else en


def _table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |',
           '|' + '---|' * len(head)]
    for r in rows:
        out.append('| ' + ' | '.join(str(c) for c in r) + ' |')
    return '\n'.join(out)


def _source(text):
    return _l('Quelle: ', 'Source: ') + text + '\n'


# ---------------------------------------------------------------------------
# chapters

def ch_start():
    keys = [('Strg+O', 'Ctrl+O', _l('PAR oeffnen', 'Open PAR')),
            ('Strg+S', 'Ctrl+S', _l('Speichern', 'Save')),
            ('Strg+Umschalt+S', 'Ctrl+Shift+S', _l('Speichern unter', 'Save as')),
            ('Strg+E', 'Ctrl+E', _l('JSON exportieren', 'Export JSON')),
            ('Strg+I', 'Ctrl+I', _l('JSON importieren', 'Import JSON')),
            ('Strg+F', 'Ctrl+F', _l('Filterfeld', 'Filter box')),
            ('Enter / F3', 'Enter / F3', _l('Naechster Treffer', 'Next match')),
            ('Esc', 'Esc', _l('Filter leeren', 'Clear filter')),
            ('Strg+Z / Strg+Y', 'Ctrl+Z / Ctrl+Y', _l('Rueckgaengig / Wiederholen', 'Undo / Redo')),
            ('F1', 'F1', _l('Dieser Guide', 'This guide'))]
    rows = [(k[0] if _lang() == 'de' else k[1], k[2]) for k in keys]
    return _l('''# Einstieg

Der PAR Editor oeffnet `TwoWorlds.par`, die Parameterdatenbank von Two
Worlds (2007). Darin steht jede Einheit, jede Waffe, jeder Zauber, Trank,
jede Tuer und jeder Klang: 609 Listen mit 5155 Eintraegen. Der Editor liest
die Datei, zeigt jedes Feld mit seinem SDK-Namen und schreibt sie Byte fuer
Byte zurueck.

## Das Fenster

- **Links der Baum:** Gruppen (Spieler, NPCs, Gegner ...) - darunter die
  SDK-Blaetter (Units, Weapon, Traps) - darunter die Eintraege.
- **Oben Gruppe und Filter:** das Dropdown zeigt eine Gruppe, das Filterfeld
  laesst nur passende Eintraege stehen.
- **Rechts die Felder** des gewaehlten Eintrags: Name, Typ, Wert. Ueber dem
  Namen schweben zeigt die Beschreibung.
- **Unten die Statusleiste:** was zuletzt passiert ist, rechts Hinweise.

## Tastenkuerzel

''', '''# Getting started

The PAR Editor opens `TwoWorlds.par`, the parameter database of Two Worlds
(2007). Every unit, weapon, spell, potion, door and sound lives in it: 609
lists with 5155 entries. The editor reads the file, shows every field with
its SDK name and writes it back byte for byte.

## The window

- **Tree on the left:** groups (Player, NPCs, Enemies ...) - below them the
  SDK sheets (Units, Weapon, Traps) - below those the entries.
- **Group and filter on top:** the dropdown shows one group, the filter box
  keeps only matching entries.
- **Fields on the right** of the selected entry: name, type, value. Hover a
  name for its description.
- **Status bar at the bottom:** what happened last, hints on the right.

## Keyboard shortcuts

''') + _table([_l('Taste', 'Key'), _l('Wirkung', 'Action')], rows) + '\n' + _source(
        'tw1_par_editor.py, _bind_keys')


def ch_first():
    return _l('''# Erstes Ergebnis in 10 Minuten

Ziel: der Wolf haelt doppelt so viel aus, und das Spiel zeigt es.

1. **Die richtige Par holen.** Das Spiel laedt `Parameters\\TwoWorlds.par`
   aus `WDFiles\\Update16.wd` - nicht aus `Parameters.wd`, die traegt das
   alte 1.0-Layout (der Editor warnt). Mit dem WD Repacker oder dem Entpacker
   des TW1 Minimap Tools entpacken.
2. **Oeffnen** (Strg+O). Die Statusleiste meldet "608 lists matched to SDK
   sheets".
3. **Filtern:** `units wolf` tippen. Es bleiben 9 Eintraege, die Gruppe
   Gegner ist offen.
4. `MO_WOLF_01` anklicken, rechts `maxHP` suchen (Feld 6) und `initParamHP`
   (Feld 34). Werte verdoppeln.
5. **Speichern** (Strg+S). Die alte Datei liegt jetzt in `_backup\\` daneben.
6. **Als Mod packen:** die Par als `Parameters\\TwoWorlds.par` in ein
   WD-Archiv, Verzeichnisflags 0x39, Datei nach `Mods\\`, in der Registry
   unter `HKCU\\SOFTWARE\\Reality Pump\\TwoWorlds\\Mods` auf 1 setzen.
7. Neues Spiel starten und einen Wolf suchen.

Was der Editor nicht macht: die Par direkt aus dem Spiel lesen oder als Mod
packen. Das kommt in einer spaeteren Version.
''', '''# First result in 10 minutes

Goal: the wolf takes twice the punishment, and the game shows it.

1. **Get the right par.** The game loads `Parameters\\TwoWorlds.par` from
   `WDFiles\\Update16.wd` - not from `Parameters.wd`, which carries the old
   1.0 layout (the editor warns). Unpack it with the WD Repacker or the
   unpacker of the TW1 Minimap Tool.
2. **Open** (Ctrl+O). The status bar says "608 lists matched to SDK sheets".
3. **Filter:** type `units wolf`. 9 entries remain, the Enemies group is
   open.
4. Click `MO_WOLF_01`, find `maxHP` on the right (field 6) and `initParamHP`
   (field 34). Double both.
5. **Save** (Ctrl+S). The old file now sits in `_backup\\` next to it.
6. **Pack it as a mod:** the par as `Parameters\\TwoWorlds.par` inside a WD
   archive, directory flags 0x39, the file into `Mods\\`, set to 1 under
   `HKCU\\SOFTWARE\\Reality Pump\\TwoWorlds\\Mods`.
7. Start a new game and find a wolf.

What the editor does not do: read the par straight from the game or pack it
as a mod. That is planned for a later version.
''')


def ch_groups():
    return _l('''# Gruppen und Filter

## Gruppen

Die Par besteht aus 609 Listen ohne Namen. Jede Liste ist genau ein Blatt
der SDK-Tabelle `TwoWorlds.xls` - Units, Weapon, Traps ... Der Editor
erkennt das Blatt an den Namen der Eintraege und sortiert die Blaetter in
Gruppen, in denen ein Modder denkt: Spieler, NPCs, Gegner, Waffen ...

Das Blatt Units enthaelt beides, Leute zum Reden und Leute zum Kaempfen.
Der Editor teilt es nach dem ersten Namen der Liste: CITIZEN, SOLDIER,
BARTENDER, KARGA, SKELDEN, NPC_ ... sind NPCs, alles andere ist Gegner.
Die Liste der Praefixe steht im Kapitel Referenz.

## Dropdown "Gruppe"

Zeigt nur eine Gruppe im Baum. "Alle" zeigt wieder alles.

## Filterfeld

Beim Tippen bleiben nur Eintraege stehen, die passen - im Namen, im
Blattnamen oder in einem Textfeld wie dem Mesh-Pfad. Mehrere Woerter muessen
alle passen:

- `wolf` - alle Woelfe: Einheiten, ihre Stimmen, ihre Modelle
- `units wolf` - nur die Einheiten
- `roadsign` - findet ueber den Mesh-Pfad alle Wegweiser
- `traps` - das ganze Blatt Fallen

Enter oder F3 springt zum naechsten Treffer, Esc leert das Feld, Strg+F
setzt den Cursor hinein.
''', '''# Groups and filter

## Groups

The par consists of 609 lists without names. Every list is exactly one
sheet of the SDK spreadsheet `TwoWorlds.xls` - Units, Weapon, Traps ... The
editor recognises the sheet by the entry names and sorts the sheets into
the groups a modder thinks in: Player, NPCs, Enemies, Weapons ...

The Units sheet holds both, people to talk to and people to fight. The
editor splits it by the first name of each list: CITIZEN, SOLDIER,
BARTENDER, KARGA, SKELDEN, NPC_ ... are NPCs, everything else is an enemy.
The prefix list is in the Reference chapter.

## The "Category" dropdown

Shows one group in the tree. "All" shows everything again.

## The filter box

While you type, only matching entries remain - by name, by sheet name or by
a text field such as the mesh path. Several words must all match:

- `wolf` - every wolf: units, their voices, their meshes
- `units wolf` - only the units
- `roadsign` - finds every road sign through its mesh path
- `traps` - the whole Traps sheet

Enter or F3 jumps to the next match, Esc clears the box, Ctrl+F puts the
cursor into it.
''')


def ch_fields():
    return _l('''# Felder bearbeiten

## Namen und Beschreibungen

Jedes Feld zeigt `[Index]`, den SDK-Namen, den Typ und den Wert. Die Namen
kommen aus dem Blatt der Liste; wer mit der Maus ueber dem Namen bleibt,
sieht die Beschreibung. Rechtsklick auf den Namen: eigenen Namen setzen
oder den SDK-Namen zurueckholen. Eigene Namen liegen pro Blatt in
`~\\tw1_par_labels_v2.json`.

## Werte

- Ganzzahlen (`int32`, `uint32`): auch `0x10` fuer 16.
- Fliesskomma (`float32`): Punkt oder Komma.
- Text (`string`): frei.
- Felder mit `[]` sind Listen; jede Zeile ein Wert.

**Roter Rand** heisst: der Text ist kein gueltiger Wert. Der alte Wert
bleibt, die Statusleiste nennt das Feld, und Speichern verweigert, bis es
stimmt.

## Rueckgaengig

Strg+Z nimmt die letzte Aenderung zurueck - eine Feldaenderung, ein
Duplizieren, Umbenennen, Loeschen oder Zusammenfuehren. Strg+Y wiederholt.

## Eintraege

Rechtsklick auf einen Eintrag im Baum: **Duplizieren** (schlaegt den
naechsten Namen vor und passt Mesh-Pfade an), **Umbenennen**, **Loeschen**.
Rechtsklick auf eine Liste: neuen leeren Eintrag anlegen.

## Speichern und Sicherung

Strg+S schreibt die Datei an Ort und Stelle. Vorher wandert die Fassung von
der Platte nach `_backup\\<Name>.<Zeit>.par` daneben - einmal pro Datei und
Sitzung. Datei > Sicherung wiederherstellen holt eine davon zurueck.
''', '''# Editing fields

## Names and descriptions

Every field shows `[index]`, the SDK name, the type and the value. Names
come from the sheet of the list; hover a name to read its description.
Right-click a name to set your own label or restore the SDK name. Your
labels live per sheet in `~\\tw1_par_labels_v2.json`.

## Values

- Integers (`int32`, `uint32`): `0x10` for 16 works too.
- Floating point (`float32`): dot or comma.
- Text (`string`): free.
- Fields ending in `[]` are lists; one value per line.

**A red border** means the text is not a valid value. The old value is kept,
the status bar names the field, and Save refuses until it is fixed.

## Undo

Ctrl+Z takes back the last change - a field edit, a duplicate, rename,
delete or merge. Ctrl+Y redoes it.

## Entries

Right-click an entry in the tree: **Duplicate** (suggests the next name and
adjusts mesh paths), **Rename**, **Delete**. Right-click a list: add a new
empty entry.

## Save and backup

Ctrl+S writes the file in place. Before that, the version on disk goes to
`_backup\\<name>.<time>.par` next to it - once per file and session. File >
Restore backup brings one of them back.
''')


def ch_compare():
    return _l('''# Vergleichen und Zusammenfuehren

Der zweite Reiter vergleicht zwei Par-Dateien Feld fuer Feld.

1. **Source** laden: deine Datei, in die etwas hinein soll.
2. **Input** laden: die Datei mit den Aenderungen, etwa die Par einer
   anderen Mod.
3. Optional **Original**: die unveraenderte Retail-Par als Bezug; der Pfad
   wird gemerkt.
4. **Compare** druecken. Jede Abweichung ist eine Zeile: Liste, Eintrag,
   Feld, die drei Werte.
5. Zeilen anhaken (Klick in die letzte Spalte), **Merge Selected into
   Source**, dann **Save Merged PAR**.

Die Filterknoepfe zeigen nur Geaendertes, nur Neues im Input oder nur, was
im Input fehlt. Merge ist rueckgaengig (Strg+Z im Editor-Reiter).
''', '''# Compare & Merge

The second tab compares two par files field by field.

1. Load **Source**: your file, the one that should receive changes.
2. Load **Input**: the file with the changes, for example another mod's par.
3. Optionally **Original**: the unmodified retail par as reference; the path
   is remembered.
4. Press **Compare**. Every difference is one row: list, entry, field, the
   three values.
5. Tick rows (click the last column), **Merge Selected into Source**, then
   **Save Merged PAR**.

The filter buttons show only changed rows, only rows new in Input, or only
rows missing from Input. Merge can be undone (Ctrl+Z in the Editor tab).
''')


def ch_mod():
    return _l('''# In eine Mod packen

Der Editor schreibt eine `.par`. Das Spiel liest sie erst, wenn sie in
einem WD-Archiv im Ordner `Mods\\` liegt und dort eingeschaltet ist.

1. Ordner anlegen: `MeineMod\\Parameters\\TwoWorlds.par`.
2. Mit dem WD Repacker packen. Der Verzeichniseintrag der Par braucht die
   Flags `0x39` wie im Retail-Archiv (gemessen an `Parameters.wd`); der
   Repacker setzt sie fuer eine zlib-gepackte Datei.
3. `MeineMod.wd` nach `<Spiel>\\Mods\\`.
4. Einschalten: Registry `HKCU\\SOFTWARE\\Reality Pump\\TwoWorlds\\Mods`,
   Wert `MeineMod.wd` = 1 (DWORD), oder im "TwoWorlds1 Mod Selector".
5. Das Spiel liest die Mod-Liste nur beim Start.

Spaeter geladene Archive gewinnen: liegt eine zweite Mod mit eigener Par
daneben, gilt die, die das Spiel zuletzt laedt.
''', '''# Packing into a mod

The editor writes a `.par`. The game reads it only once it sits inside a WD
archive in the `Mods\\` folder and is switched on there.

1. Make a folder: `MyMod\\Parameters\\TwoWorlds.par`.
2. Pack it with the WD Repacker. The directory entry of the par needs flags
   `0x39` like in the retail archive (measured on `Parameters.wd`); the
   repacker sets them for a zlib-packed file.
3. `MyMod.wd` into `<game>\\Mods\\`.
4. Switch it on: registry `HKCU\\SOFTWARE\\Reality Pump\\TwoWorlds\\Mods`,
   value `MyMod.wd` = 1 (DWORD), or use the "TwoWorlds1 Mod Selector".
5. The game reads the mod list only at startup.

Later archives win: with a second mod that carries its own par, the one the
game loads last applies.
''')


def ch_reference():
    import tw1_par_editor as M
    labels = M.FieldLabels()
    groups = [(c, ', '.join(C.sheets_of(c)) or '-') for c in C.CATEGORIES]
    sheets = [(s, len(cols), C.SHEET_CATEGORY.get(s, 'Units: NPCs / Enemies' if s == 'Units' else 'Other'))
              for s, cols in sorted(labels.sheets.items())]
    types = [(tid, name, {0: 'i32', 1: 'f32', 2: 'u32', 3: 'dstring', 4: 'u64 lead + u32 count + i32[]',
                          5: 'u64 lead + u32 count + f32[]', 6: 'u64 lead + u32 count + u32[]',
                          7: 'u64 lead + u32 count + dstring[]'}[tid])
             for tid, name in sorted(M.TYPE_NAMES.items())]
    out = _l('# Referenztabellen\n\n## Gruppen und ihre Blaetter\n\n',
             '# Reference tables\n\n## Groups and their sheets\n\n')
    out += _table([_l('Gruppe', 'Group'), _l('SDK-Blaetter', 'SDK sheets')], groups) + '\n'
    out += _source(C.SOURCE)
    out += _l('\n## NPC-Praefixe im Blatt Units\n\n', '\n## NPC prefixes in the Units sheet\n\n')
    out += _l('Eine Units-Liste, deren erster Eintrag so beginnt, zaehlt als NPC-Liste: ',
              'A Units list whose first entry starts like this counts as an NPC list: ')
    out += ', '.join(f'`{p}`' for p in C.NPC_PREFIXES) + '\n\n'
    out += _source('categories.py, NPC_PREFIXES; ' + _l('gemessen an den 95 Units-Listen der Update16-Par',
                                                        'measured on the 95 Units lists of the Update16 par'))
    out += _l('\n## Blaetter mit Feldanzahl\n\n', '\n## Sheets with field count\n\n')
    out += _table([_l('Blatt', 'Sheet'), _l('Felder', 'Fields'), _l('Gruppe', 'Group')], sheets) + '\n'
    out += _source('tw1_sdk_fields.json (TwoWorlds.xls, SDK); ' + _l(
        'Feldanzahl = Spalten des Blatts, passt bei 608 von 609 Listen der Update16-Par exakt',
        'field count = sheet columns, exact for 608 of 609 lists of the Update16 par'))
    out += _l('\n## Feldtypen\n\n', '\n## Field types\n\n')
    out += _table(['Id', 'Name', _l('Kodierung', 'Encoding')], types) + '\n'
    out += _source('tw1_par_editor.py TYPE_NAMES, PAR_FORMAT.md; ' + _l(
        'Array-Kopf gemessen an allen 5155 Eintraegen: u64 = 0 heisst leer, dann folgt keine Anzahl',
        'array lead measured on all 5155 entries: u64 = 0 means empty, and then no count follows'))
    return out


def ch_trouble():
    return _l('''# Fehlersuche

## "Keine Feldnamen, nur [0] [1] [2]"

`tw1_sdk_fields.json` fehlt neben dem Skript. Die Exe bringt sie mit; beim
Skript muss sie im selben Ordner liegen.

## "WARNING: old 1.0 layout"

Du hast die Par aus `Parameters.wd` geoeffnet. Sie hat 602 Listen und den
Helden mit 121 Feldern; die SDK-Namen passen bei 110 Listen nicht. Nimm die
Par aus `Update16.wd` (609 Listen, Held mit 130 Feldern, 608 von 609 exakt).

## "Gespeichert, im Spiel aendert sich nichts"

Die Par muss als Mod-Archiv in `Mods\\` liegen und in der Registry auf 1
stehen. Das Spiel liest die Liste nur beim Start. Liegt eine zweite Mod mit
eigener Par daneben, gewinnt die zuletzt geladene.

## "Wert wird nicht uebernommen"

Roter Rand: kein gueltiger Wert. Die Statusleiste nennt das Feld. Ganzzahlen
nehmen auch `0x10`, Fliesskomma auch Komma.

## "Speichern verweigert"

Ein Feld traegt ungueltigen Text. Zurueck zum Eintrag, roten Rand suchen,
Wert korrigieren oder Strg+Z.

## "Ich will die alte Fassung zurueck"

Datei > Sicherung wiederherstellen. Die Kopien liegen in `_backup\\` neben
der Datei, eine pro Datei und Sitzung.

## "Alle 77-Feld-Eintraege heissen wie Zauberstaebe"

Das war der Fehler bis Version 1.3: Namen nach Feldanzahl. Neun Blattpaare
teilen sich eine Anzahl. Seit 1.4 kommt der Name vom Blatt der Liste.
''', '''# Troubleshooting

## "No field names, only [0] [1] [2]"

`tw1_sdk_fields.json` is missing next to the script. The exe carries it;
with the script it must sit in the same folder.

## "WARNING: old 1.0 layout"

You opened the par from `Parameters.wd`. It has 602 lists and the hero with
121 fields; the SDK names do not fit 110 of its lists. Take the par from
`Update16.wd` (609 lists, hero with 130 fields, 608 of 609 exact).

## "Saved, but nothing changes in the game"

The par must sit inside a mod archive in `Mods\\` and be set to 1 in the
registry. The game reads the list only at startup. With a second mod that
carries its own par, the one loaded last wins.

## "The value is not taken over"

Red border: not a valid value. The status bar names the field. Integers
accept `0x10`, floats accept a comma.

## "Save refuses"

A field holds invalid text. Go back to the entry, find the red border,
correct the value or press Ctrl+Z.

## "I want the old version back"

File > Restore backup. The copies sit in `_backup\\` next to the file, one
per file and session.

## "Every 77-field entry is named like a magic staff"

That was the bug up to version 1.3: names by field count. Nine sheet pairs
share a count. Since 1.4 the name comes from the sheet of the list.
''')


CHAPTERS = (
    ('start', ('Einstieg', 'Getting started'), ch_start),
    ('first', ('Erstes Ergebnis in 10 Minuten', 'First result in 10 minutes'), ch_first),
    ('groups', ('Gruppen und Filter', 'Groups and filter'), ch_groups),
    ('fields', ('Felder bearbeiten', 'Editing fields'), ch_fields),
    ('compare', ('Vergleichen und Zusammenfuehren', 'Compare & Merge'), ch_compare),
    ('mod', ('In eine Mod packen', 'Packing into a mod'), ch_mod),
    ('reference', ('Referenztabellen', 'Reference tables'), ch_reference),
    ('trouble', ('Fehlersuche', 'Troubleshooting'), ch_trouble),
)

# "?" help keys -> chapter
HELP_CHAPTER = {
    'help.tree': 'groups', 'help.groups': 'groups', 'help.filter': 'groups',
    'help.fields': 'fields', 'help.compare': 'compare',
}


_SEPARATOR = re.compile(r'^\|[\s|:-]+\|?$')
_LIST_ITEM = re.compile(r'^(- |\d+\. )')


def _prepare(text):
    """Join wrapped prose lines into paragraphs and turn markdown tables into
    aligned columns, so the text widget shows them readably."""
    out, para, table, in_code = [], [], [], False

    def flush_para():
        if para:
            out.append(' '.join(x.strip() for x in para))
            para.clear()

    def flush_table():
        if not table:
            return
        rows = [[c.strip().replace('`', '')
                 for c in r.strip().strip('|').split('|')]
                for r in table if not _SEPARATOR.match(r.strip())]
        ncol = max(len(r) for r in rows)
        widths = [max(len(r[i]) if i < len(r) else 0 for r in rows)
                  for i in range(ncol)]
        out.append('```')
        for n, r in enumerate(rows):
            cells = [(r[i] if i < len(r) else '').ljust(widths[i])
                     for i in range(ncol)]
            out.append('  '.join(cells).rstrip())
            if n == 0:
                out.append('  '.join('-' * w for w in widths))
        out.append('```')
        table.clear()

    for ln in text.split('\n'):
        if ln.startswith('```'):
            flush_para()
            flush_table()
            in_code = not in_code
            out.append(ln)
            continue
        if in_code:
            out.append(ln)
            continue
        if ln.startswith('|'):
            flush_para()
            table.append(ln)
            continue
        flush_table()
        stripped = ln.strip()
        if not stripped or ln.startswith('#'):
            flush_para()
            out.append(ln)
        elif _LIST_ITEM.match(stripped):
            flush_para()
            para.append(ln)
        else:
            para.append(ln)
    flush_para()
    flush_table()
    return '\n'.join(out)


def render_markdown(txt, text):
    """Headings, bullets, code blocks, tables (monospace), inline code and
    bold - enough for the chapters."""
    in_code = False
    for line in text.split('\n'):
        if line.startswith('```'):
            in_code = not in_code
            continue
        if in_code or line.startswith('|'):
            txt.insert('end', line + '\n', 'code')
            continue
        m = re.match(r'(#{1,3}) (.*)', line)
        if m:
            txt.insert('end', m.group(2) + '\n', 'h%d' % len(m.group(1)))
            continue
        tag = None
        if re.match(r'\s*[-*] ', line):
            line = '• ' + re.sub(r'^\s*[-*] ', '', line)
            tag = 'li'
        elif re.match(r'\s*\d+\. ', line):
            tag = 'li'
        for part in re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', line):
            if part.startswith('`') and part.endswith('`') and len(part) > 1:
                txt.insert('end', part[1:-1], ('inline',) + ((tag,) if tag else ()))
            elif part.startswith('**') and part.endswith('**'):
                txt.insert('end', part[2:-2], ('bold',) + ((tag,) if tag else ()))
            else:
                part = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', part)
                txt.insert('end', part, tag)
        txt.insert('end', '\n', tag)


def chapter_text(cid):
    for key, _title, fn in CHAPTERS:
        if key == cid:
            return fn()
    return ''


def check_sources():
    """Every table in every chapter (both languages) carries a source line.
    Raises AssertionError otherwise - run by the translation test."""
    import tw1_par_editor as M
    saved = M._LANG
    try:
        for lang in ('de', 'en'):
            M._LANG = lang
            for cid, _t, fn in CHAPTERS:
                lines = fn().split('\n')
                for i, ln in enumerate(lines):
                    if ln.startswith('|---'):
                        j = i + 1
                        while j < len(lines) and lines[j].startswith('|'):
                            j += 1
                        tail = '\n'.join(lines[j:j + 3])
                        assert 'Quelle:' in tail or 'Source:' in tail, f'{cid}/{lang}: table without source'
    finally:
        M._LANG = saved


# ---------------------------------------------------------------------------
# window

class GuideWindow:
    _open = None

    @classmethod
    def show(cls, app, chapter='start'):
        win = cls._open
        if win is not None:
            try:
                win.win.lift()
                win.select(chapter)
                return win
            except tk.TclError:
                cls._open = None
        cls._open = cls(app, chapter)
        return cls._open

    def __init__(self, app, chapter='start'):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title(_l('PAR Editor Guide', 'PAR Editor Guide'))
        self.win.geometry('1120x760')
        self.win.minsize(820, 520)
        theme.dark_titlebar(self.win)
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.win.bind('<Escape>', lambda e: self.close())
        top = ttk.Frame(self.win, padding=(10, 8))
        top.pack(fill='x')
        ttk.Label(top, text=_l('Suche', 'Search')).pack(side='left')
        self.q = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.q, width=32)
        ent.pack(side='left', padx=6)
        ent.bind('<KeyRelease>', lambda e: self._search())
        self.hits = ttk.Label(top, style='Muted.TLabel')
        self.hits.pack(side='left', padx=8)
        body = ttk.PanedWindow(self.win, orient='horizontal')
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._show_selected())
        right = ttk.Frame(body)
        sb = ttk.Scrollbar(right, orient='vertical')
        self.txt = tk.Text(right, wrap='word', bd=0, padx=26, pady=20,
                           cursor='arrow', spacing1=2, spacing3=4,
                           yscrollcommand=sb.set, font=('Segoe UI', 10))
        sb.configure(command=self.txt.yview)
        sb.pack(side='right', fill='y')
        self.txt.pack(fill='both', expand=True)
        for tag, kw in (('h1', dict(font=theme.FONT_H1, foreground=theme.GOLD, spacing1=18)),
                        ('h2', dict(font=theme.FONT_H2, foreground=theme.GOLD_HI, spacing1=14)),
                        ('h3', dict(font=('Segoe UI Semibold', 10), foreground=theme.GOLD_HI, spacing1=8)),
                        ('li', dict(lmargin1=20, lmargin2=34)),
                        ('code', dict(font=theme.FONT_MONO, background=theme.FIELD, lmargin1=16, lmargin2=16)),
                        ('inline', dict(font=theme.FONT_MONO, foreground=theme.GOLD_HI)),
                        ('bold', dict(font=('Segoe UI Semibold', 10))),
                        ('hit', dict(background=theme.SEL, foreground=theme.GOLD_HI))):
            self.txt.tag_configure(tag, **kw)
        body.add(left, weight=0)
        body.add(right, weight=1)
        self.win.update_idletasks()
        try:
            body.sashpos(0, 270)
        except tk.TclError:
            pass
        self._fill_tree()
        self.select(chapter)

    def close(self):
        GuideWindow._open = None
        self.win.destroy()

    def _fill_tree(self, only=None):
        self.tree.delete(*self.tree.get_children())
        lang = 0 if _lang() == 'de' else 1
        for i, (cid, titles, _fn) in enumerate(CHAPTERS, start=1):
            if only is not None and cid not in only:
                continue
            self.tree.insert('', 'end', iid=cid, text=f'{i}. {titles[lang]}')

    def select(self, cid):
        if cid not in {c for c, _t, _f in CHAPTERS}:
            cid = 'start'
        if not self.tree.exists(cid):
            self._fill_tree()
        self.tree.selection_set(cid)
        self.tree.see(cid)
        self._show(cid)

    def _show_selected(self):
        sel = self.tree.selection()
        if sel:
            self._show(sel[0])

    def _show(self, cid):
        self.current = cid
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        render_markdown(self.txt, _prepare(chapter_text(cid)))
        self._mark_hits()
        self.txt.configure(state='disabled')

    def _search(self):
        needle = self.q.get().strip().lower()
        if not needle:
            self._fill_tree()
            self.hits.configure(text='')
            self.select(getattr(self, 'current', 'start'))
            return
        found = [cid for cid, _t, fn in CHAPTERS if needle in fn().lower()]
        self._fill_tree(set(found))
        self.hits.configure(text=_l('{n} Kapitel', '{n} chapters').format(n=len(found)))
        if found:
            self.select(found[0])

    def _mark_hits(self):
        needle = self.q.get().strip() if hasattr(self, 'q') else ''
        self.txt.tag_remove('hit', '1.0', 'end')
        if not needle:
            return
        first = None
        pos = '1.0'
        while True:
            pos = self.txt.search(needle, pos, nocase=True, stopindex='end')
            if not pos:
                break
            end = f'{pos}+{len(needle)}c'
            self.txt.tag_add('hit', pos, end)
            first = first or pos
            pos = end
        if first:
            self.txt.see(first)
