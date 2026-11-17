"""local email/password credentials

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'local_credentials',
        sa.Column('credential_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('password_hash', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_local_credential_user'),
        sa.PrimaryKeyConstraint('credential_id'),
        sa.UniqueConstraint('user_id', name='uq_local_credential_user'),
    )
    with op.batch_alter_table('local_credentials', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_local_credentials_email'), ['email'], unique=True)


def downgrade():
    with op.batch_alter_table('local_credentials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_local_credentials_email'))
    op.drop_table('local_credentials')
