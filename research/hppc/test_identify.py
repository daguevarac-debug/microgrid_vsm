import unittest
import numpy as np
from identify import predict, events, HERE, TRAIN, TEST, slopes, residual
from compare_models import prediction, response, error_metrics, evaluate, fit, GROUPS, objective, coordinate


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

    def test_residual_selects_only_requested_steps(self):
        e = {'t':np.arange(6.), 'i':np.zeros(6), 'v':np.array([4.,1.,2.,3.,4.,5.]),
             'step':np.array([5,6,7,8,9,4])}
        x=[.001,.001,20.,0.]
        np.testing.assert_allclose(residual(x,[e],[0],[0.]), [3.,2.,1.])
        np.testing.assert_allclose(residual(x,[e],[0],[0.],True), [3.])

    def test_metrics_and_reproducible_fit(self):
        m=error_metrics(np.array([.001,-.002,.003]))
        self.assertAlmostEqual(m['rmse_mV'],np.sqrt(14/3))
        self.assertAlmostEqual(m['mae_mV'],2.)
        self.assertAlmostEqual(m['bias_mV'],2/3)
        self.assertAlmostEqual(m['max_abs_mV'],3.)
        es=events(HERE/'source.csv'); s=slopes(es,TRAIN)
        first=fit('1rc',es,TRAIN,s); second=fit('1rc',es,TRAIN,s)
        np.testing.assert_allclose(first['parameters'],second['parameters'],rtol=1e-10,atol=1e-10)
        actual=evaluate('1rc',first,es,GROUPS['test_3_6_9'],s)
        error=prediction(es[2],'1rc',first['parameters'],s[2],first['center_Ah'],first['span_Ah'])-es[2]['v']
        self.assertAlmostEqual(actual['pulses']['3']['rest']['rmse_mV'],error_metrics(error[es[2]['step']==7])['rmse_mV'])

    def test_continuity_2rc_and_variable_recurrence(self):
        i=np.array([2.,0.,-2.]); dt=np.ones(3)
        z=response(i,dt,.02,5.,.003)
        for k in range(1,4):
            self.assertAlmostEqual(z[k],z[k-1]*np.exp(-.2)+.02*i[k-1]*(1-np.exp(-.2)))
        e={'t':np.arange(4.),'i':np.r_[0.,i], 'v':np.array([4.,0.,0.,0.]),'q':0.}
        a=prediction(e,'1rc',[1.,2.,5.,3.],.1,0.,1.)
        b=prediction(e,'variable',[1.,2.,5.,3.,0.,0.,0.],.1,0.,1.)
        np.testing.assert_allclose(a,b,rtol=0,atol=1e-12)

    def test_reserved_voltages_do_not_enter_fit(self):
        es=events(HERE/'source.csv'); s=slopes(es,TRAIN)
        original=fit('1rc',es,TRAIN,s)
        for k in TEST:
            es[k]['v']=es[k]['v']+100
        np.testing.assert_allclose(slopes(es,TRAIN),s)
        changed=fit('1rc',es,TRAIN,slopes(es,TRAIN))
        np.testing.assert_allclose(original['parameters'],changed['parameters'],atol=1e-10)

    def test_comparison_objective_ignores_other_steps(self):
        e={'t':np.arange(6.),'i':np.zeros(6),'v':np.array([4.,1.,2.,3.,4.,5.]),
           'step':np.array([5,6,7,8,9,4]),'q':0.}
        # The second event supplies a nonzero capacity span.
        e2=dict(e,q=1.)
        a=objective([1.,1.,20.,0.],'1rc',[e,e2],[0,1],[0.,0.],.5,.5)
        np.testing.assert_allclose(a, np.tile(np.array([3.,2.,1.])/np.sqrt(6),2))


if __name__ == '__main__':
    unittest.main()
