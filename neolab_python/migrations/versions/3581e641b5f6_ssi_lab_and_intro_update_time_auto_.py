"""ssi_lab and intro update_time auto update

Revision ID: 3581e641b5f6
Revises: a787eb7f323d
Create Date: 2024-10-09 14:27:28.380591

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3581e641b5f6'
down_revision = 'a787eb7f323d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('intro', schema=None) as batch_op:
        batch_op.alter_column('update_time',
               existing_type=mysql.DATETIME(),
               nullable=False)
        batch_op.alter_column('x',
               existing_type=mysql.DOUBLE(asdecimal=True),
               type_=sa.Float(precision=53),
               existing_nullable=True)
        batch_op.alter_column('y',
               existing_type=mysql.DOUBLE(asdecimal=True),
               type_=sa.Float(precision=53),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('intro', schema=None) as batch_op:
        batch_op.alter_column('y',
               existing_type=sa.Float(precision=53),
               type_=mysql.DOUBLE(asdecimal=True),
               existing_nullable=True)
        batch_op.alter_column('x',
               existing_type=sa.Float(precision=53),
               type_=mysql.DOUBLE(asdecimal=True),
               existing_nullable=True)
        batch_op.alter_column('update_time',
               existing_type=mysql.DATETIME(),
               nullable=True)

    # ### end Alembic commands ###
