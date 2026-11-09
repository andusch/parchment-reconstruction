"""Qt shell for ranked join hypotheses.

The widgets call ``prw.review``. They do not score joins. Rank runs on a
Qt thread because ADR-0005 keeps that work off the UI thread. One rank runs
at a time, and closing the window waits for it. Cancellation and a worker
process stay [Q-ENG-06](../../docs/OPEN_QUESTIONS.md#q-eng-06).
"""

from __future__ import annotations

import argparse
import tempfile
import threading
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from prw import __version__
from prw.review import (
    DECISION_NOTE,
    LOCAL_OPERATOR,
    REVIEW_BANNER,
    DecisionWord,
    PlacementSketch,
    PoolImage,
    RankRequest,
    ReviewFailure,
    ReviewSession,
    failure_line,
    hypothesis_lines,
    load_ranked_joins,
)
from prw.synthetic_tear import generate_synthetic_leaf

type Point = tuple[float, float]


class _RankThread(QThread):
    """One rank call. The UI thread does not enter ``load_ranked_joins``."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, request: RankRequest) -> None:
        super().__init__()
        self._request = request
        self.thread_id = 0

    def run(self) -> None:
        self.thread_id = threading.get_ident()
        try:
            outcome = load_ranked_joins(self._request)
        except (OSError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(outcome)


class _PlacementView(QWidget):
    """Polygon sketch. Source pixels are not drawn.

    ``fragment_local_mm`` is +x right and +y down, and so is this widget.
    """

    def __init__(self) -> None:
        super().__init__()
        self._sketch: PlacementSketch | None = None
        self.setMinimumSize(280, 220)

    def set_sketch(self, sketch: PlacementSketch | None) -> None:
        self._sketch = sketch
        self.update()

    def sketch(self) -> PlacementSketch | None:
        return self._sketch

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f4f1ea"))
        sketch = self._sketch
        if sketch is None:
            painter.end()
            return
        points = (
            *sketch.anchor_polygon,
            *sketch.moved_polygon,
            *sketch.anchor_edge,
            *sketch.moved_edge,
        )
        if not points:
            painter.end()
            return
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
        span_x = max(max(point[0] for point in points) - min_x, 1e-6)
        span_y = max(max(point[1] for point in points) - min_y, 1e-6)
        margin = 16
        width = max(self.width() - 2 * margin, 1)
        height = max(self.height() - 2 * margin, 1)
        scale = min(width / span_x, height / span_y)

        def map_point(point: Point) -> QPointF:
            return QPointF(
                margin + (point[0] - min_x) * scale,
                margin + (point[1] - min_y) * scale,
            )

        painter.setPen(QPen(QColor("#1f4e79"), 2))
        painter.setBrush(QColor(31, 78, 121, 40))
        painter.drawPolygon(_polygon(sketch.anchor_polygon, map_point))
        painter.setPen(QPen(QColor("#8c2f39"), 2))
        painter.setBrush(QColor(140, 47, 57, 40))
        painter.drawPolygon(_polygon(sketch.moved_polygon, map_point))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.setPen(QPen(QColor("#1f4e79"), 3))
        painter.drawPolyline(_polygon(sketch.anchor_edge, map_point))
        painter.setPen(QPen(QColor("#8c2f39"), 3))
        painter.drawPolyline(_polygon(sketch.moved_edge, map_point))
        painter.end()


class ReviewWindow(QMainWindow):
    """Lists ranked join hypotheses and a placement sketch of the selection."""

    settled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ranked join hypotheses")
        self.last_rank_thread_id = 0
        self._images: list[PoolImage] = []
        self._session: ReviewSession | None = None
        self._thread: _RankThread | None = None
        self._demo: tempfile.TemporaryDirectory[str] | None = None

        self.banner = QLabel(REVIEW_BANNER)
        self.banner.setWordWrap(True)
        self.decision_note = QLabel(DECISION_NOTE)
        self.decision_note.setWordWrap(True)
        self.outlines = QLabel("No outline was loaded.")
        self.outlines.setWordWrap(True)
        self.status = QLabel("Add images, then rank joins.")
        self.status.setWordWrap(True)
        self.caption = QLabel("")
        self.caption.setWordWrap(True)
        self.legend = QLabel("Select a hypothesis to see a placement sketch.")
        self.legend.setWordWrap(True)

        self.pool = QListWidget()
        self.hypotheses = QListWidget()
        self.hypotheses.currentItemChanged.connect(self._selection_changed)
        self.placement_view = _PlacementView()

        self.label_field = QLineEdit()
        self.label_field.setPlaceholderText("fragment label")
        self.threshold = QLineEdit("1")
        self.pixels_per_mm = QLineEdit("10")
        self.uncertainty = QLineEdit("0.1")
        self.minimum_edge = QLineEdit("0")
        self.code_version = QLineEdit(__version__)

        add_image = QPushButton("Add image")
        add_image.clicked.connect(self._add_image)
        remove_image = QPushButton("Remove image")
        remove_image.clicked.connect(self._remove_image)
        self.rank_button = QPushButton("Rank joins")
        self.rank_button.clicked.connect(self.rank)
        synthetic = QPushButton("Load synthetic pair")
        synthetic.clicked.connect(self.load_synthetic_pair)
        reject = QPushButton("Reject hypothesis")
        reject.clicked.connect(lambda: self._decide("reject"))
        keep = QPushButton("Keep as hypothesis")
        keep.clicked.connect(lambda: self._decide("accept"))
        defer = QPushButton("Defer")
        defer.clicked.connect(lambda: self._decide("defer"))

        parameters = QWidget()
        form = QVBoxLayout(parameters)
        form.addWidget(QLabel("Foreground threshold"))
        form.addWidget(self.threshold)
        form.addWidget(QLabel("Pixels per millimetre"))
        form.addWidget(self.pixels_per_mm)
        form.addWidget(QLabel("Scale uncertainty"))
        form.addWidget(self.uncertainty)
        form.addWidget(QLabel("Minimum edge length, millimetres"))
        form.addWidget(self.minimum_edge)
        form.addWidget(QLabel("Code version"))
        form.addWidget(self.code_version)
        form.addWidget(self.rank_button)
        form.addWidget(synthetic)
        form.addStretch(1)

        pool_column = QWidget()
        pool_layout = QVBoxLayout(pool_column)
        pool_layout.addWidget(QLabel("Fragment pool"))
        pool_layout.addWidget(self.label_field)
        pool_buttons = QHBoxLayout()
        pool_buttons.addWidget(add_image)
        pool_buttons.addWidget(remove_image)
        pool_layout.addLayout(pool_buttons)
        pool_layout.addWidget(self.pool, stretch=1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Ranked join hypotheses"))
        left_layout.addWidget(self.hypotheses, stretch=1)
        decisions = QHBoxLayout()
        decisions.addWidget(reject)
        decisions.addWidget(keep)
        decisions.addWidget(defer)
        left_layout.addLayout(decisions)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.legend)
        right_layout.addWidget(self.placement_view, stretch=1)
        right_layout.addWidget(self.caption)

        body = QHBoxLayout()
        body.addWidget(pool_column, stretch=1)
        body.addWidget(parameters)
        body.addWidget(left, stretch=2)
        body.addWidget(right, stretch=2)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(self.banner)
        layout.addWidget(self.decision_note)
        layout.addWidget(self.outlines)
        layout.addWidget(self.status)
        layout.addLayout(body, stretch=1)
        self.setCentralWidget(root)
        self.resize(1100, 720)

    def set_parameters(
        self,
        *,
        foreground_threshold: int,
        pixels_per_mm: float,
        uncertainty: float,
        minimum_edge_length_mm: float,
        code_version: str,
    ) -> None:
        self.threshold.setText(str(foreground_threshold))
        self.pixels_per_mm.setText(str(pixels_per_mm))
        self.uncertainty.setText(str(uncertainty))
        self.minimum_edge.setText(str(minimum_edge_length_mm))
        self.code_version.setText(code_version)

    def add_pool_image(self, label: str, path: Path) -> None:
        self._images.append(PoolImage(label=label, path=path))
        self._refresh_pool()

    def rank(self) -> None:
        """Start one rank on a worker thread."""
        if self._thread is not None and self._thread.isRunning():
            return
        try:
            request = self._request()
        except ValueError as exc:
            self.status.setText(str(exc))
            self.settled.emit()
            return
        self._set_busy(True)
        self.status.setText("Ranking joins off the review thread.")
        thread = _RankThread(request)
        thread.succeeded.connect(self._on_ranked)
        thread.failed.connect(self._on_rank_failed)
        thread.finished.connect(self._on_rank_finished)
        self._thread = thread
        thread.start()

    def load_synthetic_pair(self) -> None:
        """Write a disposable synthetic leaf outside the checkout and rank two pieces.

        The leaf's ``benchmarks/`` directory is not passed to rank.
        """
        if self._thread is not None and self._thread.isRunning():
            return
        if self._demo is not None:
            self._demo.cleanup()
        self._demo = tempfile.TemporaryDirectory(prefix="prw-review-")
        root = Path(self._demo.name)
        code = self.code_version.text().strip() or __version__
        generate_synthetic_leaf(
            root / "benchmarks",
            images_dir=root / "images",
            missing_fragment_percentage=0,
            edge_erosion=0,
            rotation=0,
            lighting_variation=0,
            random_seed=3,
            code_version=code,
        )
        fragments = sorted((root / "images").glob("fragment-*.tif"))
        if len(fragments) < 2:
            self.status.setText("The synthetic leaf did not write two fragment images.")
            self.settled.emit()
            return
        # The usage guide ranks the first and third sorted fragment files.
        # Some other pairs share a chord id, which the ranker refuses.
        second = fragments[2] if len(fragments) >= 3 else fragments[1]
        self._images = [
            PoolImage(label="piece-a", path=fragments[0]),
            PoolImage(label="piece-b", path=second),
        ]
        self._refresh_pool()
        self.rank()

    def closeEvent(self, event: QCloseEvent) -> None:
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.wait()
        if self._demo is not None:
            self._demo.cleanup()
            self._demo = None
        event.accept()

    def _request(self) -> RankRequest:
        if not self._images:
            raise ValueError("A pool image is one label and one existing path.")
        return RankRequest(
            images=tuple(self._images),
            foreground_threshold=_int_field(
                self.threshold.text(), "foreground_threshold"
            ),
            pixels_per_mm=_float_field(self.pixels_per_mm.text(), "pixels_per_mm"),
            uncertainty=_float_field(self.uncertainty.text(), "uncertainty"),
            minimum_edge_length_mm=_float_field(
                self.minimum_edge.text(), "minimum_edge_length_mm"
            ),
            code_version=self.code_version.text().strip(),
            recorded_at=_utc_now(),
        )

    def _on_ranked(self, outcome: object) -> None:
        self._remember_thread()
        if isinstance(outcome, ReviewFailure):
            self._session = None
            self._show_failure(outcome)
        elif isinstance(outcome, ReviewSession):
            self._show_session(outcome)
        else:
            raise TypeError("Rank returned an unknown record.")
        self.settled.emit()

    def _on_rank_failed(self, message: str) -> None:
        self._remember_thread()
        self._session = None
        self.status.setText(message)
        self._fill((message,), ())
        self._on_selected()
        self.settled.emit()

    def _on_rank_finished(self) -> None:
        if self.status.text() == "Ranking joins off the review thread.":
            self.status.setText("Rank stopped before a result.")
            self.settled.emit()
        self._set_busy(False)

    def _show_session(self, session: ReviewSession) -> None:
        self._session = session
        self.banner.setText(session.banner())
        self.decision_note.setText(session.decision_note())
        self.outlines.setText(session.outline_line())
        rows = session.rows()
        self._fill(hypothesis_lines(session), tuple(row.join_id for row in rows))
        self.status.setText("Ranked hypotheses.")
        if rows:
            self._select(str(rows[0].join_id))
        else:
            self._on_selected()

    def _show_failure(self, failure: ReviewFailure) -> None:
        self.banner.setText(REVIEW_BANNER)
        self.decision_note.setText(DECISION_NOTE)
        self.outlines.setText("No outline was loaded.")
        line = failure_line(failure)
        self.status.setText(line)
        self._fill((line,), ())
        self._on_selected()

    def _decide(self, decision: DecisionWord) -> None:
        session = self._session
        join_id = self._selected_id()
        if session is None or join_id is None:
            self.status.setText("Select a hypothesis.")
            return
        session.decide(
            join_id,
            decision,
            actor=LOCAL_OPERATOR,
            decided_at=_utc_now(),
        )
        rows = session.rows()
        self._fill(hypothesis_lines(session), tuple(row.join_id for row in rows))
        self._select(str(join_id))
        self.status.setText(
            "Recorded a validation decision. The other hypotheses stay."
        )

    def _on_selected(self) -> None:
        session = self._session
        join_id = self._selected_id()
        if session is None or join_id is None:
            self.legend.setText("Select a hypothesis to see a placement sketch.")
            self.caption.setText("")
            self.placement_view.set_sketch(None)
            return
        sketch = session.placement(join_id)
        self.caption.setText(sketch.caption)
        self.legend.setText(
            f"{sketch.moved_label} moved by the stored pose onto "
            f"{sketch.anchor_label}. Epistemic class {sketch.epistemic_class}."
        )
        self.placement_view.set_sketch(sketch)

    def _selection_changed(
        self,
        _current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self._on_selected()

    def _fill(self, lines: tuple[str, ...], join_ids: tuple[uuid.UUID, ...]) -> None:
        self.hypotheses.blockSignals(True)
        self.hypotheses.clear()
        if not join_ids:
            for line in lines:
                self.hypotheses.addItem(line)
        else:
            if len(lines) != len(join_ids):
                raise ValueError("Each hypothesis line cites one join.")
            for line, join_id in zip(lines, join_ids, strict=True):
                item = QListWidgetItem(line)
                item.setData(Qt.ItemDataRole.UserRole, str(join_id))
                self.hypotheses.addItem(item)
        self.hypotheses.blockSignals(False)

    def _select(self, join_id: str) -> None:
        for index in range(self.hypotheses.count()):
            item = self.hypotheses.item(index)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == join_id:
                self.hypotheses.setCurrentRow(index)
                return
        self._on_selected()

    def _selected_id(self) -> uuid.UUID | None:
        item = self.hypotheses.currentItem()
        if item is None:
            return None
        stored = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(stored, str) or stored == "":
            return None
        return uuid.UUID(stored)

    def _refresh_pool(self) -> None:
        self.pool.clear()
        for image in self._images:
            self.pool.addItem(f"{image.label}  {image.path}")

    def _add_image(self) -> None:
        label = self.label_field.text().strip()
        if label == "":
            self.status.setText("A fragment label is required.")
            return
        selected, _chosen = QFileDialog.getOpenFileName(
            self,
            "Fragment image",
            "",
            "TIFF (*.tif *.tiff)",
        )
        if selected == "":
            return
        self.add_pool_image(label, Path(selected))

    def _remove_image(self) -> None:
        row = self.pool.currentRow()
        if row < 0:
            return
        del self._images[row]
        self._refresh_pool()

    def _remember_thread(self) -> None:
        thread = self._thread
        if thread is not None:
            self.last_rank_thread_id = thread.thread_id

    def _set_busy(self, busy: bool) -> None:
        self.rank_button.setEnabled(not busy)


def _polygon(
    vertices: tuple[Point, ...],
    map_point: Callable[[Point], QPointF],
) -> QPolygonF:
    drawn = QPolygonF()
    for vertex in vertices:
        drawn.append(map_point(vertex))
    return drawn


def _int_field(text: str, label: str) -> int:
    try:
        return int(text.strip())
    except ValueError as exc:
        raise ValueError(f"{label} is an integer.") from exc


def _float_field(text: str, label: str) -> float:
    try:
        return float(text.strip())
    except ValueError as exc:
        raise ValueError(f"{label} is a number.") from exc


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(argv: Sequence[str] | None = None) -> int:
    """Show the window. Image flags, when present, start one rank."""
    args = _parser().parse_args(None if argv is None else list(argv))
    app = QApplication(["prw-review"])
    window = ReviewWindow()
    window.set_parameters(
        foreground_threshold=args.foreground_threshold,
        pixels_per_mm=args.pixels_per_mm,
        uncertainty=args.uncertainty,
        minimum_edge_length_mm=args.minimum_edge_length_mm,
        code_version=args.code_version,
    )
    for label, raw_path in args.images:
        window.add_pool_image(label, Path(raw_path))
    window.show()
    if args.images:
        window.rank()
    return int(app.exec())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prw-review",
        description=(
            "Show ranked join hypotheses. The command is unfrozen and is "
            "not a stable interface. Rank 1 is a hypothesis."
        ),
    )
    parser.add_argument(
        "--image",
        action="append",
        nargs=2,
        default=[],
        metavar=("LABEL", "PATH"),
        dest="images",
        help="One pool image: a label and an existing path. Repeat to add another.",
    )
    parser.add_argument("--foreground-threshold", type=int, default=1)
    parser.add_argument("--pixels-per-mm", type=float, default=10.0)
    parser.add_argument("--uncertainty", type=float, default=0.1)
    parser.add_argument("--minimum-edge-length-mm", type=float, default=0.0)
    parser.add_argument("--code-version", default=__version__)
    return parser
