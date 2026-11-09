"""Offscreen review window. The parent process does not import Qt."""

import json
import os
import subprocess
import sys
from pathlib import Path

from prw.synthetic_tear import generate_synthetic_leaf

_DRIVER = """
import json
import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from prw.review_qt import ReviewWindow


def click(window: ReviewWindow, text: str) -> None:
    matches = [
        button
        for button in window.findChildren(QPushButton)
        if button.text() == text
    ]
    if len(matches) != 1:
        raise AssertionError(text)
    matches[0].click()


def lines(window: ReviewWindow) -> list[str]:
    return [
        window.hypotheses.item(index).text()
        for index in range(window.hypotheses.count())
    ]


def main() -> int:
    app = QApplication(["prw-review-test"])
    window = ReviewWindow()
    window.add_pool_image("piece-a", Path(sys.argv[1]))
    window.add_pool_image("piece-b", Path(sys.argv[2]))
    window.set_parameters(
        foreground_threshold=1,
        pixels_per_mm=10,
        uncertainty=0.1,
        minimum_edge_length_mm=0,
        code_version="test-code",
    )
    window.show()
    loop = QEventLoop()
    window.settled.connect(loop.quit)
    QTimer.singleShot(60000, loop.quit)
    window.rank()
    loop.exec()
    if window.status.text() == "Ranking joins off the review thread.":
        print("rank timed out", file=sys.stderr)
        return 3
    before = lines(window)
    click(window, "Reject hypothesis")
    after_reject = lines(window)
    window.hypotheses.setCurrentRow(1)
    click(window, "Keep as hypothesis")
    after_keep = lines(window)
    app.processEvents()
    pixmap = window.placement_view.grab()
    report = {
        "lines_before": before,
        "lines_after_reject": after_reject,
        "lines_after_keep": after_keep,
        "banner": window.banner.text(),
        "note": window.decision_note.text(),
        "caption": window.caption.text(),
        "legend": window.legend.text(),
        "title": window.windowTitle(),
        "outlines": window.outlines.text(),
        "status": window.status.text(),
        "thread_id": window.last_rank_thread_id,
        "ui_thread_id": threading.get_ident(),
        "pixmap_width": pixmap.width(),
        "pixmap_height": pixmap.height(),
    }
    print(json.dumps(report), flush=True)
    # Offscreen Qt can segfault while the process tears the platform plugin down.
    # os._exit skips the normal flush, and a pipe is block-buffered, so the
    # report has to be flushed before that exit or CI reads an empty stdout.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
"""


def test_review_window_shows_hypotheses_and_keeps_alternatives(tmp_path: Path) -> None:
    images = tmp_path / "images"
    generate_synthetic_leaf(
        tmp_path / "benchmarks",
        images_dir=images,
        missing_fragment_percentage=0,
        edge_erosion=0,
        rotation=0,
        lighting_variation=0,
        random_seed=3,
        code_version="test-code",
    )
    found = sorted(images.glob("fragment-*.tif"))
    assert len(found) >= 3
    driver = tmp_path / "drive_review_window.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    completed = subprocess.run(
        [sys.executable, str(driver), str(found[0]), str(found[2])],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    before = report["lines_before"]
    after_reject = report["lines_after_reject"]
    after_keep = report["lines_after_keep"]
    assert before[0].startswith("Rank 1 hypothesis")
    assert all("hypothesis" in line for line in before)
    assert all("correct_join" not in line for line in before)
    assert len(after_reject) == len(before)
    assert all("hypothesis" in line for line in after_reject)
    assert any("rejected-via-ValidationDecision" in line for line in after_reject)
    assert len(after_keep) == len(before)
    assert "validation accept" in after_keep[1]
    assert "hypothesis" in after_keep[1]
    assert "status proposed" in after_keep[1]
    assert "hypothesis" in after_keep[0]
    assert "hypothesis" in report["banner"]
    assert "Rank 1" in report["banner"]
    assert "not a historical join" in report["banner"]
    assert "does not delete" in report["note"]
    assert "hypothesis" in report["caption"]
    assert "fragment-local" in report["caption"]
    assert "hypothesis" in report["legend"]
    assert "piece-a" in report["legend"]
    assert "piece-b" in report["legend"]
    assert "hypothes" in report["title"]
    assert "interpretation" in report["outlines"]
    assert report["thread_id"] not in (0, report["ui_thread_id"])
    assert report["pixmap_width"] > 0
    assert report["pixmap_height"] > 0


def test_review_help_mentions_hypotheses() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "prw.review_window", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "hypothes" in completed.stdout
