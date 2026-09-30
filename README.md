# oscillate

> Oscillation is the substrate — the first cut, and the thing that never stops.
> A field that reads where a system sits relative to its own boundary:
> ordered, edge, disordered.
> Subresultant-chain detector; theory proved, runtime in progress.

## What this is

A framework for reading the phase state of a dynamical system or agent —
where it is relative to its own boundary, not just what its state is.

- **Field** — holds global phase state, hands a local agent a compressed reading
- **Reading** — fixed-size: regime, distance, signature, digest
- **Detector** — swappable; discrete (subresultant chain) drafted, the
  continuous side (early-warning signals, blowup precursors) planned
  behind the same protocol
- **Growth chain** — leaves as verified structures, seeds as their digests,
  closure on sustained exhaustion

## What this is not

- Not another agent runtime. Field sits above runtimes, not beside them.
- Not a sandbox. Guard and containment are separate; this reads, not enforces.
- Not finished. Theory is proved; the runtime is drafted; the checks are
  written; the sweep has not been run.

## Status

See [STATUS.md](STATUS.md). Passing `run_checks.py` makes `core` and
`growth` `[run]`: the algebra against classical identities, the tracker
against designed arithmetic. The runtime modules have no check of that
kind — their ground truth is the pre-registered prediction set, and
their first `[run]` arrives with the first trace in `run-logs/`.
Until then, everything in `src/oscillate/runtime/` is `[t]`.

## Papers

- [1] The Commutator of Two Companion Matrices Has Rank at Most Two
  — DOI 10.5281/zenodo.21857156
- [2] The Companion Commutator Invariant is a Subresultant
- [3] The Signature of the Companion Commutator Invariant
- [12] Commutator Trace Invariants in LLMs — DOI 10.5281/zenodo.20338451

Papers are on Zenodo. Not duplicated in this repository.

## Design rules

1. **Nothing self-declared, nothing trusted.** Every claim carries a marker:
   `[V]` classical, `[A]` architectural choice, `[P]` patch to a named earlier
   draft, `[t]` traced/derived, `[run]` executed.
2. **A layer that did not run is not a layer that passed.** A check suite that
   exits 0 on partial coverage is not a check suite.
3. **The signal is membership, not value.** Invariants are constant on a class;
   the information is in crossing the class boundary.
4. **The observer only sees observables.** A detector that reads internal state
   is not the same detector as one that reads output, even when both compute.
5. **What you can prove, prove; what you can only predict, pre-register;
   what you can only observe, log.**

## Audits

Every bug caught in the drafting of this repository is recorded in
[STATUS.md](STATUS.md#audit-drawer), with how it was caught. That is the
same discipline the framework asks of others.

## License

Apache 2.0. See [LICENSE](LICENSE).
