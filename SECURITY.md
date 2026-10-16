# Security

## Reporting a vulnerability

Please don't open a public issue. Report it privately through GitHub: **Security → Report a vulnerability** on this repository ([direct link](https://github.com/quangnd159/lexinspect/security/advisories/new)).

Include what you found, how to reproduce it, and what an attacker could do with it. You'll get a reply within a week. This is a one-person, unpaid project, so there is no bug bounty.

## Scope

In scope: the code in this repository and the hosted app at `lexinspect.dqnotes.com`. That includes the analysis API, the Turnstile human check and its pass cookie (`src/lexinspect/_human.py`), and anything that would let someone run analyses at scale without passing the check.

Out of scope: the limits already documented in [CAVEATS.md](CAVEATS.md) (for example, reusing a pass cookie for its hour), volumetric denial of service, and findings that only affect a self-hosted copy you configured.

Please don't load-test the hosted app; run lexinspect locally instead.
