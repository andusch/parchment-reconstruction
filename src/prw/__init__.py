"""Parchment reconstruction workbench.

Headless use cases live in ``prw.ingest``, ``prw.frames``, ``prw.outlines``,
``prw.provenance``, ``prw.joins``, ``prw.assemblies``, ``prw.screening``,
``prw.edge_chord``, ``prw.pairwise_join``, ``prw.join_rank``,
``prw.assembly_rank``, ``prw.assembly_search``, ``prw.synthetic_tear``,
``prw.fixture_tiff``, ``prw.lossless_tiff``,
``prw.segment``, ``prw.scale``, ``prw.outline_agreement``,
``prw.join_recall``, ``prw.placement_error``,
``prw.assembly_join_presence``, ``prw.recognize``, and ``prw.review``.
``python -m prw.cli`` calls ingest, frames, provenance, the synthetic fixture
generator, segmentation, caller-supplied scale, outline agreement, chord
edges, pairwise joins, join recall, assembly search, assembly rank,
placement error, end-to-end join presence, and line recognition. It does
not import Qt. Line recognition imports Kraken only when that command runs,
and only when the optional ``htr`` group is installed.
``prw-review`` opens the review window in ``prw.review_qt`` when
PySide6-Essentials is installed. That command is unfrozen.
``prw.fixture_tiff`` reads that writer's uncompressed grayscale layout.
``prw.lossless_tiff`` reads other classic lossless TIFF masters. Command
names are unfrozen and are not a stable interface. The project format is
still Q-ENG-01 in ``docs/OPEN_QUESTIONS.md``.
"""

__version__ = "0.0.0"
