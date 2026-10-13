"""Superseding an outline invalidates its edges and citing joins."""

import uuid
from dataclasses import dataclass

from prw.frames import CoordinateFrame
from prw.identity import hash_value
from prw.join_rank import physical_join_order
from prw.joins import EdgeArc, EdgeArcLog, JoinHypothesis, JoinHypothesisLog
from prw.outlines import Fragment, FragmentOutlineRevision, OutlineRevisionLog
from prw.provenance import AlgorithmRun, ProvenanceEnvelope, Score, StatusStream

_RECORDED = "2020-01-01T00:00:00Z"
_TRIANGLE = ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0))
_OTHER_POLYGON = ((0.0, 0.0), (4.0, 0.0), (0.0, 1.0))
_LATER = ((0.0, 0.0), (3.0, 0.0), (0.0, 2.0))
_EDGE = ((0.0, 0.0), (2.0, 0.0))
_OTHER_EDGE = ((0.0, 0.0), (0.0, 2.0))
_KEPT = ((1.0, 0.0), (1.0, 2.0))
_KEPT_OTHER = ((2.0, 0.0), (2.0, 2.0))


def _envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"synthetic-source"),),
        parameters={"threshold": 12},
        algorithm_name="outline",
        algorithm_version="1",
        code_version="abc123",
        decoder_name="tiff",
        decoder_version="1",
    )


def _run(envelope: ProvenanceEnvelope) -> AlgorithmRun:
    return AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)


def _outline(
    envelope: ProvenanceEnvelope,
    run: AlgorithmRun,
    fragment: Fragment,
    polygon: tuple[tuple[float, float], ...],
) -> FragmentOutlineRevision:
    return FragmentOutlineRevision.create(
        fragment_id=fragment.id,
        frame_id=uuid.uuid4(),
        polygon=polygon,
        run_id=run.id,
        provenance_id=envelope.id,
    )


def _frame(fragment: Fragment) -> CoordinateFrame:
    return CoordinateFrame.fragment_local_mm(
        owner_id=fragment.id,
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=_TRIANGLE,
    )


def _edge(
    outline: FragmentOutlineRevision,
    frame: CoordinateFrame,
    envelope: ProvenanceEnvelope,
    run: AlgorithmRun,
    geometry: tuple[tuple[float, float], tuple[float, float]],
) -> EdgeArc:
    return EdgeArc.create(
        outline_revision_id=outline.id,
        frame=frame,
        geometry=geometry,
        run_id=run.id,
        provenance_id=envelope.id,
    )


def _join(
    run: AlgorithmRun,
    envelope: ProvenanceEnvelope,
    edge_a: EdgeArc,
    edge_b: EdgeArc,
    value: float,
) -> JoinHypothesis:
    return JoinHypothesis.create(
        run_id=run.id,
        fragment_a_id=uuid.uuid4(),
        edge_a_id=edge_a.id,
        fragment_b_id=uuid.uuid4(),
        edge_b_id=edge_b.id,
        transform_id=uuid.uuid4(),
        scores=(
            Score(
                value=value,
                run_id=run.id,
                channel="physical",
                hypothesis_type="join",
            ),
        ),
        provenance_id=envelope.id,
    )


@dataclass
class _Pool:
    run: AlgorithmRun
    first: FragmentOutlineRevision
    edge_a: EdgeArc
    edge_b: EdgeArc
    kept_edge: EdgeArc
    citing: JoinHypothesis
    current: JoinHypothesis
    edges: EdgeArcLog
    joins: JoinHypothesisLog
    stream: StatusStream
    log: OutlineRevisionLog


def _pool() -> _Pool:
    envelope = _envelope()
    run = _run(envelope)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="piece")
    frame = _frame(fragment)
    first = _outline(envelope, run, fragment, _TRIANGLE)
    other = _outline(envelope, run, fragment, _OTHER_POLYGON)
    edge_a = _edge(first, frame, envelope, run, _EDGE)
    edge_b = _edge(first, frame, envelope, run, _OTHER_EDGE)
    kept_edge = _edge(other, frame, envelope, run, _KEPT)
    kept_other = _edge(other, frame, envelope, run, _KEPT_OTHER)
    citing = _join(run, envelope, edge_a, edge_b, 5.0)
    current = _join(run, envelope, kept_edge, kept_other, 1.0)
    edges = EdgeArcLog()
    joins = JoinHypothesisLog()
    stream = StatusStream()
    for edge in (edge_a, edge_b, kept_edge, kept_other):
        edges.insert(stream, edge, recorded_at=_RECORDED, actor="edge-test")
    joins.insert(stream, citing, recorded_at=_RECORDED, actor="join-test")
    joins.insert(stream, current, recorded_at=_RECORDED, actor="join-test")
    log = OutlineRevisionLog(edges, joins)
    log.insert(stream, first, recorded_at=_RECORDED, actor=str(run.id))
    log.insert(stream, other, recorded_at=_RECORDED, actor=str(run.id))
    return _Pool(
        run=run,
        first=first,
        edge_a=edge_a,
        edge_b=edge_b,
        kept_edge=kept_edge,
        citing=citing,
        current=current,
        edges=edges,
        joins=joins,
        stream=stream,
        log=log,
    )


def _assert_invalidated(pool: _Pool, later: FragmentOutlineRevision) -> None:
    polygon_before = pool.first.polygon
    geometry_before = (pool.edge_a.geometry, pool.edge_b.geometry)
    content_before = pool.citing.content_bytes()
    provenance_before = pool.citing.provenance_id
    before = len(pool.stream.events)
    proposed = pool.log.insert(
        pool.stream,
        later,
        recorded_at=_RECORDED,
        actor=str(pool.run.id),
    )
    added = pool.stream.events[before:]
    assert proposed.status == "proposed"
    assert added[0].target_id == later.id
    invalidated = [event.target_id for event in added if event.status == "invalidated"]
    assert set(invalidated) == {pool.edge_a.id, pool.edge_b.id, pool.citing.id}
    assert len(invalidated) == 3
    assert pool.stream.current_status(pool.citing.id) == "invalidated"
    assert pool.stream.current_status(pool.current.id) == "proposed"
    assert pool.stream.current_status(pool.kept_edge.id) == "proposed"
    assert pool.first.polygon == polygon_before == _TRIANGLE
    assert pool.log.by_id(pool.first.id) is pool.first
    assert (pool.edge_a.geometry, pool.edge_b.geometry) == geometry_before
    assert pool.edges.by_id(pool.edge_a.id) is pool.edge_a
    assert pool.citing.content_bytes() == content_before
    assert pool.citing.provenance_id == provenance_before
    assert pool.joins.by_id(pool.citing.id) is pool.citing
    ranked = physical_join_order(
        (pool.citing, pool.current),
        (pool.run,),
        pool.stream,
    )
    assert ranked == (pool.current,)


def test_supersede_invalidates_two_edges_and_the_citing_join() -> None:
    pool = _pool()
    later = pool.first.supersede(_LATER)
    _assert_invalidated(pool, later)
    assert pool.log.by_id(later.id).polygon == _LATER


def test_correction_invalidates_two_edges_and_the_citing_join() -> None:
    pool = _pool()
    later = pool.first.correct(
        _LATER,
        operator_id="scholar-1",
        session_id="session-1",
    )
    assert later.producer == "human"
    assert later.epistemic_class == "interpretation"
    assert later.run_id is None
    assert later.provenance_id is None
    assert later.supersedes_id == pool.first.id
    _assert_invalidated(pool, later)
    stored = pool.log.by_id(later.id)
    assert stored is later
    assert stored.operator_id == "scholar-1"
    assert stored.session_id == "session-1"
    assert stored.polygon == _LATER
    assert pool.first.producer == "machine"


def test_revision_with_no_edges_appends_no_invalidation() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="bare")
    first = _outline(envelope, run, fragment, _TRIANGLE)
    stream = StatusStream()
    log = OutlineRevisionLog()
    log.insert(stream, first, recorded_at=_RECORDED, actor=str(run.id))
    later = first.supersede(_LATER)
    before = len(stream.events)
    log.insert(stream, later, recorded_at=_RECORDED, actor=str(run.id))
    added = stream.events[before:]
    assert [event.status for event in added] == ["proposed"]
    assert added[0].target_id == later.id
    assert first.polygon == _TRIANGLE
    assert log.by_id(first.id) is first
