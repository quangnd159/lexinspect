# Fix-check round 1: acceptance

**Status: fail** — failed: a deterministic breach certificate holds; the checked candidate cannot be kept

a = .05/68 = 0.000735294

Mode: production; production_eligible: True

## metadiscourse: fail

| removal frame | N | n | k_lo | k_hi | bound | ≤ .15 | certificate |
|---|---|---|---|---|---|---|---|
| COMPLETE | 2625 | 200 | 23 | 24 | 0.2053 | False | False |
| MD-A | 1741 | 200 | 25 | 25 | 0.2096 | False | False |
| MD-B | 89 | 89 | 24 | 25 | 0.2809 | False | True |
| MD-C | 49 | 49 | 12 | 12 | 0.2449 | False | True |
| MD-D | 139 | 139 | 13 | 13 | 0.0935 | True | False |
| MD-E | 27 | 27 | 13 | 13 | 0.4815 | False | True |
| MD-F | 72 | 72 | 14 | 14 | 0.1944 | False | True |
| MD-G | 88 | 88 | 12 | 13 | 0.1477 | True | False |
| MD-H | 549 | 200 | 4 | 5 | 0.0692 | True | False |
| MD-I | 0 | 0 | 0 | 0 | n/a | None | False |
| PH-A | 0 | 0 | 0 | 0 | n/a | None | False |
| PH-B | 0 | 0 | 0 | 0 | n/a | None | False |
| PH-C | 0 | 0 | 0 | 0 | n/a | None | False |

| outcome | U_loss | L_success | fraction | ≤ .05 | definite losses / N_base | certificate |
|---|---|---|---|---|---|---|
| STRICT | 449.2 | 6394.2 | 0.0703 | False | 19/16249 | False |
| LENIENT | 601.6 | 7506.4 | 0.0801 | False | 24/16249 | False |

## phrase: pass

| removal frame | N | n | k_lo | k_hi | bound | ≤ .15 | certificate |
|---|---|---|---|---|---|---|---|
| COMPLETE | 310 | 200 | 3 | 3 | 0.0452 | True | False |
| MD-A | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-B | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-C | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-D | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-E | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-F | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-G | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-H | 0 | 0 | 0 | 0 | n/a | None | False |
| MD-I | 0 | 0 | 0 | 0 | n/a | None | False |
| PH-A | 203 | 200 | 5 | 5 | 0.0345 | True | False |
| PH-B | 79 | 79 | 0 | 0 | 0.0000 | True | False |
| PH-C | 29 | 29 | 1 | 1 | 0.0345 | True | False |

| outcome | U_loss | L_success | fraction | ≤ .05 | definite losses / N_base | certificate |
|---|---|---|---|---|---|---|
| STRICT | 15.0 | 3227.0 | 0.0046 | True | 4/5048 | False |
| LIST_LENIENT | 15.0 | 3236.8 | 0.0046 | True | 4/5048 | False |
