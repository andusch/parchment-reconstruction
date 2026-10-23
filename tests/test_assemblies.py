"""In-memory page placements and an assembly log."""

import dataclasses
import uuid

import pytest

from prw.assemblies import AssemblyLog, placement_pose
from prw.frames import CoordinateFrame, PageFrame
from prw.identity import content_id
from prw.joins import RigidTransform
from prw.provenance import AssemblyContent, Placement, StatusStream

_RECORDED = "2020-01-01T00:00:00Z"
_TRIANGLE = ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0))


def _local() -> CoordinateFrame:
    return CoordinateFrame.fragment_local_mm(
        owner_id=uuid.uuid4(),
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=_TRIANGLE,
    )


def _page() -> tuple[CoordinateFrame, PageFrame]:
    frame = CoordinateFrame.page_global_mm(owner_id=uuid.uuid4())
    page = PageFrame.create(
        frame,
        min_width_mm=100.0,
        max_width_mm=120.0,
        min_height_mm=140.0,
        max_height_mm=160.0,
    )
    return frame, page


def _pose(
    local: CoordinateFrame,
    page_frame: CoordinateFrame,
    provenance_id: uuid.UUID,
) -> RigidTransform:
    return placement_pose(
        from_frame=local,
        to_frame=page_frame,
        rotation_radians=0.25,
        translation_x=3.0,
        translation_y=4.0,
        provenance_id=provenance_id,
    )


def _assembly(
    page: PageFrame,
    pose: RigidTransform,
    provenance_id: uuid.UUID,
) -> AssemblyContent:
    fragment_id = uuid.uuid4()
    outline_id = uuid.uuid4()
    return AssemblyContent.create(
        page_frame_id=page.id,
        producer="machine",
        placements=(
            Placement(
                fragment_id=fragment_id,
                outline_revision_id=outline_id,
                transform_id=pose.id,
            ),
        ),
        provenance_id=provenance_id,
    )


def test_placement_pose_is_a_machine_hypothesis_into_the_page_frame() -> None:
    provenance_id = uuid.uuid4()
    local = _local()
    page_frame, page = _page()
    pose = _pose(local, page_frame, provenance_id)
    assert local.kind == "fragment_local_mm"
    assert page_frame.kind == "page_global_mm"
    assert pose.from_frame_id == local.id
    assert pose.to_frame_id == page_frame.id
    assert pose.to_frame_id == page.frame_id
    assert pose.epistemic_class == "hypothesis"
    assert pose.producer == "machine"
    assert pose.provenance_id == provenance_id
    assert pose.rotation_radians == 0.25
    assert pose.translation_x == 3.0
    assert pose.translation_y == 4.0
    assert pose.id.version == 5
    assert pose.id == content_id(pose.content_mapping())
    assert "scale" not in {field.name for field in dataclasses.fields(pose)}
    assert "status" not in {field.name for field in dataclasses.fields(pose)}
    moved = placement_pose(
        from_frame=local,
        to_frame=page_frame,
        rotation_radians=0.25,
        translation_x=5.0,
        translation_y=4.0,
        provenance_id=provenance_id,
    )
    assert moved.id != pose.id
    with pytest.raises(TypeError, match="scale"):
        placement_pose(  # type: ignore[call-arg]
            from_frame=local,
            to_frame=page_frame,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=provenance_id,
            scale=1.0,
        )


def test_placement_pose_rejects_the_wrong_frames() -> None:
    provenance_id = uuid.uuid4()
    local = _local()
    page_frame, _page_record = _page()
    pixels = CoordinateFrame.source_pixels(owner_id=uuid.uuid4())
    other_local = _local()
    with pytest.raises(ValueError, match="fragment_local_mm"):
        placement_pose(
            from_frame=pixels,
            to_frame=page_frame,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=provenance_id,
        )
    with pytest.raises(ValueError, match="page_global_mm"):
        placement_pose(
            from_frame=local,
            to_frame=pixels,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=provenance_id,
        )
    with pytest.raises(ValueError, match="page_global_mm"):
        placement_pose(
            from_frame=local,
            to_frame=other_local,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=provenance_id,
        )
    with pytest.raises(ValueError, match="fragment_local_mm"):
        placement_pose(
            from_frame=page_frame,
            to_frame=page_frame,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=provenance_id,
        )


def test_placement_pose_rejects_other_classes_and_producers() -> None:
    provenance_id = uuid.uuid4()
    local = _local()
    page_frame, _page_record = _page()
    kwargs = {
        "from_frame": local,
        "to_frame": page_frame,
        "rotation_radians": 0.0,
        "translation_x": 0.0,
        "translation_y": 0.0,
        "provenance_id": provenance_id,
    }
    with pytest.raises(ValueError, match="hypothesis"):
        placement_pose(**kwargs, epistemic_class="interpretation")
    with pytest.raises(ValueError, match="hypothesis"):
        placement_pose(**kwargs, epistemic_class="observed")
    with pytest.raises(ValueError, match="machine"):
        placement_pose(**kwargs, producer="human")
    with pytest.raises(ValueError, match="machine"):
        placement_pose(**kwargs, producer="imported")


def test_join_constructor_still_rejects_a_page_destination() -> None:
    local = _local()
    page_frame, _page_record = _page()
    with pytest.raises(ValueError, match="destination frame"):
        RigidTransform.create(
            from_frame=local,
            to_frame=page_frame,
            rotation_radians=0.25,
            translation_x=3.0,
            translation_y=4.0,
            provenance_id=uuid.uuid4(),
        )


def test_insert_appends_proposed_and_refuses_a_second_insert() -> None:
    provenance_id = uuid.uuid4()
    local = _local()
    page_frame, page = _page()
    pose = _pose(local, page_frame, provenance_id)
    assembly = _assembly(page, pose, provenance_id)
    assert "status" not in {field.name for field in dataclasses.fields(assembly)}
    before = assembly.content_bytes()
    stream = StatusStream()
    log = AssemblyLog()
    proposed = log.insert(
        stream,
        assembly,
        recorded_at=_RECORDED,
        actor="machine-run",
    )
    assert proposed.status == "proposed"
    assert proposed.target_id == assembly.id
    assert stream.current_status(assembly.id) == "proposed"
    assert log.by_id(assembly.id) is assembly
    assert assembly.content_bytes() == before
    assert assembly.placements[0].transform_id == pose.id
    with pytest.raises(ValueError, match="once"):
        log.insert(
            stream,
            assembly,
            recorded_at=_RECORDED,
            actor="machine-run",
        )
    assert log.rows == (assembly,)
    assert stream.current_status(assembly.id) == "proposed"
    assert assembly.content_bytes() == before


def test_machine_rejection_leaves_the_content_unchanged() -> None:
    provenance_id = uuid.uuid4()
    local = _local()
    page_frame, page = _page()
    pose = _pose(local, page_frame, provenance_id)
    assembly = _assembly(page, pose, provenance_id)
    before = assembly.content_bytes()
    stream = StatusStream()
    log = AssemblyLog()
    rejected = log.insert(
        stream,
        assembly,
        recorded_at=_RECORDED,
        actor="machine-run",
        machine_rejection=True,
    )
    assert rejected.status == "rejected"
    assert rejected.id.version == 4
    assert stream.current_status(assembly.id) == "rejected"
    assert log.by_id(assembly.id) is assembly
    assert assembly.content_bytes() == before
    assert assembly.epistemic_class == "hypothesis"
    assert assembly.id == content_id(assembly.id_inputs())
