"""Crossing-emission leaf tracker.

Fixes applied vs. first draft, per audit drawer:
  A8  [P] leaf emitted at the crossing tick, not at death
  A9  [P] disjointness: t - birth >= window
  A10 [P] births counted as a separate channel
  G3  [P] roots_q carried on leaves; G5 is the probe ring buffer,
          spec'd not wired
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class Leaf:
    """A verified structure.

    Structure-identity: the leaf IS the fingerprint. Two leaves with
    the same fingerprint are the same structure regardless of when
    they occurred. Occurrence is captured by birth_tick / verified_tick,
    not by identity.

    Verified means: the fingerprint persisted for at least W ticks from
    birth, so the structure was re-inferred from data disjoint from the
    birth data (one full buffer turnover). Persistence < W is not
    evidence about the system; it is evidence about the buffer.

    The seed binds at the flip (crossing tick), not at birth: the
    digest at the moment persistence crossed W, paired with the
    fingerprint that persisted. The tick-level hash chain proves
    birth-before-flip.
    """
    fingerprint: bytes
    birth_tick: int
    birth_digest: bytes
    verified_tick: int
    verified_digest: bytes
    roots_q: tuple = ()

    @property
    def seed(self) -> bytes:
        return sha256(self.verified_digest + self.fingerprint).digest()

    def to_jsonl(self) -> str:
        return json.dumps({
            "fingerprint": self.fingerprint.hex(),
            "birth_tick": self.birth_tick,
            "birth_digest": self.birth_digest.hex(),
            "verified_tick": self.verified_tick,
            "verified_digest": self.verified_digest.hex(),
            "roots_q": [list(r) for r in self.roots_q],
            "seed": self.seed.hex(),
        })


class LeafTracker:
    """One per agent.

    Emits leaves at crossing ticks (persistence reaches W from birth),
    not at death ticks. An absorbing structure emits exactly once, at
    its crossing; the terminal leaf is in the ledger when closure fires.

    Births are counted regardless of outcome: sub-W flapping is
    invisible to leaves AND closure, so the birth rate is the only
    growth-side channel that sees the resolution limit.

    Convention: episode = ticks b..e inclusive, length L = e - b + 1,
    verification needs L >= W + 1 (first disjoint tick is b + W).
    n_births = n_episodes - 1 per agent: the initial state is a start,
    not a transition.
    """

    def __init__(self, window: int, agent: int):
        self.window = window
        self.agent = agent
        self.current_fingerprint = None
        self.current_birth_tick = 0
        self.current_birth_digest = b""
        self.current_roots_q = ()
        self._emitted = False
        self.leaves = []
        self.birth_ticks = []
        self.ticks_since_leaf = 0

    def _start(self, tick, fp, digest, roots_q):
        self.current_fingerprint = fp
        self.current_birth_tick = tick
        self.current_birth_digest = digest
        self.current_roots_q = roots_q or ()
        self._emitted = False

    def observe(self, tick, fingerprint, digest, roots_q=()):
        self.ticks_since_leaf += 1
        if self.current_fingerprint is None:
            self._start(tick, fingerprint, digest, roots_q)
            return None
        if fingerprint != self.current_fingerprint:
            self.birth_ticks.append(tick)          # a birth, not a death
            self._start(tick, fingerprint, digest, roots_q)
            return None
        if (not self._emitted
                and tick - self.current_birth_tick >= self.window):
            leaf = Leaf(
                fingerprint=self.current_fingerprint,
                birth_tick=self.current_birth_tick,
                birth_digest=self.current_birth_digest,
                verified_tick=tick,                # [P] A8
                verified_digest=digest,            # [P] A8
                roots_q=self.current_roots_q,
            )
            self.leaves.append(leaf)
            self.ticks_since_leaf = 0
            self._emitted = True
            return leaf
        return None

    def current_persistence(self, tick: int) -> int:
        if self.current_fingerprint is None:
            return 0
        return tick - self.current_birth_tick

    def closure_candidate(self, threshold: int) -> bool:
        """Current structure verified (emitted at its crossing) AND
        quiet for `threshold` ticks. An unstarted tracker is unborn,
        not closed."""
        if self.current_fingerprint is None or not self._emitted:
            return False
        return self.ticks_since_leaf >= threshold
