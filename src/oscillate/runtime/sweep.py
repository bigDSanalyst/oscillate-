"""The sweep fixture: the run that converts [t] to [run].

Pre-flights every check group via run_checks.py, then writes one
append-only JSONL row per tick. Run from the repository root.

[P] D1: default path is run-logs/trace.jsonl; the .gitignore ignores
run-logs/trace*.jsonl, not run-logs/, so small artifacts (register
hash, .ots proofs, run_checks output) can be committed.
[P] D4: header pins config, seed, environment, and register sha256.
The register itself must be OTS-anchored BEFORE the sweep runs;
one anchor at close proves coexistence, two anchors prove ordering.
[P] D5: the anchored hash covers CONFIG as well as PREDICTIONS. P4 is
conditioned on T and W, so a register hash over PREDICTIONS alone
would not show CONFIG edited after anchoring.
[P] C2: rt.summarize() inside try, after loop, before finally.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from hashlib import sha256

import numpy as np

from ..core.observable import ObservableSubresultantDetector
from ..growth.tracker import LeafTracker
from .body import KuramotoBody
from .detector import SubresultantDetector
from .field import Field
from .harness import DualRuntime
from .predictions import CONFIG, PREDICTIONS


def register_sha256() -> str:
    """[P] D5: the register is the predictions AND the config they are
    conditioned on."""
    return sha256(json.dumps(
        {"predictions": PREDICTIONS, "config": CONFIG}, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()


def _checks_pass() -> bool:
    r = subprocess.run(
        [sys.executable, "run_checks.py"],
        capture_output=True, text=True)
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode == 0


class TraceWriter:
    """Append-only JSONL, one row per tick. open('x') refuses to
    clobber a prior run; the pipeline is deterministic given the seed,
    so the seed makes the run reproducible and the log makes it
    complete."""

    def __init__(self, path: str, config: dict, predictions: dict):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.f = open(path, "x")
        self._emit({
            "type": "oscillate.trace.v1",
            "config": config,
            "predictions": predictions,
            "predictions_sha256": register_sha256(),
            "env": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
            },
        })

    def row(self, obj: dict) -> None:
        self._emit(obj)

    def _emit(self, obj: dict) -> None:
        self.f.write(json.dumps(
            obj, sort_keys=True, separators=(",", ":")) + "\n")
        self.f.flush()

    def close(self) -> None:
        self.f.close()


def run_sweep(path: str = "run-logs/trace.jsonl") -> None:
    if not _checks_pass():
        raise SystemExit("checks failed; sweep not started")

    rng = np.random.default_rng(CONFIG["seed"])
    field = Field(CONFIG["N"])
    bodies = [KuramotoBody(CONFIG["D"], 0.2, int(s))
              for s in rng.integers(1e6, size=CONFIG["N"])]
    obs = [ObservableSubresultantDetector(
               degree=CONFIG["degree"],
               n_carrier=CONFIG["n_carrier"],
               window=CONFIG["window"],
               lag=CONFIG["lag"])
           for _ in bodies]
    jac = [SubresultantDetector(lag=CONFIG["lag"]) for _ in bodies]
    trackers = [LeafTracker(CONFIG["window"], i)
                for i in range(CONFIG["N"])]

    rt = DualRuntime(field, bodies, obs, jac, leaf_trackers=trackers)
    tw = TraceWriter(path, CONFIG, PREDICTIONS)
    try:
        Ks = np.linspace(*CONFIG["K"], CONFIG["T"])
        for t in range(CONFIG["T"]):
            rt.tick(float(Ks[t]))
            row = rt.trace[-1]
            tick = int(field.tick_no)
            tw.row({
                "tick": tick,
                "K": float(row[1]),
                "r": float(row[2]),
                "rho_o": rt.last_rho_o,
                "rho_j": rt.last_rho_j,
                "gap": float(row[5]) if row[5] is not None else None,
                "regime_o": row[3].value,
                "regime_j": (row[4].value if row[4] is not None
                             else None),
                "kappa_o": int(row[6]),
                "kappa_j": int(row[7]),
                "disc": (float(row[8]) if np.isfinite(row[8])
                         else None),
                "births": sum(
                    1 for tr in trackers
                    if tr.birth_ticks
                    and tr.birth_ticks[-1] == tick),
                "leaves": sum(
                    1 for tr in trackers
                    if tr.leaves
                    and tr.leaves[-1].verified_tick == tick),
                "closed": sum(
                    tr.closure_candidate(CONFIG["closure_threshold"])
                    for tr in trackers),
                "roots": [list(rep.roots_q) if rep is not None else None
                          for rep in rt.last_reps_o],
                "digest": field.digest.hex(),
            })
        rt.summarize()          # [P] C2: A/B summary to stdout
    finally:
        tw.close()


if __name__ == "__main__":
    run_sweep()
