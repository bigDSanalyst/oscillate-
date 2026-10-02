#!/usr/bin/env python
"""Single entry point. Exit 0 only if every check group passes.

A group that does not run is not a group that passed.
"""
import subprocess
import sys


GROUPS = [
    ("core",      "tests/test_core.py"),
    ("structure", "tests/test_structure.py"),
    ("growth",    "tests/test_growth.py"),
]


def main() -> int:
    failed = []
    for name, path in GROUPS:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", path],
            capture_output=True, text=True)
        ok = r.returncode == 0
        print(f"[{'ok  ' if ok else 'FAIL'}] {name:10s} ({path})")
        if not ok:
            print(r.stdout)
            print(r.stderr, file=sys.stderr)
            failed.append(name)
    if failed:
        print(f"\nDEGRADED: {', '.join(failed)} did not pass")
        return 1
    print("\nALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
