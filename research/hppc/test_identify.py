import unittest
import numpy as np
from identify import predict, events, HERE, TRAIN, TEST, slopes


class IdentificationTests(unittest.TestCase):
    def test_exact_constant_current_and_continuity(self):
        e = {'t':np.array([0., 1., 2., 3.]), 'i':np.array([0., 2., 0., -2.]),
             'v':np.array([4., 0., 0., 0.])}
        v = predict(e, .01, .02, 5., .003, .1)
        z = .003
        q = 0.
        for k in range(1,4):
            z = z*np.exp(-.2) + .02*e['i'][k]*(1-np.exp(-.2))
            q += e['i'][k]/3600
            self.assertAlmostEqual(v[k], 4 - .1*q - .01*e['i'][k] - z + .003)

    def test_source_and_split(self):
        es = events(HERE/'source.csv')
        self.assertEqual(len(es), 10)
        self.assertFalse(set(TRAIN) & set(TEST))
        self.assertEqual(set(TRAIN) | set(TEST), set(range(10)))
        self.assertTrue(np.isfinite(slopes(es,TRAIN)).all())
        for e in es:
            self.assertEqual([(e['step']==s).sum() for s in (6,7,8)], [60,40,100])
            self.assertTrue(np.all(np.diff(e['t']) > 0))


if __name__ == '__main__':
    unittest.main()
