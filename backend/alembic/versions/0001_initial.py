"""initial empty migration

Revision ID: 0001
Revises:
Create Date: 2026-08-06

This migration intentionally contains no operations. Real tables arrive
via ``alembic revision --autogenerate`` once business models are added.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the initial (empty) migration."""


def downgrade() -> None:
    """Revert the initial (empty) migration."""
