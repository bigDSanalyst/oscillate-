"""Check group 1: Bezout identity, fit recovery. Ground truth."""
import numpy as np

from oscillate.core.subresultant import bezout_matrix_complex
from oscillate.core.observable import ObservableTransitionPoly


def test_bezout_resultant_identity():
    """[V] det(Bez(f,g)) = ±Res(f,g) = prod g(roots of f) for f monic."""
    rng = np.random.default_rng(0)
    for _ in range(20):
        n = int(rng.integers(2, 6))
        f = np.concatenate([[1.0], rng.normal(size=n)])
        g = rng.normal(size=n + 1)
        B = bezout_matrix_complex(
            f[::-1].astype(complex), g[::-1].astype(complex))
        res = np.prod(np.polyval(g, np.roots(f)))
        assert np.isclose(abs(np.linalg.det(B)), abs(res), rtol=1e-4)


def test_fit_recovers_known_modes():
    """[V] A1 falsifier. n_carrier=0 isolates the fit from deflation."""
    otp = ObservableTransitionPoly(degree=2, n_carrier=0, window=128)
    for t in range(400):
        otp.push(np.exp(1j * 0.15 * t) + 0.8 * np.exp(1j * 0.55 * t))
    roots = np.roots(otp.poly()[::-1])
    for w in (0.15, 0.55):
        assert min(abs(np.exp(1j * w) - z) for z in roots) < 1e-3, roots
