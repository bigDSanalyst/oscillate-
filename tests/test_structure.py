"""Check group 2: collision timing, contract invariants."""
import numpy as np

from oscillate.core.observable import (
    ObservableTransitionPoly,
    ObservableSubresultantDetector,
    ls_system,
)


def test_collision_event():
    """[P] A2. Fixed mode 0.2; chirp instantaneous frequency sweeps
    from 0.05 crossing 0.2 at t=200. n_carrier=0 isolates the fit."""
    det = ObservableSubresultantDetector(
        degree=3, n_carrier=0, window=128, lag=8)
    T, rows = 400, []
    for t in range(T):
        z = np.exp(1j * 0.2 * t) + 0.9 * np.exp(
            1j * (0.05 * t + 3.75e-4 * t * t))
        r = det.observe(z)
        if r is not None:
            rows.append((t, r.rel_disc))
    assert rows, "detector produced no reports"
    t_star = rows[int(np.argmin([x[1] for x in rows]))][0]
    assert 120 <= t_star <= 280, f"collision argmin at t={t_star}"


def test_structure_contract():
    """[P] A5/A6. Monic, degree m, deterministic, no empty rows."""
    otp = ObservableTransitionPoly(degree=2, n_carrier=0, window=16)
    for t in range(16):
        otp.push(0.15 + 0.6 * np.exp(1j * 0.3 * t))
    A, b = ls_system(np.asarray(otp.buf, dtype=complex), 2)
    assert A.shape == (14, 2)
    p1, p2 = otp.poly(), otp.poly()
    assert np.array_equal(p1, p2)
    assert len(p1) == 3 and abs(p1[-1] - 1.0) < 1e-9
    assert np.isfinite(p1).all()


def test_rel_disc_is_dimensionless():
    """[A18] A7 falsifier. rel_disc is a product of factors in [0, 1] and
    does not change when every root is scaled by the same constant;
    the raw discriminant scales as c^(m(m-1)). argmin-timing in
    test_collision_event cannot see this: an unnormalised product has
    its minimum at the same tick."""
    import numpy as np
    rng = np.random.default_rng(1)
    roots = rng.normal(size=5) + 1j * rng.normal(size=5)
    D = ObservableSubresultantDetector
    v = D._rel_discriminant(roots)
    assert 0.0 <= v <= 1.0
    assert np.isclose(v, D._rel_discriminant(7.5 * roots))
    assert not np.isclose(abs(D._discriminant_from_roots(roots)),
                          abs(D._discriminant_from_roots(7.5 * roots)))
