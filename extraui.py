"""Windows of 1.8.0: the jump box (Ctrl+P). The logic is in worktools.py."""

import tkinter as tk
from tkinter import ttk

import theme
import worktools as W


def _tr(text):
    import tw1_par_editor as M
    return M.tr(text)


class QuickJump:
    """Type part of a name, Enter jumps to the entry. Up/Down pick, Esc closes."""

    def __init__(self, app):
        tr = _tr
        self.app, self.hits = app, []
        self.win = win = tk.Toplevel(app.root)
        win.title(tr('Jump to entry'))
        win.transient(app.root)
        win.geometry('620x420')
        win.configure(background=theme.BG)
        theme.dark_titlebar(win)
        win.bind('<Escape>', lambda e: win.destroy())
        f = ttk.Frame(win, padding=12)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=tr('Type part of an entry name - Enter jumps there. Several words: all must match.'),
                  style='Muted.TLabel').pack(anchor='w', pady=(0, 6))
        self.var = tk.StringVar()
        self.entry = ttk.Entry(f, textvariable=self.var, font=('Consolas', 11))
        self.entry.pack(fill='x')
        lf = ttk.Frame(f)
        lf.pack(fill='both', expand=True, pady=(8, 0))
        self.box = tk.Listbox(lf, bg=theme.FIELD, fg=theme.INK, selectbackground=theme.SEL,
                              selectforeground=theme.GOLD_HI, font=('Consolas', 10), relief='flat',
                              highlightthickness=0, activestyle='none')
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.box.yview)
        self.box.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.box.pack(fill='both', expand=True)
        self.count = ttk.Label(f, text='', style='Muted.TLabel')
        self.count.pack(anchor='w', pady=(6, 0))
        self.var.trace_add('write', lambda *a: self._fill())
        for w in (self.entry, self.box):
            w.bind('<Return>', lambda e: self.go())
            w.bind('<Down>', lambda e: self._move(1))
            w.bind('<Up>', lambda e: self._move(-1))
        self.box.bind('<Double-1>', lambda e: self.go())
        win.update_idletasks()
        win.geometry(f'+{app.root.winfo_rootx() + 220}+{app.root.winfo_rooty() + 90}')
        win.lift()
        win.focus_force()
        self.entry.focus_set()

    def _fill(self):
        self.hits = W.quick_matches(self.app.par, self.var.get(), limit=200)
        self.box.delete(0, 'end')
        for li, ei, name, sheet in self.hits:
            self.box.insert('end', f'{name:<34} {sheet}')
        if self.hits:
            self.box.selection_set(0)
            self.box.activate(0)
        self.count.configure(text=_tr('{n} entries').format(n=len(self.hits)) if self.var.get().strip() else '')

    def _move(self, d):
        if not self.hits:
            return 'break'
        cur = self.box.curselection()
        i = max(0, min(len(self.hits) - 1, (cur[0] if cur else -1) + d))
        self.box.selection_clear(0, 'end')
        self.box.selection_set(i)
        self.box.activate(i)
        self.box.see(i)
        return 'break'

    def go(self):
        cur = self.box.curselection()
        if not self.hits:
            return
        li, ei, _n, _s = self.hits[cur[0] if cur else 0]
        self.win.destroy()
        self.app.jump_to(li, ei)
