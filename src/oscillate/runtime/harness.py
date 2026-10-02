"""A/B harness: observable (deployable) vs J-side (oracle).

DualRuntime advances the field on observable reports only (deployable
path, digest included). The J-side is shadow instrumentation, no
digest.

Gap := log10(rho_J) - log10(rho_obs).
  negative: observable UNDERreports -- misses degeneracy the body
            has.
  positive: observable OVERreports -- sees collapse the body doesn't;
            suspect the deflation heuristic, not the signal.

[P] B1: rho means preserved on runtime (last_rho_o, last_rho_j).
[P] B2/A14: trackers invoked from tick() after advance_digest.
[P] G4: tracker consumes the field's post-advance digest.
[P] constructor: leaf_trackers passed in; assert length matches.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .field import Regime


class ShadowClassifier:
    """Mirror of Field.classify over J-side reports. Duplicated, not
    extracted, to keep the patch surface minimal -- merge later.
    r is taken from the field (observable, common), so the DETECTOR is
    the only varying axis in the A/B."""

    def __init__(self, window: int = 48, eps_edge: float = 5e-3,
                 eps_far: float = 2e-2, r_lock: float = 0.97,
                 kappa_lock_frac: float = 0.8, tau_ac: float = 0.9):
        self.stream = deque(maxlen=window)
        self.eps_edge = eps_edge
        self.eps_far = eps_far
        self.r_lock = r_lock
        self.kappa_lock_frac = kappa_lock_frac
        self.tau_ac = tau_ac
        self._in_edge = False

    def update(self, r: float, reports) -> Regime:
        reps = [x for x in reports if x is not None]
        kb = float(np.mean([x.kappa for x in reps])) if reps else 0.0
        depth = max((len(x.minors) for x in reps), default=1)
        if reps:
            self.stream.append(float(np.mean([x.rho for x in reps])))
        rho_bar = self.stream[-1] if self.stream else 1.0
        if not self._in_edge and rho_bar < self.eps_edge:
            self._in_edge = True
        elif self._in_edge and rho_bar > self.eps_far:
            self._in_edge = False
        ac1 = 0.0
        s = np.asarray(self.stream)
        if len(s) >= 8:
            den = np.std(s[:-1]) * np.std(s[1:])
            if den > 1e-15:
                ac1 = float(np.cov(s[:-1], s[1:])[0, 1] / den)
        if r >= self.r_lock and kb >= self.kappa_lock_frac * depth:
            return Regime.SUPER
        if self._in_edge or (ac1 > self.tau_ac and rho_bar < 0.1):
            return Regime.EDGE
        return Regime.DRIFT if r < 0.2 else Regime.SUB


class DualRuntime:
    """A/B runtime. One field, one body list, two detectors."""

    def __init__(self, field, bodies, obs, jac,
                 leaf_trackers=None, split_hold: int = 8):
        assert leaf_trackers is None or len(leaf_trackers) == len(bodies), (
            "leaf_trackers length must match bodies; silent partial "
            "tracking is the failure mode this repo exists to prevent"
        )
        self.field = field
        self.bodies = bodies
        self.obs = obs
        self.jac = jac
        self.leaf_trackers = (leaf_trackers
                              if leaf_trackers is not None else [])
        self.shadow = ShadowClassifier()
        self.split_hold = split_hold
        self.split_run = 0
        self.first_split = None
        self.trace = []
        self.last_rho_o = None
        self.last_rho_j = None
        self.last_reps_o = None

    def tick(self, K: float):
        for b in self.bodies:
            b.set_coupling(K)

        reps_o, reps_j = [], []
        for i, b in enumerate(self.bodies):
            b.step()
            u = b.phasor()
            self.field.write(i, u)
            reps_o.append(self.obs[i].observe(u))
            reps_j.append(self.jac[i].observe(b.jacobian()))

        self.field.step(reps_o)
        regime_o = self.field.classify(reps_o)
        self.field.advance_digest(
            [x.fingerprint for x in reps_o if x is not None], regime_o)
        regime_j = self.shadow.update(abs(self.field.z), reps_j)

        # [P] B2/A14/G4: trackers after advance_digest. The digest
        # they bind is the one that first witnesses the tick.
        for i, rep in enumerate(reps_o):
            if rep is not None and i < len(self.leaf_trackers):
                self.leaf_trackers[i].observe(
                    self.field.tick_no, rep.fingerprint,
                    self.field.digest, rep.roots_q)

        rho_o_vals = [x.rho for x in reps_o if x is not None]
        rho_j_vals = [x.rho for x in reps_j if x is not None]
        self.last_rho_o = (float(np.mean(rho_o_vals))
                           if rho_o_vals else None)
        self.last_rho_j = (float(np.mean(rho_j_vals))
                           if rho_j_vals else None)
        self.last_reps_o = reps_o

        gap = None
        if self.last_rho_o is not None and self.last_rho_j is not None:
            gap = (np.log10(max(self.last_rho_o, 1e-12))
                   - np.log10(max(self.last_rho_j, 1e-12)))
        kappa_o = (int(np.mean([x.kappa for x in reps_o
                                if x is not None]))
                   if rho_o_vals else -1)
        kappa_j = (int(np.mean([x.kappa for x in reps_j
                                if x is not None]))
                   if rho_j_vals else -1)
        disc = (float(np.mean([x.rel_disc for x in reps_o
                               if x is not None]))
                if rho_o_vals else float("nan"))

        if regime_j is not None and regime_o != regime_j:
            self.split_run += 1
            if (self.split_run >= self.split_hold
                    and self.first_split is None):
                self.first_split = self.field.tick_no
        else:
            self.split_run = 0

        self.trace.append((
            self.field.tick_no, K, abs(self.field.z),
            regime_o, regime_j, gap, kappa_o, kappa_j, disc))
        return [self.field.read(i, reps_o[i], regime_o, self.field.digest)
                for i in range(len(self.bodies))]

    def summarize(self) -> None:
        tr = [row for row in self.trace if row[5] is not None]
        live = sum(1 for row in self.trace if row[4] is not None)
        dis = sum(1 for row in self.trace
                  if row[4] is not None and row[3] != row[4])
        print(f"both-live ticks: {len(tr)}/{len(self.trace)}, "
              f"disagreement: {dis}/{live} "
              f"({100 * dis / max(live, 1):.0f}%)")
        print(f"first_split (held {self.split_hold}+ ticks): "
              f"{self.first_split}")
        if tr:
            gaps = np.array([row[5] for row in tr])
            i = int(np.argmax(np.abs(gaps)))
            row = tr[i]
            print(f"peak |gap| = {gaps[i]:+.2f} at K={row[1]:.2f}  "
                  f"regime_obs={row[3].value}, regime_J={row[4].value}")
