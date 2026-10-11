"""Parchment reconstruction workbench.

Headless use cases live in ``prw.ingest``, ``prw.frames``, ``prw.outlines``,
``prw.provenance``, ``prw.synthetic_tear``, ``prw.fixture_tiff``,
``prw.segment``, and ``prw.scale``. ``python -m prw.cli`` calls ingest,
frames, provenance, and the synthetic fixture generator.
``prw.fixture_tiff`` reads that writer's uncompressed grayscale layout
only. It is not a decoder for arbitrary scans. Command names are unfrozen
and are not a stable interface. The project format is still Q-ENG-01 in
``docs/OPEN_QUESTIONS.md``.
"""

__version__ = "0.0.0"
