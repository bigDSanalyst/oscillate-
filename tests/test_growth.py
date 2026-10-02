"""Check group 3: leaf tracker. Ground truth: window arithmetic.

Conventions pinned by A9:
  episode = ticks b..e inclusive, length L = e - b + 1
  verification needs L >= W + 1, i.e. first disjoint tick = b + W
  n_births = n_episodes - 1 per agent: initial state is a start.
"""
from oscillate.growth.tracker import LeafTracker


def test_terminal_leaf():
    """[A8] Absorbing structure emits at the crossing tick, not at
    death. The terminal leaf is in the ledger when closure fires."""
    lt = LeafTracker(window=10, agent=0)
    fp = b"z" * 32
    for t in range(25):
        lt.observe(t, fp, f"d{t}".encode())
    assert len(lt.leaves) == 1
    assert lt.leaves[0].verified_tick == 10     # not the death


def test_persistence_gate():
    """[A8] Crossing vs death with both present: fp_b born at 5,
    verified at 15 (birth + W), dies at 21; the leaf carries 15, not
    21. The only case that discriminates crossing-emission from
    death-emission when both events occur."""
    lt = LeafTracker(window=10, agent=0)
    fp_a, fp_b, fp_c = b"a" * 32, b"b" * 32, b"c" * 32
    for t in range(5):
        lt.observe(t, fp_a, f"d{t}".encode())       # sub-W: no leaf
    emitted = None
    for t in range(5, 21):
        r = lt.observe(t, fp_b, f"d{t}".encode())
        if r is not None:
            emitted = r
    assert emitted is not None
    assert (emitted.fingerprint, emitted.birth_tick,
            emitted.verified_tick) == (fp_b, 5, 15)
    lt.observe(21, fp_c, b"d21")                    # the death: silent
    assert len(lt.leaves) == 1 and len(lt.birth_ticks) == 2


def test_threshold_disjointness():
    """[A9] Episode of exactly W ticks is unverified. First verified
    episode is W+1 ticks long, crossing at birth + W."""
    lt = LeafTracker(window=10, agent=0)
    fp_a, fp_b = b"a" * 32, b"b" * 32
    for t in range(10):
        lt.observe(t, fp_a, b"d")
    for t in range(10, 40):
        lt.observe(t, fp_b, b"d")
    assert any(l.fingerprint == fp_b and l.verified_tick == 20
               for l in lt.leaves)
    assert all(l.fingerprint != fp_a for l in lt.leaves)


def test_flapping_is_silent():
    """[A10] Sub-W flapping: no leaves, no closure, births counted.
    The birth channel is the only growth-side signal at the resolution
    limit."""
    lt = LeafTracker(window=10, agent=0)
    fp_a, fp_b = b"a" * 32, b"b" * 32
    for t in range(40):
        lt.observe(t, fp_a if (t // 2) % 2 == 0 else fp_b, b"d")
    assert lt.leaves == []
    assert not lt.closure_candidate(threshold=5)
    assert len(lt.birth_ticks) > 0


def test_structure_identity():
    """Same fingerprint at two times: two leaves, same fp, different
    ticks, different seeds (the seed binds at occurrence)."""
    lt = LeafTracker(window=5, agent=0)
    fp_a, fp_b = b"a" * 32, b"b" * 32
    for t in range(7):
        lt.observe(t, fp_a, f"d{t}".encode())
    for t in range(7, 14):
        lt.observe(t, fp_b, f"d{t}".encode())
    for t in range(14, 21):
        lt.observe(t, fp_a, f"d{t}".encode())
    assert len(lt.leaves) == 3
    first, third = lt.leaves[0], lt.leaves[2]
    assert first.fingerprint == third.fingerprint
    assert first.verified_tick != third.verified_tick
    assert first.seed != third.seed


def test_closure():
    """[R1] range(11): emission needs an observe at tick 10;
    range(10) asserted an event at a tick it never fed."""
    lt = LeafTracker(window=10, agent=0)
    fp = b"z" * 32
    for t in range(11):
        assert not lt.closure_candidate(threshold=3)
        lt.observe(t, fp, b"d")
    assert lt.leaves and lt.leaves[0].verified_tick == 10
    for t in range(11, 20):
        lt.observe(t, fp, b"d")
    assert lt.closure_candidate(threshold=3)


def test_quiet_is_counted_from_the_leaf():
    """[A18] Closure needs `threshold` quiet ticks AFTER the leaf, not
    since the tracker started: a structure verified at tick 10 is not
    closed at tick 11, however long it lived before verifying.
    test_closure waits long enough that closure fires either way, so it
    cannot see a tracker that never resets its quiet counter."""
    lt = LeafTracker(window=10, agent=0)
    fp = b"z" * 32
    for t in range(11):
        lt.observe(t, fp, b"d")
    assert lt.leaves and lt.leaves[0].verified_tick == 10
    assert not lt.closure_candidate(threshold=3)
    for t in range(11, 13):
        lt.observe(t, fp, b"d")
    assert not lt.closure_candidate(threshold=3)
    lt.observe(13, fp, b"d")
    assert lt.closure_candidate(threshold=3)
