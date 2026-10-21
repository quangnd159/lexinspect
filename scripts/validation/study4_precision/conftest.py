"""Two fix-check tests whose live-tree premise ended with the fix check.

They stay in fixcheck/ unchanged, because today's fixcheck/ is byte-identical
to the harness bound in round 2's freeze record. They run as strict expected
failures (an AssertionError is expected; passing, or any other error, fails the
suite). pilot040/test_fixcheck_history.py checks against history what they
protected, and pins the exact reason each one now fails.
"""

from __future__ import annotations

import pytest

SUPERSEDED = {
    "fixcheck/test_r9.py::test_g1_g4_real_round1_still_authenticates_against_this_tree": (
        "G1 gate for round-2 collection: round 1's bound files equal the live tree. It held "
        "through round 2's registration; the preregistration was edited for Stage 1 afterwards "
        "(pilot040/test_fixcheck_history.py)"
    ),
    "fixcheck/test_fixcheck.py::test_pinned_src_record_checks_tree_and_lock": (
        "uses the live repository as the --pinned-src candidate checkout; the repository now "
        "holds the v0.4.0 lock, not dec79bc's (pilot040/test_fixcheck_history.py)"
    ),
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        for key, reason in SUPERSEDED.items():
            if item.nodeid.endswith(key):
                item.add_marker(
                    pytest.mark.xfail(reason=reason, strict=True, raises=AssertionError)
                )
