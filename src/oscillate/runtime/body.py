"""Minimal oscillator body. Stand-in for OscNet / WONN.

An OscNet instance drops in by implementing phasor() (e.g., Hilbert
or PCA phase of the state) and jacobian(). The Field never reads body
internals; the detector reads only phasor().
"""
from __future__ import annotations

import numpy as np


def wrap(a):
    return (a + np.pi) % (2.0 * np.pi) - np.pi


def wrap_vec(v):
    return (v + np.pi) % (2.0 * np.pi) - np.pi


class KuramotoBody:
    """All-to-all phase-coupled oscillators, mean-field Kuramoto.

    The Jacobian has an exact zero eigenvalue on the uniform mode
    (rotational invariance), so J preserves 1^perp and Q^T J Q is a
    genuine restriction, not an approximation.
    """

    def __init__(self, dim: int, K: float, seed: int):
        rng = np.random.default_rng(seed)
        self.dim = dim
        self.K = K
        self.omega = rng.normal(0.0, 0.5, size=dim)
        self.theta = rng.uniform(-np.pi, np.pi, size=dim)

    def set_coupling(self, K: float) -> None:
        self.K = K

    def step(self, dt: float = 0.05) -> None:
        C = np.sin(self.theta[None, :] - self.theta[:, :])
        self.theta = wrap_vec(
            self.theta + dt * (self.omega
                               + (self.K / self.dim) * C.sum(axis=1)))

    def phasor(self) -> complex:
        return complex(np.exp(1j * self.theta).mean())

    def jacobian(self) -> np.ndarray:
        C = np.cos(self.theta[None, :] - self.theta[:, :])
        return (self.K / self.dim) * (C - np.diag(C.sum(axis=1)))
