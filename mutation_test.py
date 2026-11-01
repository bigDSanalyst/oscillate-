#!/usr/bin/env python
"""Put each audit-drawer bug back and check that the suite fails on it.

A check that cannot fail on the bug it names is not a check (A18). This
script makes the mutation pass that found A18 repeatable: each mutant
reintroduces one drawer bug into a scratch copy of the repository, runs
the check suite there, and expects it to fail.

Every drawer row in STATUS.md must be accounted for, either as a mutant
here or in HAND_AUDIT with the reason no mutant exists. A row in neither
place fails the run, so a new drawer entry cannot be added without
deciding which it is.

Exit 0 only if the unmutated copy passes, every mutant is caught, and
every drawer row is accounted for. Adapted from dark-synth's
tools/mutation_test.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OBS = "src/oscillate/core/observable.py"
TRK = "src/oscillate/growth/tracker.py"
SWP = "src/oscillate/runtime/sweep.py"

# (drawer id, what the mutant puts back, [(file, old, new), ...]).
# `old` must occur exactly once in `file`; otherwise the mutant is
# stale and the run fails rather than testing nothing.
MUTANTS = [
    ("A1", "LS solution used most-recent-first as power order",
     [(OBS, "np.concatenate([a[::-1], [1.0 + 0j]])",
            "np.concatenate([a, [1.0 + 0j]])")]),
    ("A2", "u[t-1:t-M-1:-1] slice, empty at r=0",
     [(OBS, "A[r, :] = u[t - M:t][::-1]",
            "A[r, :] = u[t - 1:t - M - 1:-1]")]),
    ("A5", "warm-up reports emitted before the buffer is full",
     [(OBS, "        if len(self.otp.buf) < self.otp.window:     # [P] A5\n"
            "            return None\n",
            "")]),
    ("A7", "discriminant not normalised",
     [(OBS, "v *= abs(roots[i] - roots[j]) / (\n"
            "                    abs(roots[i]) + abs(roots[j]) + 1e-300)",
            "v *= abs(roots[i] - roots[j])")]),
    ("A8", "leaf emitted at death instead of at the crossing",
     [(TRK, "        if fingerprint != self.current_fingerprint:\n"
            "            self.birth_ticks.append(tick)          # a birth, not a death\n",
            "        if fingerprint != self.current_fingerprint:\n"
            "            if tick - self.current_birth_tick >= self.window:\n"
            "                self.leaves.append(Leaf(\n"
            "                    self.current_fingerprint, self.current_birth_tick,\n"
            "                    self.current_birth_digest, tick, digest,\n"
            "                    self.current_roots_q))\n"
            "                self.ticks_since_leaf = 0\n"
            "                self._emitted = True\n"
            "            self.birth_ticks.append(tick)          # a birth, not a death\n"),
      (TRK, "        if (not self._emitted\n"
            "                and tick - self.current_birth_tick >= self.window):",
            "        if (False and not self._emitted\n"
            "                and tick - self.current_birth_tick >= self.window):")]),
    ("A9", "episode of exactly W ticks admitted",
     [(TRK, "and tick - self.current_birth_tick >= self.window):",
            "and tick - self.current_birth_tick >= self.window - 1):")]),
    ("A10", "births not counted",
     [(TRK, "self.birth_ticks.append(tick)          # a birth, not a death",
            "pass")]),
    ("A18", "quiet counter not reset at the leaf",
     [(TRK, "            self.leaves.append(leaf)\n"
            "            self.ticks_since_leaf = 0\n",
            "            self.leaves.append(leaf)\n")]),
    ("A19", "register hash covers PREDICTIONS only",
     [(SWP, '{"predictions": PREDICTIONS, "config": CONFIG}, sort_keys=True,',
            'PREDICTIONS, sort_keys=True,')]),
]

# Drawer rows with no mutant, and why. These are defended by review
# only; listing them here is the admission, not a pass.
HAND_AUDIT = {
    "A3": "a smoke test described as weak was unrunnable; a property of "
          "the old test, not of the code",
    "A4": "rho read with the wrong sign: fixed by amending the prediction "
          "text, which the register hash pins (A19), not by code",
    "A6": "dead fallbacks replaced by assertions; removing an assertion "
          "changes no output a check can see",
    "A11": "trackers fed the previous tick's digest: harness ordering, "
           "exercised only by the sweep, which has no check yet",
    "A12": "W-probe spec presumed a buffer that did not exist; spec-level",
    "A13": "names referenced but never defined: an import-time failure, "
           "already caught by any import, so a mutant tests nothing new",
    "A14": "trackers never invoked from tick(): harness wiring, exercised "
           "only by the sweep, which has no check yet",
    "A15": "a suite referenced but never defined: same class as A13",
    "A16": "numpy scalars in JSONL rows: sweep serialisation, no check yet",
    "A17": "file handle not closed in finally: resource handling, no check",
    "A20": "a missing check, not a code bug; its falsifier is the A19 "
           "mutant above",
}

DRAWER_ROW = re.compile(r"^\|\s*(A\d+)\s*\|")


def drawer_ids(status: Path) -> list[str]:
    return [m.group(1) for line in status.read_text().splitlines()
            if (m := DRAWER_ROW.match(line))]


def _copy() -> Path:
    d = Path(tempfile.mkdtemp(prefix="osc-mut-")) / "repo"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc", ".pytest_cache", "*.egg-info",
        "build", "dist", "trace*.jsonl"))
    return d


def _env(repo: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src") + os.pathsep + env.get(
        "PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _imports_from(repo: Path) -> bool:
    """The copy must shadow any installed oscillate, or every mutant
    would be tested against the unmutated source and 'survive'."""
    r = subprocess.run(
        [sys.executable, "-c", "import oscillate; print(oscillate.__file__)"],
        cwd=repo, env=_env(repo), capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip().startswith(str(repo))


def _suite_fails(repo: Path) -> bool:
    r = subprocess.run([sys.executable, "run_checks.py"], cwd=repo,
                       env=_env(repo), capture_output=True, text=True,
                       timeout=600)
    return r.returncode != 0


def _apply(repo: Path, edits) -> str | None:
    for rel, old, new in edits:
        p = repo / rel
        src = p.read_text()
        n = src.count(old)
        if n != 1:
            return f"stale mutant: expected 1 match in {rel}, found {n}"
        p.write_text(src.replace(old, new))
    return None


def run() -> tuple[bool, list[dict]]:
    results = []
    ok = True

    ids = drawer_ids(ROOT / "STATUS.md")
    mutated = {m[0] for m in MUTANTS}
    for i in ids:
        if i not in mutated and i not in HAND_AUDIT:
            results.append({"id": i, "status": "UNACCOUNTED",
                            "why": "drawer row with no mutant and no "
                                   "HAND_AUDIT entry"})
            ok = False
    for i in sorted(mutated | set(HAND_AUDIT)):
        if i not in ids:
            results.append({"id": i, "status": "UNACCOUNTED",
                            "why": "listed here but not in the drawer"})
            ok = False

    base = _copy()
    try:
        if not _imports_from(base):
            return False, results + [{"id": "baseline", "status": "BROKEN",
                                      "why": "copy does not shadow the "
                                             "installed package"}]
        if _suite_fails(base):
            return False, results + [{"id": "baseline", "status": "BROKEN",
                                      "why": "unmutated suite fails"}]
    finally:
        shutil.rmtree(base.parent, ignore_errors=True)

    for aid, what, edits in MUTANTS:
        repo = _copy()
        try:
            err = _apply(repo, edits)
            if err:
                results.append({"id": aid, "status": "STALE", "why": err})
                ok = False
                continue
            caught = _suite_fails(repo)
            results.append({"id": aid, "status": "CAUGHT" if caught
                            else "SURVIVED", "why": what})
            ok = ok and caught
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    for aid, why in sorted(HAND_AUDIT.items(), key=lambda x: int(x[0][1:])):
        results.append({"id": aid, "status": "HAND-AUDIT", "why": why})
    return ok, results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    ok, results = run()
    if a.json:
        print(json.dumps({"ok": ok, "results": results}, indent=2))
    else:
        for r in results:
            print(f"[{r['status']:11s}] {r['id']:8s} {r['why']}")
        caught = sum(r["status"] == "CAUGHT" for r in results)
        print(f"\n{caught}/{len(MUTANTS)} mutants caught; "
              f"{len(HAND_AUDIT)} drawer rows hand-audit only")
        print("ALL MUTANTS CAUGHT" if ok else "MUTATION TEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
