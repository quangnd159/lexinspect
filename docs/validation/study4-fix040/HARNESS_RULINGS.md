# Maintainer rulings on HARNESS_REPORT.md §7.1 (ambiguous protocol clauses)

2026-10-17. Made before any fix-check text was collected and before any label. Each ruling picks the reading that follows the protocol's text literally; where the protocol leaves room, it picks the reading that is conservative against the candidate.

- **A1. Accept** one SRS for the REMOVED cell and the genuine-deletion frame. They are the same population, so a second SRS would only add labelling cost.
- **A2. Accept** counting a dropped sibling claim at a retained span as a genuine deletion in the removal gate. This is conservative.
- **A3. Accept** the literal reading. The removal gate uses the genuine-deletion subset (the REMOVED cell). Unresolved span changes count as possible losses in U_loss, as the protocol states ("unresolved crosswalks count conservatively as possible losses"). Adding them to the removal frame would change the frozen acceptance calculation, which needs a reviewed amendment. Their size is reported for every round.
- **A4. Accept** sampling and labelling every family frame. This is the literal reading of "each frame". The cost is accepted.
- **A5. Accept** and disclose: a breach certificate can be unattainable for N > 1,333. Those frames can only pass or be inconclusive, and neither result keeps a failing candidate.
- **A6. Accept** the declared power grids and planning shares.
- **A7. Accept** separate batches as separate fresh sessions. Disclose that A and B each see all items across their sessions.
- **A8. Accept** seeds derived by SHA-256 from one archived round seed.
- **A9. Accept.** There is no development label transfer in the fix-check. The development-pilot rebuild comes later.
- **A10. Accept** the snapshot policy: pool listings are frozen; bodies are fetched at collection and archived with SHA-256. The `retrieved` field caveat is disclosed.
