"""Check group 4: the anchored register. Ground truth: run-logs/.

The register was OTS-anchored before the sweep (D4). These checks fail
if PREDICTIONS or CONFIG change after anchoring, or if the hash stops
covering either of them (A19), so the sweep's pre-flight refuses to run
against a register other than the anchored one.
"""
import json
from hashlib import sha256
from pathlib import Path

from oscillate.runtime.predictions import CONFIG, PREDICTIONS
from oscillate.runtime.sweep import register_sha256

LOGS = Path(__file__).resolve().parent.parent / "run-logs"
OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"


def _anchored() -> str:
    return (LOGS / "register.sha256").read_text().split()[0]


def test_register_matches_anchor():
    """[A19] The code's register hash is the anchored one. Editing a
    prediction or a config value, or hashing PREDICTIONS alone, fails
    here."""
    assert register_sha256() == _anchored()


def test_register_file_is_the_hashed_bytes():
    """register.json is the exact byte string register_sha256() hashes,
    and it decodes to the current PREDICTIONS and CONFIG."""
    raw = (LOGS / "register.json").read_bytes()
    assert sha256(raw).hexdigest() == _anchored()
    assert json.loads(raw) == {"predictions": PREDICTIONS, "config": CONFIG}


def test_proof_commits_to_the_register():
    """The committed .ots proof is a sha256 proof over the anchored
    hash. This parses the header only; whether the proof reaches a
    Bitcoin block is recorded in STATUS.md, not checked here."""
    d = (LOGS / "register.json.ots").read_bytes()
    assert d.startswith(OTS_MAGIC)
    assert d[len(OTS_MAGIC)] == 1                 # proof format version
    assert d[len(OTS_MAGIC) + 1] == 0x08          # file hash op: sha256
    off = len(OTS_MAGIC) + 2
    assert d[off:off + 32].hex() == _anchored()
