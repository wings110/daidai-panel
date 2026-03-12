"""添加环境变量 Position 排序

Revision ID: add_env_position
Create Date: 2024-01-15 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_env_position'
down_revision = 'add_task_hooks'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 position 字段
    with op.batch_alter_table('env_vars', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Float(), nullable=True, server_default='10000.0'))
        batch_op.create_index('ix_env_vars_position', ['position'])

    # 迁移现有数据：将 sort_order 转换为 position
    op.execute("""
        UPDATE env_vars
        SET position = 10000.0 + (sort_order * 100.0)
        WHERE position IS NULL
    """)


def downgrade():
    # 移除 position 字段
    with op.batch_alter_table('env_vars', schema=None) as batch_op:
        batch_op.drop_index('ix_env_vars_position')
        batch_op.drop_column('position')
