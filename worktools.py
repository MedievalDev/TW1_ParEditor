"""Working aids of the PAR Editor (1.8.0), without Tk so they can be tested
on a real par:

- ``changed_map`` - which entries and fields differ from the par as opened
  (the marks in the tree and the "changed only" filter).
- ``find_game_par`` / ``RefIndex`` - the par the game runs (Update16.wd) as
  reference: its value next to each field, "reset to game value".
- ``export_csv`` / ``import_csv`` - a list, a category or a selection as a
  table for Excel or LibreOffice, and back.
- entry templates - an entry kept across files, used for new entries.
- ``free_name`` - the next name that is not taken yet.
- ``quick_matches`` - the jump box (Ctrl+P).
"""

import copy
import csv
import io
import json
import os
import re
import struct

TYPE_INT32, TYPE_FLOAT32, TYPE_UINT32, TYPE_STRING = 0, 1, 2, 3
TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT, TYPE_ARRAY_UINT32, TYPE_ARRAY_STR = 4, 5, 6, 7
FLOATS = (TYPE_FLOAT32, TYPE_ARRAY_FLOAT)
INTS = (TYPE_INT32, TYPE_UINT32, TYPE_ARRAY_INT32, TYPE_ARRAY_UINT32)
ARRAYS = (TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT, TYPE_ARRAY_UINT32, TYPE_ARRAY_STR)
ARRAY_SEP = ' | '
FIXED_COLUMNS = ('list', 'sheet', 'entry')


def _sheet(par, li):
    sheets = getattr(par, 'sheets', None) or []
    return sheets[li] if li < len(sheets) else None


def _label(labels, par, li, fi):
    name = labels.get(_sheet(par, li), fi) if labels else None
    return name or f'field {fi}'


def _f32(v):
    try:
        return struct.unpack('<f', struct.pack('<f', float(v)))[0]
    except (OverflowError, struct.error, TypeError, ValueError):
        return v


def same_value(a, b, dtype):
    """Equal as the game sees it: floats compared as float32."""
    if dtype in FLOATS:
        if isinstance(a, list) or isinstance(b, list):
            return (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)
                    and all(_f32(x) == _f32(y) for x, y in zip(a, b)))
        return _f32(a) == _f32(b)
    return a == b


# ---------------------------------------------------------------- changes -----

def orig_index(orig, li):
    """{name: entry} of one list of the par as opened (first one wins)."""
    out = {}
    if orig is not None and li < len(orig.lists):
        for e in orig.lists[li].entries:
            out.setdefault(e.name, e)
    return out


def changed_fields(entry, before):
    """Set of field numbers that differ from ``before``; None for a new entry."""
    if before is None:
        return None
    out = set()
    for fi, f in enumerate(entry.fields):
        ov = before.fields[fi].value if fi < len(before.fields) else None
        if not same_value(f.value, ov, f.dtype):
            out.add(fi)
    if len(before.fields) != len(entry.fields):
        out.add(-1)
    return out


def changed_map(orig, cur):
    """{(li, ei): set of field numbers, or None for an entry that is new} for
    every entry that differs from the par as opened (matched per list by name)."""
    out = {}
    if orig is None or cur is None:
        return out
    for li, pl in enumerate(cur.lists):
        idx = orig_index(orig, li)
        for ei, e in enumerate(pl.entries):
            ch = changed_fields(e, idx.get(e.name))
            if ch is None or ch:
                out[(li, ei)] = ch
    return out


# ---------------------------------------------------------------- game par ----

GAME_FOLDERS = ('Two Worlds - Epic Edition', 'Two Worlds', 'Two Worlds Epic Edition')


def find_game_par(filepath=None, configured=None, drives='CDEFGH'):
    """Path of the game's WDFiles\\Update16.wd: the one set by hand, the game
    folder above the open file, then the usual Steam folders."""
    if configured and os.path.isfile(configured):
        return configured
    if filepath:
        d = os.path.dirname(os.path.abspath(filepath))
        for _ in range(6):
            p = os.path.join(d, 'WDFiles', 'Update16.wd')
            if os.path.isfile(p):
                return p
            up = os.path.dirname(d)
            if up == d:
                break
            d = up
    for drv in drives:
        for base in (r'SteamLibrary\steamapps\common', r'Program Files (x86)\Steam\steamapps\common',
                     r'Program Files\Steam\steamapps\common', r'Steam\steamapps\common', r'GOG Games'):
            for game in GAME_FOLDERS:
                p = os.path.join(f'{drv}:\\', base, game, 'WDFiles', 'Update16.wd')
                if os.path.isfile(p):
                    return p
    return None


class RefIndex:
    """The reference par by entry name: ``value(entry, fi)`` is the game's
    value of that field, or a marker when the game has no such entry/field."""
    MISSING = object()

    def __init__(self, par, path=''):
        self.par, self.path = par, path
        self.by_name = {}
        for pl in par.lists:
            for e in pl.entries:
                self.by_name.setdefault(e.name, e)

    def entry(self, name):
        return self.by_name.get(name)

    def value(self, entry, fi):
        ref = self.by_name.get(entry.name)
        if ref is None or len(ref.fields) != len(entry.fields) or ref.fields[fi].dtype != entry.fields[fi].dtype:
            return self.MISSING
        return ref.fields[fi].value

    def differs(self, entry, fi):
        v = self.value(entry, fi)
        return v is not self.MISSING and not same_value(entry.fields[fi].value, v, entry.fields[fi].dtype)


# ---------------------------------------------------------------- csv ---------

def cell_text(value, dtype):
    """A value as table cell: floats as short as float32 allows, arrays joined."""
    if isinstance(value, list):
        return ARRAY_SEP.join(cell_text(v, dtype) for v in value)
    if dtype in FLOATS:
        for p in range(6, 10):
            s = f'{value:.{p}g}'
            if _f32(float(s)) == _f32(value):
                return s
        return repr(value)
    return str(value)


def parse_cell(text, dtype):
    """Cell text -> value of the field type; ValueError if it does not fit."""
    if dtype in ARRAYS:
        text = text.strip()
        if not text:
            return []
        items = [t.strip() for t in text.split('|')]
        base = {TYPE_ARRAY_INT32: TYPE_INT32, TYPE_ARRAY_FLOAT: TYPE_FLOAT32,
                TYPE_ARRAY_UINT32: TYPE_UINT32, TYPE_ARRAY_STR: TYPE_STRING}[dtype]
        return [parse_cell(t, base) for t in items]
    if dtype == TYPE_STRING:
        return text
    t = text.strip().replace(',', '.') if dtype == TYPE_FLOAT32 else text.strip()
    if dtype == TYPE_FLOAT32:
        v = float(t)
        struct.pack('<f', v)
        return v
    if re.fullmatch(r'[+-]?\d+\.0*', t):          # 250.0 from a spreadsheet
        t = t.split('.')[0]
    v = int(t, 0)
    lo, hi = (-2**31, 2**31 - 1) if dtype == TYPE_INT32 else (0, 2**32 - 1)
    if not lo <= v <= hi:
        raise ValueError(f'{v} is out of range')
    return v


def export_csv(par, tgts, labels, path, delimiter=';'):
    """One row per entry: list, sheet, entry, then every field by its SDK
    name (union over the sheets, first seen first). Returns the row count."""
    cols, seen = [], set()
    for li, ei in tgts:
        for fi in range(len(par.lists[li].entries[ei].fields)):
            lab = _label(labels, par, li, fi)
            if lab not in seen:
                seen.add(lab)
                cols.append(lab)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(list(FIXED_COLUMNS) + cols)
        for li, ei in tgts:
            e = par.lists[li].entries[ei]
            row = {_label(labels, par, li, fi): cell_text(fl.value, fl.dtype) for fi, fl in enumerate(e.fields)}
            w.writerow([li, _sheet(par, li) or '', e.name] + [row.get(c, '') for c in cols])
    return len(tgts)


def _sniff(first_line):
    counts = {d: first_line.count(d) for d in (';', ',', '\t')}
    return max(counts, key=counts.get)


def import_csv(par, path, labels, change_cls):
    """(changes, problems): what the table would change. An empty cell leaves
    the field alone; an entry is found by list number and name, else by name
    anywhere. ``change_cls`` is bulktools.Change."""
    with open(path, encoding='utf-8-sig', newline='') as f:
        text = f.read()
    lines = text.splitlines()
    if not lines:
        return [], ['the file is empty']
    if lines[0].lower().startswith('sep='):
        text = '\n'.join(lines[1:])
        lines = lines[1:]
    rows = list(csv.reader(io.StringIO(text), delimiter=_sniff(lines[0])))
    head = [h.strip() for h in rows[0]]
    low = [h.lower() for h in head]
    if 'entry' not in low:
        return [], ['no column "entry" - export a table first and keep its first row']
    c_entry = low.index('entry')
    c_list = low.index('list') if 'list' in low else None
    fixed = {i for i, h in enumerate(low) if h in FIXED_COLUMNS}
    by_name = {}
    for li, pl in enumerate(par.lists):
        for ei, e in enumerate(pl.entries):
            by_name.setdefault(e.name, (li, ei))
    changes, problems = [], []
    for rn, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        name = row[c_entry].strip() if c_entry < len(row) else ''
        hit = None
        if c_list is not None and c_list < len(row) and row[c_list].strip().isdigit():
            li = int(row[c_list])
            if li < len(par.lists):
                hit = next(((li, ei) for ei, e in enumerate(par.lists[li].entries) if e.name == name), None)
        hit = hit or by_name.get(name)
        if not hit:
            problems.append(f'row {rn}: no entry "{name}"')
            continue
        li, ei = hit
        e = par.lists[li].entries[ei]
        where = {_label(labels, par, li, fi): fi for fi in range(len(e.fields))}
        for ci, col in enumerate(head):
            if ci in fixed or ci >= len(row) or row[ci] == '' or col not in where:
                continue
            fi = where[col]
            fl = e.fields[fi]
            try:
                new = parse_cell(row[ci], fl.dtype)
            except (ValueError, OverflowError, struct.error) as ex:
                problems.append(f'row {rn} {name}.{col}: "{row[ci]}" ({ex})')
                continue
            if not same_value(new, fl.value, fl.dtype):
                changes.append(change_cls(li, ei, fi, e.name, col, copy.deepcopy(fl.value), new))
    return changes, problems


# ---------------------------------------------------------------- templates ---

def make_template(entry, sheet):
    return {'sheet': sheet or '', 'count': len(entry.fields), 'entry': entry.name,
            'extra': [entry.unknown_byte, entry.unknown_u16a, entry.unknown_u16b],
            'fields': [[f.dtype, copy.deepcopy(f.value)] for f in entry.fields]}


def check_template(t):
    return (isinstance(t, dict) and isinstance(t.get('fields'), list) and isinstance(t.get('entry'), str)
            and all(isinstance(x, list) and len(x) == 2 and isinstance(x[0], int) for x in t['fields']))


def template_fits(t, sheet, count):
    return t.get('count') == count and (t.get('sheet') or '') == (sheet or '')


def _swap_name(text, old, new):
    i = text.lower().find(old.lower())
    return text if i < 0 or not old else text[:i] + new + text[i + len(old):]


def entry_from_template(t, new_name, entry_cls, field_cls):
    """A new entry from a template; text fields that carried the template's
    name get the new one (mesh paths, like Duplicate does)."""
    e = entry_cls()
    e.name = new_name
    e.unknown_byte, e.unknown_u16a, e.unknown_u16b = (list(t.get('extra') or [0, 0, 0]) + [0, 0, 0])[:3]
    for dtype, value in t['fields']:
        f = field_cls(dtype)
        v = copy.deepcopy(value)
        if dtype == TYPE_STRING and isinstance(v, str):
            v = _swap_name(v, t['entry'], new_name)
        elif dtype == TYPE_ARRAY_STR and isinstance(v, list):
            v = [_swap_name(s, t['entry'], new_name) if isinstance(s, str) else s for s in v]
        f.value = v
        e.fields.append(f)
    return e


def load_templates(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if check_template(v)} if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_templates(path, templates):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------- names -------

def free_name(par, name):
    """The next name after ``name`` that no entry uses: MO_WOLF_01 ->
    MO_WOLF_02 (or _03 if _02 exists), NAME -> NAME_02."""
    taken = {e.name for pl in par.lists for e in pl.entries}
    m = re.match(r'^(.*?)(\d+)$', name)
    prefix, num, width = (m.group(1), int(m.group(2)), len(m.group(2))) if m else (name + '_', 1, 2)
    for n in range(num + 1, num + 10000):
        cand = f'{prefix}{n:0{width}d}'
        if cand not in taken:
            return cand
    return name + '_COPY'


# ---------------------------------------------------------------- jump box ----

def quick_matches(par, query, limit=60):
    """[(li, ei, name, sheet)] for the jump box: every word must occur in the
    name (or the sheet); exact names first, then names that start with it."""
    terms = [t for t in query.lower().split() if t]
    if not terms or par is None:
        return []
    first = terms[0]
    hits = []
    for li, pl in enumerate(par.lists):
        sheet = _sheet(par, li) or ''
        sl = sheet.lower()
        for ei, e in enumerate(pl.entries):
            nl = e.name.lower()
            if all(t in nl or t in sl for t in terms):
                rank = 0 if nl == first else 1 if nl.startswith(first) else 2 if first in nl else 3
                hits.append((rank, len(nl), nl, li, ei, e.name, sheet))
    hits.sort()
    return [(li, ei, name, sheet) for _r, _l, _n, li, ei, name, sheet in hits[:limit]]
