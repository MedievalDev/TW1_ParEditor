#!/usr/bin/env python3
"""TW1 PAR Editor — View, edit, and export Two Worlds 1 .par parameter files
   Now with SDK field labels, duplicate/delete/rename entries"""

import re
import struct
import os
import sys
import threading
import json
import io
import zlib
import copy
from pathlib import Path
from collections import OrderedDict

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    HAS_TK = True
except ImportError:
    HAS_TK = False

import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if HAS_TK:
    import theme                       # colours, dark titlebar, Menu (PY_TOOL_DESIGN.md)
    import guidebook                   # Help > Guide (F1), ?-marks
import updater                         # update check + self-update from GitHub
from version import VERSION
from categories import CATEGORIES, SHEET_CATEGORY, NPC_PREFIXES, category_of   # noqa: F401

APP_NAME = 'TW1 PAR EDITOR'
GITHUB_URL = 'https://github.com/MedievalDev/TW1_ParEditor'
SITE_URL = 'https://alchemy-fox.de/'
GUIDE_URL = 'https://alchemy-fox.de/game/TW1_ParEditor/'
COMMUNITY_URL = 'https://twmp.alchemy-fox.de/'
LINKS = (('GitHub-Repo', GITHUB_URL), ('Alchemy Fox', SITE_URL),
         ('Guide-Seite', GUIDE_URL), ('Community', COMMUNITY_URL))


# ------------------------------------------------------------------ Sprache --
# The editor's texts are English (community tool); DE is the translation
# table at the end of the file. Default follows the Windows display language.

_LANG = 'en'


def system_is_german():
    try:
        import ctypes
        return (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x07
    except Exception:
        return False


def tr(text):
    if _LANG == 'de':
        return DE.get(text, text)
    return text


# ------------------------------------------------------------------- Konfig --

def data_dir():
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.environ.get('LOCALAPPDATA', HERE), 'TW1ParEditor')
        os.makedirs(d, exist_ok=True)
        return d
    return HERE


class Config(dict):
    def __init__(self):
        super().__init__()
        self.path = os.path.join(data_dir(), 'par_editor_settings.json')
        try:
            self.update(json.load(open(self.path, encoding='utf-8')))
        except Exception:
            pass

    def save(self):
        try:
            json.dump(self, open(self.path, 'w', encoding='utf-8'), indent=2)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# PAR FORMAT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

PAR_MAGIC = b'PAR\x00'
PAR_VERSION_TW1 = 0x600

# Data type IDs
TYPE_INT32        = 0
TYPE_FLOAT32      = 1
TYPE_UINT32       = 2
TYPE_STRING       = 3
TYPE_ARRAY_INT32  = 4
TYPE_ARRAY_FLOAT  = 5
TYPE_ARRAY_UINT32 = 6
TYPE_ARRAY_STR    = 7

TYPE_NAMES = {
    0: "int32",
    1: "float32",
    2: "uint32",
    3: "string",
    4: "int32[]",
    5: "float32[]",
    6: "uint32[]",
    7: "string[]",
}

# ═══════════════════════════════════════════════════════════════════════════════
# PAR DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class ParFile:
    """Represents a complete PAR file."""
    def __init__(self):
        self.version = PAR_VERSION_TW1
        self.lists = []       # [ParList, ...]
        self.filepath = ""
        self.wrapper_header = None   # zlib wrapper header (stream 1)
        self.was_compressed = False   # file was zlib-compressed on disk
        self.trailing_data = None     # bytes after parsed content

class ParList:
    """A list within the PAR file."""
    def __init__(self):
        self.unknown1 = 0
        self.unknown2 = 0
        self.entries = []     # [ParEntry, ...]

class ParEntry:
    """A single named entry with typed data fields."""
    def __init__(self):
        self.name = ""
        self.unknown_byte = 0
        self.unknown_u16a = 0
        self.unknown_u16b = 0
        self.fields = []      # [ParField, ...]

class ParField:
    """A single typed data field within an entry."""
    def __init__(self, dtype=0, value=None):
        self.dtype = dtype    # Type ID (0-7)
        self.value = value    # Python value (int, float, str, list)

# ═══════════════════════════════════════════════════════════════════════════════
# PAR BINARY READER
# ═══════════════════════════════════════════════════════════════════════════════

class ParReader:
    """Reads PAR binary format."""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.size = len(data)

    def read_bytes(self, n):
        if self.pos + n > self.size:
            raise ValueError(f"Read past end at offset 0x{self.pos:X}, need {n} bytes")
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def read_u8(self):
        return struct.unpack_from('<B', self.data, self._advance(1))[0]

    def read_i8(self):
        return struct.unpack_from('<b', self.data, self._advance(1))[0]

    def read_u16(self):
        return struct.unpack_from('<H', self.data, self._advance(2))[0]

    def read_u32(self):
        return struct.unpack_from('<I', self.data, self._advance(4))[0]

    def read_i32(self):
        return struct.unpack_from('<i', self.data, self._advance(4))[0]

    def read_f32(self):
        return struct.unpack_from('<f', self.data, self._advance(4))[0]

    def read_u64(self):
        return struct.unpack_from('<Q', self.data, self._advance(8))[0]

    def read_delphi_string(self):
        length = self.read_u32()
        if length > 1000000:
            raise ValueError(f"Unreasonable string length {length} at 0x{self.pos:X}")
        if length == 0:
            return ""
        raw = self.read_bytes(length)
        return raw.decode('ascii', errors='replace')

    def _advance(self, n):
        if self.pos + n > self.size:
            raise ValueError(f"Read past end at offset 0x{self.pos:X}")
        p = self.pos
        self.pos += n
        return p



def read_par(data):
    """Parse a PAR binary file. Returns ParFile."""
    r = ParReader(data)

    # Header
    magic = r.read_bytes(4)
    if magic != PAR_MAGIC:
        raise ValueError(f"Not a PAR file (header: {magic!r}, expected {PAR_MAGIC!r})")

    par = ParFile()
    par.version = r.read_u32()

    # Root list
    list_count = r.read_u32()
    _pad = r.read_u32()       # unknown pad

    for li in range(list_count):
        pl = ParList()
        pl.unknown1 = r.read_u32()
        pl.unknown2 = r.read_u32()

        # Prefixed Array<List Entry>
        entry_count = r.read_u32()

        for ei in range(entry_count):
            entry = ParEntry()
            entry.name = r.read_delphi_string()
            entry.unknown_byte = r.read_i8()

            data_entry_count = r.read_u16()
            entry.unknown_u16a = r.read_u16()
            entry.unknown_u16b = r.read_u16()

            # Data Type List
            type_list = []
            for _ in range(data_entry_count):
                type_list.append(r.read_u8())

            # Data Entry List
            for dtype in type_list:
                field = ParField(dtype)

                if dtype == TYPE_INT32:
                    field.value = r.read_i32()
                elif dtype == TYPE_FLOAT32:
                    field.value = r.read_f32()
                elif dtype == TYPE_UINT32:
                    field.value = r.read_u32()
                elif dtype == TYPE_STRING:
                    field.value = r.read_delphi_string()
                elif dtype == TYPE_ARRAY_INT32:
                    field.value = _read_extra_array(r, 'i')
                elif dtype == TYPE_ARRAY_FLOAT:
                    field.value = _read_extra_array(r, 'f')
                elif dtype == TYPE_ARRAY_UINT32:
                    field.value = _read_extra_array(r, 'I')
                elif dtype == TYPE_ARRAY_STR:
                    field.value = _read_extra_string_array(r)
                else:
                    raise ValueError(f"Unknown data type {dtype} at 0x{r.pos:X}")

                entry.fields.append(field)

            pl.entries.append(entry)
        par.lists.append(pl)

    # Preserve trailing data (some PAR files have extra data after the listed entries)
    if r.pos < r.size:
        par.trailing_data = data[r.pos:]

    return par


def _read_extra_array(reader, fmt_char):
    """Read Extra Prefixed Array<T> for numeric types."""
    check = reader.read_u64()
    if check == 0:
        return []
    length = reader.read_u32()
    values = []
    for _ in range(length):
        if fmt_char == 'i':
            values.append(reader.read_i32())
        elif fmt_char == 'f':
            values.append(reader.read_f32())
        elif fmt_char == 'I':
            values.append(reader.read_u32())
    return values


def _read_extra_string_array(reader):
    """Read Extra Prefixed Array<Delphi ASCII>."""
    check = reader.read_u64()
    if check == 0:
        return []
    length = reader.read_u32()
    values = []
    for _ in range(length):
        values.append(reader.read_delphi_string())
    return values


# ═══════════════════════════════════════════════════════════════════════════════
# PAR BINARY WRITER
# ═══════════════════════════════════════════════════════════════════════════════

class ParWriter:
    """Writes PAR binary format."""

    def __init__(self):
        self.buf = io.BytesIO()

    def write_bytes(self, b):
        self.buf.write(b)

    def write_u8(self, v):
        self.buf.write(struct.pack('<B', v & 0xFF))

    def write_i8(self, v):
        self.buf.write(struct.pack('<b', v))

    def write_u16(self, v):
        self.buf.write(struct.pack('<H', v & 0xFFFF))

    def write_u32(self, v):
        self.buf.write(struct.pack('<I', v & 0xFFFFFFFF))

    def write_i32(self, v):
        self.buf.write(struct.pack('<i', v))

    def write_f32(self, v):
        self.buf.write(struct.pack('<f', v))

    def write_u64(self, v):
        self.buf.write(struct.pack('<Q', v))

    def write_delphi_string(self, s):
        encoded = s.encode('ascii', errors='replace')
        self.write_u32(len(encoded))
        self.buf.write(encoded)

    def get_bytes(self):
        return self.buf.getvalue()


def write_par(par):
    """Write a ParFile to binary. Returns bytes."""
    w = ParWriter()

    # Header
    w.write_bytes(PAR_MAGIC)
    w.write_u32(par.version)

    # Root list
    w.write_u32(len(par.lists))
    w.write_u32(0)   # pad

    for pl in par.lists:
        w.write_u32(pl.unknown1)
        w.write_u32(pl.unknown2)

        # Prefixed Array<List Entry>
        w.write_u32(len(pl.entries))

        for entry in pl.entries:
            w.write_delphi_string(entry.name)
            w.write_i8(entry.unknown_byte)

            field_count = len(entry.fields)
            w.write_u16(field_count)
            w.write_u16(entry.unknown_u16a)
            w.write_u16(entry.unknown_u16b)

            # Data Type List
            for field in entry.fields:
                w.write_u8(field.dtype)

            # Data Entry List
            for field in entry.fields:
                dtype = field.dtype
                val = field.value

                if dtype == TYPE_INT32:
                    w.write_i32(int(val))
                elif dtype == TYPE_FLOAT32:
                    w.write_f32(float(val))
                elif dtype == TYPE_UINT32:
                    w.write_u32(int(val))
                elif dtype == TYPE_STRING:
                    w.write_delphi_string(str(val))
                elif dtype == TYPE_ARRAY_INT32:
                    _write_extra_array(w, val, 'i')
                elif dtype == TYPE_ARRAY_FLOAT:
                    _write_extra_array(w, val, 'f')
                elif dtype == TYPE_ARRAY_UINT32:
                    _write_extra_array(w, val, 'I')
                elif dtype == TYPE_ARRAY_STR:
                    _write_extra_string_array(w, val)

    result = w.get_bytes()

    # Append trailing data if present (for byte-perfect roundtrips)
    if getattr(par, 'trailing_data', None):
        result += par.trailing_data

    return result


def _write_extra_array(writer, values, fmt_char):
    """Write Extra Prefixed Array<T> for numeric types."""
    if not values:
        writer.write_u64(0)
        return
    writer.write_u64(1)
    writer.write_u32(len(values))
    for v in values:
        if fmt_char == 'i':
            writer.write_i32(int(v))
        elif fmt_char == 'f':
            writer.write_f32(float(v))
        elif fmt_char == 'I':
            writer.write_u32(int(v))


def _write_extra_string_array(writer, values):
    """Write Extra Prefixed Array<Delphi ASCII>."""
    if not values:
        writer.write_u64(0)
        return
    writer.write_u64(1)
    writer.write_u32(len(values))
    for v in values:
        writer.write_delphi_string(str(v))


# ═══════════════════════════════════════════════════════════════════════════════
# ZLIB WRAPPER (TW1 .par files are double-zlib: wrapper stream + PAR stream)
# ═══════════════════════════════════════════════════════════════════════════════

def decompress_par_file(raw_data):
    """Decompress a .par file from disk.
    
    TW1 .par files consist of two concatenated zlib streams:
      Stream 1 (wrapper): 44 bytes with marker, name, GUID
      Stream 2 (payload): the actual PAR binary data
    
    Returns (par_data, wrapper_bytes_or_None, was_compressed).
    If data is not zlib-compressed, returns (raw_data, None, False).
    """
    # Check for zlib header (0x78 = CMF byte for deflate)
    if len(raw_data) < 4 or raw_data[0] != 0x78:
        # Not compressed — check if it's raw PAR
        if raw_data[:4] == PAR_MAGIC:
            return raw_data, None, False
        raise ValueError(f"Unknown format (header: {raw_data[:4].hex()})")

    # Decompress stream 1 (wrapper)
    dec1 = zlib.decompressobj()
    wrapper = dec1.decompress(raw_data)
    remaining = dec1.unused_data

    if not remaining:
        # Single stream — check if it's PAR directly
        if wrapper[:4] == PAR_MAGIC:
            return wrapper, None, True
        raise ValueError(f"Single zlib stream but not PAR (header: {wrapper[:4].hex()})")

    # Decompress stream 2 (PAR payload)
    dec2 = zlib.decompressobj()
    par_data = dec2.decompress(remaining)

    if par_data[:4] != PAR_MAGIC:
        raise ValueError(f"Stream 2 is not PAR (header: {par_data[:4].hex()})")

    return par_data, wrapper, True


def compress_par_file(par_data, wrapper=None):
    """Compress PAR data back to .par file format.
    
    If wrapper is provided, creates dual-stream zlib (wrapper + PAR).
    Otherwise just compresses the PAR data as a single stream.
    """
    if wrapper is not None:
        # Dual-stream: compress wrapper, then compress PAR, concatenate
        stream1 = zlib.compress(wrapper)
        stream2 = zlib.compress(par_data)
        return stream1 + stream2
    else:
        return zlib.compress(par_data)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON EXPORT / IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

def par_to_dict(par, field_labels=None):
    """Convert ParFile to a serializable dict."""
    result = OrderedDict()
    result["_format"] = "TW1_PAR"
    result["_version"] = par.version

    lists = []
    for li, pl in enumerate(par.lists):
        list_data = OrderedDict()
        list_data["_index"] = li
        if field_labels and FieldLabels.sheet_of(par, li):
            list_data["_sheet"] = FieldLabels.sheet_of(par, li)
        list_data["_unknown1"] = pl.unknown1
        list_data["_unknown2"] = pl.unknown2
        list_data["_entry_count"] = len(pl.entries)

        entries = []
        for entry in pl.entries:
            ed = OrderedDict()
            ed["name"] = entry.name
            ed["_unknown_byte"] = entry.unknown_byte
            ed["_unknown_u16a"] = entry.unknown_u16a
            ed["_unknown_u16b"] = entry.unknown_u16b

            fields = []
            sheet = FieldLabels.sheet_of(par, li) if field_labels else None
            for fi, field in enumerate(entry.fields):
                fd = OrderedDict()
                # Add label if available
                if field_labels:
                    lbl = field_labels.get(sheet, fi)
                    if lbl:
                        fd["label"] = lbl
                fd["type"] = TYPE_NAMES.get(field.dtype, f"unknown({field.dtype})")
                fd["type_id"] = field.dtype
                fd["value"] = field.value
                fields.append(fd)

            ed["fields"] = fields
            entries.append(ed)

        list_data["entries"] = entries
        lists.append(list_data)

    result["lists"] = lists

    # Preserve trailing data for byte-perfect roundtrips
    if par.trailing_data:
        import base64
        result["_trailing_data"] = base64.b64encode(par.trailing_data).decode('ascii')

    # Preserve wrapper header for compressed roundtrips
    if par.wrapper_header:
        import base64
        result["_wrapper_header"] = base64.b64encode(par.wrapper_header).decode('ascii')
        result["_was_compressed"] = True

    return result


def export_json(par, filepath, field_labels=None):
    """Export ParFile as JSON."""
    if field_labels and getattr(par, 'sheets', None) is None:
        field_labels.resolve(par)
    data = par_to_dict(par, field_labels)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def import_json(filepath):
    """Import ParFile from JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    par = ParFile()
    par.version = data.get("_version", PAR_VERSION_TW1)

    # Restore trailing data if present
    if "_trailing_data" in data:
        import base64
        par.trailing_data = base64.b64decode(data["_trailing_data"])

    # Restore wrapper header if present
    if "_wrapper_header" in data:
        import base64
        par.wrapper_header = base64.b64decode(data["_wrapper_header"])
        par.was_compressed = data.get("_was_compressed", True)

    for list_data in data.get("lists", []):
        pl = ParList()
        pl.unknown1 = list_data.get("_unknown1", 0)
        pl.unknown2 = list_data.get("_unknown2", 0)

        for ed in list_data.get("entries", []):
            entry = ParEntry()
            entry.name = ed.get("name", "")
            entry.unknown_byte = ed.get("_unknown_byte", 0)
            entry.unknown_u16a = ed.get("_unknown_u16a", 0)
            entry.unknown_u16b = ed.get("_unknown_u16b", 0)

            for fd in ed.get("fields", []):
                field = ParField()
                field.dtype = fd.get("type_id", 0)
                field.value = fd.get("value")

                # Ensure correct Python types
                if field.dtype in (TYPE_INT32, TYPE_UINT32):
                    if field.value is not None:
                        field.value = int(field.value)
                elif field.dtype == TYPE_FLOAT32:
                    if field.value is not None:
                        field.value = float(field.value)
                elif field.dtype == TYPE_STRING:
                    if field.value is not None:
                        field.value = str(field.value)

                entry.fields.append(field)

            pl.entries.append(entry)
        par.lists.append(pl)

    return par


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# FIELD LABEL SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

# Labels are stored per field-count category (e.g. all 65-field entries share labels)
# This is because the PAR format uses the same column layout for all entries
# with the same number of fields.
#
# Label sources (in order of priority):
#   1. User overrides (~/tw1_par_labels.json)
#   2. SDK labels (tw1_sdk_labels.json - generated from TwoWorlds.xls)
#   3. Minimal fallback defaults (hardcoded below)

DEFAULT_LABELS = {
    6: {0: "soundCue", 1: "volume", 2: "distanceMinA", 3: "distanceMaxA",
        4: "soundFlags", 5: "playPriority"},
    65: {0: "classID", 1: "mesh", 15: "moveWalkSpeed", 16: "moveRunSpeed",
         34: "initParamHP", 35: "initParamDamage", 36: "initParamAttack",
         37: "initParamDefence"},
}


def _find_sdk_labels_path():
    """Find tw1_sdk_labels.json next to the script or in common locations."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tw1_sdk_labels.json'),
        os.path.join(os.path.expanduser('~'), 'tw1_sdk_labels.json'),
        os.path.join(os.getcwd(), 'tw1_sdk_labels.json'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _find_data_file(name):
    """Find a data file next to the script (or exe), in the home dir, or cwd."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base, name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), name),
        os.path.join(os.path.expanduser('~'), name),
        os.path.join(os.getcwd(), name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


class FieldLabels:
    """Field names per SDK sheet, from tw1_sdk_fields.json.

    A list in the .par is exactly one SDK sheet (TwoWorlds.xls). The sheet is
    found by the entry NAMES of a list, not by its field count: nine sheet
    pairs share a field count (Traps/MagicClub 77, Units/ShopUnits 65,
    BasicUnits/BasicUnitsAnimations 26, ...) and the old count-based lookup
    mislabelled 414 of 609 lists. Measured 16.09.2026 against Update16.wd:
    608 of 609 lists resolve, all with the exact column count. The one that
    does not is the "--NULL--" list.

    User overrides live per sheet in ~/tw1_par_labels_v2.json.
    """

    def __init__(self, user_filepath=None):
        self.sheets = {}         # sheet -> [column names]
        self.entry_sheet = {}    # entry name -> sheet
        self.count_sheet = {}    # str(field count) -> sheet (last resort)
        self.user = {}           # sheet -> {field_idx: label}
        self.user_filepath = user_filepath
        self.loaded_from = None
        path = _find_data_file('tw1_sdk_fields.json')
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.sheets = data.get('sheets', {})
                self.entry_sheet = data.get('entries', {})
                self.count_sheet = data.get('counts', {})
                self.loaded_from = path
            except Exception:
                pass
        if user_filepath and os.path.isfile(user_filepath):
            try:
                with open(user_filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for sheet, fields in data.items():
                    self.user[sheet] = {int(fi): lbl for fi, lbl in fields.items()}
            except Exception:
                pass

    @property
    def total(self):
        return sum(len(v) for v in self.sheets.values())

    # ---- sheet resolution ----

    def resolve(self, par):
        """Attach par.sheets: one sheet name (or None) per list."""
        out = []
        for pl in par.lists:
            sheet = None
            if pl.entries:
                votes = {}
                for e in pl.entries:
                    s = self.entry_sheet.get(e.name)
                    if s:
                        votes[s] = votes.get(s, 0) + 1
                if votes:
                    sheet = max(votes, key=votes.get)
                else:
                    sheet = self.count_sheet.get(str(len(pl.entries[0].fields)))
            out.append(sheet)
        par.sheets = out
        return out

    @staticmethod
    def sheet_of(par, li):
        sheets = getattr(par, 'sheets', None)
        if sheets is None or li >= len(sheets):
            return None
        return sheets[li]

    def exact(self, sheet, field_count):
        """True when the sheet's column count equals the entry's field count."""
        return sheet in self.sheets and len(self.sheets[sheet]) == field_count

    # ---- labels ----

    def get(self, sheet, field_idx):
        """Label for a field of a sheet, or None."""
        if not sheet:
            return None
        u = self.user.get(sheet, {})
        if field_idx in u:
            return u[field_idx]
        cols = self.sheets.get(sheet, [])
        return cols[field_idx] if field_idx < len(cols) else None

    def set(self, sheet, field_idx, label):
        if not sheet:
            return
        self.user.setdefault(sheet, {})[field_idx] = label
        self._save_user()

    def remove(self, sheet, field_idx):
        if sheet in self.user and field_idx in self.user[sheet]:
            del self.user[sheet][field_idx]
            self._save_user()

    def _save_user(self):
        if not self.user_filepath:
            return
        data = {s: {str(fi): lbl for fi, lbl in fields.items()}
                for s, fields in self.user.items() if fields}
        try:
            with open(self.user_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


class FieldDescriptions:
    """German field descriptions, keyed by LABEL NAME.

    tw1_sdk_descriptions.json is keyed by field count and index like the old
    label file; both are joined here into {label: description}. Measured
    16.09.2026: 1178 label names, none with two different descriptions.
    """

    def __init__(self):
        self.descs = {}  # label -> description
        lp = _find_data_file('tw1_sdk_labels.json')
        dp = _find_data_file('tw1_sdk_descriptions.json')
        if not (lp and dp):
            return
        try:
            with open(lp, 'r', encoding='utf-8') as f:
                labels = json.load(f)
            with open(dp, 'r', encoding='utf-8') as f:
                descs = json.load(f)
        except Exception:
            return
        for fc, fields in descs.items():
            for fi, d in fields.items():
                lbl = labels.get(fc, {}).get(fi)
                if lbl and lbl not in self.descs:
                    self.descs[lbl] = d

    def get(self, label):
        return self.descs.get(label) if label else None


def help_mark(parent, text, chapter, app, panel=False):
    """Small gold "?" next to a panel title or field: hover explains, click
    opens the guide at the chapter (PY_TOOL_DESIGN.md 6.3)."""
    lbl = ttk.Label(parent, text='?', style='Panel.TLabel' if panel else 'TLabel',
                    foreground=theme.GOLD, cursor='hand2')
    lbl.pack(side='left', padx=(6, 0))
    theme.Tooltip(lbl, text)
    lbl.bind('<Button-1>', lambda ev: app.show_help(text, chapter))
    return lbl


def placeholder(widget, var, text):
    """Grey example inside an empty entry; gone as soon as something is typed."""
    def show():
        if not var.get():
            widget.configure(foreground=theme.DIM)
            var.set(text)
            widget._placeholder = True

    def clear(_ev=None):
        if getattr(widget, '_placeholder', False):
            var.set('')
            widget.configure(foreground=theme.INK)
            widget._placeholder = False

    widget.bind('<FocusIn>', clear, add='+')
    widget.bind('<FocusOut>', lambda ev: show(), add='+')
    show()
    return widget


class ToolTip:
    """Hover-Tooltip für Tkinter-Widgets."""

    def __init__(self, widget, text='', delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self._after_id = None
        widget.bind('<Enter>', self._schedule)
        widget.bind('<Leave>', self._hide)
        widget.bind('<ButtonPress>', self._hide)

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        if not self.text or self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        label = tk.Label(tw, text=self.text, justify='left',
                         background=theme.PANEL, foreground=theme.INK,
                         relief='solid', borderwidth=1, highlightbackground=theme.LINE,
                         font=('Segoe UI', 9), wraplength=420, padx=6, pady=4)
        label.pack()

    def _hide(self, event=None):
        self._cancel()
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    def update_text(self, text):
        self.text = text


class ListboxToolTip:
    """Tooltip für Tkinter Listbox — zeigt Beschreibung je nach Zeile unter dem Cursor."""

    def __init__(self, listbox, delay=350):
        self.listbox = listbox
        self.delay = delay
        self.tip_window = None
        self._after_id = None
        self._last_index = None
        self._get_desc = None  # callback: index -> description or None
        listbox.bind('<Motion>', self._on_motion)
        listbox.bind('<Leave>', self._hide)
        listbox.bind('<ButtonPress>', self._hide)

    def set_callback(self, fn):
        """Set callback fn(index) -> str or None."""
        self._get_desc = fn

    def _on_motion(self, event):
        idx = self.listbox.nearest(event.y)
        if idx < 0 or idx == self._last_index:
            return
        self._last_index = idx
        self._cancel()
        self._hide()
        self._after_id = self.listbox.after(self.delay, lambda: self._show(idx, event))

    def _cancel(self):
        if self._after_id:
            self.listbox.after_cancel(self._after_id)
            self._after_id = None

    def _show(self, idx, event):
        if not self._get_desc or self.tip_window:
            return
        text = self._get_desc(idx)
        if not text:
            return
        x = self.listbox.winfo_rootx() + 20
        y = self.listbox.winfo_rooty() + event.y + 20
        self.tip_window = tw = tk.Toplevel(self.listbox)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        label = tk.Label(tw, text=text, justify='left',
                         background=theme.PANEL, foreground=theme.INK,
                         relief='solid', borderwidth=1, highlightbackground=theme.LINE,
                         font=('Segoe UI', 9), wraplength=420, padx=6, pady=4)
        label.pack()

    def _hide(self, event=None):
        self._cancel()
        self._last_index = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ═══════════════════════════════════════════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════════════════════════════════════════

GUIDE_STEPS = [
    {'title': 'Welcome', 'widget': None, 'text':
     'This editor opens the .par parameter database of Two Worlds 1 - every unit, weapon, '
     'spell, potion and object lives in it. Changes are written back byte-exact; the file '
     'on disk is backed up before it is overwritten.'},
    {'title': 'Open', 'widget': 'btn_open', 'text':
     'Open a TwoWorlds.par. The game runs the one from WDFiles\\Update16.wd - unpack that '
     'one, not Parameters.wd (old 1.0 layout, the editor warns about it).'},
    {'title': 'Groups and sheets', 'widget': 'tree', 'text':
     'The tree is grouped: Player, NPCs, Enemies, Weapons ... Below each group sit the SDK '
     'sheets (Units, Weapon, Traps) and their entries. The dropdown shows one group only. '
     'Right-click an entry to duplicate, rename or delete it.'},
    {'title': 'Filter', 'widget': 'search_entry', 'text':
     'Type to show only matching entries - by name, by sheet (traps, units) or by any text '
     'field such as the mesh path. Several words must all match: "units wolf". '
     'Enter jumps through the matches, Esc clears.'},
    {'title': 'Fields', 'widget': 'detail_canvas', 'text':
     'Each field shows its SDK name; hover it for a description. A red border means the '
     'text is not a valid value - the old value is kept and Save refuses until it is fixed. '
     'Integers accept 0x hex.'},
    {'title': 'Save', 'widget': 'btn_save', 'text':
     'Ctrl+S writes the file in place, the previous version goes to _backup next to it. '
     'Pack the result into a mod archive (Parameters\\TwoWorlds.par, flags 0x39) for the game.'},
    {'title': 'Compare & Merge', 'widget': 'notebook', 'text':
     'The second tab compares two .par files field by field and merges chosen changes - '
     'handy for bringing another mod\'s values into yours.'},
]


class Guide:
    def __init__(self, app):
        self.app, self.i, self.frames, self.win = app, 0, [], None

    def start(self):
        self.i = 0
        if self.win:
            self.win.destroy()
        self.win = tk.Toplevel(self.app.root)
        self.win.title(tr('Guide'))
        self.win.configure(background=theme.PANEL)
        self.win.transient(self.app.root)
        self.win.attributes('-topmost', True)
        self.win.protocol('WM_DELETE_WINDOW', lambda: self.finish(False))
        theme.dark_titlebar(self.win)
        f = ttk.Frame(self.win, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        self.head = ttk.Label(f, style='PanelTitle.TLabel')
        self.head.pack(anchor='w')
        self.title = ttk.Label(f, style='Panel.TLabel', font=theme.FONT_H2, foreground=theme.GOLD)
        self.title.pack(anchor='w', pady=(4, 6))
        self.text = ttk.Label(f, style='Panel.TLabel', wraplength=360, justify='left')
        self.text.pack(anchor='w')
        self.dont = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text=tr("Don't show at startup"), variable=self.dont,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(14, 8))
        b = ttk.Frame(f, style='Panel.TFrame')
        b.pack(fill='x')
        self.back = ttk.Button(b, text=tr('Back'), command=self.prev)
        self.back.pack(side='left')
        self.next = ttk.Button(b, text=tr('Next'), style='Accent.TButton', command=self.nxt)
        self.next.pack(side='left', padx=8)
        ttk.Button(b, text=tr('Quit guide'), command=lambda: self.finish(self.dont.get())).pack(side='right')
        self.show()
        r = self.app.root
        self.win.geometry(f'+{r.winfo_rootx() + 460}+{r.winfo_rooty() + 110}')

    def show(self):
        s = GUIDE_STEPS[self.i]
        self.head.configure(text=tr('Step {n} of {m}').format(n=self.i + 1, m=len(GUIDE_STEPS)))
        self.title.configure(text=tr(s['title']))
        self.text.configure(text=tr(s['text']))
        self.back.state(['!disabled'] if self.i > 0 else ['disabled'])
        self.next.configure(text=tr('Next') if self.i < len(GUIDE_STEPS) - 1 else tr('Finish'))
        self.highlight(getattr(self.app, s['widget'], None) if s['widget'] else None)

    def prev(self):
        if self.i > 0:
            self.i -= 1
            self.show()

    def nxt(self):
        if self.i < len(GUIDE_STEPS) - 1:
            self.i += 1
            self.show()
        else:
            self.finish(True)

    def highlight(self, widget):
        for f in self.frames:
            f.destroy()
        self.frames = []
        if widget is None:
            return
        root = self.app.root
        root.update_idletasks()
        x = widget.winfo_rootx() - root.winfo_rootx()
        y = widget.winfo_rooty() - root.winfo_rooty()
        w, h, t = widget.winfo_width(), widget.winfo_height(), 3
        for fx, fy, fw, fh in ((x, y, w, t), (x, y + h - t, w, t), (x, y, t, h), (x + w - t, y, t, h)):
            f = tk.Frame(root, background=theme.GOLD)
            f.place(x=fx, y=fy, width=fw, height=fh)
            self.frames.append(f)

    def finish(self, dont_show):
        self.highlight(None)
        if dont_show or self.i == len(GUIDE_STEPS) - 1:
            self.app.cfg['guide_seen'] = True
            self.app.cfg.save()
        if self.win:
            self.win.destroy()
            self.win = None


class ParEditorApp:
    def __init__(self, root, carry=None):
        self.root = root
        self.cfg = Config()
        self._carry = carry or {}      # state handed over by the DE/EN rebuild
        self.selftest = os.environ.get('PAR_EDITOR_SELFTEST')
        self.undo_stack, self.redo_stack = [], []
        global _LANG
        _LANG = self.cfg.get('lang') or ('de' if system_is_german() else 'en')
        self.restart = False          # set by the DE/EN toggle; main() rebuilds
        self.guide = Guide(self)
        self.root.withdraw()
        self.root.title(f"TW1 PAR Editor v{VERSION}")
        self.root.geometry("1200x750")
        self.root.minsize(900, 550)
        self._icon()

        self.par = None           # Current ParFile
        self.filepath = ""        # Current file path
        self.modified = False     # Unsaved changes flag
        self.search_results = []  # (list_idx, entry_idx) tuples
        self.search_idx = 0       # Current result index

        # Compare & Merge state
        self.cmp_source = None     # ParFile
        self.cmp_input = None      # ParFile
        self.cmp_original = None   # ParFile (optional reference)
        self.cmp_diffs = []        # list of diff dicts
        self.cmp_checks = {}       # diff_idx -> BooleanVar
        self._cmp_original_path = self.cfg.get('original_par_path', '')

        # Field labels: SDK sheets, user overrides per sheet in the home dir
        default_labels_path = os.path.join(os.path.expanduser('~'), 'tw1_par_labels_v2.json')
        self.field_labels = FieldLabels(default_labels_path)
        self.field_descs = FieldDescriptions()
        self._filter_job = None       # debounce timer of the live filter
        self._invalid = {}            # field_idx -> label of fields with bad input

        self.update_var = tk.BooleanVar(value=bool(self.cfg.get('update_check', True)))
        self._setup_theme()
        self._build_ui()
        self._bind_keys()
        if self._carry.get('geometry'):
            self.root.geometry(self._carry['geometry'])
        self.root.deiconify()
        self.root.after(200, self._startup)

    # ── Start-up: carried state, update check, selftest ──

    def _startup(self):
        updater.cleanup_old()
        c = self._carry
        if c.get('path') and os.path.isfile(c['path']):
            self._load_par(c['path'])
            if c.get('select') and self.par:
                li, ei = c['select']
                iid = f"L{li}E{ei}"
                if self.tree.exists(iid):
                    self._open_list(f"L{li}")
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    self._show_entry(li, ei)
            if c.get('tab'):
                self.notebook.select(c['tab'])
        if self.selftest:
            self._run_selftest()
            return
        if not c and self.cfg.get('update_check', True):
            self.root.after(1500, self.check_updates)
        if not c and not self.cfg.get('guide_seen'):
            self.root.after(700, self.guide.start)

    def _run_selftest(self):
        """PAR_EDITOR_SELFTEST=<file>: write the core facts and quit."""
        try:
            https = 'ok'
            try:
                import http.client  # noqa: F401
                import ssl  # noqa: F401
                import urllib.request  # noqa: F401
            except ImportError as e:
                https = f'missing:{e.name}'
            with open(self.selftest, 'w', encoding='utf-8') as f:
                f.write(f'version={VERSION} sheets={len(self.field_labels.sheets)} '
                        f'names={self.field_labels.total} descs={len(self.field_descs.descs)} '
                        f'chapters={len(guidebook.CHAPTERS)} https={https} '
                        f'frozen={getattr(sys, "frozen", False)}\n')
        except Exception as e:
            with open(self.selftest, 'a', encoding='utf-8') as f:
                f.write(f'selftest failed: {e!r}\n')
        finally:
            self.root.after(50, self.root.destroy)

    def _toggle_update_check(self):
        self.cfg['update_check'] = bool(self.update_var.get())
        self.cfg.save()

    def check_updates(self, manual=False):
        """Ask GitHub for the latest release (thread) and tell the user when
        it is newer. On start silently, from the menu with an answer."""
        results = []
        updater.check_async(lambda info, err: results.append((info, err)))

        def poll():
            try:
                if not self.root.winfo_exists():
                    return
            except tk.TclError:
                return
            if not results:
                self.root.after(200, poll)
                return
            info, err = results[0]
            if err is not None or info is None:
                if manual:
                    messagebox.showwarning(tr("Update"), tr("GitHub was not reachable: {err}").format(err=err),
                                           parent=self.root)
                return
            if not updater.is_newer(info['tag']):
                if manual:
                    messagebox.showinfo(tr("Update"), tr("You have the latest version ({version}).").format(version=VERSION),
                                        parent=self.root)
                return
            if not manual and self.cfg.get('update_skip') == info['tag']:
                return
            self.set_hint(tr("Update available: version {version}").format(version=info['version']))
            UpdateWindow(self, info)
        self.root.after(200, poll)

    def _confirm_discard(self):
        """True when unsaved changes may be dropped (asks to save first)."""
        if not self.modified:
            return True
        r = messagebox.askyesnocancel(tr("Unsaved Changes"), tr("Save changes first?"), parent=self.root)
        if r is None:
            return False
        if r:
            self._save()
            return not self.modified
        return True

    # ── Guide window and ?-marks ──

    def show_guide(self, chapter='start'):
        guidebook.GuideWindow.show(self, chapter)

    def show_help(self, text, chapter):
        self.set_hint(text.split('\n')[0])
        self.show_guide(chapter)

    def set_hint(self, text):
        self.hint_label.configure(text=(text or '')[:140])

    # ── Undo / Redo (snapshot per change, PY_TOOL_DESIGN.md 7.2) ──

    def _snapshot(self, scope):
        kind = scope[0]
        if kind == 'entry':
            e = self.par.lists[scope[1]].entries[scope[2]]
            return (e.name, [copy.deepcopy(f.value) for f in e.fields])
        if kind == 'list':
            pl = self.par.lists[scope[1]]
            return (list(pl.entries), [(e.name, [copy.deepcopy(f.value) for f in e.fields]) for e in pl.entries])
        return [(list(pl.entries), [(e.name, [copy.deepcopy(f.value) for f in e.fields]) for e in pl.entries])
                for pl in self.par.lists]

    def _restore(self, scope, state):
        kind = scope[0]
        if kind == 'entry':
            e = self.par.lists[scope[1]].entries[scope[2]]
            e.name, vals = state
            for f, v in zip(e.fields, vals):
                f.value = v
        elif kind == 'list':
            pl = self.par.lists[scope[1]]
            pl.entries[:] = state[0]
            for e, (name, vals) in zip(pl.entries, state[1]):
                e.name = name
                for f, v in zip(e.fields, vals):
                    f.value = v
        else:
            for pl, (ents, vals) in zip(self.par.lists, state):
                pl.entries[:] = ents
                for e, (name, fv) in zip(pl.entries, vals):
                    e.name = name
                    for f, v in zip(e.fields, fv):
                        f.value = v

    def push_undo(self, scope, label):
        if not self.par:
            return
        self.undo_stack.append((label, scope, self._snapshot(scope)))
        del self.undo_stack[:-50]
        self.redo_stack.clear()

    def _apply_undo(self, take_from, put_to, word):
        if not take_from or not self.par:
            self.set_hint(tr("Nothing to {word}").format(word=word))
            return
        label, scope, state = take_from.pop()
        put_to.append((label, scope, self._snapshot(scope)))
        self._restore(scope, state)
        self.modified = True
        self._update_title()
        keep = (self.current_li, self.current_ei) if self.current_entry else None
        self._populate_tree(keep_selection=keep)
        if keep and self.tree.exists(f"L{keep[0]}E{keep[1]}"):
            self._show_entry(*keep)
        self._set_status(f"{word.capitalize()}: {label}")

    def do_undo(self):
        self._apply_current_edits()
        self._apply_undo(self.undo_stack, self.redo_stack, tr("undo"))

    def do_redo(self):
        self._apply_current_edits()
        self._apply_undo(self.redo_stack, self.undo_stack, tr("redo"))

    def _typing(self):
        w = self.root.focus_get()
        return isinstance(w, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Listbox))

    def _key(self, fn):
        """Global shortcut that lets the key through while typing in a field."""
        def handler(ev):
            if self._typing():
                return None
            fn()
            return 'break'
        return handler

    def _restore_backup(self):
        """File > Restore backup: pick a copy from _backup and load it as the
        current file (saving then writes it back over the original)."""
        if not self.filepath:
            messagebox.showinfo(tr("Restore backup"), tr("Open a .par first - backups sit next to it."), parent=self.root)
            return
        bdir = os.path.join(os.path.dirname(self.filepath), '_backup')
        if not os.path.isdir(bdir):
            messagebox.showinfo(tr("Restore backup"), tr("No _backup folder next to this file yet."), parent=self.root)
            return
        p = filedialog.askopenfilename(title=tr("Restore backup"), initialdir=bdir,
                                       filetypes=[("PAR backups", "*.par"), ("All Files", "*.*")])
        if not p or not self._confirm_discard():
            return
        target = self.filepath
        self._load_par(p)
        self.filepath = target
        self.par.filepath = target
        self.modified = True
        self._update_title()
        self._set_status(tr("Loaded {b} - Save (Ctrl+S) writes it back to {f}").format(
            b=os.path.basename(p), f=os.path.basename(target)))

    def _icon(self):
        base = getattr(sys, '_MEIPASS', HERE)
        ico = os.path.join(base, 'par_editor.ico')
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass

    # ── Menubar (dark frame with popup menus, DE/EN toggle) ──

    def _build_menubar(self):
        bar = ttk.Frame(self.root, style='Menubar.TFrame')
        bar.pack(fill='x')
        self.menubar = bar
        for key, filler in ((tr('File'), self._fill_file), (tr('Edit'), self._fill_edit),
                            (tr('View'), self._fill_view), (tr('Compare'), self._fill_compare),
                            (tr('Help'), self._fill_help)):
            item = ttk.Label(bar, text=key, style='Menubar.TLabel')
            item.pack(side='left')
            item.bind('<Button-1>', lambda ev, f=filler, w=item: self._popup(f, w))
            item.bind('<Enter>', lambda ev, w=item: w.state(['active']))
            item.bind('<Leave>', lambda ev, w=item: w.state(['!active']))
        ttk.Label(bar, text=APP_NAME, style='Menubar.TLabel').pack(side='right', padx=(0, 6))
        self.lang_toggle = self._build_lang_toggle(bar)
        self.lang_toggle.pack(side='right', padx=(0, 10))

    def _build_lang_toggle(self, bar):
        box = ttk.Frame(bar, style='Menubar.TFrame')
        self.lang_labels = {}
        for i, code in enumerate(('de', 'en')):
            if i:
                ttk.Label(box, text='·', style='Menubar.TLabel', padding=(2, 5)).pack(side='left')
            lbl = ttk.Label(box, text=code.upper(), style='Menubar.TLabel', padding=(4, 5), cursor='hand2')
            lbl.pack(side='left')
            lbl.bind('<Button-1>', lambda ev, c=code: self.set_lang(c))
            self.lang_labels[code] = lbl
        self._paint_lang_toggle()
        return box

    def _paint_lang_toggle(self):
        for code, lbl in self.lang_labels.items():
            lbl.configure(foreground=theme.GOLD if code == _LANG else theme.MUT)

    def set_lang(self, code):
        global _LANG
        if code == _LANG:
            return
        if not self._confirm_discard():
            return
        self.cfg['lang'] = code
        self.cfg.save()
        _LANG = code
        self.restart = True
        self.carry_out = {'path': self.filepath if self.filepath and os.path.isfile(self.filepath) else None,
                          'select': (self.current_li, self.current_ei) if self.current_entry else None,
                          'tab': self.notebook.index(self.notebook.select()) if hasattr(self, 'notebook') else 0,
                          'geometry': self.root.geometry()}
        self.root.destroy()

    def _popup(self, filler, widget):
        menu = theme.Menu(self.root)
        filler(menu)
        try:
            menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        finally:
            menu.grab_release()

    def _fill_file(self, m):
        m.add_command(label=tr("Open PAR..."), accelerator="Ctrl+O", command=self._open_par)
        m.add_command(label=tr("Open JSON..."), accelerator="Ctrl+I", command=self._open_json)
        m.add_separator()
        m.add_command(label=tr("Save"), accelerator="Ctrl+S", command=self._save,
                      state='normal' if self.par else 'disabled')
        m.add_command(label=tr("Save As..."), accelerator="Ctrl+Shift+S", command=self._save_as,
                      state='normal' if self.par else 'disabled')
        m.add_separator()
        m.add_command(label=tr("Export JSON..."), accelerator="Ctrl+E", command=self._export_json,
                      state='normal' if self.par else 'disabled')
        m.add_separator()
        m.add_command(label=tr("Restore backup..."), command=self._restore_backup,
                      state='normal' if self.par else 'disabled')
        m.add_separator()
        m.add_command(label=tr("Exit"), accelerator="Alt+F4", command=self._on_close)

    def _fill_edit(self, m):
        has = bool(self.par and self.current_entry)
        li, ei = self.current_li, self.current_ei
        m.add_command(label=tr("Undo"), accelerator="Ctrl+Z", command=self.do_undo,
                      state='normal' if self.undo_stack else 'disabled')
        m.add_command(label=tr("Redo"), accelerator="Ctrl+Y", command=self.do_redo,
                      state='normal' if self.redo_stack else 'disabled')
        m.add_separator()
        m.add_command(label=tr("Duplicate entry..."), command=lambda: self._duplicate_entry(li, ei),
                      state='normal' if has else 'disabled')
        m.add_command(label=tr("Rename entry..."), command=lambda: self._rename_entry(li, ei),
                      state='normal' if has else 'disabled')
        m.add_command(label=tr("Delete entry"), command=lambda: self._delete_entry(li, ei),
                      state='normal' if has else 'disabled')
        m.add_separator()
        m.add_command(label=tr("Filter"), accelerator="Ctrl+F",
                      command=lambda: self.search_entry.focus_set())
        m.add_command(label=tr("Next match"), accelerator="F3", command=self._search_next)
        m.add_command(label=tr("Clear filter"), accelerator="Esc",
                      command=lambda: self.search_var.set(''))

    def _fill_view(self, m):
        m.add_command(label=tr("Editor"), command=lambda: self.notebook.select(0))
        m.add_command(label=tr("Compare & Merge"), command=lambda: self.notebook.select(1))
        m.add_separator()
        sub = theme.Menu(m)
        for code, name in (('de', 'Deutsch'), ('en', 'English')):
            sub.add_radiobutton(label=name, value=code, variable=tk.StringVar(value=_LANG),
                                command=lambda c=code: self.set_lang(c))
        m.add_cascade(label=tr("Language"), menu=sub)

    def _fill_compare(self, m):
        m.add_command(label=tr("Open Compare Tab"), command=lambda: self.notebook.select(1))
        m.add_separator()
        m.add_command(label=tr("Set Original PAR..."), command=self._cmp_set_original)

    def _fill_help(self, m):
        m.add_command(label=tr("Guide"), accelerator="F1", command=self.show_guide)
        m.add_command(label=tr("Start tour"), command=self.guide.start)
        m.add_command(label=tr("Documentation"), command=lambda: webbrowser.open(GUIDE_URL))
        m.add_separator()
        for name, url in LINKS:
            m.add_command(label=f'{name}  ({url})', command=lambda u=url: webbrowser.open(u))
        m.add_separator()
        m.add_command(label=tr("Check for updates"), command=lambda: self.check_updates(manual=True))
        m.add_checkbutton(label=tr("Check for updates on start"), variable=self.update_var,
                          command=self._toggle_update_check)
        m.add_command(label=tr("Latest version on GitHub"), command=lambda: webbrowser.open(updater.LATEST_PAGE))
        m.add_separator()
        m.add_command(label=tr("About"), command=self.show_about)

    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title(tr("About"))
        win.configure(background=theme.BG)
        win.transient(self.root)
        theme.dark_titlebar(win)
        f = ttk.Frame(win, padding=16)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=f'TW1 PAR Editor {VERSION}', style='Brand.TLabel').pack(anchor='w')
        ttk.Label(f, text=tr("Edits the .par parameter database of Two Worlds 1: every unit,\n"
                             "weapon, spell, potion and object. Field names from the SDK sheets,\n"
                             "byte-identical round trip, compare & merge between two files."),
                  style='Muted.TLabel', justify='left').pack(anchor='w', pady=(6, 10))
        for name, url in LINKS:
            lnk = ttk.Label(f, text=f'{name}: {url}', style='Link.TLabel', cursor='hand2')
            lnk.pack(anchor='w', padx=(12, 0))
            lnk.bind('<Button-1>', lambda e, u=url: webbrowser.open(u))
        ttk.Button(f, text=tr("Close"), command=win.destroy).pack(anchor='e', pady=(12, 0))

    # ── Theme ──

    def _setup_theme(self):
        """Colours from theme.py (PY_TOOL_DESIGN.md). The old attribute names
        stay so the rest of the file reads as before; no hex outside theme."""
        theme.apply_dark_theme(self.root)
        self.BG = theme.BG            # window, detail area
        self.FG = theme.INK
        self.BG2 = theme.BG           # detail rows
        self.BG3 = theme.PANEL        # bars, panels, menus
        self.BG4 = theme.FIELD        # input fields
        self.ACCENT = theme.GOLD
        self.GREEN = theme.OK         # int values
        self.YELLOW = theme.GOLD_HI   # float values, "changed"
        self.RED = theme.ERR
        self.ORANGE = theme.SPEAKER_COLORS[2]   # string values
        self.BLUE = theme.PLAYER_COLOR          # arrays, "source only"
        self.PURPLE = theme.SPEAKER_COLORS[3]   # type names

        style = ttk.Style(self.root)
        style.configure('Small.TButton', padding=(6, 2), font=theme.FONT)
        style.configure('Title.TLabel', foreground=theme.GOLD, font=theme.FONT_H1)
        style.configure('Info.TLabel', foreground=theme.MUT, font=theme.FONT_MONO)
        style.configure('Dim.TLabel', foreground=theme.MUT, font=theme.FONT_SMALL)
        style.configure('Treeview', font=('Consolas', 10))

    # ── UI Build ──

    def _build_ui(self):
        self._build_menubar()

        # ── Status bar: packed before the panes so it never gets squeezed
        # out at small window sizes (PY_TOOL_DESIGN.md 7.5) ──
        self.statusbar = ttk.Frame(self.root, style='Status.TFrame')
        self.statusbar.pack(fill='x', side='bottom')
        self.status = ttk.Label(self.statusbar, text="Ready", style='Status.TLabel')
        self.status.pack(side='left')
        self.hint_label = ttk.Label(self.statusbar, text="", style='Status.TLabel')
        self.hint_label.pack(side='right')
        self.dirty_label = ttk.Label(self.statusbar, text="", style='StatusErr.TLabel')
        self.dirty_label.pack(side='right')

        # ── Toolbar ──
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(fill='x')

        self.btn_open = ttk.Button(toolbar, text=tr("Open"), command=self._open_par,
                                   style='Small.TButton')
        self.btn_open.pack(side='left', padx=(0, 4))
        self.btn_save = ttk.Button(toolbar, text=tr("Save"), command=self._save,
                                   style='Small.TButton')
        self.btn_save.pack(side='left', padx=(0, 4))
        ttk.Button(toolbar, text=tr("Export JSON"), command=self._export_json,
                   style='Small.TButton').pack(side='left', padx=(0, 16))

        # Category dropdown: one group instead of 609 lists
        ttk.Label(toolbar, text=tr("Category:")).pack(side='left', padx=(0, 4))
        self.cat_var = tk.StringVar(value=tr('All'))
        self.cat_box = ttk.Combobox(toolbar, textvariable=self.cat_var, state='readonly',
                                    width=20, values=[tr('All')] + [tr(c) for c in CATEGORIES])
        self.cat_box.pack(side='left', padx=(0, 12))
        self.cat_box.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())
        help_mark(toolbar, tr("One group of the par: player, NPCs, enemies, weapons ... The tree is grouped the same way. Click for the guide."), 'groups', self)
        ToolTip(self.cat_box, tr("Show only one group: player, NPCs, enemies, weapons, "
                                 "game parameters ... The tree is grouped the same way."))

        # Filter: the tree shows only matching entries while you type
        # (name, sheet, string fields; several words = all must match).
        ttk.Label(toolbar, text=tr("Filter:")).pack(side='left', padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var,
                                       font=('Consolas', 10), width=30)
        self.search_entry.pack(side='left', padx=(0, 4))
        ttk.Button(toolbar, text="\u25B6", command=self._search_next,
                   style='Small.TButton', width=3).pack(side='left', padx=(0, 2))
        ttk.Button(toolbar, text="\u2715", command=lambda: self.search_var.set(''),
                   style='Small.TButton', width=3).pack(side='left', padx=(0, 2))
        self.search_label = ttk.Label(toolbar, text="", style='Dim.TLabel')
        self.search_label.pack(side='left', padx=(4, 0))
        help_mark(toolbar, tr("Type to keep only matching entries: name, sheet or text field. Several words must all match. Click for the guide."), 'filter', self)
        placeholder(self.search_entry, self.search_var, tr("wolf, traps, units wolf ..."))
        ToolTip(self.search_entry, tr(
                "Type to filter the tree: entry name, sheet (Units, Weapon, Traps ...)\n"
                "or any text field such as the mesh path. Several words: all must match.\n"
                "Enter / F3 jumps to the next match, Esc clears, Ctrl+F focuses."))

        # File info on right
        self.file_label = ttk.Label(toolbar, text=tr("No file loaded"),
                                     style='Dim.TLabel')
        self.file_label.pack(side='right')

        # ── Notebook (Editor + Compare & Merge) ──
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=4, pady=(0, 4))

        # Tab 1: Editor
        editor_tab = ttk.Frame(self.notebook)
        self.notebook.add(editor_tab, text="  " + tr("Editor") + "  ")

        paned = tk.PanedWindow(editor_tab, orient='horizontal', bg=self.BG,
                                sashwidth=4, sashrelief='flat')
        paned.pack(fill='both', expand=True)

        # Left: Tree
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, width=420, minsize=250)

        hdr = ttk.Frame(left_frame)
        hdr.pack(fill='x', pady=(0, 2))
        tree_label = ttk.Label(hdr, text="  " + tr("Lists & Entries"),
                                style='TLabel', font=('Segoe UI', 10, 'bold'))
        tree_label.pack(side='left')
        help_mark(hdr, tr("Groups, below them the SDK sheets, below those the entries. Right-click an entry to duplicate, rename or delete it."), 'tree', self)

        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill='both', expand=True)
        # Empty state: never a blank pane without a way forward (7.4)
        self.empty_box = ttk.Frame(tree_container, style='Panel.TFrame', padding=16)
        ttk.Label(self.empty_box, text=tr("No file loaded"), style='PanelTitle.TLabel').pack()
        ttk.Label(self.empty_box, text=tr("Open the TwoWorlds.par from WDFiles\\Update16.wd - the one the game runs."),
                  style='PanelMuted.TLabel', wraplength=260, justify='center').pack(pady=(0, 10))
        ttk.Button(self.empty_box, text=tr("Open PAR...") + "  (Ctrl+O)", style='Accent.TButton',
                   command=self._open_par).pack()
        self.empty_box.place(relx=0.5, rely=0.38, anchor='center')

        self.tree = ttk.Treeview(tree_container, show='tree',
                                  selectmode='browse')
        tree_scroll = ttk.Scrollbar(tree_container, orient='vertical',
                                     command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        tree_scroll.pack(side='right', fill='y')

        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.tree.bind('<Button-3>', self._tree_context_menu)

        # Right: Detail Panel
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, minsize=400)

        dh = ttk.Frame(right_frame)
        dh.pack(fill='x', padx=8, pady=(4, 2))
        self.detail_header = ttk.Label(dh, text=tr("Select an entry to view details"),
                                        style='Title.TLabel')
        self.detail_header.pack(side='left')
        help_mark(dh, tr("Every field with its SDK name; hover a name for the description. Red border = not a valid value, the old one is kept."), 'fields', self)

        self.detail_info = ttk.Label(right_frame, text="", style='Info.TLabel')
        self.detail_info.pack(fill='x', padx=8, pady=(0, 2))
        self.field_error = ttk.Label(right_frame, text="", style='StatusErr.TLabel')
        self.field_error.pack(fill='x', padx=8, pady=(0, 2))

        # Scrollable detail area
        detail_container = ttk.Frame(right_frame)
        detail_container.pack(fill='both', expand=True, padx=4)

        self.detail_canvas = tk.Canvas(detail_container, bg=self.BG2,
                                        highlightthickness=0)
        detail_scroll = ttk.Scrollbar(detail_container, orient='vertical',
                                       command=self.detail_canvas.yview)
        self.detail_canvas.configure(yscrollcommand=detail_scroll.set)

        self.detail_inner = tk.Frame(self.detail_canvas, bg=self.BG2)
        self.detail_canvas.create_window((0, 0), window=self.detail_inner,
                                          anchor='nw', tags='inner')

        self.detail_canvas.pack(side='left', fill='both', expand=True)
        detail_scroll.pack(side='right', fill='y')

        self.detail_inner.bind('<Configure>', self._on_detail_configure)
        self.detail_canvas.bind('<Configure>', self._on_canvas_configure)
        # Mouse wheel scrolling
        self.detail_canvas.bind('<Enter>', self._bind_mousewheel)
        self.detail_canvas.bind('<Leave>', self._unbind_mousewheel)

        # Tab 2: Compare & Merge
        self._build_compare_tab()

        # Show label info
        total_labels = self.field_labels.total
        total_descs = len(self.field_descs.descs)
        if total_labels:
            desc_info = f", {total_descs} descriptions" if total_descs > 0 else ""
            self.status.configure(
                text=f"Ready — {len(self.field_labels.sheets)} SDK sheets, "
                     f"{total_labels} field names{desc_info} loaded")
        else:
            self.status.configure(
                text="Ready — tw1_sdk_fields.json not found next to the editor: no field names")

    def _bind_keys(self):
        self.root.bind('<Control-o>', lambda e: self._open_par())
        self.root.bind('<Control-s>', lambda e: self._save())
        self.root.bind('<Control-Shift-S>', lambda e: self._save_as())
        self.root.bind('<Control-e>', lambda e: self._export_json())
        self.root.bind('<Control-i>', lambda e: self._open_json())
        self.root.bind('<Control-f>', lambda e: (self.search_entry.focus_set(),
                                                 self.search_entry.select_range(0, 'end')))
        self.root.bind('<F3>', lambda e: self._search_next())
        self.root.bind('<F1>', lambda e: self.show_guide())
        self.root.bind('<Control-z>', self._key(self.do_undo))
        self.root.bind('<Control-y>', self._key(self.do_redo))
        self.root.bind('<Return>', lambda e: self._search_next()
                       if self.search_entry == self.root.focus_get() else None)
        self.root.bind('<Escape>', lambda e: self.search_var.set('')
                       if self.search_entry == self.root.focus_get() else None)
        self.search_var.trace_add('write', lambda *a: self._on_filter_change())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bind_mousewheel(self, event):
        self.detail_canvas.bind_all('<MouseWheel>',
                                     lambda e: self.detail_canvas.yview_scroll(
                                         int(-1 * (e.delta / 120)), "units"))
        self.detail_canvas.bind_all('<Button-4>',
                                     lambda e: self.detail_canvas.yview_scroll(-3, "units"))
        self.detail_canvas.bind_all('<Button-5>',
                                     lambda e: self.detail_canvas.yview_scroll(3, "units"))

    def _unbind_mousewheel(self, event):
        self.detail_canvas.unbind_all('<MouseWheel>')
        self.detail_canvas.unbind_all('<Button-4>')
        self.detail_canvas.unbind_all('<Button-5>')

    def _on_detail_configure(self, event):
        self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox('all'))

    def _on_canvas_configure(self, event):
        self.detail_canvas.itemconfig('inner', width=event.width)

    # ── File Operations ──

    def _open_par(self):
        path = filedialog.askopenfilename(
            title="Open PAR File",
            filetypes=[("PAR Files", "*.par"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._load_par(path)

    def _load_par(self, path):
        try:
            with open(path, 'rb') as f:
                raw_data = f.read()

            par_data, wrapper, was_compressed = decompress_par_file(raw_data)
            self.par = read_par(par_data)
            self.par.filepath = path
            self.par.wrapper_header = wrapper
            self.par.was_compressed = was_compressed
            self.filepath = path
            self.modified = False
            self._backed_up = set()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.field_labels.resolve(self.par)
            self.empty_box.place_forget()
            self._populate_tree()
            self._update_title()

            total_entries = sum(len(pl.entries) for pl in self.par.lists)
            comp_str = "  [zlib]" if was_compressed else ""
            self.file_label.configure(
                text=f"{Path(path).name}{comp_str}  |  {len(self.par.lists)} lists, "
                     f"{total_entries} entries  |  "
                     f"v0x{self.par.version:X}")
            resolved = sum(1 for s in self.par.sheets if s)
            inexact = sum(1 for li, s in enumerate(self.par.sheets)
                          if s and self.par.lists[li].entries
                          and not self.field_labels.exact(s, len(self.par.lists[li].entries[0].fields)))
            layout = ''
            if inexact:
                # Parameters.wd carries the 1.0 layout; the game actually runs
                # the par from Update16.wd, which matches the SDK sheets.
                layout = (f" — WARNING: {inexact} lists do not match the SDK sheets "
                          f"(old 1.0 layout? open the par from Update16.wd)")
            self._set_status(f"Opened {Path(path).name} — "
                            f"{len(self.par.lists)} lists, {total_entries} entries, "
                            f"{resolved} lists matched to SDK sheets"
                            f"{' (zlib compressed)' if was_compressed else ''}{layout}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open:\n{e}")

    def _open_json(self):
        path = filedialog.askopenfilename(
            title="Open JSON File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            self.par = import_json(path)
            self.filepath = path.replace('.json', '.par')
            self.par.filepath = self.filepath
            self.modified = True
            self._backed_up = set()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.field_labels.resolve(self.par)
            self.empty_box.place_forget()
            self._populate_tree()
            self._update_title()

            total_entries = sum(len(pl.entries) for pl in self.par.lists)
            self.file_label.configure(
                text=f"Imported from JSON  |  {len(self.par.lists)} lists, "
                     f"{total_entries} entries")
            self._set_status(f"Imported from {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import:\n{e}")

    def _save(self):
        if not self.par:
            return
        if not self.filepath or self.filepath.endswith('.json'):
            self._save_as()
            return
        self._do_save(self.filepath)

    def _save_as(self):
        if not self.par:
            return
        path = filedialog.asksaveasfilename(
            title="Save PAR File",
            defaultextension=".par",
            filetypes=[("PAR Files", "*.par"), ("All Files", "*.*")],
            initialfile=Path(self.filepath).name if self.filepath else "TwoWorlds.par"
        )
        if not path:
            return
        self._do_save(path)

    def _backup(self, path):
        """Copy the file about to be overwritten into _backup\\ next to it.

        Once per file and session: the first save keeps the state the editor
        found on disk, later saves in the same session do not pile up copies.
        """
        if not os.path.isfile(path) or path in self._backed_up:
            return None
        import shutil
        import time
        bdir = os.path.join(os.path.dirname(path), '_backup')
        os.makedirs(bdir, exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(path))
        dst = os.path.join(bdir, f"{stem}.{time.strftime('%Y-%m-%d_%H-%M-%S')}{ext}")
        shutil.copy2(path, dst)
        self._backed_up.add(path)
        return dst

    def _do_save(self, path):
        try:
            self._apply_current_edits()
            if self._invalid:
                names = ', '.join(self._invalid.values())
                messagebox.showerror(
                    "Invalid values",
                    f"Not saved. These fields hold text that is not a valid value:\n{names}\n\n"
                    f"Fix them (red border) or restore the old value.")
                return
            par_data = write_par(self.par)

            # Re-compress if the original was compressed
            if self.par.was_compressed:
                out_data = compress_par_file(par_data, self.par.wrapper_header)
            else:
                out_data = par_data

            backup = self._backup(path)
            with open(path, 'wb') as f:
                f.write(out_data)
            self.filepath = path
            self.par.filepath = path
            self.modified = False
            self._update_title()
            comp_str = " (zlib)" if self.par.was_compressed else ""
            bak_str = f"  |  backup: _backup\\{os.path.basename(backup)}" if backup else ""
            self._set_status(f"Saved {Path(path).name} ({len(out_data)} bytes{comp_str}){bak_str}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    def _export_json(self):
        if not self.par:
            messagebox.showinfo("No Data", "Open a PAR file first.")
            return
        default_name = Path(self.filepath).stem + ".json" if self.filepath else "TwoWorlds.json"
        path = filedialog.asksaveasfilename(
            title="Export as JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=default_name
        )
        if not path:
            return
        try:
            self._apply_current_edits()
            export_json(self.par, path, self.field_labels)
            self._set_status(f"Exported to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export:\n{e}")

    def _on_close(self):
        if self.modified:
            r = messagebox.askyesnocancel("Unsaved Changes",
                                           "Save changes before closing?")
            if r is None:
                return
            if r:
                self._save()
        self.root.destroy()

    def _update_title(self):
        name = Path(self.filepath).name if self.filepath else "Untitled"
        mod = " *" if self.modified else ""
        self.dirty_label.configure(text=tr("unsaved changes") + "  " if self.modified else "")
        self.root.title(f"TW1 PAR Editor v{VERSION} — {name}{mod}")

    def _set_status(self, msg):
        self.status.configure(text=msg)

    # ── Tree Population ──

    @staticmethod
    def _entry_matches(entry, sheet, terms):
        """All terms must occur in the name, the sheet name or a string field."""
        hay = [entry.name.lower(), (sheet or '').lower()]
        hay += [str(f.value).lower() for f in entry.fields if f.dtype == TYPE_STRING and f.value]
        for a in entry.fields:
            if a.dtype == TYPE_ARRAY_STR and a.value:
                hay += [str(s).lower() for s in a.value]
        return all(any(t in h for h in hay) for t in terms)

    def _on_filter_change(self):
        """Debounced live filter: rebuild the tree 250 ms after the last key."""
        if self._filter_job:
            self.root.after_cancel(self._filter_job)
        self._filter_job = self.root.after(250, self._apply_filter)

    def _apply_filter(self):
        self._filter_job = None
        if not self.par:
            return
        self._apply_current_edits()
        keep = (self.current_li, self.current_ei) if self.current_entry else None
        self._populate_tree(keep_selection=keep)

    def _populate_tree(self, keep_selection=None):
        self.tree.delete(*self.tree.get_children())
        self._clear_detail()

        if not self.par:
            return

        terms = [t for t in self._filter_text().lower().split() if t]
        self.search_results = []
        self.search_idx = 0
        self._last_query = ' '.join(terms)
        shown = 0
        sheets = getattr(self.par, 'sheets', None) or [None] * len(self.par.lists)

        # Category nodes first, in fixed order; lists hang below them.
        want = self.cat_var.get()
        only = None if want == tr('All') else next((c for c in CATEGORIES if tr(c) == want), None)
        cat_nodes = {}
        cat_count = {c: 0 for c in CATEGORIES}
        for c in CATEGORIES:
            if only and c != only:
                continue
            cat_nodes[c] = self.tree.insert('', 'end', iid=f"C{CATEGORIES.index(c)}",
                                            text=f"  {tr(c)}", open=bool(only or terms))

        for li, pl in enumerate(self.par.lists):
            sheet = sheets[li] if li < len(sheets) else None
            cat = category_of(sheet, pl.entries[0].name if pl.entries else '')
            if cat not in cat_nodes:
                continue
            entries = [(ei, e) for ei, e in enumerate(pl.entries)
                       if not terms or self._entry_matches(e, sheet, terms)]
            if terms and not entries:
                continue
            cat_count[cat] += len(entries)

            # List node: SDK sheet, first entry as hint, count
            entry_count = len(pl.entries)
            head = sheet or f"List {li}"
            if entry_count == 0:
                list_label = f"{head}  (empty)"
            elif entry_count == 1:
                list_label = f"{head}  ({pl.entries[0].name})"
            else:
                first = pl.entries[0].name
                shown_str = f"{len(entries)} of {entry_count}" if terms else f"{entry_count}"
                list_label = f"{head}  ({first}...)  [{shown_str}]"

            list_id = self.tree.insert(cat_nodes[cat], 'end', iid=f"L{li}",
                                        text=f"  {list_label}",
                                        open=bool(terms))

            # Entry nodes
            for ei, entry in entries:
                field_count = len(entry.fields)
                if terms:
                    self.search_results.append((li, ei))
                shown += 1
                # Find best preview: prefer first string field, else first value
                preview = ""
                for f in entry.fields[:5]:
                    if f.dtype == TYPE_STRING and f.value:
                        s = str(f.value)
                        if len(s) > 35:
                            s = s[-32:] 
                            preview = f"...{s}"
                        else:
                            preview = s
                        break
                if not preview and field_count > 0:
                    preview = self._field_preview(entry.fields[0])

                entry_text = f"  {entry.name}"
                if preview:
                    entry_text = f"  {entry.name}  \u2502 {preview}"

                self.tree.insert(list_id, 'end',
                                  iid=f"L{li}E{ei}",
                                  text=entry_text)

        for c, node in cat_nodes.items():
            if terms and not cat_count[c]:
                self.tree.delete(node)
            else:
                self.tree.item(node, text=f"  {tr(c)}  [{cat_count[c]}]")
        if terms:
            self.search_label.configure(text=tr("{n} entries").format(n=shown))
        else:
            self.search_label.configure(text="")
        if keep_selection:
            li, ei = keep_selection
            iid = f"L{li}E{ei}"
            if self.tree.exists(iid):
                self._open_list(f"L{li}")
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _open_list(self, list_iid):
        """Expand a list node and the category above it."""
        if not self.tree.exists(list_iid):
            return
        parent = self.tree.parent(list_iid)
        if parent:
            self.tree.item(parent, open=True)
        self.tree.item(list_iid, open=True)

    def _field_preview(self, field):
        """Short preview string for a field value."""
        if field.dtype == TYPE_STRING:
            s = str(field.value)
            if len(s) > 30:
                return f'"{s[:27]}..."'
            return f'"{s}"'
        elif field.dtype == TYPE_FLOAT32:
            return f"{field.value:.4f}"
        elif field.dtype in (TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT,
                             TYPE_ARRAY_UINT32, TYPE_ARRAY_STR):
            arr = field.value if field.value else []
            return f"[{len(arr)} items]"
        else:
            return str(field.value)

    # ── Tree Selection → Detail ──

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        item_id = sel[0]

        # Parse item ID (C = category, L = list, L..E.. = entry)
        if item_id.startswith('C'):
            self._apply_current_edits()
            self._clear_detail()
            return
        if item_id.startswith('L') and 'E' in item_id:
            # Entry node: L{li}E{ei}
            parts = item_id[1:].split('E')
            li = int(parts[0])
            ei = int(parts[1])
            self._apply_current_edits()
            self._show_entry(li, ei)
        elif item_id.startswith('L'):
            # List node
            li = int(item_id[1:])
            self._apply_current_edits()
            self._show_list_info(li)

    def _show_list_info(self, li):
        """Show info about a list (no editable fields)."""
        self._clear_detail()

        if not self.par or li >= len(self.par.lists):
            return

        pl = self.par.lists[li]
        self.detail_header.configure(text=f"List {li}")
        self.detail_info.configure(
            text=f"{len(pl.entries)} entries  |  "
                 f"unknown1=0x{pl.unknown1:X}  unknown2=0x{pl.unknown2:X}")

        self.current_entry = None
        self.current_li = li
        self.current_ei = -1
        self.edit_widgets = []

    def _show_entry(self, li, ei):
        """Show entry details in the right panel with editable fields."""
        self._clear_detail()

        if not self.par or li >= len(self.par.lists):
            return
        pl = self.par.lists[li]
        if ei >= len(pl.entries):
            return

        entry = pl.entries[ei]
        self.current_entry = entry
        self.current_li = li
        self.current_ei = ei
        self.edit_widgets = []

        field_count = len(entry.fields)
        sheet = FieldLabels.sheet_of(self.par, li)
        self.detail_header.configure(text=entry.name)
        info = f"{sheet or 'unknown sheet'}  |  {field_count} fields  |  List {li}, Entry {ei}"
        if sheet and not self.field_labels.exact(sheet, field_count):
            # Old 1.0 layout (Parameters.wd) - the game runs Update16's par,
            # which matches the SDK sheets exactly. Names past the first
            # divergence are guesses here, so say so instead of lying.
            info += (f"  |  WARNING: sheet has {len(self.field_labels.sheets[sheet])} "
                     f"columns, entry {field_count} fields - field names unreliable")
        self.detail_info.configure(text=info)
        self._invalid = {}

        parent = self.detail_inner

        for fi, field in enumerate(entry.fields):
            row = tk.Frame(parent, bg=self.BG2)
            row.pack(fill='x', padx=8, pady=2)

            # Field index, label, and type
            type_name = TYPE_NAMES.get(field.dtype, f"?{field.dtype}")
            label_name = self.field_labels.get(sheet, fi)

            header_frame = tk.Frame(row, bg=self.BG2)
            header_frame.pack(fill='x')

            idx_label = tk.Label(header_frame, text=f"[{fi}]",
                                  bg=self.BG2, fg=theme.DIM,
                                  font=('Consolas', 9), width=5, anchor='e')
            idx_label.pack(side='left')

            # Show label if available
            if label_name:
                name_label = tk.Label(header_frame, text=label_name,
                                       bg=self.BG2, fg=theme.GOLD,
                                       font=('Consolas', 10, 'bold'),
                                       anchor='w')
                name_label.pack(side='left', padx=(4, 4))
                # Right-click to rename
                name_label.bind('<Button-3>',
                    lambda e, sh=sheet, fidx=fi: self._label_context(e, sh, fidx))
                # Tooltip with German description
                tip_text = self.field_descs.get(label_name)
                if tip_text:
                    ToolTip(name_label, f"{label_name}\n{tip_text}")
            else:
                # Clickable placeholder to add label
                name_label = tk.Label(header_frame, text="···",
                                       bg=self.BG2, fg=theme.DIM,
                                       font=('Consolas', 9),
                                       cursor='hand2', anchor='w')
                name_label.pack(side='left', padx=(4, 4))
                name_label.bind('<Button-1>',
                    lambda e, sh=sheet, fidx=fi: self._add_label(sh, fidx))
                name_label.bind('<Button-3>',
                    lambda e, sh=sheet, fidx=fi: self._label_context(e, sh, fidx))

            type_label = tk.Label(header_frame, text=type_name,
                                   bg=self.BG2, fg=self.PURPLE,
                                   font=('Consolas', 10), width=10, anchor='w')
            type_label.pack(side='left', padx=(0, 8))

            # Value widget
            if field.dtype in (TYPE_INT32, TYPE_UINT32):
                var = tk.StringVar(value=str(field.value))
                w = tk.Entry(header_frame, textvariable=var, bg=self.BG4,
                             fg=self.GREEN, font=('Consolas', 10),
                             insertbackground=self.FG, relief='flat',
                             highlightthickness=1,
                             highlightcolor=self.ACCENT,
                             highlightbackground=self.BG3)
                w.pack(side='left', fill='x', expand=True, ipady=2)
                self._watch_input(var, w, field.dtype, label_name or f"[{fi}]")
                self.edit_widgets.append((fi, field.dtype, var))

            elif field.dtype == TYPE_FLOAT32:
                var = tk.StringVar(value=f"{field.value:.6f}")
                w = tk.Entry(header_frame, textvariable=var, bg=self.BG4,
                             fg=self.YELLOW, font=('Consolas', 10),
                             insertbackground=self.FG, relief='flat',
                             highlightthickness=1,
                             highlightcolor=self.ACCENT,
                             highlightbackground=self.BG3)
                w.pack(side='left', fill='x', expand=True, ipady=2)
                self._watch_input(var, w, field.dtype, label_name or f"[{fi}]")
                self.edit_widgets.append((fi, field.dtype, var))

            elif field.dtype == TYPE_STRING:
                var = tk.StringVar(value=str(field.value))
                w = tk.Entry(header_frame, textvariable=var, bg=self.BG4,
                             fg=self.ORANGE, font=('Consolas', 10),
                             insertbackground=self.FG, relief='flat',
                             highlightthickness=1,
                             highlightcolor=self.ACCENT,
                             highlightbackground=self.BG3)
                w.pack(side='left', fill='x', expand=True, ipady=2)
                self.edit_widgets.append((fi, field.dtype, var))

            elif field.dtype in (TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT,
                                  TYPE_ARRAY_UINT32, TYPE_ARRAY_STR):
                arr = field.value if field.value else []
                arr_label = tk.Label(
                    header_frame,
                    text=f"[{len(arr)} items]",
                    bg=self.BG2, fg=self.BLUE,
                    font=('Consolas', 10))
                arr_label.pack(side='left', padx=(0, 8))

                # Show array contents below
                if arr:
                    arr_frame = tk.Frame(row, bg=self.BG2)
                    arr_frame.pack(fill='x', padx=(90, 0))

                    arr_text = tk.Text(arr_frame, bg=self.BG4, fg=self.FG,
                                        font=('Consolas', 9), relief='flat',
                                        height=min(len(arr), 8),
                                        insertbackground=self.FG,
                                        highlightthickness=1,
                                        highlightcolor=self.ACCENT,
                                        highlightbackground=self.BG3,
                                        wrap='none')
                    for ai, av in enumerate(arr):
                        if field.dtype == TYPE_ARRAY_FLOAT:
                            line = f"{av:.6f}"
                        else:
                            line = str(av)
                        arr_text.insert('end', line + ('\n' if ai < len(arr)-1 else ''))
                    arr_text.pack(fill='x', pady=1)
                    self.edit_widgets.append((fi, field.dtype, arr_text))

            # Separator line
            sep = tk.Frame(parent, bg=self.BG3, height=1)
            sep.pack(fill='x', padx=4, pady=1)

    @staticmethod
    def _value_ok(text, dtype):
        """Would _apply_current_edits accept this text for the type?"""
        try:
            if dtype in (TYPE_INT32, TYPE_UINT32):
                v = int(text.strip(), 0)
                lo, hi = (-2**31, 2**31 - 1) if dtype == TYPE_INT32 else (0, 2**32 - 1)
                return lo <= v <= hi
            if dtype == TYPE_FLOAT32:
                float(text.strip().replace(',', '.'))
            return True
        except (ValueError, TypeError):
            return False

    def _watch_input(self, var, widget, dtype, label=''):
        """Red border while the text is not a valid value for the field, and
        one line under the header that says why (7.1: instant check)."""
        def check(*_):
            ok = self._value_ok(var.get(), dtype)
            widget.configure(highlightbackground=self.BG3 if ok else self.RED,
                             highlightcolor=self.ACCENT if ok else self.RED,
                             highlightthickness=1 if ok else 2)
            if ok:
                if self.field_error.cget('text').startswith(label + ':'):
                    self.field_error.configure(text='')
            else:
                why = tr("not a whole number (0x.. is fine)") if dtype in (TYPE_INT32, TYPE_UINT32) else tr("not a number")
                self.field_error.configure(text=f"{label}: {why}")
        var.trace_add('write', check)

    def _label_context(self, event, sheet, field_idx):
        """Show right-click context menu for field labels."""
        if not sheet:
            return
        menu = theme.Menu(self.root)
        current = self.field_labels.get(sheet, field_idx)
        if current:
            menu.add_command(
                label=f"Rename '{current}'...",
                command=lambda: self._rename_label(sheet, field_idx, current))
            if field_idx in self.field_labels.user.get(sheet, {}):
                menu.add_command(
                    label="Restore SDK name",
                    command=lambda: self._remove_label(sheet, field_idx))
        else:
            menu.add_command(
                label="Set label...",
                command=lambda: self._add_label(sheet, field_idx))
        menu.tk_popup(event.x_root, event.y_root)

    def _add_label(self, sheet, field_idx):
        """Add a new label for a field."""
        if not sheet:
            return
        name = simpledialog.askstring(
            "Set Field Label",
            f"Label for field [{field_idx}] of sheet {sheet}:",
            parent=self.root)
        if name and name.strip():
            self.field_labels.set(sheet, field_idx, name.strip())
            self._set_status(f"Label [{field_idx}] = '{name.strip()}' (for all {sheet} entries)")
            # Refresh display
            if self.current_entry:
                self._show_entry(self.current_li, self.current_ei)

    def _rename_label(self, sheet, field_idx, current):
        """Rename an existing label."""
        name = simpledialog.askstring(
            "Rename Field Label",
            f"Rename field [{field_idx}] of sheet {sheet}:",
            initialvalue=current,
            parent=self.root)
        if name and name.strip():
            self.field_labels.set(sheet, field_idx, name.strip())
            self._set_status(f"Renamed [{field_idx}] → '{name.strip()}'")
            if self.current_entry:
                self._show_entry(self.current_li, self.current_ei)

    def _remove_label(self, sheet, field_idx):
        """Drop the user override; the SDK name shows again."""
        self.field_labels.remove(sheet, field_idx)
        self._set_status(f"Restored SDK name for [{field_idx}]")
        if self.current_entry:
            self._show_entry(self.current_li, self.current_ei)

    # ── Tree Context Menu (Right-Click) ──

    def _tree_context_menu(self, event):
        """Show right-click context menu on tree items."""
        item_id = self.tree.identify_row(event.y)
        if not item_id or not self.par or item_id.startswith('C'):
            return

        # Select the item under cursor
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)

        menu = theme.Menu(self.root)

        if item_id.startswith('L') and 'E' in item_id:
            # Entry node: L{li}E{ei}
            parts = item_id[1:].split('E')
            li, ei = int(parts[0]), int(parts[1])
            entry = self.par.lists[li].entries[ei]

            menu.add_command(
                label=f"\u2398 Duplicate '{entry.name}'...",
                command=lambda: self._duplicate_entry(li, ei))
            menu.add_command(
                label=f"\u270E Rename '{entry.name}'...",
                command=lambda: self._rename_entry(li, ei))
            menu.add_separator()
            menu.add_command(
                label=f"\u2716 Delete '{entry.name}'",
                command=lambda: self._delete_entry(li, ei))

        elif item_id.startswith('L'):
            # List node
            li = int(item_id[1:])
            pl = self.par.lists[li]
            menu.add_command(
                label=f"Add New Entry to List {li}...",
                command=lambda: self._add_entry_to_list(li))
            if pl.entries:
                menu.add_command(
                    label=f"Duplicate Last Entry...",
                    command=lambda: self._duplicate_entry(li, len(pl.entries) - 1))

        menu.tk_popup(event.x_root, event.y_root)

    def _duplicate_entry(self, li, ei):
        """Deep-copy an entry, ask for new name, insert after original."""
        if not self.par or li >= len(self.par.lists):
            return
        pl = self.par.lists[li]
        if ei >= len(pl.entries):
            return

        src = pl.entries[ei]

        # Suggest a name: try incrementing trailing number
        suggested = self._suggest_next_name(src.name)

        new_name = simpledialog.askstring(
            "Duplicate Entry",
            f"Name for the copy of '{src.name}':",
            initialvalue=suggested,
            parent=self.root)
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()

        # Check for duplicate names
        all_names = set()
        for plist in self.par.lists:
            for e in plist.entries:
                all_names.add(e.name)
        if new_name in all_names:
            if not messagebox.askyesno(
                "Name exists",
                f"'{new_name}' already exists.\nDuplicate anyway?"):
                return

        # Deep copy entry
        new_entry = ParEntry()
        new_entry.name = new_name
        new_entry.unknown_byte = src.unknown_byte
        new_entry.unknown_u16a = src.unknown_u16a
        new_entry.unknown_u16b = src.unknown_u16b
        for f in src.fields:
            nf = ParField(f.dtype)
            if isinstance(f.value, list):
                nf.value = copy.deepcopy(f.value)
            else:
                nf.value = f.value
            new_entry.fields.append(nf)

        # Update string fields that contain the old name (e.g. mesh path)
        old_lower = src.name.lower()
        new_lower = new_name.lower()
        for nf in new_entry.fields:
            if nf.dtype == TYPE_STRING and isinstance(nf.value, str):
                if old_lower in nf.value.lower():
                    # Case-preserving replace
                    idx = nf.value.lower().find(old_lower)
                    nf.value = nf.value[:idx] + new_name + nf.value[idx + len(old_lower):]

        # Insert after original
        self.push_undo(('list', li), tr("duplicate {name}").format(name=src.name))
        pl.entries.insert(ei + 1, new_entry)

        self.modified = True
        self._update_title()
        self._populate_tree()

        # Select the new entry
        new_item_id = f"L{li}E{ei + 1}"
        parent_id = f"L{li}"
        self._open_list(parent_id)
        self.tree.selection_set(new_item_id)
        self.tree.see(new_item_id)
        self.tree.focus(new_item_id)

        self._set_status(f"Duplicated '{src.name}' → '{new_name}'")

    def _rename_entry(self, li, ei):
        """Rename an entry."""
        if not self.par or li >= len(self.par.lists):
            return
        entry = self.par.lists[li].entries[ei]
        old_name = entry.name

        new_name = simpledialog.askstring(
            "Rename Entry",
            f"New name for '{old_name}':",
            initialvalue=old_name,
            parent=self.root)
        if not new_name or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()

        self.push_undo(('entry', li, ei), tr("rename {name}").format(name=old_name))
        entry.name = new_name

        # Optionally update string fields referencing old name
        old_lower = old_name.lower()
        updated_fields = 0
        for f in entry.fields:
            if f.dtype == TYPE_STRING and isinstance(f.value, str):
                if old_lower in f.value.lower():
                    idx = f.value.lower().find(old_lower)
                    f.value = f.value[:idx] + new_name + f.value[idx + len(old_lower):]
                    updated_fields += 1

        self.modified = True
        self._update_title()
        self._populate_tree()

        # Reselect
        item_id = f"L{li}E{ei}"
        parent_id = f"L{li}"
        self._open_list(parent_id)
        self.tree.selection_set(item_id)
        self.tree.see(item_id)

        extra = f" (+{updated_fields} fields)" if updated_fields else ""
        self._set_status(f"Renamed '{old_name}' → '{new_name}'{extra}")

    def _delete_entry(self, li, ei):
        """Delete an entry after confirmation."""
        if not self.par or li >= len(self.par.lists):
            return
        pl = self.par.lists[li]
        if ei >= len(pl.entries):
            return

        name = pl.entries[ei].name
        if not messagebox.askyesno(
            "Delete Entry",
            f"Delete '{name}' from List {li}?\n\nThis cannot be undone."):
            return

        self.push_undo(('list', li), tr("delete {name}").format(name=name))
        pl.entries.pop(ei)
        self.modified = True
        self._update_title()
        self._clear_detail()
        self._populate_tree()
        self._set_status(f"Deleted '{name}' from List {li}")

    def _add_entry_to_list(self, li):
        """Add a new empty entry to a list. Copies field structure from existing entries."""
        if not self.par or li >= len(self.par.lists):
            return
        pl = self.par.lists[li]

        new_name = simpledialog.askstring(
            "New Entry",
            f"Name for new entry in List {li}:",
            parent=self.root)
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()

        new_entry = ParEntry()
        new_entry.name = new_name

        # Copy field structure from first entry in same list (same types, zero/empty values)
        if pl.entries:
            template = pl.entries[0]
            new_entry.unknown_byte = template.unknown_byte
            new_entry.unknown_u16a = template.unknown_u16a
            new_entry.unknown_u16b = template.unknown_u16b
            for f in template.fields:
                nf = ParField(f.dtype)
                if f.dtype == TYPE_INT32:
                    nf.value = 0
                elif f.dtype == TYPE_FLOAT32:
                    nf.value = 0.0
                elif f.dtype == TYPE_UINT32:
                    nf.value = 0
                elif f.dtype == TYPE_STRING:
                    nf.value = ""
                elif f.dtype in (TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT,
                                 TYPE_ARRAY_UINT32, TYPE_ARRAY_STR):
                    nf.value = []
                new_entry.fields.append(nf)

        self.push_undo(('list', li), tr("add {name}").format(name=new_name))
        pl.entries.append(new_entry)

        self.modified = True
        self._update_title()
        self._populate_tree()

        new_ei = len(pl.entries) - 1
        item_id = f"L{li}E{new_ei}"
        parent_id = f"L{li}"
        self._open_list(parent_id)
        self.tree.selection_set(item_id)
        self.tree.see(item_id)

        self._set_status(f"Added '{new_name}' to List {li}")

    def _suggest_next_name(self, name):
        """Suggest next name by incrementing trailing number."""
        import re
        m = re.match(r'^(.*?)(\d+)$', name)
        if m:
            prefix = m.group(1)
            num = int(m.group(2))
            width = len(m.group(2))
            return f"{prefix}{num + 1:0{width}d}"
        return name + "_COPY"

    def _clear_detail(self):
        """Clear the detail panel."""
        for w in self.detail_inner.winfo_children():
            w.destroy()
        self.detail_header.configure(text=tr("Select an entry"))
        self.detail_info.configure(text="")
        self.field_error.configure(text="")
        self.edit_widgets = []
        self.current_entry = None

    def _apply_current_edits(self):
        """Apply edits from the detail panel back to the data model."""
        if not self.current_entry or not self.edit_widgets:
            return

        entry = self.current_entry
        changed = False
        before = self._snapshot(('entry', self.current_li, self.current_ei))

        self._invalid = {}
        for fi, dtype, widget in self.edit_widgets:
            if fi >= len(entry.fields):
                continue
            field = entry.fields[fi]

            try:
                if dtype in (TYPE_INT32, TYPE_UINT32):
                    new_val = int(widget.get().strip(), 0)     # 0x.. allowed
                    lo, hi = (-2**31, 2**31 - 1) if dtype == TYPE_INT32 else (0, 2**32 - 1)
                    if not lo <= new_val <= hi:
                        raise ValueError('out of range')
                    if new_val != field.value:
                        field.value = new_val
                        changed = True

                elif dtype == TYPE_FLOAT32:
                    new_val = float(widget.get().strip().replace(',', '.'))
                    if new_val != field.value:
                        field.value = new_val
                        changed = True

                elif dtype == TYPE_STRING:
                    new_val = widget.get()
                    if new_val != field.value:
                        field.value = new_val
                        changed = True

                elif dtype in (TYPE_ARRAY_INT32, TYPE_ARRAY_FLOAT,
                               TYPE_ARRAY_UINT32, TYPE_ARRAY_STR):
                    # widget is a Text widget
                    text = widget.get('1.0', 'end').strip()
                    if text:
                        lines = [l.strip() for l in text.split('\n')
                                 if l.strip()]
                        if dtype == TYPE_ARRAY_INT32:
                            new_val = [int(l) for l in lines]
                        elif dtype == TYPE_ARRAY_FLOAT:
                            new_val = [float(l) for l in lines]
                        elif dtype == TYPE_ARRAY_UINT32:
                            new_val = [int(l) for l in lines]
                        elif dtype == TYPE_ARRAY_STR:
                            new_val = lines
                        else:
                            new_val = field.value
                    else:
                        new_val = []

                    if new_val != field.value:
                        field.value = new_val
                        changed = True

            except (ValueError, TypeError):
                # Keep the old value - but say so. Silently dropping the
                # input was the old behaviour and nobody noticed their edit
                # never happened.
                sheet = FieldLabels.sheet_of(self.par, self.current_li) if self.par else None
                self._invalid[fi] = self.field_labels.get(sheet, fi) or f"[{fi}]"

        if self._invalid:
            self._set_status(tr("Invalid value kept OLD value: ") + ', '.join(self._invalid.values()))
        if changed:
            self.undo_stack.append((tr("edit {name}").format(name=entry.name),
                                    ('entry', self.current_li, self.current_ei), before))
            del self.undo_stack[:-50]
            self.redo_stack.clear()
            self.modified = True
            self._update_title()

    # ── Search ──

    def _filter_text(self):
        """Filter box content, '' while it shows the grey example."""
        if getattr(self.search_entry, '_placeholder', False):
            return ''
        return self.search_var.get().strip()

    def _search_next(self):
        """Jump to the next entry of the filtered tree."""
        query = ' '.join(self._filter_text().lower().split())
        if not query or not self.par:
            self.search_label.configure(text="")
            return

        # The filter may still be pending (debounce) - apply it now
        if self._filter_job or getattr(self, '_last_query', None) != query:
            if self._filter_job:
                self.root.after_cancel(self._filter_job)
                self._filter_job = None
            self._apply_filter()

        if not self.search_results:
            self.search_label.configure(text="No results")
            return

        # Cycle through results
        if self.search_idx >= len(self.search_results):
            self.search_idx = 0

        li, ei = self.search_results[self.search_idx]
        self.search_idx += 1

        self.search_label.configure(
            text=f"{self.search_idx}/{len(self.search_results)}")

        # Select in tree
        item_id = f"L{li}E{ei}"
        parent_id = f"L{li}"

        self._open_list(parent_id)
        self.tree.selection_set(item_id)
        self.tree.see(item_id)
        self.tree.focus(item_id)

    # ══════════════════════════════════════════════════════════════════════
    # COMPARE & MERGE TAB
    # ══════════════════════════════════════════════════════════════════════

    def _save_cmp_config(self):
        """Remember the original PAR path in the tool config."""
        self.cfg['original_par_path'] = self._cmp_original_path
        self.cfg.save()

    def _build_compare_tab(self):
        """Build the Compare & Merge tab UI."""
        cmp_tab = ttk.Frame(self.notebook)
        self.notebook.add(cmp_tab, text="  " + tr("Compare & Merge") + "  ")

        # ── Top: File loaders ──
        loader_frame = tk.Frame(cmp_tab, bg=self.BG3, padx=8, pady=8)
        loader_frame.pack(fill='x')

        # Source
        sf = tk.Frame(loader_frame, bg=self.BG3)
        sf.pack(fill='x', pady=(0, 4))
        tk.Label(sf, text="Source PAR:", bg=self.BG3, fg=self.GREEN,
                 font=('Segoe UI', 10, 'bold'), width=14, anchor='w').pack(side='left')
        help_mark(sf, tr("Source: your file. Input: the file with the changes to take over. Original: the untouched retail par as reference. Compare, tick rows, Merge."), 'compare', self, panel=True)
        ttk.Button(sf, text="Load...", command=self._cmp_load_source,
                   style='Small.TButton').pack(side='left', padx=(0, 8))
        self.cmp_source_label = tk.Label(sf, text="(none)", bg=self.BG3,
                                          fg=self.FG, font=('Consolas', 9), anchor='w')
        self.cmp_source_label.pack(side='left', fill='x', expand=True)

        # Input
        inf = tk.Frame(loader_frame, bg=self.BG3)
        inf.pack(fill='x', pady=(0, 4))
        tk.Label(inf, text="Input PAR:", bg=self.BG3, fg=self.YELLOW,
                 font=('Segoe UI', 10, 'bold'), width=14, anchor='w').pack(side='left')
        ttk.Button(inf, text="Load...", command=self._cmp_load_input,
                   style='Small.TButton').pack(side='left', padx=(0, 8))
        self.cmp_input_label = tk.Label(inf, text="(none)", bg=self.BG3,
                                         fg=self.FG, font=('Consolas', 9), anchor='w')
        self.cmp_input_label.pack(side='left', fill='x', expand=True)

        # Original (optional)
        of = tk.Frame(loader_frame, bg=self.BG3)
        of.pack(fill='x')
        tk.Label(of, text="Original PAR:", bg=self.BG3, fg=theme.MUT,
                 font=('Segoe UI', 10), width=14, anchor='w').pack(side='left')
        ttk.Button(of, text="Load...", command=self._cmp_set_original,
                   style='Small.TButton').pack(side='left', padx=(0, 4))
        ttk.Button(of, text="Clear", command=self._cmp_clear_original,
                   style='Small.TButton').pack(side='left', padx=(0, 8))
        self.cmp_original_label = tk.Label(of, text=self._cmp_original_path or "(optional — unmodified TwoWorlds.par)",
                                            bg=self.BG3, fg=theme.MUT,
                                            font=('Consolas', 9), anchor='w')
        self.cmp_original_label.pack(side='left', fill='x', expand=True)

        # ── Compare button + filter bar ──
        action_frame = tk.Frame(cmp_tab, bg=self.BG, padx=8, pady=6)
        action_frame.pack(fill='x')

        ttk.Button(action_frame, text="\u25B6 Compare",
                   command=self._cmp_run_compare,
                   style='Accent.TButton').pack(side='left', padx=(0, 16))

        # Filter toggles
        self.cmp_show_changed = tk.BooleanVar(value=True)
        self.cmp_show_input_only = tk.BooleanVar(value=True)
        self.cmp_show_source_only = tk.BooleanVar(value=True)

        self.cmp_filter_changed = tk.Checkbutton(
            action_frame, text="\u25CF Changed (0)", bg=self.BG, fg=self.YELLOW,
            selectcolor=self.BG2, activebackground=self.BG, activeforeground=self.YELLOW,
            variable=self.cmp_show_changed, command=self._cmp_apply_filter,
            font=('Segoe UI', 9, 'bold'))
        self.cmp_filter_changed.pack(side='left', padx=(0, 12))

        self.cmp_filter_input = tk.Checkbutton(
            action_frame, text="\u25CF Input only (0)", bg=self.BG, fg=self.GREEN,
            selectcolor=self.BG2, activebackground=self.BG, activeforeground=self.GREEN,
            variable=self.cmp_show_input_only, command=self._cmp_apply_filter,
            font=('Segoe UI', 9, 'bold'))
        self.cmp_filter_input.pack(side='left', padx=(0, 12))

        self.cmp_filter_source = tk.Checkbutton(
            action_frame, text="\u25CF Source only (0)", bg=self.BG, fg=self.BLUE,
            selectcolor=self.BG2, activebackground=self.BG, activeforeground=self.BLUE,
            variable=self.cmp_show_source_only, command=self._cmp_apply_filter,
            font=('Segoe UI', 9, 'bold'))
        self.cmp_filter_source.pack(side='left', padx=(0, 12))

        # Select all / none
        ttk.Button(action_frame, text="Select All",
                   command=self._cmp_select_all,
                   style='Small.TButton').pack(side='right', padx=(4, 0))
        ttk.Button(action_frame, text="Deselect All",
                   command=self._cmp_deselect_all,
                   style='Small.TButton').pack(side='right', padx=(4, 0))

        # ── Diff Treeview ──
        tree_frame = ttk.Frame(cmp_tab)
        tree_frame.pack(fill='both', expand=True, padx=4)

        cols = ('path', 'original', 'source', 'input', 'check')
        self.cmp_tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                                      selectmode='browse')
        self.cmp_tree.heading('path', text='Path (List \u2192 Entry \u2192 Field)')
        self.cmp_tree.heading('original', text='Original')
        self.cmp_tree.heading('source', text='Source')
        self.cmp_tree.heading('input', text='Input')
        self.cmp_tree.heading('check', text='\u2610')

        self.cmp_tree.column('path', width=380, minwidth=200)
        self.cmp_tree.column('original', width=150, minwidth=80)
        self.cmp_tree.column('source', width=150, minwidth=80)
        self.cmp_tree.column('input', width=150, minwidth=80)
        self.cmp_tree.column('check', width=40, minwidth=40, anchor='center')

        cmp_scroll = ttk.Scrollbar(tree_frame, orient='vertical',
                                    command=self.cmp_tree.yview)
        self.cmp_tree.configure(yscrollcommand=cmp_scroll.set)
        self.cmp_tree.pack(side='left', fill='both', expand=True)
        cmp_scroll.pack(side='right', fill='y')

        # Click on check column to toggle
        self.cmp_tree.bind('<ButtonRelease-1>', self._cmp_on_tree_click)

        # Tag colors
        self.cmp_tree.tag_configure('changed', foreground=self.YELLOW)
        self.cmp_tree.tag_configure('input_only', foreground=self.GREEN)
        self.cmp_tree.tag_configure('source_only', foreground=self.BLUE)
        self.cmp_tree.tag_configure('checked', background=theme.SEL)

        # ── Bottom: Merge actions ──
        merge_frame = tk.Frame(cmp_tab, bg=self.BG3, padx=8, pady=8)
        merge_frame.pack(fill='x', side='bottom')

        self.cmp_merge_info = tk.Label(merge_frame, text="Load Source and Input, then click Compare",
                                        bg=self.BG3, fg=self.FG, font=('Segoe UI', 9))
        self.cmp_merge_info.pack(side='left')

        ttk.Button(merge_frame, text="\u2913 Save Merged PAR...",
                   command=self._cmp_save,
                   style='Accent.TButton').pack(side='right', padx=(8, 0))
        ttk.Button(merge_frame, text="\u25B6 Merge Selected into Source",
                   command=self._cmp_merge,
                   style='Accent.TButton').pack(side='right')

    # ── Compare: File Loading ──

    def _cmp_load_par_file(self, title="Open PAR"):
        """Load and parse a PAR file, return ParFile or None."""
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("PAR Files", "*.par"), ("All Files", "*.*")])
        if not path:
            return None, ''
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            par_data, wrapper, was_compressed = decompress_par_file(raw)
            par = read_par(par_data)
            par.filepath = path
            par.wrapper_header = wrapper
            par.was_compressed = was_compressed
            self.field_labels.resolve(par)
            return par, path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PAR:\n{e}")
            return None, ''

    def _cmp_load_source(self):
        par, path = self._cmp_load_par_file("Open Source PAR")
        if par:
            self.cmp_source = par
            total = sum(len(pl.entries) for pl in par.lists)
            self.cmp_source_label.configure(
                text=f"{Path(path).name}  ({len(par.lists)} lists, {total} entries)")

    def _cmp_load_input(self):
        par, path = self._cmp_load_par_file("Open Input PAR")
        if par:
            self.cmp_input = par
            total = sum(len(pl.entries) for pl in par.lists)
            self.cmp_input_label.configure(
                text=f"{Path(path).name}  ({len(par.lists)} lists, {total} entries)")

    def _cmp_set_original(self):
        par, path = self._cmp_load_par_file("Set Original (unmodified) PAR")
        if par:
            self.cmp_original = par
            self._cmp_original_path = path
            self._save_cmp_config()
            self.cmp_original_label.configure(text=Path(path).name, fg=self.FG)

    def _cmp_clear_original(self):
        self.cmp_original = None
        self._cmp_original_path = ''
        self._save_cmp_config()
        self.cmp_original_label.configure(
            text="(optional — unmodified TwoWorlds.par)", fg=theme.MUT)

    def _cmp_load_original_from_config(self):
        """Auto-load original PAR from saved config path."""
        if self._cmp_original_path and os.path.isfile(self._cmp_original_path):
            try:
                with open(self._cmp_original_path, 'rb') as f:
                    raw = f.read()
                par_data, wrapper, was_compressed = decompress_par_file(raw)
                self.cmp_original = read_par(par_data)
                self.cmp_original.filepath = self._cmp_original_path
                self.cmp_original_label.configure(
                    text=Path(self._cmp_original_path).name, fg=self.FG)
            except:
                pass

    # ── Compare: Core Logic ──

    def _cmp_field_value_str(self, field):
        """Format a field value for display."""
        if field is None:
            return "—"
        v = field.value
        if isinstance(v, float):
            return f"{v:.4f}" if v != int(v) else f"{v:.1f}"
        if isinstance(v, list):
            if len(v) <= 4:
                return str(v)
            return f"[{len(v)} items]"
        return str(v)

    def _cmp_fields_equal(self, f1, f2):
        """Compare two ParFields for equality."""
        if f1.dtype != f2.dtype:
            return False
        if isinstance(f1.value, float) and isinstance(f2.value, float):
            return abs(f1.value - f2.value) < 1e-7
        return f1.value == f2.value

    def _cmp_run_compare(self):
        """Run the comparison between source and input."""
        if not self.cmp_source:
            messagebox.showwarning("Compare", "Load a Source PAR first.")
            return
        if not self.cmp_input:
            messagebox.showwarning("Compare", "Load an Input PAR first.")
            return

        # Auto-load original from config if not loaded yet
        if not self.cmp_original and self._cmp_original_path:
            self._cmp_load_original_from_config()

        self.cmp_diffs = []
        self.cmp_checks = {}

        src = self.cmp_source
        inp = self.cmp_input
        orig = self.cmp_original  # may be None

        # Match lists by index (PAR list structure is stable across mods)
        max_lists = max(len(src.lists), len(inp.lists))

        for li in range(max_lists):
            src_list = src.lists[li] if li < len(src.lists) else None
            inp_list = inp.lists[li] if li < len(inp.lists) else None
            orig_list = orig.lists[li] if (orig and li < len(orig.lists)) else None

            if src_list is None and inp_list is not None:
                # Entire list only in input
                for ei, entry in enumerate(inp_list.entries):
                    self.cmp_diffs.append({
                        'type': 'input_only',
                        'list_idx': li,
                        'entry_name': entry.name,
                        'field_idx': -1,
                        'field_label': '',
                        'source_val': '—',
                        'input_val': f'({len(entry.fields)} fields)',
                        'original_val': '—',
                        'inp_li': li, 'inp_ei': ei,
                        'src_li': -1, 'src_ei': -1,
                    })
                continue

            if inp_list is None and src_list is not None:
                # Entire list only in source
                for ei, entry in enumerate(src_list.entries):
                    self.cmp_diffs.append({
                        'type': 'source_only',
                        'list_idx': li,
                        'entry_name': entry.name,
                        'field_idx': -1,
                        'field_label': '',
                        'source_val': f'({len(entry.fields)} fields)',
                        'input_val': '—',
                        'original_val': '—',
                        'src_li': li, 'src_ei': ei,
                        'inp_li': -1, 'inp_ei': -1,
                    })
                continue

            # Both lists exist — match entries by name
            src_by_name = {}
            for ei, e in enumerate(src_list.entries):
                src_by_name[e.name] = (ei, e)

            inp_by_name = {}
            for ei, e in enumerate(inp_list.entries):
                inp_by_name[e.name] = (ei, e)

            orig_by_name = {}
            if orig_list:
                for ei, e in enumerate(orig_list.entries):
                    orig_by_name[e.name] = (ei, e)

            # Field count for SDK labels
            field_count = 0
            if src_list.entries:
                field_count = len(src_list.entries[0].fields)
            elif inp_list.entries:
                field_count = len(inp_list.entries[0].fields)

            # Entries in both — compare fields
            all_names = set(list(src_by_name.keys()) + list(inp_by_name.keys()))
            for name in sorted(all_names):
                in_src = name in src_by_name
                in_inp = name in inp_by_name

                if in_src and not in_inp:
                    sei, se = src_by_name[name]
                    self.cmp_diffs.append({
                        'type': 'source_only',
                        'list_idx': li,
                        'entry_name': name,
                        'field_idx': -1,
                        'field_label': '',
                        'source_val': f'({len(se.fields)} fields)',
                        'input_val': '—',
                        'original_val': '—',
                        'src_li': li, 'src_ei': sei,
                        'inp_li': -1, 'inp_ei': -1,
                    })
                    continue

                if in_inp and not in_src:
                    iei, ie = inp_by_name[name]
                    self.cmp_diffs.append({
                        'type': 'input_only',
                        'list_idx': li,
                        'entry_name': name,
                        'field_idx': -1,
                        'field_label': '',
                        'source_val': '—',
                        'input_val': f'({len(ie.fields)} fields)',
                        'original_val': '—',
                        'inp_li': li, 'inp_ei': iei,
                        'src_li': -1, 'src_ei': -1,
                    })
                    continue

                # Both exist — compare field by field
                sei, se = src_by_name[name]
                iei, ie = inp_by_name[name]
                _, oe = orig_by_name.get(name, (-1, None))

                max_fields = max(len(se.fields), len(ie.fields))
                for fi in range(max_fields):
                    sf = se.fields[fi] if fi < len(se.fields) else None
                    inf_f = ie.fields[fi] if fi < len(ie.fields) else None
                    of = None
                    if oe and fi < len(oe.fields):
                        of = oe.fields[fi]

                    # Skip if identical
                    if sf and inf_f and self._cmp_fields_equal(sf, inf_f):
                        continue

                    # Get field label (sheet of the source list)
                    label = self.field_labels.get(FieldLabels.sheet_of(src, li), fi) or ''

                    self.cmp_diffs.append({
                        'type': 'changed',
                        'list_idx': li,
                        'entry_name': name,
                        'field_idx': fi,
                        'field_label': label,
                        'source_val': self._cmp_field_value_str(sf),
                        'input_val': self._cmp_field_value_str(inf_f),
                        'original_val': self._cmp_field_value_str(of) if of else '—',
                        'src_li': li, 'src_ei': sei,
                        'inp_li': li, 'inp_ei': iei,
                    })

        # Initialize checkboxes (all unchecked)
        for i in range(len(self.cmp_diffs)):
            self.cmp_checks[i] = False

        # Update filter counts and populate tree
        self._cmp_update_counts()
        self._cmp_apply_filter()

        total = len(self.cmp_diffs)
        self.cmp_merge_info.configure(
            text=f"Found {total} differences. Select entries to merge, then click Merge.")
        self._set_status(f"Compare: {total} differences found")

    def _cmp_update_counts(self):
        """Update filter button labels with counts."""
        counts = {'changed': 0, 'input_only': 0, 'source_only': 0}
        for d in self.cmp_diffs:
            counts[d['type']] += 1
        self.cmp_filter_changed.configure(text=f"\u25CF Changed ({counts['changed']})")
        self.cmp_filter_input.configure(text=f"\u25CF Input only ({counts['input_only']})")
        self.cmp_filter_source.configure(text=f"\u25CF Source only ({counts['source_only']})")

    # ── Compare: Treeview Display ──

    def _cmp_apply_filter(self):
        """Populate the compare treeview based on active filters."""
        self.cmp_tree.delete(*self.cmp_tree.get_children())

        show = set()
        if self.cmp_show_changed.get():
            show.add('changed')
        if self.cmp_show_input_only.get():
            show.add('input_only')
        if self.cmp_show_source_only.get():
            show.add('source_only')

        for i, d in enumerate(self.cmp_diffs):
            if d['type'] not in show:
                continue

            # Build path string
            if d['field_idx'] >= 0:
                flabel = d['field_label'] or f"field_{d['field_idx']}"
                path = f"List[{d['list_idx']}] \u2192 {d['entry_name']} \u2192 [{d['field_idx']}] {flabel}"
            else:
                path = f"List[{d['list_idx']}] \u2192 {d['entry_name']}  (entire entry)"

            check_str = '\u2611' if self.cmp_checks.get(i, False) else '\u2610'

            tag = d['type']
            if self.cmp_checks.get(i, False):
                tag = (d['type'], 'checked')

            iid = f"D{i}"
            self.cmp_tree.insert('', 'end', iid=iid,
                                  values=(path, d['original_val'],
                                          d['source_val'], d['input_val'],
                                          check_str),
                                  tags=tag)

    def _cmp_on_tree_click(self, event):
        """Handle click on the check column to toggle checkbox."""
        region = self.cmp_tree.identify_region(event.x, event.y)
        col = self.cmp_tree.identify_column(event.x)
        item = self.cmp_tree.identify_row(event.y)

        if not item:
            return

        # col '#5' is the check column
        if col == '#5' or (region == 'cell' and col == '#5'):
            idx = int(item[1:])  # "D0" -> 0
            d = self.cmp_diffs[idx]

            # Don't allow checking source_only (nothing to merge)
            if d['type'] == 'source_only':
                return

            self.cmp_checks[idx] = not self.cmp_checks.get(idx, False)

            check_str = '\u2611' if self.cmp_checks[idx] else '\u2610'
            tag = d['type']
            if self.cmp_checks[idx]:
                tag = (d['type'], 'checked')
            self.cmp_tree.item(item, values=(
                self.cmp_tree.item(item)['values'][0],
                self.cmp_tree.item(item)['values'][1],
                self.cmp_tree.item(item)['values'][2],
                self.cmp_tree.item(item)['values'][3],
                check_str), tags=tag)

            # Update merge info
            selected = sum(1 for v in self.cmp_checks.values() if v)
            self.cmp_merge_info.configure(
                text=f"{selected} of {len(self.cmp_diffs)} selected for merge")

    def _cmp_select_all(self):
        """Select all visible (non-source-only) diffs."""
        for i, d in enumerate(self.cmp_diffs):
            if d['type'] != 'source_only':
                self.cmp_checks[i] = True
        self._cmp_apply_filter()
        selected = sum(1 for v in self.cmp_checks.values() if v)
        self.cmp_merge_info.configure(
            text=f"{selected} of {len(self.cmp_diffs)} selected for merge")

    def _cmp_deselect_all(self):
        """Deselect all diffs."""
        for i in self.cmp_checks:
            self.cmp_checks[i] = False
        self._cmp_apply_filter()
        self.cmp_merge_info.configure(
            text=f"0 of {len(self.cmp_diffs)} selected for merge")

    # ── Compare: Merge Logic ──

    def _cmp_merge(self):
        """Apply selected changes from input into source."""
        if not self.cmp_source or not self.cmp_input:
            messagebox.showwarning("Merge", "Load Source and Input first.")
            return

        selected = [(i, d) for i, d in enumerate(self.cmp_diffs)
                     if self.cmp_checks.get(i, False)]

        if not selected:
            messagebox.showinfo("Merge", "No entries selected. Click the checkboxes to select changes.")
            return

        # Confirm
        n_changes = sum(1 for _, d in selected if d['type'] == 'changed')
        n_new = sum(1 for _, d in selected if d['type'] == 'input_only')
        msg = f"Apply {len(selected)} changes to Source?\n"
        if n_changes:
            msg += f"  \u2022 {n_changes} field value(s) updated\n"
        if n_new:
            msg += f"  \u2022 {n_new} new entry/entries added\n"

        if not messagebox.askyesno("Confirm Merge", msg):
            return

        src = self.cmp_source
        inp = self.cmp_input

        # Apply changes
        added_count = 0
        changed_count = 0

        for _, d in selected:
            if d['type'] == 'changed':
                # Update field value in source
                sli, sei = d['src_li'], d['src_ei']
                ili, iei = d['inp_li'], d['inp_ei']
                fi = d['field_idx']

                if (sli >= 0 and sei >= 0 and sli < len(src.lists)
                        and sei < len(src.lists[sli].entries)):
                    src_entry = src.lists[sli].entries[sei]
                    if (ili >= 0 and iei >= 0 and ili < len(inp.lists)
                            and iei < len(inp.lists[ili].entries)):
                        inp_entry = inp.lists[ili].entries[iei]
                        if fi < len(inp_entry.fields):
                            # Ensure source has enough fields
                            while len(src_entry.fields) <= fi:
                                src_entry.fields.append(ParField(0, 0))
                            inp_f = inp_entry.fields[fi]
                            src_entry.fields[fi] = ParField(inp_f.dtype,
                                copy.deepcopy(inp_f.value) if isinstance(inp_f.value, list)
                                else inp_f.value)
                            changed_count += 1

            elif d['type'] == 'input_only':
                # Add entire entry from input to source
                ili, iei = d['inp_li'], d['inp_ei']
                if ili >= 0 and iei >= 0 and ili < len(inp.lists):
                    inp_entry = inp.lists[ili].entries[iei]

                    # Ensure source has enough lists
                    while len(src.lists) <= ili:
                        new_list = ParList()
                        src.lists.append(new_list)

                    # Deep copy entry
                    new_entry = ParEntry()
                    new_entry.name = inp_entry.name
                    new_entry.unknown_byte = inp_entry.unknown_byte
                    new_entry.unknown_u16a = inp_entry.unknown_u16a
                    new_entry.unknown_u16b = inp_entry.unknown_u16b
                    for f in inp_entry.fields:
                        nf = ParField(f.dtype,
                            copy.deepcopy(f.value) if isinstance(f.value, list)
                            else f.value)
                        new_entry.fields.append(nf)

                    # Check if name already exists
                    exists = any(e.name == new_entry.name
                                 for e in src.lists[ili].entries)
                    if not exists:
                        src.lists[ili].entries.append(new_entry)
                        added_count += 1

        self.cmp_merge_info.configure(
            text=f"Merged: {changed_count} fields updated, {added_count} entries added. Save to write to disk.")
        self._set_status(f"Merge complete — {changed_count} changed, {added_count} added")

    def _cmp_save(self):
        """Save the merged source PAR to file."""
        if not self.cmp_source:
            messagebox.showwarning("Save", "No Source PAR loaded.")
            return

        path = filedialog.asksaveasfilename(
            title="Save Merged PAR",
            defaultextension=".par",
            filetypes=[("PAR Files", "*.par"), ("All Files", "*.*")],
            initialfile="TwoWorlds_merged.par")
        if not path:
            return

        try:
            par_data = write_par(self.cmp_source)
            if self.cmp_source.was_compressed:
                output = compress_par_file(par_data, self.cmp_source.wrapper_header)
            else:
                output = par_data
            with open(path, 'wb') as f:
                f.write(output)

            total = sum(len(pl.entries) for pl in self.cmp_source.lists)
            self.cmp_merge_info.configure(
                text=f"Saved to {Path(path).name} ({len(self.cmp_source.lists)} lists, {total} entries)")
            self._set_status(f"Saved merged PAR to {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    # ── Helpers ──

    @property
    def current_entry(self):
        return self._current_entry

    @current_entry.setter
    def current_entry(self, val):
        self._current_entry = val

    _current_entry = None
    current_li = -1
    current_ei = -1
    edit_widgets = []


# ═══════════════════════════════════════════════════════════════════════════════
# CLI MODE
# ═══════════════════════════════════════════════════════════════════════════════

def cli_info(path):
    """Print info about a PAR file."""
    with open(path, 'rb') as f:
        raw_data = f.read()

    par_data, wrapper, was_compressed = decompress_par_file(raw_data)
    par = read_par(par_data)
    total = sum(len(pl.entries) for pl in par.lists)
    print(f"PAR File: {path}")
    if was_compressed:
        print(f"Compressed: zlib ({len(raw_data)} → {len(par_data)} bytes)")
        if wrapper:
            print(f"Wrapper:  {wrapper!r}")
    print(f"Version:  0x{par.version:X}")
    print(f"Lists:    {len(par.lists)}")
    print(f"Entries:  {total}")
    print()

    for li, pl in enumerate(par.lists):
        print(f"  List {li}: {len(pl.entries)} entries "
              f"(unk1=0x{pl.unknown1:X}, unk2=0x{pl.unknown2:X})")
        for ei, entry in enumerate(pl.entries):
            fields_str = ", ".join(
                TYPE_NAMES.get(f.dtype, '?') for f in entry.fields)
            print(f"    [{ei}] {entry.name}  ({fields_str})")


def cli_export(par_path, json_path):
    """Export PAR to JSON."""
    with open(par_path, 'rb') as f:
        raw_data = f.read()
    par_data, wrapper, was_compressed = decompress_par_file(raw_data)
    par = read_par(par_data)
    export_json(par, json_path)
    total = sum(len(pl.entries) for pl in par.lists)
    print(f"Exported {len(par.lists)} lists, {total} entries to {json_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateWindow:
    """A newer release exists: notes, update now, later, skip (design 9)."""

    def __init__(self, app, info):
        self.app = app
        self.info = info
        self.win = tk.Toplevel(app.root)
        self.win.title(tr("Update"))
        self.win.transient(app.root)
        self.win.geometry('620x480')
        theme.dark_titlebar(self.win)
        self.win.bind('<Escape>', lambda e: self.win.destroy())
        f = ttk.Frame(self.win, padding=16)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=tr("Version {version} is out").format(version=info['version']),
                  style='Brand.TLabel').pack(anchor='w')
        ttk.Label(f, text=tr("You have {current}. The update downloads the exe from GitHub, checks its SHA-256 checksum, closes the tool and starts version {version}. The old exe stays as .old until the next start.").format(current=VERSION, version=info['version']),
                  style='Muted.TLabel', wraplength=580, justify='left').pack(anchor='w', pady=(2, 8))
        txt = tk.Text(f, wrap='word', font=theme.FONT, height=12)
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', info['notes'].split('\n---')[0].strip() or info['page'])
        txt.configure(state='disabled')
        self.status = ttk.Label(f, text='', style='Muted.TLabel', wraplength=580, justify='left')
        self.status.pack(anchor='w', pady=(8, 0))
        self.bar = ttk.Progressbar(f, maximum=100)
        btns = ttk.Frame(f)
        btns.pack(fill='x', side='bottom', pady=(10, 0))
        ttk.Button(btns, text=tr("Later"), command=self.win.destroy).pack(side='right')
        ttk.Button(btns, text=tr("Skip this version"), command=self.skip).pack(side='right', padx=6)
        self.exe = updater.frozen_exe()
        self.go = ttk.Button(btns, text=tr("Update now") if self.exe else tr("Open release page"),
                             style='Accent.TButton', command=self.start)
        self.go.pack(side='right')
        ttk.Button(btns, text=tr("View on GitHub"), command=lambda: webbrowser.open(info['page'])).pack(side='left')
        if self.exe and not info.get('sha256'):
            self.status.configure(text=tr("This release has no checksum. Without one the tool installs nothing; Update now opens the release page."))

    def skip(self):
        self.app.cfg['update_skip'] = self.info['tag']
        self.app.cfg.save()
        self.win.destroy()

    def start(self):
        if not self.exe or not self.info.get('sha256') or not self.info.get('url'):
            webbrowser.open(self.info['page'])
            if not self.exe:
                self.win.destroy()
            return
        if not self.app._confirm_discard():
            return
        self.go.state(['disabled'])
        self.bar.pack(fill='x', pady=(6, 0), before=self.status)
        self.status.configure(text=tr("Downloading ..."))
        new = self.exe + '.new'
        state = {}

        def progress(done, total):
            state['p'] = (done, total)

        def work():
            try:
                updater.download(self.info, new, progress)
                state['ok'] = True
            except Exception as e:       # shown in the window
                state['err'] = e
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                if not self.win.winfo_exists():
                    return
            except tk.TclError:
                return
            done, total = state.get('p', (0, 0))
            if total:
                self.bar.configure(value=100 * done / total)
                self.status.configure(text=tr("Downloading {done} of {total} MB ...").format(
                    done=done // 1048576, total=max(1, total // 1048576)))
            if 'err' in state:
                self.go.state(['!disabled'])
                self.status.configure(text=tr("Update failed, nothing was changed: {err}").format(err=state['err']))
                return
            if not state.get('ok'):
                self.win.after(150, poll)
                return
            self.status.configure(text=tr("Checksum matches. The tool closes and starts the new version."))
            try:
                updater.start_swap(self.exe, new)
            except OSError as e:
                self.status.configure(text=tr("Update failed, nothing was changed: {err}").format(err=e))
                self.go.state(['!disabled'])
                return
            self.win.after(600, self._close_app)
        poll()

    def _close_app(self):
        app = self.app
        try:
            app.cfg['window'] = app.root.geometry()
            app.cfg.save()
        finally:
            app.root.destroy()


def run_gui(path=None):
    """Window loop; the DE/EN toggle destroys and rebuilds the window and
    hands the open file, selection, tab and geometry over."""
    carry = {'path': path} if path else None
    while True:
        root = tk.Tk()
        app = ParEditorApp(root, carry)
        root.mainloop()
        if not app.restart:
            break
        carry = getattr(app, 'carry_out', None) or {}

# ------------------------------------------------------------------ Deutsch --

DE = {
    'Category:': 'Gruppe:', 'All': 'Alle', 'Player': 'Spieler', 'NPCs': 'NPCs', 'Enemies': 'Gegner',
    'Animals & Mounts': 'Tiere & Reittiere', 'Weapons & Missiles': 'Waffen & Geschosse',
    'Armour & Equipment': 'Ruestung & Ausruestung', 'Magic & Effects': 'Magie & Effekte',
    'Potions & Items': 'Traenke & Gegenstaende', 'Objects & Buildings': 'Objekte & Gebaeude',
    'Traps': 'Fallen', 'Sounds & Voices': 'Klaenge & Stimmen', 'Meshes & Animations': 'Modelle & Animationen',
    'Game Parameters': 'Spielparameter', 'Other': 'Sonstiges', '{n} entries': '{n} Eintraege',
    'Show only one group: player, NPCs, enemies, weapons, game parameters ... The tree is grouped the same way.':
        'Nur eine Gruppe zeigen: Spieler, NPCs, Gegner, Waffen, Spielparameter ... Der Baum ist genauso gruppiert.',
    'Guide': 'Guide', 'Start tour': 'Rundgang starten', 'Check for updates': 'Nach Updates suchen',
    'Check for updates on start': 'Beim Start nach Updates suchen', 'Latest version on GitHub': 'Neueste Version auf GitHub',
    'Restore backup...': 'Sicherung wiederherstellen...', 'Restore backup': 'Sicherung wiederherstellen',
    'Open a .par first - backups sit next to it.': 'Erst eine .par oeffnen - die Sicherungen liegen daneben.',
    'No _backup folder next to this file yet.': 'Neben dieser Datei gibt es noch keinen Ordner _backup.',
    'Loaded {b} - Save (Ctrl+S) writes it back to {f}': '{b} geladen - Speichern (Strg+S) schreibt sie zurueck nach {f}',
    'Undo': 'Rueckgaengig', 'Redo': 'Wiederholen', 'undo': 'rueckgaengig', 'redo': 'wiederholen',
    'Nothing to {word}': 'Nichts zum {word}', 'edit {name}': '{name} bearbeiten', 'duplicate {name}': '{name} duplizieren',
    'rename {name}': '{name} umbenennen', 'delete {name}': '{name} loeschen', 'add {name}': '{name} anlegen',
    'Save changes first?': 'Aenderungen vorher speichern?', 'unsaved changes': 'ungespeichert',
    'Select an entry': 'Eintrag waehlen', 'Invalid value kept OLD value: ': 'Ungueltiger Wert, ALTER Wert bleibt: ',
    'not a whole number (0x.. is fine)': 'keine ganze Zahl (0x.. geht auch)', 'not a number': 'keine Zahl',
    'wolf, traps, units wolf ...': 'wolf, traps, units wolf ...',
    'Open the TwoWorlds.par from WDFiles\\Update16.wd - the one the game runs.':
        'Oeffne die TwoWorlds.par aus WDFiles\\Update16.wd - die, die das Spiel benutzt.',
    'One group of the par: player, NPCs, enemies, weapons ... The tree is grouped the same way. Click for the guide.':
        'Eine Gruppe der Par: Spieler, NPCs, Gegner, Waffen ... Der Baum ist genauso gruppiert. Klick oeffnet den Guide.',
    'Type to keep only matching entries: name, sheet or text field. Several words must all match. Click for the guide.':
        'Tippen laesst nur passende Eintraege stehen: Name, Blatt oder Textfeld. Mehrere Woerter muessen alle passen. Klick oeffnet den Guide.',
    'Groups, below them the SDK sheets, below those the entries. Right-click an entry to duplicate, rename or delete it.':
        'Gruppen, darunter die SDK-Blaetter, darunter die Eintraege. Rechtsklick auf einen Eintrag dupliziert, benennt um oder loescht.',
    'Every field with its SDK name; hover a name for the description. Red border = not a valid value, the old one is kept.':
        'Jedes Feld mit seinem SDK-Namen; ueber dem Namen schweben zeigt die Beschreibung. Roter Rand = kein gueltiger Wert, der alte bleibt.',
    'Source: your file. Input: the file with the changes to take over. Original: the untouched retail par as reference. Compare, tick rows, Merge.':
        'Source: deine Datei. Input: die Datei mit den Aenderungen. Original: die unveraenderte Retail-Par als Bezug. Compare, Zeilen anhaken, Merge.',
    'Update': 'Update', 'GitHub was not reachable: {err}': 'GitHub war nicht erreichbar: {err}',
    'You have the latest version ({version}).': 'Du hast die neueste Version ({version}).',
    'Update available: version {version}': 'Update verfuegbar: Version {version}',
    'Version {version} is out': 'Version {version} ist da',
    'You have {current}. The update downloads the exe from GitHub, checks its SHA-256 checksum, closes the tool and starts version {version}. The old exe stays as .old until the next start.':
        'Du hast {current}. Das Update laedt die Exe von GitHub, prueft ihre SHA-256-Pruefsumme, schliesst das Tool und startet Version {version}. Die alte Exe bleibt bis zum naechsten Start als .old liegen.',
    'Later': 'Spaeter', 'Skip this version': 'Diese Version ueberspringen', 'Update now': 'Jetzt aktualisieren',
    'Open release page': 'Release-Seite oeffnen', 'View on GitHub': 'Auf GitHub ansehen', 'Downloading ...': 'Lade ...',
    'Downloading {done} of {total} MB ...': 'Lade {done} von {total} MB ...',
    'Update failed, nothing was changed: {err}': 'Update fehlgeschlagen, nichts wurde geaendert: {err}',
    'Checksum matches. The tool closes and starts the new version.': 'Pruefsumme stimmt. Das Tool schliesst sich und startet die neue Version.',
    'This release has no checksum. Without one the tool installs nothing; Update now opens the release page.':
        'Dieses Release hat keine Pruefsumme. Ohne Pruefsumme installiert das Tool nichts; Jetzt aktualisieren oeffnet die Release-Seite.',
    'File': 'Datei', 'Edit': 'Bearbeiten', 'View': 'Ansicht', 'Compare': 'Vergleich', 'Help': 'Hilfe',
    'Open PAR...': 'PAR oeffnen...', 'Open JSON...': 'JSON oeffnen...', 'Save': 'Speichern',
    'Save As...': 'Speichern unter...', 'Export JSON...': 'JSON exportieren...', 'Exit': 'Beenden',
    'Duplicate entry...': 'Eintrag duplizieren...', 'Rename entry...': 'Eintrag umbenennen...',
    'Delete entry': 'Eintrag loeschen', 'Filter': 'Filter', 'Next match': 'Naechster Treffer',
    'Clear filter': 'Filter leeren', 'Editor': 'Editor', 'Compare & Merge': 'Vergleichen & Zusammenfuehren',
    'Language': 'Sprache', 'Open Compare Tab': 'Vergleichsreiter oeffnen',
    'Set Original PAR...': 'Original-PAR festlegen...', 'Start guide': 'Guide starten',
    'Documentation': 'Dokumentation', 'About': 'Ueber', 'Close': 'Schliessen',
    'Open': 'Oeffnen', 'Export JSON': 'JSON exportieren', 'Filter:': 'Filter:',
    'No file loaded': 'Keine Datei geladen', 'Lists & Entries': 'Listen & Eintraege',
    'Select an entry to view details': 'Eintrag waehlen, um die Felder zu sehen',
    'Unsaved Changes': 'Ungespeicherte Aenderungen',
    'Switching the language rebuilds the window. Discard unsaved changes?':
        'Der Sprachwechsel baut das Fenster neu auf. Ungespeicherte Aenderungen verwerfen?',
    "Type to filter the tree: entry name, sheet (Units, Weapon, Traps ...)\n"
    "or any text field such as the mesh path. Several words: all must match.\n"
    "Enter / F3 jumps to the next match, Esc clears, Ctrl+F focuses.":
        "Tippen filtert den Baum: Eintragsname, Blatt (Units, Weapon, Traps ...)\n"
        "oder ein Textfeld wie der Mesh-Pfad. Mehrere Woerter muessen alle passen.\n"
        "Enter / F3 springt zum naechsten Treffer, Esc leert, Strg+F fokussiert.",
    "Edits the .par parameter database of Two Worlds 1: every unit,\n"
    "weapon, spell, potion and object. Field names from the SDK sheets,\n"
    "byte-identical round trip, compare & merge between two files.":
        "Bearbeitet die .par-Parameterdatenbank von Two Worlds 1: jede Einheit,\n"
        "Waffe, Zauber, Trank und jedes Objekt. Feldnamen aus den SDK-Blaettern,\n"
        "byte-identischer Roundtrip, Vergleich und Zusammenfuehren zweier Dateien.",
    'Guide': 'Guide', "Don't show at startup": 'Beim Start nicht mehr anzeigen', 'Back': 'Zurueck',
    'Next': 'Weiter', 'Finish': 'Fertig', 'Quit guide': 'Guide beenden', 'Step {n} of {m}': 'Schritt {n} von {m}',
    'Welcome': 'Willkommen', 'Lists and sheets': 'Listen und Blaetter', 'Fields': 'Felder',
    'This editor opens the .par parameter database of Two Worlds 1 - every unit, weapon, spell, potion and object lives in it. Changes are written back byte-exact; the file on disk is backed up before it is overwritten.':
        'Dieser Editor oeffnet die .par-Parameterdatenbank von Two Worlds 1 - jede Einheit, Waffe, jeder Zauber, Trank und jedes Objekt steht darin. Aenderungen werden byte-genau zurueckgeschrieben; die Datei auf der Platte wird vorher gesichert.',
    'Open a TwoWorlds.par. The game runs the one from WDFiles\\Update16.wd - unpack that one, not Parameters.wd (old 1.0 layout, the editor warns about it).':
        'Oeffne eine TwoWorlds.par. Das Spiel benutzt die aus WDFiles\\Update16.wd - diese entpacken, nicht Parameters.wd (altes 1.0-Layout, der Editor warnt davor).',
    'The tree is grouped: Player, NPCs, Enemies, Weapons ... Below each group sit the SDK sheets (Units, Weapon, Traps) and their entries. The dropdown shows one group only. Right-click an entry to duplicate, rename or delete it.':
        'Der Baum ist gruppiert: Spieler, NPCs, Gegner, Waffen ... Unter jeder Gruppe liegen die SDK-Blaetter (Units, Weapon, Traps) mit ihren Eintraegen. Das Dropdown zeigt nur eine Gruppe. Rechtsklick auf einen Eintrag dupliziert, benennt um oder loescht.',
    'Groups and sheets': 'Gruppen und Blaetter',
    'Type to show only matching entries - by name, by sheet (traps, units) or by any text field such as the mesh path. Several words must all match: "units wolf". Enter jumps through the matches, Esc clears.':
        'Tippen zeigt nur passende Eintraege - nach Name, Blatt (traps, units) oder einem Textfeld wie dem Mesh-Pfad. Mehrere Woerter muessen alle passen: "units wolf". Enter springt durch die Treffer, Esc leert.',
    'Each field shows its SDK name; hover it for a description. A red border means the text is not a valid value - the old value is kept and Save refuses until it is fixed. Integers accept 0x hex.':
        'Jedes Feld zeigt seinen SDK-Namen; darueber schweben zeigt die Beschreibung. Roter Rand heisst: kein gueltiger Wert - der alte bleibt, und Speichern verweigert, bis es stimmt. Ganzzahlen nehmen auch 0x-Hex.',
    'Ctrl+S writes the file in place, the previous version goes to _backup next to it. Pack the result into a mod archive (Parameters\\TwoWorlds.par, flags 0x39) for the game.':
        'Strg+S schreibt die Datei an Ort und Stelle, die vorherige Fassung wandert nach _backup daneben. Fuer das Spiel das Ergebnis in ein Mod-Archiv packen (Parameters\\TwoWorlds.par, Flags 0x39).',
    "The second tab compares two .par files field by field and merges chosen changes - handy for bringing another mod's values into yours.":
        'Der zweite Reiter vergleicht zwei .par-Dateien Feld fuer Feld und fuehrt gewaehlte Aenderungen zusammen - praktisch, um die Werte einer anderen Mod in die eigene zu holen.',
}


def _check_translations():
    guidebook.check_sources()
    for k in list(DE):
        assert set(re.findall(r'\{\w+\}', k)) == set(re.findall(r'\{\w+\}', DE[k])), k
    for s in GUIDE_STEPS:
        assert s['text'] in DE and s['title'] in DE, s['title']


if __name__ == '__main__':
    _check_translations()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == '--info' and len(sys.argv) > 2:
            cli_info(sys.argv[2])
        elif cmd == '--export' and len(sys.argv) > 3:
            cli_export(sys.argv[2], sys.argv[3])
        elif cmd == '--help':
            print(f"TW1 PAR Editor v{VERSION}")
            print()
            print("GUI:   python tw1_par_editor.py")
            print("Info:  python tw1_par_editor.py --info file.par")
            print("Export: python tw1_par_editor.py --export file.par output.json")
        else:
            # Try to open as file in GUI
            if HAS_TK:
                run_gui(cmd if os.path.isfile(cmd) else None)
            else:
                print("Usage: python tw1_par_editor.py [--info|--export] file.par")
    else:
        if not HAS_TK:
            print("Usage: python tw1_par_editor.py [--info|--export|--help] file.par")
            print("       or run without args for GUI (requires tkinter)")
            sys.exit(1)
        run_gui()
