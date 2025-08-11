"""Add custom_geos table for persistent custom GEO storage

Revision ID: 003_custom_geos_table
Revises: 002_missing_user_fields
Create Date: 2025-08-11 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_custom_geos_table'
down_revision = '002_missing_user_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create custom_geos table
    op.create_table('custom_geos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=4), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_custom_geos_code'), 'custom_geos', ['code'], unique=True)
    print("Created custom_geos table with unique index on code")


def downgrade() -> None:
    # Drop custom_geos table
    op.drop_index(op.f('ix_custom_geos_code'), table_name='custom_geos')
    op.drop_table('custom_geos')
    print("Dropped custom_geos table")