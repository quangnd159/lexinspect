# Study 4 text-free export and recompute

The Stage-1 access route (tier 2 of `docs/validation/study4-archive.md`, section 7). The output folder and its documentation are in [`docs/validation/study4-textfree/`](../../../../docs/validation/study4-textfree/README.md).

| File | Role |
|---|---|
| `export.py` | Builds the folder from the private archive and the local caches (read-only), deterministically. `--check` rebuilds in memory and compares byte for byte. It proves every label file equivalent under the frozen validator and refuses to write if the guard finds text. |
| `recompute.py` | Reads only the folder and the public repository. It rebuilds a text-free shadow package and runs the frozen `analyse.main` (pilots) and `fixcheck.accept.acceptance_of` (gates, sensitivity) on it. It compares every result with the published documents and exits 1 on any difference. |
| `guard.py` | Scans a folder (or in-memory files) for text-bearing keys, for 30-character substrings of the source texts, guidelines and inventory, for PHRASE headwords, and for the harness's restricted fragments |
| `common.py` | Deterministic writers, order-preserving sub-stratum codes, and the label and item shapes with their equivalence proof (`verify_labels`) |
| `test_textfree.py` | Shape and guard unit tests on synthetic records. End-to-end recompute, a tamper test, the guard on the real folder, and `export --check`. |

```sh
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/export.py [--check]
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/recompute.py [--json OUT]
uv run --offline --no-sync python -I scripts/validation/study4_precision/textfree/guard.py
uv run --offline --no-sync python -I -m pytest scripts/validation/study4_precision/textfree/test_textfree.py
```

The frozen Study 4 scripts (`analyse.py`, `estimators.py`, `fixcheck/`) are imported, never copied or edited.
