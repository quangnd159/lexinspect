# Contributing

Thanks for helping. Bug reports, wrong results, data corrections and small focused pull requests are all welcome.

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Before you start

- Read [CAVEATS.md](CAVEATS.md). Many apparent bugs are documented trade-offs (the small spaCy model, lemma-only lookups, partial marker lists). If a caveat is wrong or missing, that's worth an issue too.
- For anything larger than a fix, open an issue first so we can agree on the approach.

## Set up

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/quangnd159/lexinspect.git
cd lexinspect
uv sync --extra dev --extra web
uv run lexinspect serve --reload     # web UI at http://127.0.0.1:8000
```

Local runs have no Turnstile keys, so the API is open; you don't need a Cloudflare account.

## Make a change

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

The Quality workflow runs the tests and Ruff on every pull request.

- **Tests.** Add or update a test for any change in output. Results are JSON, so assert on the fields that changed.
- **Output shape.** Treat the JSON as a public API. Adding a field is fine; renaming or removing one needs a `SCHEMA_VERSION` bump in `_schema.py` and a note in the pull request.
- **Web UI.** Plain HTML, CSS and JavaScript in `src/lexinspect/static/`, with no framework or build step. Keep it that way.
- **Data files.** Don't edit the JSON under `src/lexinspect/data/` by hand. Change the builder in `scripts/build_data/` and regenerate. New data needs a licence that allows redistribution, recorded in `data/SOURCES.md` and `data/LICENSE.md`.

## Pull requests

Keep each pull request to one change, explain what it fixes and how you checked it, and link the issue. By contributing you agree that your code is released under the project's MIT licence.
