from app.domain.knowledge_graph import (
    DETERMINISTIC_RELATION_TYPES,
    KNOWLEDGE_GRAPH_NODE_TYPES,
    KNOWLEDGE_GRAPH_PROVENANCE_TYPES,
    KNOWLEDGE_GRAPH_RELATION_TYPES,
    edge_key,
    node_key,
)


def test_node_key_is_deterministic():
    a = node_key("source", "11111111-1111-1111-1111-111111111111")
    b = node_key("source", "11111111-1111-1111-1111-111111111111")
    assert a == b
    assert a.startswith("source:")


def test_node_key_differs_by_type():
    a = node_key("source", "x")
    b = node_key("chunk", "x")
    assert a != b


def test_edge_key_includes_provenance():
    a = edge_key("s:1", "t:1", "supports", "database", None)
    b = edge_key("s:1", "t:1", "supports", "llm", "chunk-1")
    assert a != b
    assert "supports" in a


def test_node_types_contains_supported_set():
    for nt in (
        "project", "report", "report_version", "source", "chunk",
        "literature_item", "literature_cluster", "literature_gap",
        "research_plan", "research_plan_section",
        "evidence_requirement",
    ):
        assert nt in KNOWLEDGE_GRAPH_NODE_TYPES


def test_relation_types_deterministic_subset():
    for r in DETERMINISTIC_RELATION_TYPES:
        assert r in KNOWLEDGE_GRAPH_RELATION_TYPES


def test_provenance_types():
    for p in ("database", "citation_link", "llm", "human", "system"):
        assert p in KNOWLEDGE_GRAPH_PROVENANCE_TYPES
