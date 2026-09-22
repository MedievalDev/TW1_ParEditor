"""1.8.0 in the window, driven like a user: reused rows, change marks and the
"changed only" filter, the game's values with reset, favourites, templates,
CSV export/import, the jump box. Settings live in a temp folder, nothing is
sent, nothing is written below the game folder, the window is never topmost."""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import tkinter as tk  # noqa: E402
import bulkui  # noqa: E402
import extraui  # noqa: E402
import foxfeedback  # noqa: E402
import foxfeedback_ui  # noqa: E402
import theme  # noqa: E402
import tw1_par_editor as M  # noqa: E402

GAME = r'F:\SteamLibrary\steamapps\common\Two Worlds - Epic Edition\WDFiles\Update16.wd'


@unittest.skipUnless(os.path.isfile(GAME), 'game not on this PC')
class Work(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='par_work_ui_')
        cls._orig = (M.data_dir, foxfeedback.submit, foxfeedback_ui.FeedbackUI.start, M.ErrorDialog,
                     M.simpledialog.askstring, M.messagebox.askyesno, M.filedialog.asksaveasfilename,
                     M.filedialog.askopenfilename, bulkui.ReviewDialog)
        M.data_dir = lambda: cls.tmp
        cls.errors = []
        foxfeedback.submit = lambda *a, **k: (_ for _ in ()).throw(AssertionError('nothing is sent'))
        foxfeedback_ui.FeedbackUI.start = lambda self: None
        M.ErrorDialog = lambda app, key, message, shown, guide=None, title=None: cls.errors.append((key, shown))
        M.messagebox.askyesno = lambda *a, **k: True
        cfg = M.Config()
        cfg.update(guide_seen=True, update_check=False, lang='en', review_before_save=False,
                   original_par_path=GAME, show_game_values=True)
        cfg.save()
        cls.root = tk.Tk()
        cls.app = M.ParEditorApp(cls.root)
        cls.root.geometry('1200x750+40+40')
        cls.root.lower()
        cls.pump(0.5)
        # a mod par outside the game folder: the game's par is the reference
        cls.app._load_par(GAME)
        cls.mod = os.path.join(cls.tmp, 'Mod.par')
        cls.app._do_save(cls.mod)
        cls.pump()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass
        (M.data_dir, foxfeedback.submit, foxfeedback_ui.FeedbackUI.start, M.ErrorDialog,
         M.simpledialog.askstring, M.messagebox.askyesno, M.filedialog.asksaveasfilename,
         M.filedialog.askopenfilename, bulkui.ReviewDialog) = cls._orig
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def pump(cls, secs=0.2):
        end = time.time() + secs
        while time.time() < end:
            cls.root.update()
            time.sleep(0.01)

    def setUp(self):
        self.errors.clear()
        self.app.modified = False
        self.app.changed_only_var.set(False)
        self.app._load_par(self.mod)
        end = time.time() + 30
        while self.app.game_ref is None and time.time() < end:
            self.pump(0.1)
        self.assertIsNotNone(self.app.game_ref, 'the game par is read in the background')
        self.li, self.ei = self.find('MO_WOLF_01')

    def find(self, name):
        return next((li, ei) for li, pl in enumerate(self.app.par.lists)
                    for ei, e in enumerate(pl.entries) if e.name == name)

    def show(self, li, ei):
        self.app.jump_to(li, ei)
        self.pump(0.05)

    def row(self, fi):
        return next(r for r in self.app._pool['rows'] if r['fi'] == fi)

    def test_1_rows_are_reused_and_quick(self):
        self.show(self.li, 0)
        frame = self.app._pool['frame']
        t = time.perf_counter()
        for ei in range(1, 6):
            self.app._show_entry(self.li, ei)
            self.root.update()
        per = (time.perf_counter() - t) / 5
        self.assertIs(self.app._pool['frame'], frame, 'same layout, same rows')
        self.assertLess(per, 0.25, f'{per:.3f} s per entry')
        self.assertEqual(self.row(34)['var'].get(), str(self.app.par.lists[self.li].entries[5].fields[34].value))

    def test_2_marks_and_changed_only(self):
        self.show(self.li, self.ei)
        old = self.app.current_entry.fields[34].value
        self.row(34)['var'].set(str(old + 7))
        self.app._apply_current_edits()
        self.pump()
        iid = f"L{self.li}E{self.ei}"
        self.assertIn('changed', self.app.tree.item(iid, 'tags'))
        self.assertTrue(self.app.tree.item(iid, 'text').startswith('\u25CF'))
        self.assertEqual(str(self.row(34)['idx'].cget('fg')), theme.MOD)
        self.assertIn(f'was {old}', self.row(34)['note'].cget('text'))
        self.app.changed_only_var.set(True)
        self.app._apply_filter()
        self.pump()
        self.assertEqual(self.app.search_results, [(self.li, self.ei)])
        self.app.changed_only_var.set(False)

    def test_3_game_value_and_reset(self):
        e = self.app.par.lists[self.li].entries[self.ei]
        game = e.fields[34].value
        e.fields[34].value = game + 50
        self.show(self.li, self.ei)
        self.assertIn(f'game {game}', self.row(34)['note'].cget('text'))
        self.app._reset_field(34, self.app.game_ref.value(e, 34), "game's value")
        self.assertEqual(e.fields[34].value, game)
        self.assertEqual(self.row(34)['note'].cget('text'), '')
        self.app.do_undo()
        self.assertEqual(self.app.par.lists[self.li].entries[self.ei].fields[34].value, game + 50)

    def test_4_favourites(self):
        self.app.toggle_favorite('MO_WOLF_01')
        self.pump()
        fav = f"F{self.li}E{self.ei}"
        self.assertTrue(self.app.tree.exists('FAV'))
        self.assertTrue(self.app.tree.exists(fav))
        self.app.tree.selection_set(fav)
        self.pump()
        self.assertEqual(self.app.current_entry.name, 'MO_WOLF_01')
        self.app.toggle_favorite('MO_WOLF_01')
        self.pump()
        self.assertFalse(self.app.tree.exists('FAV'))

    def test_5_template(self):
        answers = iter(['Wolf template', 'MO_WOLF_TEMPLATE_01'])
        M.simpledialog.askstring = lambda *a, **k: next(answers)
        self.app.save_template(self.li, self.ei)
        self.assertIn('Wolf template', self.app.templates())
        n = len(self.app.par.lists[self.li].entries)
        self.app.new_from_template(self.li, 'Wolf template')
        pl = self.app.par.lists[self.li]
        self.assertEqual(len(pl.entries), n + 1)
        self.assertEqual(pl.entries[-1].name, 'MO_WOLF_TEMPLATE_01')
        self.assertEqual(pl.entries[-1].fields[34].value, pl.entries[self.ei].fields[34].value)

    def test_6_csv_export_and_import(self):
        path = os.path.join(self.tmp, 'units.csv')
        M.filedialog.asksaveasfilename = lambda *a, **k: path
        M.filedialog.askopenfilename = lambda *a, **k: path
        self.app.export_csv('list', self.li)
        with open(path, encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        head = lines[0].split(';')
        col, cname = head.index('initParamHP'), head.index('entry')
        for i, line in enumerate(lines[1:], 1):
            cells = line.split(';')
            if cells[cname] == 'MO_WOLF_01':
                cells[col] = '999'
                lines[i] = ';'.join(cells)
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write('\n'.join(lines) + '\n')

        class KeepAll:
            def __init__(dlg, app, changes, **kw):
                dlg.win = tk.Toplevel(app.root)
                dlg.result = []
                dlg.seen = changes
                dlg.win.after(10, dlg.win.destroy)
        bulkui.ReviewDialog = KeepAll
        self.app.import_csv()
        self.assertEqual(self.app.par.lists[self.li].entries[self.ei].fields[34].value, 999)
        self.assertTrue(self.app.modified)
        self.assertEqual(self.errors, [])

    def test_7_jump_box(self):
        box = self.app.quick_jump()
        self.pump()
        box.var.set('mo_wolf_01')
        self.pump()
        self.assertEqual(box.hits[0][2], 'MO_WOLF_01')
        box.go()
        self.pump()
        self.assertEqual(self.app.current_entry.name, 'MO_WOLF_01')
        self.assertFalse(box.win.winfo_exists())


if __name__ == '__main__':
    unittest.main()
