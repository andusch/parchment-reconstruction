"""Parchment reconstruction workbench.

Headless use cases live in ``prw.ingest``, ``prw.frames``, ``prw.outlines``,
``prw.provenance``, ``prw.joins``, ``prw.assemblies``, ``prw.screening``,
``prw.edge_chord``, ``prw.pairwise_join``, ``prw.join_rank``,
``prw.assembly_rank``, ``prw.assembly_search``, ``prw.synthetic_tear``,
``prw.fixture_tiff``,
``prw.segment``, ``prw.scale``, ``prw.outline_agreement``,
``prw.join_recall``, ``prw.placement_error``, and
``prw.assembly_join_presence``.
``python -m prw.cli`` calls ingest, frames, provenance, the synthetic fixture
generator, segmentation, caller-supplied scale, outline agreement, chord
edges, pairwise joins, and join recall.
``prw.fixture_tiff`` reads that writer's uncompressed grayscale layout
only. It is not a decoder for arbitrary scans. Command names are unfrozen
and are not a stable interface. The project format is still Q-ENG-01 in
``docs/OPEN_QUESTIONS.md``.
"""

__version__ = "0.0.0"
