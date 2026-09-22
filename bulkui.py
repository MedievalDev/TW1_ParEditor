"""The windows of 1.7.0: bulk edit with presets, review before saving,
references. The logic is in bulktools.py; these only show it and ask."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import bulktools as B
import theme


def _tr(text):
    import tw1_par_editor as M
    return M.tr(text)


OP_LABELS = (('set', 'Set to'), ('add', 'Add'), ('mul', 'Change by %'), ('replace', 'Replace text (old=>new)'))


class BulkDialog:
    """Pick entries, a field and an operation; see every change before it is made."""

    def __init__(self, app, scope='selected', key=None, preset=None):
        from categories import category_of
        self.app, self.par, self.category_of = app, app.par, category_of
        self.changes, self.skipped = [], 0
        tr = _tr
        self.win = win = tk.Toplevel(app.root)
        win.title(tr('Bulk edit'))
        win.transient(app.root)
        win.geometry('980x660')
        win.minsize(820, 520)
        win.configure(background=theme.BG)
        theme.dark_titlebar(win)
        win.bind('<Escape>', lambda e: win.destroy())
        f = ttk.Frame(win, padding=14)
        f.pack(fill='both', expand=True)

        # scope
        self.scopes = self._scopes(key)
        ttk.Label(f, text=tr('Which entries'), style='H2.TLabel').pack(anchor='w')
        self.scope = tk.StringVar(value=scope if scope in self.scopes else next(iter(self.scopes), 'list'))
        box = ttk.Frame(f)
        box.pack(fill='x', pady=(4, 10))
        for sid, (text, tg, _key) in self.scopes.items():
            ttk.Radiobutton(box, text=f'{text}  ({len(tg)})', value=sid, variable=self.scope,
                            command=self._fill_fields).pack(anchor='w')

        # field + operation
        row = ttk.Frame(f)
        row.pack(fill='x')
        ttk.Label(row, text=tr('Field')).pack(side='left')
        self.field = tk.StringVar()
        self.field_box = ttk.Combobox(row, textvariable=self.field, width=46, state='readonly')
        self.field_box.pack(side='left', padx=(6, 14))
        self.field_box.bind('<<ComboboxSelected>>', lambda e: self._clear())
        ttk.Label(row, text=tr('Operation')).pack(side='left')
        self.op = tk.StringVar(value=tr(OP_LABELS[0][1]))
        ttk.Combobox(row, textvariable=self.op, values=[tr(t) for _k, t in OP_LABELS], width=24,
                     state='readonly').pack(side='left', padx=6)
        ttk.Label(row, text=tr('Value')).pack(side='left', padx=(8, 0))
        self.value = tk.StringVar()
        ent = ttk.Entry(row, textvariable=self.value, width=16)
        ent.pack(side='left', padx=6)
        ent.bind('<Return>', lambda e: self.preview())
        ttk.Button(row, text=tr('Preview'), command=self.preview).pack(side='left', padx=6)

        # presets
        pr = ttk.Frame(f)
        pr.pack(fill='x', pady=(10, 6))
        ttk.Label(pr, text=tr('Preset')).pack(side='left')
        self.preset = tk.StringVar()
        self.preset_box = ttk.Combobox(pr, textvariable=self.preset, width=30, state='readonly')
        self.preset_box.pack(side='left', padx=6)
        self.preset_box.bind('<<ComboboxSelected>>', lambda e: self.load_preset(self.preset.get()))
        ttk.Button(pr, text=tr('Save as preset...'), command=self.save_preset).pack(side='left', padx=4)
        ttk.Button(pr, text=tr('Delete preset'), command=self.delete_preset).pack(side='left', padx=4)
        self._fill_presets()

        # preview list
        self.info = ttk.Label(f, text=tr('Pick a field and an operation, then Preview.'), style='Muted.TLabel')
        self.info.pack(anchor='w', pady=(4, 4))
        lf = ttk.Frame(f)
        lf.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(lf, columns=('field', 'old', 'new'), show='tree headings')
        for c, t, w in (('#0', 'Entry', 260), ('field', 'Field', 200), ('old', 'Old', 180), ('new', 'New', 180)):
            self.tree.heading(c, text=tr(t))
            self.tree.column(c, width=w, anchor='w')
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)

        btns = ttk.Frame(f)
        btns.pack(fill='x', pady=(10, 0))
        ttk.Button(btns, text=tr('Close'), command=win.destroy).pack(side='right')
        self.apply_btn = ttk.Button(btns, text=tr('Apply'), style='Accent.TButton', command=self.apply)
        self.apply_btn.pack(side='right', padx=6)
        self.apply_btn.state(['disabled'])

        self._fill_fields()
        if preset:
            self.load_preset(preset)
        win.update_idletasks()
        win.geometry(f'+{app.root.winfo_rootx() + 60}+{app.root.winfo_rooty() + 50}')
        win.lift()
        win.focus_force()

    # -- scopes / fields ----------------------------------------------------------
    def _scopes(self, key):
        app, par, tr = self.app, self.par, _tr
        out = {}
        sel = app.selected_entries()
        if sel:
            out['selected'] = (tr('Selected entries'), B.targets(par, 'selected', selected=sel), None)
        li = app.current_li if getattr(app, 'current_li', None) is not None else None
        if isinstance(key, int):
            li = key
        if li is not None and li < len(par.lists):
            sheet = B.sheet_of(par, li) or f'List {li}'
            out['list'] = (tr('List') + f' {sheet}', B.targets(par, 'list', li), li)
        cat = key if isinstance(key, str) else None
        if cat is None and li is not None and li < len(par.lists):
            first = par.lists[li].entries[0].name if par.lists[li].entries else ''
            cat = self.category_of(B.sheet_of(par, li), first)
        if cat:
            out['category'] = (tr('Category') + f' {tr(cat)}',
                               B.targets(par, 'category', cat, category_of=self.category_of), cat)
        if app.search_results:
            out['results'] = (tr('Search results'), B.targets(par, 'results', results=app.search_results), None)
        return out

    def _targets(self):
        return self.scopes.get(self.scope.get(), ('', [], None))[1]

    def _fill_fields(self):
        self.choices = B.field_choices(self.par, self._targets(), self.app.field_labels)
        names = {0: 'int', 1: 'float', 2: 'uint', 3: 'text', 4: 'int[]', 5: 'float[]', 6: 'uint[]', 7: 'text[]'}
        self.field_box.configure(values=[f'{lab}   ({n}, {names.get(dt, "?")})' for lab, n, dt in self.choices])
        if self.choices and self.field.get().split('   (')[0] not in [c[0] for c in self.choices]:
            self.field_box.current(0)
        self._clear()

    def _label(self):
        return self.field.get().split('   (')[0]

    def _op(self):
        for k, t in OP_LABELS:
            if _tr(t) == self.op.get():
                return k
        return 'set'

    def _clear(self):
        self.tree.delete(*self.tree.get_children())
        self.changes = []
        try:
            self.apply_btn.state(['disabled'])
        except (tk.TclError, AttributeError):
            pass

    # -- preview / apply ---------------------------------------------------------
    def preview(self):
        tr = _tr
        self._clear()
        if not self.value.get().strip() and self._op() != 'set':
            self.info.configure(text=tr('Enter a value first.'), foreground=theme.ERR)
            return
        try:
            self.changes, self.skipped = B.plan_bulk(self.par, self._targets(), self.app.field_labels,
                                                     self._label(), self._op(), self.value.get())
        except (ValueError, TypeError) as e:
            self.info.configure(text=tr('That value does not fit the field: {e}').format(e=e), foreground=theme.ERR)
            return
        for c in self.changes[:2000]:
            self.tree.insert('', 'end', text=c.entry, values=(c.label, B.show(c.old), B.show(c.new)))
        text = tr('{n} changes').format(n=len(self.changes))
        if self.skipped:
            text += '  |  ' + tr('{k} entries have no such field and stay as they are').format(k=self.skipped)
        if len(self.changes) > 2000:
            text += '  |  ' + tr('the list shows the first 2000')
        self.info.configure(text=text, foreground=theme.GOLD if self.changes else theme.MUT)
        if self.changes:
            self.apply_btn.state(['!disabled'])

    def apply(self):
        if not self.changes:
            return
        app, tr = self.app, _tr
        app._apply_current_edits()
        app.push_undo(('all',), tr('Bulk edit'))
        n = B.apply_changes(self.par, self.changes)
        app.after_bulk(tr('Bulk edit: {n} fields changed ({field}). Undo with Ctrl+Z.').format(n=n, field=self._label()))
        self._clear()
        self.info.configure(text=tr('Done: {n} fields changed.').format(n=n), foreground=theme.OK)

    # -- presets -------------------------------------------------------------------
    def _presets(self):
        p = self.app.cfg.get('bulk_presets')
        return {k: v for k, v in (p.items() if isinstance(p, dict) else []) if B.check_preset(v)}

    def _fill_presets(self):
        self.preset_box.configure(values=sorted(self._presets()))

    def save_preset(self):
        tr = _tr
        name = simpledialog.askstring(tr('Save as preset'), tr('Name of the preset:'), parent=self.win)
        if not name:
            return
        sid = self.scope.get()
        key = self.scopes.get(sid, ('', [], None))[2]
        if sid == 'list':
            key = B.sheet_of(self.par, key)          # a sheet name survives reopening, a list number not
        presets = self._presets()
        presets[name.strip()] = B.make_preset(sid, key, self._label(), self._op(), self.value.get())
        self.app.cfg['bulk_presets'] = presets
        self.app.cfg.save()
        self._fill_presets()
        self.preset.set(name.strip())
        self.info.configure(text=tr('Preset saved.'), foreground=theme.OK)

    def load_preset(self, name):
        p = self._presets().get(name)
        if not p:
            return
        sid = p['scope']
        if sid == 'list' and p.get('key'):
            li = next((i for i in range(len(self.par.lists)) if B.sheet_of(self.par, i) == p['key']), None)
            if li is not None:
                self.scopes['list'] = (_tr('List') + f" {p['key']}", B.targets(self.par, 'list', li), li)
        if sid == 'category' and p.get('key'):
            self.scopes['category'] = (_tr('Category') + f" {_tr(p['key'])}",
                                       B.targets(self.par, 'category', p['key'], category_of=self.category_of), p['key'])
        if sid in self.scopes:
            self.scope.set(sid)
        self._fill_fields()
        for i, (lab, _n, _dt) in enumerate(self.choices):
            if lab == p['label']:
                self.field_box.current(i)
        for k, t in OP_LABELS:
            if k == p['op']:
                self.op.set(_tr(t))
        self.value.set(p.get('arg', ''))
        self.preset.set(name)
        self.preview()

    def delete_preset(self):
        name = self.preset.get()
        presets = self._presets()
        if name in presets and messagebox.askyesno(_tr('Delete preset'), _tr('Delete the preset {name}?').format(name=name),
                                                   parent=self.win):
            del presets[name]
            self.app.cfg['bulk_presets'] = presets
            self.app.cfg.save()
            self.preset.set('')
            self._fill_presets()


class ReviewDialog:
    """Every change since opening; untick what should not be saved."""

    def __init__(self, app, changes, saving=True, head=None, ok_text=None, note=None):
        tr = _tr
        self.app, self.changes = app, changes
        self.keep = {i: True for i, c in enumerate(changes) if c.kind == 'field'}
        self.result = None
        self.win = win = tk.Toplevel(app.root)
        win.title(tr('Review changes'))
        win.transient(app.root)
        win.geometry('1000x620')
        win.minsize(780, 460)
        win.configure(background=theme.BG)
        theme.dark_titlebar(win)
        win.protocol('WM_DELETE_WINDOW', self.cancel)
        win.bind('<Escape>', lambda e: self.cancel())
        f = ttk.Frame(win, padding=14)
        f.pack(fill='both', expand=True)
        fields = sum(1 for c in changes if c.kind == 'field')
        entries = sum(1 for c in changes if c.kind != 'field')
        head = head or tr('{n} fields changed since the file was opened.').format(n=fields)
        if entries:
            head += ' ' + tr('{k} entries added or removed (undo those with Ctrl+Z).').format(k=entries)
        ttk.Label(f, text=head, style='H2.TLabel', wraplength=940, justify='left').pack(anchor='w')
        ttk.Label(f, text=note or tr('Click a row (or press Space) to keep or drop it. Dropped changes get their old value back.'),
                  style='Muted.TLabel').pack(anchor='w', pady=(2, 8))
        lf = ttk.Frame(f)
        lf.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(lf, columns=('keep', 'field', 'old', 'new'), show='tree headings')
        for c, t, w in (('#0', 'Entry', 240), ('keep', 'Keep', 60), ('field', 'Field', 200),
                        ('old', 'Old', 190), ('new', 'New', 190)):
            self.tree.heading(c, text=tr(t))
            self.tree.column(c, width=w, anchor='w')
        self.tree.tag_configure('drop', foreground=theme.MUT)
        self.tree.tag_configure('entry', foreground=theme.GOLD)
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.rows = {}
        for i, c in enumerate(changes):
            if c.kind == 'field':
                iid = self.tree.insert('', 'end', text=c.entry, values=('✓', c.label, B.show(c.old), B.show(c.new)))
            else:
                iid = self.tree.insert('', 'end', text=c.entry,
                                       values=('', tr('entry added') if c.kind == 'added' else tr('entry removed'), '', ''),
                                       tags=('entry',))
            self.rows[iid] = i
        self.tree.bind('<ButtonRelease-1>', self._click)
        self.tree.bind('<space>', lambda e: self._toggle(self.tree.focus()))
        self.tree.bind('<Double-1>', self._jump)
        btns = ttk.Frame(f)
        btns.pack(fill='x', pady=(10, 0))
        ttk.Button(btns, text=tr('Keep all'), command=lambda: self._all(True)).pack(side='left')
        ttk.Button(btns, text=tr('Drop all'), command=lambda: self._all(False)).pack(side='left', padx=6)
        ttk.Button(btns, text=tr('Back') if saving else tr('Close'), command=self.cancel).pack(side='right')
        ttk.Button(btns, text=ok_text or (tr('Save') if saving else tr('Drop the unticked')), style='Accent.TButton',
                   command=self.ok).pack(side='right', padx=6)
        win.update_idletasks()
        win.geometry(f'+{app.root.winfo_rootx() + 60}+{app.root.winfo_rooty() + 50}')
        win.lift()
        win.focus_force()

    def _click(self, ev):
        if self.tree.identify_column(ev.x) in ('#1', '#0'):
            self._toggle(self.tree.identify_row(ev.y))

    def _toggle(self, iid):
        i = self.rows.get(iid)
        if i is None or i not in self.keep:
            return
        self.keep[i] = not self.keep[i]
        self.tree.set(iid, 'keep', '✓' if self.keep[i] else '')
        self.tree.item(iid, tags=() if self.keep[i] else ('drop',))

    def _all(self, on):
        for iid, i in self.rows.items():
            if i in self.keep and self.keep[i] != on:
                self._toggle(iid)

    def _jump(self, ev):
        i = self.rows.get(self.tree.identify_row(ev.y))
        if i is not None:
            c = self.changes[i]
            self.app.jump_to(c.li, c.ei)

    def dropped(self):
        return [self.changes[i] for i, k in self.keep.items() if not k]

    def ok(self):
        self.result = self.dropped()
        self.win.destroy()

    def cancel(self):
        self.result = None
        self.win.destroy()


class ReferencesWindow:
    """A list of places in the par; double click jumps there."""

    def __init__(self, app, title, rows, columns=('Entry', 'Field', 'Value')):
        tr = _tr
        self.app, self.rows = app, rows
        self.win = win = tk.Toplevel(app.root)
        win.title(title)
        win.transient(app.root)
        win.geometry('860x520')
        win.configure(background=theme.BG)
        theme.dark_titlebar(win)
        win.bind('<Escape>', lambda e: win.destroy())
        f = ttk.Frame(win, padding=12)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=title, style='H2.TLabel').pack(anchor='w')
        ttk.Label(f, text=tr('{n} places. Double click jumps there.').format(n=len(rows)) if rows
                  else tr('Nothing found.'), style='Muted.TLabel').pack(anchor='w', pady=(2, 8))
        lf = ttk.Frame(f)
        lf.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(lf, columns=('sheet', 'field', 'value'), show='tree headings')
        for c, t, w in (('#0', 'Entry', 240), ('sheet', 'List', 180), ('field', 'Field', 170), ('value', 'Value', 240)):
            self.tree.heading(c, text=tr(t))
            self.tree.column(c, width=w, anchor='w')
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.map = {}
        for r in rows[:5000]:
            li, ei, fi, name, lab, value = r
            iid = self.tree.insert('', 'end', text=name, values=(B.sheet_of(app.par, li) or f'List {li}', lab, B.show(value)))
            self.map[iid] = (li, ei)
        self.tree.bind('<Double-1>', self._jump)
        self.tree.bind('<Return>', self._jump)
        ttk.Button(f, text=tr('Close'), command=win.destroy).pack(anchor='e', pady=(10, 0))
        win.update_idletasks()
        win.geometry(f'+{app.root.winfo_rootx() + 80}+{app.root.winfo_rooty() + 70}')
        win.lift()
        win.focus_force()

    def _jump(self, ev=None):
        t = self.map.get(self.tree.focus())
        if t:
            self.app.jump_to(*t)
