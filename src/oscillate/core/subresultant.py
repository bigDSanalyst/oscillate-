"""Complex Bezout matrix and leading-minor subresultant chain.

[V] det(Bez(f,g)) = ±Res(f,g); [V] Laidacker: leading principal minors
of Bez = subresultant chain, up to sign/index convention. Complex
coefficients: same formula, same identities.
"""
from __future__ import annotations

import numpy as np


def bezout_matrix_complex(f, g):
    """[V] Bezout matrix of f and g; coefficient arrays, index=power,
    padded to equal degree. det(Bez) = ±Res(f,g)."""
    n = max(len(f), len(g)) - 1
    a = np.zeros(n + 1, dtype=complex)
    a[n + 1 - len(f):] = f
    b = np.zeros(n + 1, dtype=complex)
    b[n + 1 - len(g):] = g
    B = np.zeros((n, n), dtype=complex)
    for p in range(n):
        for q in range(n):
            s_lo, s_hi = max(0, q - p), min(q, n - 1 - p)
            if s_lo > s_hi:
                continue
            s = np.arange(s_lo, s_hi + 1)
            B[p, q] = np.sum(
                a[p + 1 + s] * b[q - s] - a[q - s] * b[p + 1 + s]
            )
    return B


def leading_minors(B):
    """d_k = det(B[:k,:k]) for k=1..n. [V] Laidacker: this sequence is
    the subresultant chain, up to sign/index convention."""
    return np.array([np.linalg.det(B[:k, :k])
                     for k in range(1, B.shape[0] + 1)])


def hadamard_scales(B):
    """Upper bound on |det(B[:k,:k])| via Hadamard: product of row
    norms. Used to normalise leading minors into rel in [0, 1]."""
    norms = np.linalg.norm(B, axis=1)
    return np.array([np.prod(norms[:k]) for k in range(1, B.shape[0] + 1)])
