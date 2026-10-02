"""Field: global phase holder.

One-way observation channel: bodies write phasors, the field never
forces them; actuation happens downstream through the phase gate.
"""
from __future__ import annotations

import hashlib
import struct
from collections import deque
from dataclasses import dataclass
from enum import Enum

import numpy as np

from ..core.observable import _q


TWO_PI = 2.0 * np.pi


def wrap(a):
    return (a + np.pi) % TWO_PI - np.pi


class Regime(Enum):
    SUB = "sub"
    EDGE = "edge"
    SUPER = "super"
    DRIFT = "drift"


@dataclass(frozen=True)
class Reading:
    tick: int
    agent: int
    r: float
    psi: float
    delta: float
    rho: float
    kappa: int
    regime: Regime
    digest: bytes
    fingerprint: bytes

    def packed(self) -> bytes:
        """32 bytes: the compression guarantee, made literal."""
        return struct.pack("<qiiiiii", self.tick, self.agent,
                           _q(self.r), _q(self.psi), _q(self.delta),
                           _q(self.rho), self.kappa)


class Field:
    """The field. Owns the state readings. Runs the tick loop."""

    def __init__(self, n_agents: int, *, decay: float = 0.93,
                 omega_field: float = 0.03, psi_gain: float = 0.2,
                 window: int = 48, eps_edge: float = 5e-3,
                 eps_far: float = 2e-2, r_lock: float = 0.97,
                 kappa_lock_frac: float = 0.8, tau_ac: float = 0.9):
        self.n = n_agents
        self.u = np.zeros(n_agents, dtype=complex)
        self.w = np.zeros(n_agents)
        self.z = 0.0j
        self.psi = 0.0
        self.decay = decay
        self.omega_field = omega_field
        self.psi_gain = psi_gain
        self.rho_stream = deque(maxlen=window)
        self.eps_edge = eps_edge
        self.eps_far = eps_far
        self.r_lock = r_lock
        self.kappa_lock_frac = kappa_lock_frac
        self.tau_ac = tau_ac
        self._in_edge = False
        self._regime = Regime.DRIFT
        self.tick_no = 0
        self.digest = hashlib.sha256(b"oscillate:genesis").digest()

    def write(self, i: int, phasor: complex) -> None:
        m = abs(phasor)
        self.u[i] = phasor / m if m > 1e-12 else 1.0 + 0.0j
        self.w[i] = 1.0

    def step(self, reports) -> None:
        self.w *= self.decay
        W = self.w.sum()
        self.z = (self.u * self.w).sum() / W if W > 1e-12 else 0.0j
        self.psi = wrap(self.psi + self.omega_field
                        + self.psi_gain * np.angle(self.z))
        rhos = [r.rho for r in reports if r is not None]
        if rhos:
            self.rho_stream.append(float(np.mean(rhos)))
        self.tick_no += 1

    def _ac1(self) -> float:
        s = np.asarray(self.rho_stream)
        if len(s) < 8:
            return 0.0
        den = np.std(s[:-1]) * np.std(s[1:])
        return (float(np.cov(s[:-1], s[1:])[0, 1] / den)
                if den > 1e-15 else 0.0)

    def classify(self, reports) -> Regime:
        r = abs(self.z)
        reps = [x for x in reports if x is not None]
        kappa_bar = float(np.mean([x.kappa for x in reps])) if reps else 0.0
        depth = max((len(x.minors) for x in reps), default=1)
        rho_bar = self.rho_stream[-1] if self.rho_stream else 1.0
        if not self._in_edge and rho_bar < self.eps_edge:
            self._in_edge = True
        elif self._in_edge and rho_bar > self.eps_far:
            self._in_edge = False
        if r >= self.r_lock and kappa_bar >= self.kappa_lock_frac * depth:
            self._regime = Regime.SUPER
        elif (self._in_edge
              or (self._ac1() > self.tau_ac and rho_bar < 0.1)):
            self._regime = Regime.EDGE
        elif r < 0.2:
            self._regime = Regime.DRIFT
        else:
            self._regime = Regime.SUB
        return self._regime

    def advance_digest(self, fingerprints, regime: Regime) -> bytes:
        payload = (struct.pack("<qii", self.tick_no,
                               _q(abs(self.z)), _q(self.psi))
                   + regime.value.encode("ascii")
                   + b"".join(fingerprints))
        self.digest = hashlib.sha256(self.digest + payload).digest()
        return self.digest

    def read(self, i: int, report, regime: Regime, digest: bytes) -> Reading:
        phi = np.angle(self.u[i]) if self.w[i] > 1e-9 else self.psi
        return Reading(
            tick=self.tick_no, agent=i,
            r=float(abs(self.z)), psi=float(self.psi),
            delta=float(wrap(self.psi - phi)),
            rho=report.rho if report else 1.0,
            kappa=report.kappa if report else 0,
            regime=regime, digest=digest,
            fingerprint=(report.fingerprint if report
                         else hashlib.sha256(b"cold").digest()),
        )
