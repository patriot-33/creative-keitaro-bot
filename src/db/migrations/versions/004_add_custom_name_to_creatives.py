"""Add custom_name field to creatives table for user-defined creative names

Revision ID: 004_custom_name_field
Revises: 003_custom_geos_table
Create Date: 2025-01-13 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_custom_name_field'
down_revision = '003_custom_geos_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add custom_name column to creatives table
    op.add_column('creatives', sa.Column('custom_name', sa.String(), nullable=True))
    print("Added custom_name column to creatives table")


def downgrade() -> None:
    # Remove custom_name column from creatives table
    op.drop_column('creatives', 'custom_name')
    print("Removed custom_name column from creatives table")