"""Add NotificationLog table for rate limiting

Revision ID: 002
Revises: 001_comments_collaboration
Create Date: 2026-04-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001_comments_collaboration'
branch_labels = None
depends_on = None


def upgrade():
    """Create notification_logs table"""

    # notification_logs Tabelle erstellen
    op.create_table(
        'notification_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('store_id', UUID(as_uuid=True), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('notification_type', sa.String(100), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='sent'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indexes für Rate-Limit Queries erstellen
    op.create_index('idx_notification_user_time', 'notification_logs', ['user_id', 'created_at'])
    op.create_index('idx_notification_type_time', 'notification_logs', ['notification_type', 'created_at'])
    op.create_index('ix_notification_logs_user_id', 'notification_logs', ['user_id'])
    op.create_index('ix_notification_logs_notification_type', 'notification_logs', ['notification_type'])
    op.create_index('ix_notification_logs_created_at', 'notification_logs', ['created_at'])


def downgrade():
    """Drop notification_logs table"""

    # Indexes löschen
    op.drop_index('ix_notification_logs_created_at', table_name='notification_logs')
    op.drop_index('ix_notification_logs_notification_type', table_name='notification_logs')
    op.drop_index('ix_notification_logs_user_id', table_name='notification_logs')
    op.drop_index('idx_notification_type_time', table_name='notification_logs')
    op.drop_index('idx_notification_user_time', table_name='notification_logs')

    # Tabelle löschen
    op.drop_table('notification_logs')
