"""Vercel entrypoint.

An explicit function in `api/` rather than the FastAPI framework preset's
auto-detected `main.py`: the Vercel CLI only applies `functions` settings
(`maxDuration`, `memory`, `excludeFiles` in vercel.json) to functions under
`api/`, and those limits are part of the cost and abuse budget. vercel.json
rewrites `/v1/*`, `/docs`, `/openapi.json` and `/healthz` here; everything else
is static and served from the CDN out of `public/`.

The module re-exports the app from the installed package (vendored from
uv.lock at build time), so `from lexinspect import ...` resolves normally.
"""

from lexinspect.api import app

__all__ = ["app"]
