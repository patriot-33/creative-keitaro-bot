"""Add duplication tracking fields

Revision ID: 003
Revises: 002
Create Date: 2024-12-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import expression


# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """Add fields for tracking creative duplication to storage channel"""
    # Add duplication tracking fields
    op.add_column('creatives', sa.Column('is_duplicated', sa.Boolean(), nullable=False, server_default=expression.false()))
    op.add_column('creatives', sa.Column('duplication_error', sa.Text(), nullable=True))
    op.add_column('creatives', sa.Column('duplicated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('creatives', sa.Column('duplication_message_id', sa.String(255), nullable=True))


def downgrade():
    """Remove duplication tracking fields"""
    op.drop_column('creatives', 'duplication_message_id')
    op.drop_column('creatives', 'duplicated_at')
    op.drop_column('creatives', 'duplication_error')
    op.drop_column('creatives', 'is_duplicated')