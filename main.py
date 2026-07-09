"""Vercel entrypoint.

Vercel's Python runtime discovers an ASGI `app` by scanning a fixed set of
filenames (`main.py` among them) and resolves the module by *file path*, not by
installed-package name. Pointing it at `src/lexinspect/api.py` directly would
make that module's absolute `from lexinspect import ...` imports fail, so this
shim re-exports the real app from the installed package instead. `requirements.txt`
installs the project (the bare `.` line), which is what puts `lexinspect` on the
path.

Nothing else should live here — the app is defined in `lexinspect.api`.
"""

from lexinspect.api import app

__all__ = ["app"]
