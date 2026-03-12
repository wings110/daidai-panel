"""添加任务钩子和多实例支持

Revision ID: add_task_hooks
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_task_hooks'
down_revision = None  # 设置为你的上一个迁移版本
branch_labels = None
depends_on = None


def upgrade():
    # 添加任务钩子字段
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('task_before', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('task_after', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('allow_multiple_instances', sa.Boolean(), nullable=True, server_default='0'))


def downgrade():
    # 移除任务钩子字段
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('allow_multiple_instances')
        batch_op.drop_column('task_after')
        batch_op.drop_column('task_before')
