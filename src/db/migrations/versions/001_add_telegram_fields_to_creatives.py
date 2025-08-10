"""Add telegram fields to creatives

Revision ID: 001_telegram_fields
Revises: 
Create Date: 2024-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_telegram_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tables if they don't exist
    
    # Check if users table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'users' not in existing_tables:
        op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=False),
        sa.Column('tg_username', sa.String(), nullable=True),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('role', sa.Enum('OWNER', 'MEMBER', name='userrole'), nullable=False),
        sa.Column('buyer_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('google_access_token', sa.String(), nullable=True),
        sa.Column('google_refresh_token', sa.String(), nullable=True),
        sa.Column('google_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tg_user_id')
        )
    else:
        # Table exists, add Google OAuth columns if they don't exist
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'google_access_token' not in existing_columns:
            op.add_column('users', sa.Column('google_access_token', sa.String(), nullable=True))
        
        if 'google_refresh_token' not in existing_columns:
            op.add_column('users', sa.Column('google_refresh_token', sa.String(), nullable=True))
        
        if 'google_token_expires_at' not in existing_columns:
            op.add_column('users', sa.Column('google_token_expires_at', sa.DateTime(timezone=True), nullable=True))
        
        if 'is_active' not in existing_columns:
            op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
        
        if 'created_by_id' not in existing_columns:
            op.add_column('users', sa.Column('created_by_id', sa.Integer(), nullable=True))
    
    if 'geo_counters' not in existing_tables:
        op.create_table('geo_counters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('geo', sa.String(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('last_seq', sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('geo', 'date')
        )
    
    if 'creatives' not in existing_tables:
        # Create new table with Telegram fields
        op.create_table('creatives',
        sa.Column('creative_id', sa.String(), nullable=False),
        sa.Column('geo', sa.String(), nullable=False),
        sa.Column('telegram_file_id', sa.String(), nullable=False),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('drive_file_id', sa.String(), nullable=True),
        sa.Column('drive_link', sa.String(), nullable=True),
        sa.Column('uploader_user_id', sa.Integer(), nullable=False),
        sa.Column('uploader_buyer_id', sa.String(), nullable=True),
        sa.Column('original_name', sa.String(), nullable=True),
        sa.Column('ext', sa.String(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('sha256', sa.String(), nullable=True),
        sa.Column('upload_dt', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['uploader_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('creative_id')
        )
    else:
        # Table exists, add Telegram columns if they don't exist
        existing_columns = [col['name'] for col in inspector.get_columns('creatives')]
        
        if 'telegram_file_id' not in existing_columns:
            # Add telegram_file_id as nullable first, then update existing records
            op.add_column('creatives', sa.Column('telegram_file_id', sa.String(), nullable=True))
            
            # Update existing records with a default value (use drive_file_id as fallback)
            conn.execute(sa.text(
                "UPDATE creatives SET telegram_file_id = COALESCE(drive_file_id, 'legacy_' || creative_id) WHERE telegram_file_id IS NULL"
            ))
            
            # Now make it NOT NULL
            op.alter_column('creatives', 'telegram_file_id', nullable=False)
        
        if 'telegram_message_id' not in existing_columns:
            op.add_column('creatives', sa.Column('telegram_message_id', sa.BigInteger(), nullable=True))
        
        # Make existing Google Drive fields optional
        if 'drive_file_id' in existing_columns:
            op.alter_column('creatives', 'drive_file_id', nullable=True)
        if 'drive_link' in existing_columns:
            op.alter_column('creatives', 'drive_link', nullable=True)


def downgrade() -> None:
    # Remove Telegram columns if they exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'creatives' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('creatives')]
        
        if 'telegram_message_id' in existing_columns:
            op.drop_column('creatives', 'telegram_message_id')
        if 'telegram_file_id' in existing_columns:
            op.drop_column('creatives', 'telegram_file_id')