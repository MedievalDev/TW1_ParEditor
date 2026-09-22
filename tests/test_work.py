"""worktools against the par the game runs (Update16.wd): marks, CSV round
trip, templates, free names, jump box, game reference."""
import copy
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bulktools as B  # noqa: E402
import worktools as W  # noqa: E402
import tw1_par_editor as M  # noqa: E402
from categories import category_of  # noqa: E402

GAME = r'F:\SteamLibrary\steamapps\common\Two Worlds - Epic Edition\WDFiles\Update16.wd'


class Values(unittest.TestCase):
    def test_cells(self):
        self.assertEqual(W.cell_text(0.1, W.TYPE_FLOAT32), '0.1', 'float32 0.1 written short')
        self.assertEqual(W.parse_cell('0,1', W.TYPE_FLOAT32), 0.1)
        self.assertEqual(W.parse_cell('250.0', W.TYPE_INT32), 250, 'a spreadsheet adds .0')
        self.assertEqual(W.parse_cell('1 | 2 | 3', W.TYPE_ARRAY_INT32), [1, 2, 3])
        self.assertEqual(W.parse_cell('', W.TYPE_ARRAY_STR), [])
        with self.assertRaises(ValueError):
            W.parse_cell('-1', W.TYPE_UINT32)
        self.assertTrue(W.same_value(0.1, 0.10000000149011612, W.TYPE_FLOAT32))

    def test_find_game_par_by_hand(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, 'x.wd')
            open(p, 'wb').close()
            self.assertEqual(W.find_game_par(None, p, drives=''), p)
            self.assertIsNone(W.find_game_par(os.path.join(d, 'a.par'), None, drives=''))
        finally:
            shutil.rmtree(d)


@unittest.skipUnless(os.path.isfile(GAME), 'game not on this PC')
class RealPar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.par = M.read_par(M.read_par_source(GAME)[0])
        cls.lpath = os.path.join(tempfile.gettempdir(), '_par_work_labels.json')
        cls.labels = M.FieldLabels(cls.lpath)
        cls.labels.resolve(cls.par)
        cls.tmp = tempfile.mkdtemp(prefix='par_work_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        if os.path.exists(cls.lpath):
            os.remove(cls.lpath)

    def setUp(self):
        self.p = copy.deepcopy(self.par)

    def test_changed_map(self):
        self.assertEqual(W.changed_map(self.par, self.p), {})
        li = self.p.sheets.index('Units')
        self.p.lists[li].entries[2].fields[34].value += 5
        extra = copy.deepcopy(self.p.lists[li].entries[0])
        extra.name = 'ZZ_NEW'
        self.p.lists[li].entries.append(extra)
        m = W.changed_map(self.par, self.p)
        self.assertEqual(m[(li, 2)], {34})
        self.assertIsNone(m[(li, len(self.p.lists[li].entries) - 1)], 'a new entry is None')
        self.assertEqual(len(m), 2)

    def test_csv_round_trip(self):
        tg = B.targets(self.p, 'category', 'Enemies', category_of=category_of)
        path = os.path.join(self.tmp, 'enemies.csv')
        self.assertEqual(W.export_csv(self.p, tg, self.labels, path), len(tg))
        changes, problems = W.import_csv(self.p, path, self.labels, B.Change)
        self.assertEqual((changes, problems), ([], []), 'unchanged table = nothing to import')
        # change one cell like a spreadsheet would (comma decimal, .0 ints)
        with open(path, encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        head = lines[0].split(';')
        col = head.index('initParamHP')
        row = lines[1].split(';')
        old = int(row[col])
        row[col] = f'{old * 2}.0'
        lines[1] = ';'.join(row)
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write('\n'.join(lines) + '\n')
        changes, problems = W.import_csv(self.p, path, self.labels, B.Change)
        self.assertEqual(problems, [])
        self.assertEqual(len(changes), 1)
        self.assertEqual((changes[0].label, changes[0].old, changes[0].new), ('initParamHP', old, old * 2))

    def test_csv_problems(self):
        path = os.path.join(self.tmp, 'bad.csv')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('list,sheet,entry,initParamHP\n0,x,NO_SUCH_ENTRY,5\n')
        changes, problems = W.import_csv(self.p, path, self.labels, B.Change)
        self.assertEqual(changes, [])
        self.assertIn('NO_SUCH_ENTRY', problems[0])

    def test_template_and_free_name(self):
        li, src = next((li, e) for li, pl in enumerate(self.p.lists) for e in pl.entries if e.name == 'MO_WOLF_01')
        t = W.make_template(src, 'Units')
        path = os.path.join(self.tmp, 'templates.json')
        W.save_templates(path, {'Wolf': t})
        t = W.load_templates(path)['Wolf']
        self.assertTrue(W.template_fits(t, 'Units', len(src.fields)))
        name = W.free_name(self.p, 'MO_WOLF_01')
        self.assertNotIn(name, {e.name for pl in self.p.lists for e in pl.entries})
        e = W.entry_from_template(t, name, M.ParEntry, M.ParField)
        self.assertEqual(len(e.fields), len(src.fields))
        self.assertEqual(e.fields[34].value, src.fields[34].value)
        self.p.lists[li].entries.append(e)
        back = M.read_par(M.write_par(self.p))
        self.assertEqual(back.lists[li].entries[-1].name, name, 'a template entry saves and reads back')

    def test_quick_matches(self):
        hits = W.quick_matches(self.p, 'wolf_01')
        self.assertTrue(hits)
        self.assertTrue(hits[0][2].lower().startswith('mo_wolf_01') or 'wolf_01' in hits[0][2].lower())
        self.assertEqual(W.quick_matches(self.p, 'MO_WOLF_01')[0][2], 'MO_WOLF_01', 'exact name first')
        self.assertEqual(W.quick_matches(self.p, ''), [])

    def test_ref_index(self):
        ref = W.RefIndex(self.par, GAME)
        li = self.p.sheets.index('Units')
        e = self.p.lists[li].entries[0]
        self.assertFalse(ref.differs(e, 34))
        e.fields[34].value += 1
        self.assertTrue(ref.differs(e, 34))
        self.assertEqual(ref.value(e, 34), e.fields[34].value - 1)


if __name__ == '__main__':
    unittest.main()
