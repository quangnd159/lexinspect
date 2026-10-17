"""Study 4 fix-check harness for the lexinspect 0.4.0 candidate (development only).

Implements docs/validation/study4-fix-protocol.md, sections "Diff and label
transfer" and "Held-out check", against the round-1 candidate ledger
(.cache/validation/study4_fix040/CANDIDATE_LEDGER.md: 12 families, J = 68,
a = .05/68). Entry point: `cli.py` (subcommands ledger, collect, run,
verify-baseline, diff, sample, assign, flash, accept, dryrun).

The frozen Study 4 scripts next to this package (build.py, analyse.py,
estimators.py, frame.py, batches.py) are imported, never copied or edited.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY4 = HERE.parent  # scripts/validation/study4_precision
REPO = HERE.parents[3]
if str(STUDY4) not in sys.path:
    sys.path.insert(0, str(STUDY4))
