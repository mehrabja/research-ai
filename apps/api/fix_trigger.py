from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Drop old triggers/functions if they exist
    db.execute(text("DROP TRIGGER IF EXISTS trg_kg_build_runs_no_modify ON knowledge_graph_build_runs"))
    db.execute(text("DROP TRIGGER IF EXISTS trg_kg_build_runs_no_update ON knowledge_graph_build_runs"))
    db.execute(text("DROP FUNCTION IF EXISTS knowledge_graph_build_runs_no_modify()"))
    db.execute(text("DROP FUNCTION IF EXISTS knowledge_graph_build_runs_no_update()"))

    # Create the function that raises an exception on UPDATE
    db.execute(text("""
        CREATE OR REPLACE FUNCTION knowledge_graph_build_runs_no_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'knowledge_graph_build_runs is append-only; UPDATE is forbidden';
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Create the trigger
    db.execute(text("""
        CREATE TRIGGER trg_kg_build_runs_no_update
        BEFORE UPDATE ON knowledge_graph_build_runs
        FOR EACH ROW EXECUTE FUNCTION knowledge_graph_build_runs_no_update();
    """))

    db.commit()
    print("Trigger recreated")
finally:
    db.close()