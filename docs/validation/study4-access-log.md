# Study 4: access log for restricted material

The access arrangement is in [`study4-archive.md`](study4-archive.md), section 7. Each request for tier-3 (supervised) access and each inspection session is recorded here, in order, including refused or withdrawn requests.

This log is an append-only administrative record, versioned in git. It is outside the immutable scientific-input comparison: the Stage-1 freeze manifest names this file but doesn't hash it, so recording a request never requires rebuilding the manifest. The log's Stage-1 state is kept, unchanged, as [`study4-access-log.stage1.md`](study4-access-log.stage1.md), which the manifest does hash. Entries are only appended; a correction is a new entry. Before each inspection, `pilot040/freeze.py --check` verifies the scientific inputs, and the inspection's entry records the commit and SHA-256 of this file as it stood before the entry was added.

| Date (UTC) | Requester | Request (issue) | What was inspected | Commands run | Outcome | Log version (commit, SHA-256) |
|---|---|---|---|---|---|---|

No request has been received (as of 2026-10-21).
