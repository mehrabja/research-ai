"""M39 F01 — expand usage metrics for provider metering."""
from alembic import op


revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_usage_events_metric", "usage_events", type_="check")
    op.create_check_constraint(
        "ck_usage_events_metric",
        "usage_events",
        "metric IN ('reports_created','jobs_enqueued','files_uploaded',"
        "'storage_bytes','ai_generation_units','ai_input_tokens',"
        "'ai_output_tokens','embedding_input_tokens','search_requests')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_usage_events_metric", "usage_events", type_="check")
    op.create_check_constraint(
        "ck_usage_events_metric",
        "usage_events",
        "metric IN ('reports_created','jobs_enqueued','files_uploaded',"
        "'storage_bytes','ai_generation_units','search_requests')",
    )
