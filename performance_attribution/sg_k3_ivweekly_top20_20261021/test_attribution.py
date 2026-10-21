import unittest
import numpy as np
from sector_attribution import effects


class AttributionIdentities(unittest.TestCase):
    def test_FX_bridge_with_nonzero_interaction(self):
        q,p0,p1,f0,f1=100.,10.,12.,1.3,1.4
        components=[q*(p1-p0)*f0,q*p0*(f1-f0),q*(p1-p0)*(f1-f0)]
        np.testing.assert_allclose(components,[260.,100.,20.])
        self.assertAlmostEqual(sum(components),q*(p1*f1-p0*f0))

    def test_multiplicative_return_link_is_not_simple_sum(self):
        returns=np.array([.1,-.1])
        linked=returns*np.array([1.,1.1])
        self.assertAlmostEqual(linked.sum(),-.01)
        self.assertAlmostEqual(np.prod(1+returns)-1,linked.sum())
        self.assertNotAlmostEqual(returns.sum(),linked.sum())

    def test_brinson_with_cash_and_empty_portfolio_sector(self):
        wp=np.array([.6,0.,.4]);wb=np.array([.5,.5,0.])
        rp=np.array([.08,-.03,0.]);rb=np.array([.05,-.03,0.])
        A,S,I=effects(wp,wb,rp,rb)
        self.assertAlmostEqual((A+S+I).sum(),.038)
        self.assertEqual(S[1],0.);self.assertEqual(I[1],0.)

    def test_active_wealth_link_with_different_compounding_paths(self):
        p=np.array([.1,-.05,.02]);b=np.array([.02,.01,-.03])
        prior=np.r_[1.,np.cumprod(1+p)[:-1]]
        future=np.array([np.prod(1+b[i+1:]) for i in range(len(b))])
        self.assertAlmostEqual(np.sum(prior*(p-b)*future),np.prod(1+p)-np.prod(1+b))


if __name__=='__main__':unittest.main()
