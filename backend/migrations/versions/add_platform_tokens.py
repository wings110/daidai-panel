"""添加多平台 Token 管理

Revision ID: add_platform_tokens
Revises: add_subscription_enhancements
Create Date: 2024-01-15 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_platform_tokens'
down_revision = 'add_subscription_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    # 创建平台表
    op.create_table('platforms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 创建平台 Token 表
    op.create_table('platform_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('token_encrypted', sa.Text(), nullable=False),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_ip', sa.String(length=64), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['platform_id'], ['platforms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index(op.f('ix_platform_tokens_platform_id'), 'platform_tokens', ['platform_id'], unique=False)
    op.create_index(op.f('ix_platform_tokens_token'), 'platform_tokens', ['token'], unique=False)

    # 创建平台 Token 调用日志表
    op.create_table('platform_token_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('method', sa.String(length=8), nullable=False),
        sa.Column('path', sa.String(length=256), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('called_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['token_id'], ['platform_tokens.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_platform_token_logs_token_id'), 'platform_token_logs', ['token_id'], unique=False)
    op.create_index(op.f('ix_platform_token_logs_called_at'), 'platform_token_logs', ['called_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_platform_token_logs_called_at'), table_name='platform_token_logs')
    op.drop_index(op.f('ix_platform_token_logs_token_id'), table_name='platform_token_logs')
    op.drop_table('platform_token_logs')
    op.drop_index(op.f('ix_platform_tokens_token'), table_name='platform_tokens')
    op.drop_index(op.f('ix_platform_tokens_platform_id'), table_name='platform_tokens')
    op.drop_table('platform_tokens')
    op.drop_table('platforms')
