"""bulktools against the par the game runs (Update16.wd) and against made-up
values. Skips the real-par part when the game is not on this PC."""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bulktools as B  # noqa: E402
import tw1_par_editor as M  # noqa: E402
from categories import category_of  # noqa: E402

GAME = r'F:\SteamLibrary\steamapps\common\Two Worlds - Epic Edition\WDFiles\Update16.wd'


class Values(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(B.new_value(100, B.TYPE_INT32, 'mul', '20'), 120)
        self.assertEqual(B.new_value(100, B.TYPE_INT32, 'mul', '-50%'), 50)
        self.assertEqual(B.new_value(7, B.TYPE_INT32, 'add', '-10'), -3)
        self.assertEqual(B.new_value(7, B.TYPE_UINT32, 'add', '-10'), 0, 'uint never goes below 0')
        self.assertEqual(B.new_value(1.5, B.TYPE_FLOAT32, 'mul', '10'), 1.65)
        self.assertEqual(B.new_value(1, B.TYPE_INT32, 'set', '0x10'), 16)
        self.assertEqual(B.new_value(2.0, B.TYPE_FLOAT32, 'set', '2,5'), 2.5, 'comma as decimal sign')

    def test_text_and_arrays(self):
        self.assertEqual(B.new_value('SWORD_01', B.TYPE_STRING, 'replace', 'SWORD=>BLADE'), 'BLADE_01')
        self.assertEqual(B.new_value('x', B.TYPE_STRING, 'mul', '10'), 'x', 'numbers ops leave text alone')
        self.assertEqual(B.new_value([10, 20], B.TYPE_ARRAY_INT32, 'mul', '50'), [15, 30])
        self.assertEqual(B.new_value(['a_1', 'b_1'], B.TYPE_ARRAY_STR, 'replace', '_1=>_2'), ['a_2', 'b_2'])
        with self.assertRaises(ValueError):
            B.new_value(1, B.TYPE_INT32, 'set', 'abc')

    def test_preset_check(self):
        p = B.make_preset('category', 'Enemies', 'maxHP', 'mul', 20)
        self.assertTrue(B.check_preset(p))
        self.assertFalse(B.check_preset({'scope': 'bad'}))


@unittest.skipUnless(os.path.isfile(GAME), 'game not on this PC')
class RealPar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data, _w, _c, _wd = M.read_par_source(GAME)
        cls.par = M.read_par(data)
        cls.labels = M.FieldLabels(os.path.join(ROOT, '_labels_test_do_not_keep.json'))
        cls.labels.resolve(cls.par)

    def setUp(self):
        self.par = copy.deepcopy(self.__class__.par)
        self.orig = copy.deepcopy(self.par)

    def test_category_by_field_name(self):
        tg = B.targets(self.par, 'category', 'Enemies', category_of=category_of)
        self.assertGreater(len(tg), 100)
        names = [c[0] for c in B.field_choices(self.par, tg, self.labels)]
        self.assertIn('maxHP', names)
        changes, skipped = B.plan_bulk(self.par, tg, self.labels, 'maxHP', 'mul', '20')
        self.assertGreater(len(changes), 50)
        for c in changes[:50]:
            self.assertEqual(B.label_of(self.labels, self.par, c.li, c.fi), 'maxHP')
            self.assertEqual(c.new, int(round(c.old * 1.2)))
        B.apply_changes(self.par, changes)
        d = B.diff(self.orig, self.par, self.labels)
        self.assertEqual(len(d), len(changes), 'the review sees exactly the bulk edit')
        B.revert(self.par, d)
        self.assertEqual(B.diff(self.orig, self.par, self.labels), [])

    def test_write_and_read_back(self):
        tg = B.targets(self.par, 'category', 'Enemies', category_of=category_of)
        changes, _ = B.plan_bulk(self.par, tg, self.labels, 'maxHP', 'add', '7')
        B.apply_changes(self.par, changes)
        back = M.read_par(M.write_par(self.par))
        c = changes[0]
        self.assertEqual(back.lists[c.li].entries[c.ei].fields[c.fi].value, c.new)

    def test_added_and_removed_entries_in_the_review(self):
        pl = next(p for p in self.par.lists if len(p.entries) >= 3)
        gone = pl.entries.pop(1)                 # an original entry goes
        extra = copy.deepcopy(pl.entries[0])
        extra.name = 'ZZ_NEW_ENTRY'
        pl.entries.append(extra)                 # a new one comes
        kinds = {(c.kind, c.entry) for c in B.diff(self.orig, self.par, self.labels)}
        self.assertIn(('added', 'ZZ_NEW_ENTRY'), kinds)
        self.assertIn(('removed', gone.name), kinds)

    def test_references_and_field_everywhere(self):
        # take a text value that some entry uses, find it as a reference
        for pl in self.par.lists:
            for e in pl.entries:
                for f in e.fields:
                    if (f.dtype == B.TYPE_STRING and f.value and f.value != e.name and any(
                            x.name == f.value for p2 in self.par.lists for x in p2.entries)):
                        refs = B.references(self.par, f.value, self.labels)
                        self.assertTrue(any(r[4] == f.value for r in refs))
                        rows = B.field_everywhere(self.par, self.labels, 'maxHP')
                        self.assertGreater(len(rows), 100)
                        return
        self.skipTest('no entry name used as a text value')

    @classmethod
    def tearDownClass(cls):
        p = os.path.join(ROOT, '_labels_test_do_not_keep.json')
        if os.path.exists(p):
            os.remove(p)


if __name__ == '__main__':
    unittest.main()
