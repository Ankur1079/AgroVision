"""Add advisory request and recommendation fields.

Revision ID: 20261027_advisory
Revises:
"""

from alembic import op
import sqlalchemy as sa

from app import models

revision = "20261027_advisory"
down_revision = None
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"]
        for column in sa.inspect(bind).get_columns(table_name)
    }


def upgrade() -> None:
    bind = op.get_bind()
    models.Base.metadata.create_all(bind=bind)

    additions = (
        (
            "advisory_requests",
            sa.Column(
                "category",
                sa.String(length=50),
                nullable=False,
                server_default="general",
            ),
        ),
        (
            "advisory_requests",
            sa.Column(
                "priority",
                sa.String(length=20),
                nullable=False,
                server_default="normal",
            ),
        ),
        (
            "advisor_recommendations",
            sa.Column(
                "action_items",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        ),
    )

    for table_name, column in additions:
        if not _column_exists(bind, table_name, column.name):
            op.add_column(table_name, column)

    op.execute(
        sa.text(
            "UPDATE advisory_requests "
            "SET status = 'open' WHERE status = 'pending'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        sa.text(
            "UPDATE advisory_requests "
            "SET status = 'pending' WHERE status = 'open'"
        )
    )
    if _column_exists(bind, "advisor_recommendations", "action_items"):
        op.drop_column("advisor_recommendations", "action_items")
    if _column_exists(bind, "advisory_requests", "priority"):
        op.drop_column("advisory_requests", "priority")
    if _column_exists(bind, "advisory_requests", "category"):
        op.drop_column("advisory_requests", "category")
