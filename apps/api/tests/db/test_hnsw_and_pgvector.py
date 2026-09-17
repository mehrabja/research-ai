"""DB tests: pgvector extension, vector dimension, HNSW opclass, EXPLAIN paths."""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection


def test_pgvector_extension_present(conn: Connection) -> None:
    v = conn.execute(
        text(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        )
    ).scalar()
    assert v is not None


def test_embedding_is_vector_1536(conn: Connection) -> None:
    typ = conn.execute(
        text(
            "SELECT format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE c.relname = 'chunks' AND a.attname = 'embedding'"
        )
    ).scalar_one()
    assert typ == "vector(1536)"


def test_hnsw_index_opclass(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT am.amname, opc.opcname "
            "FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indexrelid "
            "JOIN pg_am am ON am.oid = c.relam "
            "JOIN pg_opclass opc ON opc.oid = i.indclass[0] "
            "WHERE c.relname = 'ix_chunks_embedding_hnsw'"
        )
    ).one_or_none()
    assert row is not None
    assert row.amname == "hnsw"
    assert row.opcname == "vector_cosine_ops"


def test_gin_lexical_index_present(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname='public' "
            "AND indexname='ix_chunks_content_tsv'"
        )
    ).scalar()
    assert row == 1


def _seed_source_with_chunk(conn: Connection) -> uuid.UUID:
    """Return the source_id that owns a single embedded chunk."""
    uid = conn.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ),
        {"e": f"explain-{uuid.uuid4().hex}@example.com"},
    ).scalar()
    rid = conn.execute(
        text(
            "INSERT INTO reports (user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ),
        {"u": uid},
    ).scalar()
    sid = conn.execute(
        text(
            "INSERT INTO sources (report_id, title, status) "
            "VALUES (:r, 'T', 'full_text') RETURNING id"
        ),
        {"r": rid},
    ).scalar()
    vec = "[" + ",".join(["0.1"] * 1536) + "]"
    conn.execute(
        text(
            "INSERT INTO chunks "
            "(source_id, content, chunk_index, embedding, "
            " embedding_status, embedding_model_version, "
            " embedding_provider, embedding_dimensions) "
            "VALUES (:s, 'x', 0, CAST(:v AS vector), 'completed', "
            "        'p', 'openai', 1536)"
        ),
        {"s": sid, "v": vec},
    )
    return sid


def _plan(conn: Connection, sql: str, params: dict) -> str:
    rows = conn.execute(text(f"EXPLAIN {sql}"), params).scalars().all()
    return "\n".join(rows)

def test_ann_uses_hnsw_index(conn: Connection) -> None:
    sid = _seed_source_with_chunk(conn)
    # Tiny tables make the planner prefer seqscan + sort over HNSW.
    # The standard pgvector test recipe: disable seqscan and sort,
    # and make random page access cheap, so the planner is forced to
    # use the HNSW index. This does not change production behaviour.
    conn.execute(text("SET LOCAL enable_seqscan = off"))
    conn.execute(text("SET LOCAL enable_sort = off"))
    conn.execute(text("SET LOCAL random_page_cost = 1"))
    conn.execute(text("SET LOCAL hnsw.ef_search = 100"))
    q = "[" + ",".join(["0.1"] * 1536) + "]"
    plan = _plan(
        conn,
        "SELECT id FROM chunks "
        "WHERE embedding IS NOT NULL "
        "  AND source_id = :s "
        "ORDER BY embedding <=> CAST(:q AS vector) LIMIT 5",
        {"s": sid, "q": q},
    )
    assert "ix_chunks_embedding_hnsw" in plan

def test_exact_disables_index(conn: Connection) -> None:
    sid = _seed_source_with_chunk(conn)
    conn.execute(text("SET LOCAL enable_indexscan = off"))
    conn.execute(text("SET LOCAL enable_bitmapscan = off"))
    conn.execute(text("SET LOCAL enable_indexonlyscan = off"))
    conn.execute(text("SET LOCAL enable_seqscan = on"))
    q = "[" + ",".join(["0.1"] * 1536) + "]"
    plan = _plan(
        conn,
        "SELECT id FROM chunks "
        "WHERE embedding IS NOT NULL "
        "  AND source_id = :s "
        "ORDER BY embedding <=> CAST(:q AS vector) LIMIT 5",
        {"s": sid, "q": q},
    )
    assert "ix_chunks_embedding_hnsw" not in plan
