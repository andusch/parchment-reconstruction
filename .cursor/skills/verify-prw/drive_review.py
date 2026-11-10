#!/usr/bin/env python3
"""Drive ``prw-review`` on the offscreen Qt platform and print the window.

``prw.review_window.main`` blocks in ``QApplication.exec`` and prints
nothing. This script calls that entry, reads the widgets after rank
settles, and exits. It is part of verify-prw, not a product command.

Offscreen Qt can segfault while the process tears the platform plugin
down. The report is flushed and the process exits with ``os._exit`` so
the transcript is that report. ``tests/test_review_window.py`` uses the
same exit. That test is not this proof.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Sequence

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from prw.review_qt import ReviewWindow
from prw.review_window import main as review_main

_TIMEOUT_MS = 60_000
_CONNECTED: set[int] = set()
_FINISHED = False


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the review entry and print one JSON report."""
    args = list(sys.argv[1:] if argv is None else argv)
    load_synthetic = "--load-synthetic" in args
    if load_synthetic:
        args = [arg for arg in args if arg != "--load-synthetic"]
        if "--image" in args:
            print(
                "--load-synthetic does not take --image.",
                file=sys.stderr,
            )
            return 2
    _install_hooks(load_synthetic=load_synthetic)
    return review_main(args)


def _install_hooks(*, load_synthetic: bool) -> None:
    original_show = ReviewWindow.show
    original_rank = ReviewWindow.rank

    def show(self: ReviewWindow) -> None:
        original_show(self)
        QTimer.singleShot(_TIMEOUT_MS, _timeout)
        if load_synthetic:
            QTimer.singleShot(0, lambda: _kick_synthetic(self))

    def rank(self: ReviewWindow) -> None:
        _connect(self)
        original_rank(self)

    ReviewWindow.show = show  # type: ignore[method-assign]
    ReviewWindow.rank = rank  # type: ignore[method-assign]


def _kick_synthetic(window: ReviewWindow) -> None:
    _connect(window)
    _click(window, "Load synthetic pair")


def _connect(window: ReviewWindow) -> None:
    if id(window) in _CONNECTED:
        return
    _CONNECTED.add(id(window))
    window.settled.connect(lambda: _on_settled(window))


def _on_settled(window: ReviewWindow) -> None:
    global _FINISHED
    if _FINISHED:
        return
    if window.status.text() == "Ranking joins off the review thread.":
        return
    _FINISHED = True
    print(json.dumps(_capture(window), sort_keys=True), flush=True)
    sys.stdout.flush()
    os._exit(0)


def _timeout() -> None:
    print("rank timed out", file=sys.stderr)
    os._exit(3)


def _capture(window: ReviewWindow) -> dict[str, object]:
    lines_before = _lines(window)
    report: dict[str, object] = {
        "banner": window.banner.text(),
        "caption": window.caption.text(),
        "code_version": window.code_version.text(),
        "legend": window.legend.text(),
        "lines_before": lines_before,
        "note": window.decision_note.text(),
        "outlines": window.outlines.text(),
        "status": window.status.text(),
        "thread_id": window.last_rank_thread_id,
        "title": window.windowTitle(),
        "ui_thread_id": threading.get_ident(),
    }
    if window.status.text() != "Ranked hypotheses.":
        report["lines_after_defer"] = lines_before
        report["lines_after_keep"] = lines_before
        report["lines_after_reject"] = lines_before
        report["pixmap_height"] = 0
        report["pixmap_width"] = 0
        report["status_after_decisions"] = window.status.text()
        return report
    _click(window, "Reject hypothesis")
    report["lines_after_reject"] = _lines(window)
    window.hypotheses.setCurrentRow(1)
    _click(window, "Keep as hypothesis")
    report["lines_after_keep"] = _lines(window)
    window.hypotheses.setCurrentRow(2)
    _click(window, "Defer")
    report["lines_after_defer"] = _lines(window)
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.processEvents()
    pixmap = window.placement_view.grab()
    report["pixmap_height"] = pixmap.height()
    report["pixmap_width"] = pixmap.width()
    report["status_after_decisions"] = window.status.text()
    return report


def _lines(window: ReviewWindow) -> list[str]:
    return [
        window.hypotheses.item(index).text()
        for index in range(window.hypotheses.count())
    ]


def _click(window: ReviewWindow, text: str) -> None:
    matches = [
        button for button in window.findChildren(QPushButton) if button.text() == text
    ]
    if len(matches) != 1:
        print(f"expected one button {text!r}", file=sys.stderr)
        os._exit(4)
    matches[0].click()


if __name__ == "__main__":
    raise SystemExit(main())
