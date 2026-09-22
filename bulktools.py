"""Bulk edit, presets, change review and references for the PAR Editor (1.7.0).

The logic here knows nothing about Tk, so it can be tested on a real par:

- ``targets`` - which entries a bulk edit touches: the selected ones, one
  list, one category or the current search results.
- ``plan_bulk`` - what a bulk edit would change, field by field. A field is
  chosen by its SDK name, not its number, because the lists of one category
  have different layouts: ``maxHP`` is field 6 in one sheet and field 9 in
  another. Entries whose sheet has no such field are counted, not touched.
- ``diff`` - every change between the par as it was opened and as it is now,
  for the review before saving.
- ``references`` - where an entry's name is used in the text fields of other
  entries; ``field_everywhere`` - one field with its value in every entry.

The windows (BulkDialog, ReviewDialog, ReferencesWindow) sit at the end.
"""

import copy
import re

TYPE_INT32, TYPE_FLOAT32, TYPE_UINT32, TYPE_STRING = 0, 1, 2, 3
TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT, TYPE_ARRAY_UINT32, TYPE_ARRAY_STR = 4, 5, 6, 7
NUMBER = (TYPE_INT32, TYPE_FLOAT32, TYPE_UINT32)
NUM_ARRAY = (TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT, TYPE_ARRAY_UINT32)
OPS = ('set', 'add', 'mul', 'replace')


class Change:
    """One field of one entry: old value -> new value."""
    __slots__ = ('li', 'ei', 'fi', 'entry', 'label', 'old', 'new', 'kind')

    def __init__(self, li, ei, fi, entry, label, old, new, kind='field'):
        self.li, self.ei, self.fi = li, ei, fi
        self.entry, self.label = entry, label
        self.old, self.new, self.kind = old, new, kind

    def __repr__(self):
        return f'Change({self.entry}.{self.label}: {self.old!r} -> {self.new!r})'


def sheet_of(par, li):
    sheets = getattr(par, 'sheets', None) or []
    return sheets[li] if li < len(sheets) else None


def label_of(labels, par, li, fi):
    """The SDK name of a field; 'field N' where the sheet has no name for it."""
    name = labels.get(sheet_of(par, li), fi) if labels else None
    return name or f'field {fi}'


# ---------------------------------------------------------------- targets -----

def targets(par, scope, key=None, selected=None, results=None, category_of=None):
    """[(li, ei)] for a scope: 'selected' (list of (li, ei)), 'list' (key = li),
    'category' (key = category name, category_of(sheet, first_name) -> name),
    'results' (the search results of the tree)."""
    if scope == 'selected':
        return [t for t in (selected or []) if _exists(par, t)]
    if scope == 'results':
        return [t for t in (results or []) if _exists(par, t)]
    if scope == 'list':
        li = int(key)
        return [(li, ei) for ei in range(len(par.lists[li].entries))] if 0 <= li < len(par.lists) else []
    if scope == 'category':
        out = []
        for li, pl in enumerate(par.lists):
            first = pl.entries[0].name if pl.entries else ''
            if category_of and category_of(sheet_of(par, li), first) == key:
                out += [(li, ei) for ei in range(len(pl.entries))]
        return out
    raise ValueError(f'unknown scope {scope}')


def _exists(par, t):
    li, ei = t
    return 0 <= li < len(par.lists) and 0 <= ei < len(par.lists[li].entries)


def field_choices(par, tgts, labels):
    """[(label, how many target entries have it, dtype)] - most common first."""
    seen = {}
    for li, ei in tgts:
        entry = par.lists[li].entries[ei]
        for fi, f in enumerate(entry.fields):
            lab = label_of(labels, par, li, fi)
            if lab not in seen:
                seen[lab] = [0, f.dtype]
            seen[lab][0] += 1
    return sorted(((lab, n, dt) for lab, (n, dt) in seen.items()), key=lambda x: (-x[1], x[0].lower()))


# ---------------------------------------------------------------- bulk --------

def _number(text, dtype):
    text = str(text).strip().replace(',', '.')
    if dtype == TYPE_FLOAT32:
        return float(text)
    return int(float(text)) if re.fullmatch(r'[+-]?\d+(\.\d+)?', text) else int(text, 0)


def _one(value, dtype, op, arg):
    """The new value of one scalar, or the old one when the operation does not
    fit the type."""
    if dtype in NUMBER or dtype in NUM_ARRAY:
        base = TYPE_FLOAT32 if dtype in (TYPE_FLOAT32, TYPE_ARRAY_FLOAT) else TYPE_INT32
        if op == 'set':
            new = _number(arg, base)
        elif op == 'add':
            new = value + _number(arg, base)
        elif op == 'mul':
            new = value * (1 + float(str(arg).replace(',', '.').rstrip('%')) / 100.0)
        else:
            return value
        if base == TYPE_INT32:
            new = int(round(new))
            if dtype in (TYPE_UINT32, TYPE_ARRAY_UINT32):
                new = max(0, min(new, 0xFFFFFFFF))
            else:
                new = max(-0x80000000, min(new, 0x7FFFFFFF))
        else:
            new = round(float(new), 6)
        return new
    if dtype in (TYPE_STRING, TYPE_ARRAY_STR):
        if op == 'set':
            return str(arg)
        if op == 'replace':
            old, _, repl = str(arg).partition('=>')
            return value.replace(old, repl) if old else value
    return value


def new_value(value, dtype, op, arg):
    if op not in OPS:
        raise ValueError(f'unknown operation {op}')
    if isinstance(value, list):
        return [_one(v, dtype, op, arg) for v in value]
    return _one(value, dtype, op, arg)


def plan_bulk(par, tgts, labels, label, op, arg):
    """(changes, skipped): what the bulk edit would do. ``skipped`` counts
    target entries whose sheet has no field of that name."""
    changes, skipped = [], 0
    for li, ei in tgts:
        entry = par.lists[li].entries[ei]
        hit = False
        for fi, f in enumerate(entry.fields):
            if label_of(labels, par, li, fi) != label:
                continue
            hit = True
            new = new_value(f.value, f.dtype, op, arg)
            if new != f.value:
                changes.append(Change(li, ei, fi, entry.name, label, copy.deepcopy(f.value), new))
        if not hit:
            skipped += 1
    return changes, skipped


def apply_changes(par, changes):
    for c in changes:
        if c.kind == 'field':
            par.lists[c.li].entries[c.ei].fields[c.fi].value = copy.deepcopy(c.new)
    return len(changes)


# ---------------------------------------------------------------- presets -----

def make_preset(scope, key, label, op, arg):
    """A bulk edit to use again: a category or sheet name survives reopening a
    par, a list number or a selection does not, so those are stored by name."""
    return {'scope': scope, 'key': key, 'label': label, 'op': op, 'arg': str(arg)}


def check_preset(p):
    return (isinstance(p, dict) and p.get('scope') in ('category', 'list', 'results', 'selected')
            and p.get('op') in OPS and isinstance(p.get('label'), str))


# ---------------------------------------------------------------- review ------

def diff(orig, cur, labels):
    """Every change from ``orig`` to ``cur``: field changes, and entries added
    or removed (matched per list by name)."""
    out = []
    for li, pl in enumerate(cur.lists):
        before = {}
        if li < len(orig.lists):
            for ei, e in enumerate(orig.lists[li].entries):
                before.setdefault(e.name, (ei, e))
        now = set()
        for ei, e in enumerate(pl.entries):
            now.add(e.name)
            old = before.get(e.name)
            if old is None:
                out.append(Change(li, ei, -1, e.name, '', None, None, 'added'))
                continue
            oe = old[1]
            for fi, f in enumerate(e.fields):
                ov = oe.fields[fi].value if fi < len(oe.fields) else None
                if f.value != ov:
                    out.append(Change(li, ei, fi, e.name, label_of(labels, cur, li, fi), copy.deepcopy(ov),
                                      copy.deepcopy(f.value)))
        for name, (ei, _e) in before.items():
            if name not in now:
                out.append(Change(li, ei, -1, name, '', None, None, 'removed'))
    return out


def revert(par, changes):
    """Put the old value back for field changes (added/removed entries are
    left to Undo)."""
    n = 0
    for c in changes:
        if c.kind == 'field':
            par.lists[c.li].entries[c.ei].fields[c.fi].value = copy.deepcopy(c.old)
            n += 1
    return n


# ---------------------------------------------------------------- references --

def _texts(value):
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return [value] if isinstance(value, str) else []


def references(par, name, labels=None, whole=True):
    """[(li, ei, fi, label, value)]: text fields of other entries that name
    ``name`` - whole value (case-insensitive) or, with whole=False, anywhere
    inside the text."""
    want = name.lower()
    out = []
    for li, pl in enumerate(par.lists):
        for ei, e in enumerate(pl.entries):
            if e.name.lower() == want:
                continue
            for fi, f in enumerate(e.fields):
                for t in _texts(f.value):
                    tl = t.lower()
                    if (tl == want) if whole else (want in tl):
                        out.append((li, ei, fi, label_of(labels, par, li, fi), f.value))
                        break
    return out


def field_everywhere(par, labels, label):
    """[(li, ei, fi, entry name, value)]: this field in every entry that has it."""
    out = []
    for li, pl in enumerate(par.lists):
        for ei, e in enumerate(pl.entries):
            for fi, f in enumerate(e.fields):
                if label_of(labels, par, li, fi) == label:
                    out.append((li, ei, fi, e.name, f.value))
    return out


def show(value, limit=60):
    """A value as short text for lists."""
    if isinstance(value, float):
        s = f'{value:g}'
    elif isinstance(value, list):
        s = '[' + ', '.join(show(v, 12) for v in value[:6]) + (', ...' if len(value) > 6 else '') + ']'
    else:
        s = str(value)
    return s if len(s) <= limit else s[:limit - 3] + '...'
