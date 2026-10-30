# Study 4: PHRASE List permission (addendum)

This addendum records the answer to open point 1 of [`study4-archive.md`](study4-archive.md) (section 8) after the Stage-1 freeze. The archive is hashed by `study4-freeze.json`, so it is not edited; it still reads "permission pending".

| Date | From | Asked about | Answer |
| --- | --- | --- | --- |
| 2026-10-16 | Norbert Schmitt | The hosted app, and `phrase.json` with its added variant fields in the public repository | "I am fine with this, but the list is really Dr. Martinez's work." He cc'd Ron Martinez. |
| 2026-10-30 | Ron Martinez | The app, the open-source repository, and "the study materials based on the list", with full attribution to both authors | "As long as Norbert is also OK with it, I can also give the green light." |

Both authors attached no conditions beyond attribution. Schmitt called the list Martinez's work, and Martinez gave the permission. Martinez's condition is Schmitt's agreement, which was on record two weeks before. The emails are kept by the maintainer.

**What follows from the archive's own terms** (section 7):

- **Tier 4** (glosses, examples, the sense inventory `a761f159…`, the guidelines `276d35e8…`) was to be "published with the registration or the results once permission is given". The permission is now given. Released files must match the public SHA-256 values.
- **Tier 3** (full packages) was supervised-only "until the PHRASE redistribution permission is resolved". The PHRASE restriction is resolved. The packages still hold personal data, and the archive lists that as a separate reason to restrict them.

**Not yet updated:** the `license` field in `src/lexinspect/data/phrase.json` still reads "No stated terms of use". The file is detector data pinned by the freeze. `build_phase2.py` now emits the new wording, so the field changes at the next data rebuild, with a new evaluation build.

Each release, when it happens, is dated here.
