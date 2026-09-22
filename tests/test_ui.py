"""The editor window driven like a user: a real WM_DROPFILES opens the par,
bulk edit with a preset, the review before saving drops one change, the
references windows, the error dialog. Settings live in a temp folder,
nothing is sent, the window is never topmost."""
import copy
import ctypes
import os
import shutil
import sys
import tempfile
import time
import unittest
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import tkinter as tk  # noqa: E402
import bulktools as B  # noqa: E402
import bulkui  # noqa: E402
import foxfeedback  # noqa: E402
import foxfeedback_ui  # noqa: E402
import tw1_par_editor as M  # noqa: E402

GAME = r'F:\SteamLibrary\steamapps\common\Two Worlds - Epic Edition\WDFiles\Update16.wd'
WM_DROPFILES = 0x0233
_k32, _u32 = ctypes.windll.kernel32, ctypes.windll.user32
_k32.GlobalAlloc.restype = wintypes.HGLOBAL
_k32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
_k32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
_u32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


def explorer_drop(hwnd, paths):
    names = (chr(0).join(paths) + chr(0) + chr(0)).encode('utf-16-le')
    head = (20).to_bytes(4, 'little') + bytes(8) + bytes(4) + (1).to_bytes(4, 'little')
    h = _k32.GlobalAlloc(0x0042, len(head) + len(names))
    p = _k32.GlobalLock(h)
    ctypes.memmove(p, head + names, len(head) + len(names))
    _k32.GlobalUnlock(h)
    _u32.SendMessageW(hwnd, WM_DROPFILES, h, 0)


@unittest.skipUnless(os.path.isfile(GAME), 'game not on this PC')
class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='par_ui_')
        cls._orig = (M.data_dir, foxfeedback.submit, foxfeedback_ui.FeedbackUI.start, M.ErrorDialog,
                     M.messagebox.askyesnocancel, bulkui.simpledialog.askstring, bulkui.messagebox.askyesno)
        M.data_dir = lambda: cls.tmp
        cls.errors = []
        foxfeedback.submit = lambda *a, **k: (_ for _ in ()).throw(AssertionError('nothing is sent'))
        foxfeedback_ui.FeedbackUI.start = lambda self: None
        M.ErrorDialog = lambda app, key, message, shown, guide=None, title=None: cls.errors.append(key)
        M.messagebox.askyesnocancel = lambda *a, **k: False          # "save first?" -> no
        bulkui.messagebox.askyesno = lambda *a, **k: True
        cfg = M.Config()
        cfg.update(guide_seen=True, update_check=False, lang='en')
        cfg.save()
        cls.root = tk.Tk()
        cls.app = M.ParEditorApp(cls.root)
        cls.root.geometry('1200x750+40+40')
        cls.root.lower()
        cls.pump(0.6)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass
        (M.data_dir, foxfeedback.submit, foxfeedback_ui.FeedbackUI.start, M.ErrorDialog,
         M.messagebox.askyesnocancel, bulkui.simpledialog.askstring, bulkui.messagebox.askyesno) = cls._orig
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def pump(cls, secs=0.2):
        end = time.time() + secs
        while time.time() < end:
            cls.root.update()
            time.sleep(0.01)

    def setUp(self):
        self.errors.clear()
        if self.app.par is None or self.app.modified:
            self.app.modified = False
            self.app._load_par(GAME)
            self.pump()

    def test_1_drop_opens_the_archive(self):
        self.app.par = None
        explorer_drop(self.root.winfo_id(), [GAME])
        end = time.time() + 30
        while self.app.par is None and time.time() < end:
            self.pump(0.1)
        self.assertIsNotNone(self.app.par)
        self.assertTrue(self.app.filepath.endswith('Update16.wd'))

    def test_2_bulk_edit_category_and_undo(self):
        dlg = self.app.bulk_edit('category', 'Enemies')
        self.pump()
        labels = [c[0] for c in dlg.choices]
        dlg.field_box.current(labels.index('maxHP'))
        dlg.op.set(M.tr('Change by %'))
        dlg.value.set('20')
        dlg.preview()
        n = len(dlg.changes)
        self.assertGreater(n, 50)
        first = dlg.changes[0]
        dlg.apply()
        self.pump()
        entry = self.app.par.lists[first.li].entries[first.ei]
        self.assertEqual(entry.fields[first.fi].value, first.new)
        self.assertTrue(self.app.modified)
        self.app.do_undo()
        self.pump()
        self.assertEqual(self.app.par.lists[first.li].entries[first.ei].fields[first.fi].value, first.old)
        dlg.win.destroy()

    def test_3_preset_roundtrip(self):
        dlg = self.app.bulk_edit('category', 'Enemies')
        labels = [c[0] for c in dlg.choices]
        dlg.field_box.current(labels.index('maxHP'))
        dlg.op.set(M.tr('Add'))
        dlg.value.set('5')
        bulkui.simpledialog.askstring = lambda *a, **k: 'Tougher enemies'
        dlg.save_preset()
        dlg.win.destroy()
        self.assertIn('Tougher enemies', self.app.cfg['bulk_presets'])
        dlg2 = self.app.bulk_edit(preset='Tougher enemies')
        self.pump()
        self.assertEqual(dlg2._label(), 'maxHP')
        self.assertEqual(dlg2._op(), 'add')
        self.assertGreater(len(dlg2.changes), 50, 'a preset shows its preview at once')
        dlg2.delete_preset()
        self.assertNotIn('Tougher enemies', self.app.cfg.get('bulk_presets', {}))
        dlg2.win.destroy()

    def test_4_review_drops_one_change_on_save(self):
        par = self.app.par
        tg = B.targets(par, 'category', 'Enemies', category_of=M.category_of)
        changes, _ = B.plan_bulk(par, tg, self.app.field_labels, 'maxHP', 'add', '11')
        B.apply_changes(par, changes[:3])
        self.app.modified = True
        real = bulkui.ReviewDialog

        class Drop:
            def __init__(dlg, app, found, saving=True):
                dlg.win = tk.Toplevel(app.root)
                dlg.seen = len(found)
                dlg.result = [c for c in found if c.kind == 'field'][:1]    # drop the first
                dlg.win.after(10, dlg.win.destroy)
        bulkui.ReviewDialog = Drop
        out = os.path.join(self.tmp, 'Test.par')
        try:
            self.app._do_save(out)
        finally:
            bulkui.ReviewDialog = real
        data, *_ = M.read_par_source(out)
        back = M.read_par(data)
        vals = [back.lists[c.li].entries[c.ei].fields[c.fi].value for c in changes[:3]]
        self.assertEqual(vals[0], changes[0].old, 'the dropped change kept its old value')
        self.assertEqual(vals[1:], [c.new for c in changes[1:3]], 'the rest was saved')
        self.assertFalse(self.app.modified)

    def test_5_references_and_field_everywhere(self):
        par = self.app.par
        for li, pl in enumerate(par.lists):
            for ei, e in enumerate(pl.entries):
                if B.references(par, e.name, self.app.field_labels):
                    before = len(self.root.winfo_children())
                    self.app.find_references(li, ei)
                    self.pump()
                    self.assertGreater(len(self.root.winfo_children()), before)
                    self.root.winfo_children()[-1].destroy()
                    self.app.field_everywhere('maxHP')
                    self.pump()
                    self.root.winfo_children()[-1].destroy()
                    return
        self.skipTest('no referenced entry')

    def test_6_errors_go_through_the_dialog(self):
        bad = os.path.join(self.tmp, 'broken.par')
        with open(bad, 'wb') as f:
            f.write(b'not a par' * 20)
        self.app._load_par(bad)
        self.assertEqual(self.errors, ['open.failed'])
        self.app._load_par(GAME)


if __name__ == '__main__':
    unittest.main()
