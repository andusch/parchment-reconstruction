"""Entry point for the review window.

This module does not import Qt. ``prw-review`` calls ``main``. The command
is unfrozen and is not a stable interface. The headless ``prw`` console does
not import this module.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

_MISSING = (
    "The review window needs PySide6-Essentials "
    "(LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only). "
    "From the checkout, install the ui group: uv sync --group ui"
)


def main(argv: Sequence[str] | None = None) -> int:
    """Open the review window, or print how to install PySide6."""
    try:
        from prw.review_qt import run
    except ImportError as exc:
        name = exc.name or ""
        if name.startswith("PySide6") or "PySide6" in str(exc):
            print(_MISSING, file=sys.stderr)
            return 2
        raise
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
