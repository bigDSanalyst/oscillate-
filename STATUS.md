# Status

**Last updated:** commit 2, runtime drafted; sweep not yet run.

Every claim in this repository carries one of these markers:

| Marker | Meaning |
|---|---|
| `[V]` | Classical result. Cited or textbook. |
| `[A]` | Architectural choice. Correctness is a matter of design, not proof. |
| `[P]` | Patch to a named earlier draft. Names the bug it fixes. |
| `[t]` | Traced / derived. Consistent with the design. **Not executed.** |
| `[run]` | Executed. sha256(output) recorded here; proofs in `run-logs/`; regenerate from the pinned seed and compare. |

The distinction between `[t]` and `[run]` is load-bearing. A `[t]` claim about
runtime behaviour is a hypothesis. Discrepancies between what was traced and
what runs are findings.

## What is proved

| Component | Status | Evidence |
|---|---|---|
| Commutator rank ≤ 2 for companion matrices | `[V]` published | Paper [1], DOI |
| Hankel determinant = subresultant, up to sign | `[V]` published | Paper [2] |
| Invariant c = s₀s₂ − s₁² as a quadratic form | `[V]` published | Paper [2] |
| Signature (1, 2, n−3), definite on Weil locus | `[V]` published | Paper [3] |
| Commutator traces as LLM diagnostics | `[V]` empirical | Paper [12], DOI |

## What is drafted

| Module | Status | Checks |
|---|---|---|
| `core/subresultant.py` | `[t]` | `test_core.py::test_bezout_resultant_identity` |
| `core/observable.py` | `[t]` | `test_core.py::test_fit_recovers_known_modes`, `test_structure.py` |
| `growth/tracker.py` | `[t]` | `test_growth.py` (six tests) |
| `runtime/predictions.py` | `[t]` | register; hashed with `CONFIG` (D5) |
| `runtime/body.py` | `[t]` | none yet; first check is the sweep |
| `runtime/field.py` | `[t]` | none yet; first check is the sweep |
| `runtime/detector.py` | `[t]` | uses the checked `core/subresultant.py` functions (D3) |
| `runtime/harness.py` | `[t]` | none yet; first check is the sweep |
| `runtime/sweep.py` | `[t]` | pre-flights `run_checks.py`; refuses on failure |

The runtime modules import cleanly; none of them has executed a sweep.
Their first check is the sweep itself, which must not run before the
register hash is OTS-anchored.

## What is run

Nothing, yet. The check suite is written and the drafts contain every fix
identified during drafting, but `run_checks.py` has not been executed in
this repository. The first `[run]` marker in this file is the commit that
attaches a passing output.

## Checks

The suite in `tests/` encodes three check groups, in run order. Ground truth
is named per check; consistency checks are marked separately, because the
bugs caught during drafting both passed consistency and failed only against
ground truth.

| Check | Ground truth | Falsifies |
|---|---|---|
| `test_bezout_resultant_identity` | det(Bez(f,g)) = ±Res(f,g) | Bezout construction |
| `test_fit_recovers_known_modes` | known roots of known modes | LS coefficient order (A1) |
| `test_collision_event` | known event time from chirp | order-collapse timing |
| `test_structure_contract` | monic, degree m, deterministic | contract invariants |
| `test_terminal_leaf` | absorbing case | terminal-structure-in-ledger (A8) |
| `test_persistence_gate` | crossing vs death | emission policy (A8) |
| `test_threshold_disjointness` | W+1 episode length | off-by-one (A9) |
| `test_flapping_is_silent` | sub-W episodes | birth channel (A10) |
| `test_structure_identity` | same fp, different tick | identity policy |
| `test_closure` | verified + quiet | closure predicate |
| `test_rel_disc_is_dimensionless` | rel_disc in [0, 1], scale-invariant | discriminant normalisation (A7, A18) |
| `test_quiet_is_counted_from_the_leaf` | quiet ticks counted from the leaf | closure quiet-counter reset (A18) |

Run order is load-bearing: `test_fit_recovers_known_modes` fails on the
module as it existed before A1, and every check after it consumes the fit.
If that check fails, nothing downstream means anything.

## Predictions

The register is `src/oscillate/runtime/predictions.py`. Seven entries,
one conditioned. The register's `sha256` covers the predictions and the
`CONFIG` they are conditioned on (A19), and is recorded in the trace header at first `[run]`; a mismatch between the
recorded hash and a trace header means the register was edited after
the run.

## Audit drawer

Every bug found in the drafting of this repository, and how it was caught.

| ID | Bug | Caught by | Fix |
|---|---|---|---|
| A1 | LS solution placed most-recent-first, used as power-order | Root-sum check on M=2 | `a[::-1]` |
| A2 | `u[t-1:t-M-1:-1]` empty at r=0 (stop=-1 wraps) | Slice semantics review | `u[t-M:t][::-1]` |
| A3 | Smoke test described as weak; was unrunnable | Second-read | Replaced by check suite |
| A4 | rho semantically inverted between J-side and observable-side | Derivation of gap profile | Amended prediction; DRIFT/EDGE/SUPER read on (r, stability, disc) |
| A5 | Warmup reports read as SUPER (Bézout(p,p) ≡ 0) | Static review | Gate on buffer full |
| A6 | Fallback branches dead and wrong | Static review | Assertions |
| A7 | Discriminant magnitude degree-locked | Static review | `rel_disc` normalisation |
| A8 | Terminal leaf never emitted (death vs crossing) | Absorbing-case analysis | Crossing emission |
| A9 | Off-by-one in disjointness: W ticks admitted | Episode-length algebra | `t - birth ≥ W` |
| A10 | Flapping invisible under persistence gate | Sub-W analysis | Births as separate channel |
| A11 | Leaf tracker used previous tick's digest | Integration ordering | After `advance_digest` |
| A12 | W-probe spec presumed buffer that didn't exist | Memory check | 2W+lag ring buffer per agent |
| A13 | `row_rho_o`/`row_rho_j` referenced but never defined | Second-read | Means carried on runtime |
| A14 | Leaf trackers never invoked from `tick()` | Integration check | Loop after `advance_digest` |
| A15 | `_growth_suite()` referenced but never defined | Second-read | Sweep pre-flights `run_checks.py` |
| A16 | numpy scalars in JSONL rows | Serialization review | `float()` at boundary |
| A17 | `open("x")` without `try/finally` | Review | Handle closed in `finally` |
| A18 | Two checks could not fail: nothing checked `rel_disc` normalisation (A7's argmin is the same unnormalised), and `test_closure` waited long enough that closure fired without the quiet counter being reset at the leaf | Mutation: each bug put back one at a time; these two survived the suite | `test_rel_disc_is_dimensionless`, `test_quiet_is_counted_from_the_leaf`; each fails on its mutant |
| A19 | Register hash covered `PREDICTIONS` only; P4 is conditioned on `T` and `W`, so `CONFIG` could be edited after anchoring without the anchored hash changing | Review of what the anchor binds | `register_sha256()` hashes `{"predictions", "config"}` (D5) |

A18 is the mirror class: checks described as falsifying a bug that
could not fail on it. Found by putting each audit-drawer bug back and
watching the suite: nine of eleven were caught, these two were not.

A3, A13, A15 are one class: code described as running that had never
resolved. The last two landed in the turn that introduced the `[t]`/
`[run]` markers. The markers did not prevent them; they made them
cheap to find. That is the property the markers are for.

## OTS protocol

OTS proofs are committed in *pending* state. `ots stamp` returns a proof
that upgrades asynchronously as the Bitcoin transaction confirms;
`ots verify` on a fresh proof reports pending, not confirmed. Run
`ots upgrade <file>` before verifying, hours after stamping. The
committed `.ots` files are valid from creation; their confirmation is a
background fact about Bitcoin, not about the repo.
