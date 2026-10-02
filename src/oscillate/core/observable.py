"""Observable transition polynomial and detector.

Fixes applied vs. first draft, per audit drawer:
  A1 [P]  LS solution reversed into power order
  A2 [P]  slice is u[t-M:t][::-1], unambiguous for all r
  A5 [P]  observe returns None until buffer full
  A6 [P]  dead fallbacks replaced with asserts
  A7 [P]  discriminant normalised, dimensionless
  G3 [P]  roots_q carried on reports, pre-hash material
"""
from __future__ import annotations

import hashlib
import struct
from collections import deque
from dataclasses import dataclass

import numpy as np

from .subresultant import (
    bezout_matrix_complex,
    leading_minors,
    hadamard_scales,
)


def _q(x, step=1e-3):
    """Quantize to a signed integer bin at resolution `step`.
    The shared grid with roots_q; the fingerprint hashes over the same
    bins, so roots_q and fingerprint never misalign."""
    return int(np.clip(round(x / step), -2**31, 2**31 - 1))


def ls_system(u: np.ndarray, M: int):
    """Least-squares system for the annihilating recurrence.

    Row r encodes u_t + c_1 u_{t-1} + ... + c_M u_{t-M} = 0 at
    t = M + r. A[r, j] pairs with u_{t-1-j}, so the lstsq solution is
    most-recent-first and MUST be reversed into power order (A1).
    """
    N = len(u) - M
    A = np.zeros((N, M), dtype=complex)
    b = np.zeros(N, dtype=complex)
    for r in range(N):
        t = M + r
        A[r, :] = u[t - M:t][::-1]   # [P] A2: unambiguous for all r
        b[r] = -u[t]
    assert A.shape == (N, M) and N >= 1
    assert np.isfinite(A).all() and np.isfinite(b).all()
    assert (np.abs(A).sum(axis=1) > 0).all()
    return A, b


class ObservableTransitionPoly:
    """LS-fit annihilating recurrence of the phasor stream,
    carrier-deflated.

    Fit degree M = degree + n_carrier. Deflate the n_carrier roots
    closest to the unit circle. Emit a monic degree-m poly in
    index=power order.

    No access to body internals. The only input is push(u_t) with u_t
    the same complex scalar field.write() receives.
    """

    def __init__(self, degree: int = 6, n_carrier: int = 2,
                 window: int = 64):
        self.degree = degree
        self.n_carrier = n_carrier
        self.window = window
        self._M = degree + n_carrier
        self.buf: deque = deque(maxlen=window)

    def push(self, u_t: complex) -> None:
        self.buf.append(complex(u_t))

    def poly(self) -> np.ndarray:
        m, M = self.degree, self._M

        if len(self.buf) < self.window:            # [P] A5: warm-up
            return np.concatenate(
                [np.zeros(m, dtype=complex), [1.0 + 0j]])

        A, b = ls_system(np.asarray(self.buf, dtype=complex), M)
        a, *_ = np.linalg.lstsq(A, b, rcond=None)
        poly_full = np.concatenate([a[::-1], [1.0 + 0j]])   # [P] A1

        if self.n_carrier > 0:
            roots = np.roots(poly_full[::-1])
            assert len(roots) == M                          # [P] A6
            order = np.argsort(np.abs(1.0 - np.abs(roots)))
            keep = roots[order[self.n_carrier:]]
            assert len(keep) == m
            out = np.poly(keep)[::-1]
        else:
            out = poly_full

        out = np.asarray(out, dtype=complex)
        out = out / out[-1]
        assert len(out) == m + 1
        assert np.isfinite(out).all() and abs(out[-1] - 1.0) < 1e-9
        return out


@dataclass(frozen=True)
class ObservableChainReport:
    """One per tick, per agent.

    roots_q uses integer bins via _q, the same grid the fingerprint
    hashes over: one grid, two consumers. The fingerprint packs the
    bins for the digest chain; roots_q carries them for the W-probe
    (value comparison within bin resolution)."""
    minors: np.ndarray
    rho: float
    kappa: int
    discriminant: complex
    rel_disc: float
    fingerprint: bytes
    roots_q: tuple = ()


class ObservableSubresultantDetector:
    """Per-agent observable-side detector.

    Two chains from one fitted poly:
      (p_t, p_{t-lag})   -> cross-window persistence (rho, kappa)
      (p_t, p_t')        -> within-window defectiveness (discriminant)

    Access: phasor stream only. No J, no body state.
    """

    def __init__(self, degree: int = 6, n_carrier: int = 2,
                 window: int = 64, lag: int = 20,
                 eps_chain: float = 1e-6, fp_decimals: int = 3):
        self.otp = ObservableTransitionPoly(degree, n_carrier, window)
        self.lag = lag
        self.eps_chain = eps_chain
        self.fp_decimals = fp_decimals
        self.snapshot = None
        self.count = 0

    def observe(self, u_t: complex):
        self.otp.push(u_t)
        if len(self.otp.buf) < self.otp.window:     # [P] A5
            return None
        self.count += 1
        c = self.otp.poly()

        if self.snapshot is None:
            self.snapshot = c
            return None

        roots = np.roots(c[::-1])

        B = bezout_matrix_complex(self.snapshot, c)
        d = leading_minors(B)
        s = hadamard_scales(B)
        rel = np.abs(d) / np.maximum(s, 1e-300)
        rho = float(rel.min()) if len(rel) else 1.0
        kappa = 0
        for v in rel[::-1]:
            if v < self.eps_chain:
                kappa += 1
            else:
                break

        rel_disc = self._rel_discriminant(roots)     # [P] A7
        disc = self._discriminant_from_roots(roots)

        step = 10.0 ** (-self.fp_decimals)
        roots_q = tuple(sorted(
            (_q(z.real, step), _q(z.imag, step)) for z in roots))

        if self.count % self.lag == 0:
            self.snapshot = c

        return ObservableChainReport(
            minors=d,
            rho=rho,
            kappa=kappa,
            discriminant=disc,
            rel_disc=rel_disc,
            fingerprint=self._fingerprint_from_roots(roots, step),
            roots_q=roots_q,
        )

    @staticmethod
    def _discriminant_from_roots(roots):
        """Disc(p) = prod_{i<j} (r_i - r_j)^2 for monic p. Near-zero
        signals a repeated root within the current window."""
        prod = 1.0 + 0j
        m = len(roots)
        for i in range(m):
            for j in range(i + 1, m):
                prod *= (roots[i] - roots[j]) ** 2
        return prod

    @staticmethod
    def _rel_discriminant(roots):
        """[P] A7: dimensionless defectiveness, each factor in [0, 1].
        Comparable at fixed m."""
        v = 1.0
        m = len(roots)
        for i in range(m):
            for j in range(i + 1, m):
                v *= abs(roots[i] - roots[j]) / (
                    abs(roots[i]) + abs(roots[j]) + 1e-300)
        return v

    @staticmethod
    def _fingerprint_from_roots(roots, step):
        """Root-quantized, order-independent. Uses the same _q grid as
        roots_q; the fingerprint hashes the bins, roots_q carries them."""
        hashes = sorted(
            hashlib.sha256(
                struct.pack("<ii", _q(z.real, step), _q(z.imag, step))
            ).digest()
            for z in roots
        )
        return hashlib.sha256(b"".join(hashes)).digest()
