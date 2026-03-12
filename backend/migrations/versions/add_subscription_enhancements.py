"""添加订阅系统增强功能

Revision ID: add_subscription_enhancements
Create Date: 2024-01-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_subscription_enhancements'
down_revision = 'add_env_position'
branch_labels = None
depends_on = None


def upgrade():
    # 创建 SSH 密钥表
    op.create_table(
        'ssh_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('private_key', sa.Text(), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('remarks', sa.String(length=256), server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 添加订阅增强字段
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('use_ssh_key', sa.Boolean(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('ssh_key_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sub_before', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('sub_after', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('pull_option', sa.String(length=16), nullable=True, server_default='merge'))
        batch_op.create_foreign_key('fk_subscriptions_ssh_key_id', 'ssh_keys', ['ssh_key_id'], ['id'])


def downgrade():
    # 移除订阅增强字段
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_subscriptions_ssh_key_id', type_='foreignkey')
        batch_op.drop_column('pull_option')
        batch_op.drop_column('sub_after')
        batch_op.drop_column('sub_before')
        batch_op.drop_column('ssh_key_id')
        batch_op.drop_column('use_ssh_key')

    # 删除 SSH 密钥表
    op.drop_table('ssh_keys')
