"""J-side subresultant detector. Sim-only instrumentation.

[P] D3: this module previously defined its own float bezout_matrix.
Assembled into the repo it created an unchecked twin of the checked
core function. It now imports bezout_matrix_complex, leading_minors,
hadamard_scales from ..core.subresultant. Real coefficients are a
special case of the complex function; rel = |d|/s is unchanged;
ShadowClassifier reads only kappa, len(minors), rho -- nothing
downstream moves.

This detector reads the body's Jacobian and is therefore NOT the
deployable detector. It is the ground-truth oracle for the observable
side. In simulation, both run on the same field, and the difference
between their readings is the observability gap.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np

from ..core.subresultant import (
    bezout_matrix_complex,
    leading_minors,
    hadamard_scales,
)


@dataclass(frozen=True)
class ChainReport:
    minors: np.ndarray
    rho: float
    kappa: int
    fingerprint: bytes


class SubresultantDetector:
    """Per-agent J-side discrete detector.

    The transition polynomial is the characteristic polynomial of the
    body Jacobian restricted to the complement of the invariant
    (carrier) subspace. Without carrier deflation, symmetric all-to-all
    coupling gives J an exact zero eigenvalue on span{ones}, so
    consecutive char polys ALWAYS share root 0 and the chain is
    vacuous. Deflation is mandatory, not an optimization.
    """

    def __init__(self, lag: int = 20, eps_chain: float = 1e-6):
        self.lag = lag
        self.eps_chain = eps_chain
        self.snapshot = None
        self.count = 0

    @staticmethod
    def transition_poly(J: np.ndarray, carrier_dim: int = 1) -> np.ndarray:
        n = J.shape[0]
        q, _ = np.linalg.qr(np.ones((n, carrier_dim)), mode="complete")
        Q = q[:, carrier_dim:]
        A = Q.T @ J @ Q
        return np.poly(A)[::-1]

    def observe(self, J: np.ndarray):
        self.count += 1
        c = self.transition_poly(J)
        if self.snapshot is None:
            self.snapshot = c
            return None

        # [P] D3: use the checked core function
        B = bezout_matrix_complex(
            self.snapshot.astype(complex), c.astype(complex))
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
        fp = sha256(
            np.asarray(np.round(rel, 5), dtype="<f8").tobytes()
        ).digest()
        if self.count % self.lag == 0:
            self.snapshot = c
        return ChainReport(d, rho, kappa, fp)
