from __future__ import annotations

import uuid

import pytest

from app.schemas.research_canvas import CanvasNode
from app.services.research_canvas import CanvasInvalid, _validate_canvas_graph


def _node(node_id: str, **extra: object) -> dict[str, object]:
    return {
        "id": node_id,
        "type": "idea",
        "title": node_id,
        "body": "",
        "x": 0,
        "y": 0,
        **extra,
    }


def test_canvas_node_can_reference_canonical_evidence() -> None:
    evidence_id = uuid.uuid4()
    node = CanvasNode(
        id="e1",
        type="evidence",
        title="Evidence",
        ref_type="evidence",
        ref_id=evidence_id,
        evidence_key=f"m28_evidence:{evidence_id}",
    )

    assert node.ref_type == "evidence"
    assert node.ref_id == evidence_id
    assert node.evidence_key == f"m28_evidence:{evidence_id}"


def test_canvas_graph_rejects_duplicate_node_ids() -> None:
    with pytest.raises(CanvasInvalid, match="node ids must be unique"):
        _validate_canvas_graph(
            nodes=[_node("a"), _node("a")],
            edges=[],
        )


def test_canvas_graph_rejects_unknown_edge_target() -> None:
    with pytest.raises(CanvasInvalid, match="unknown node"):
        _validate_canvas_graph(
            nodes=[_node("a")],
            edges=[{"id": "e1", "source": "a", "target": "missing"}],
        )


def test_canvas_graph_rejects_evidence_node_without_key() -> None:
    with pytest.raises(
        CanvasInvalid,
        match="evidence_key is required",
    ):
        _validate_canvas_graph(
            nodes=[
                _node(
                    "e1",
                    type="evidence",
                    ref_type="evidence",
                    ref_id=uuid.uuid4(),
                )
            ],
            edges=[],
        )


def test_canvas_graph_accepts_valid_edges() -> None:
    _validate_canvas_graph(
        nodes=[_node("a"), _node("b")],
        edges=[{"id": "e1", "source": "a", "target": "b"}],
    )
