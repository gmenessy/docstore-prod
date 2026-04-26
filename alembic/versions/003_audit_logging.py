"""Add AuditLog table for DSGVO compliance

Revision ID: 003
Revises: 002_notification_logging
Create Date: 2026-04-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002_notification_logging'
branch_labels = None
depends_on = None


def upgrade():
    """Create audit_logs table"""

    # audit_logs Tabelle erstellen
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('store_id', UUID(as_uuid=True), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('changes', JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),  # IPv6-kompatibel
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('metadata', JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indexes für Performance erstellen
    op.create_index('idx_audit_store_time', 'audit_logs', ['store_id', 'created_at'])
    op.create_index('idx_audit_user_time', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('idx_audit_action_time', 'audit_logs', ['action', 'created_at'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_logs_store_id', 'audit_logs', ['store_id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade():
    """Drop audit_logs table"""

    # Indexes löschen
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_store_id', table_name='audit_logs')
    op.drop_index('idx_audit_resource', table_name='audit_logs')
    op.drop_index('idx_audit_action_time', table_name='audit_logs')
    op.drop_index('idx_audit_user_time', table_name='audit_logs')
    op.drop_index('idx_audit_store_time', table_name='audit_logs')

    # Tabelle löschen
    op.drop_table('audit_logs')
