"""Add missing user fields for existing tables

Revision ID: 002_missing_user_fields
Revises: 001_telegram_fields
Create Date: 2024-08-10 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_missing_user_fields'
down_revision = '001_telegram_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to users table if they don't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if users table exists
    if 'users' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Add Google OAuth fields
        if 'google_access_token' not in existing_columns:
            op.add_column('users', sa.Column('google_access_token', sa.String(), nullable=True))
            print("Added google_access_token column to users table")
        
        if 'google_refresh_token' not in existing_columns:
            op.add_column('users', sa.Column('google_refresh_token', sa.String(), nullable=True))
            print("Added google_refresh_token column to users table")
        
        if 'google_token_expires_at' not in existing_columns:
            op.add_column('users', sa.Column('google_token_expires_at', sa.DateTime(timezone=True), nullable=True))
            print("Added google_token_expires_at column to users table")
        
        # Add other missing fields
        if 'is_active' not in existing_columns:
            op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
            print("Added is_active column to users table")
        
        if 'created_by_id' not in existing_columns:
            op.add_column('users', sa.Column('created_by_id', sa.Integer(), nullable=True))
            print("Added created_by_id column to users table")
            
        # Add timestamp fields if missing
        if 'created_at' not in existing_columns:
            op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
            print("Added created_at column to users table")
            
        if 'updated_at' not in existing_columns:
            op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
            print("Added updated_at column to users table")


def downgrade() -> None:
    # Remove added columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'users' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        # Remove columns in reverse order
        if 'updated_at' in existing_columns:
            op.drop_column('users', 'updated_at')
        if 'created_at' in existing_columns:
            op.drop_column('users', 'created_at')
        if 'created_by_id' in existing_columns:
            op.drop_column('users', 'created_by_id')
        if 'is_active' in existing_columns:
            op.drop_column('users', 'is_active')
        if 'google_token_expires_at' in existing_columns:
            op.drop_column('users', 'google_token_expires_at')
        if 'google_refresh_token' in existing_columns:
            op.drop_column('users', 'google_refresh_token')
        if 'google_access_token' in existing_columns:
            op.drop_column('users', 'google_access_token')