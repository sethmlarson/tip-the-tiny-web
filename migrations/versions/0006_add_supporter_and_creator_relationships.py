"""Add Supporter and Creator relationships

Revision ID: 0006
Revises: 0005
Create Date: 2024-11-26 22:18:10.455664
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "supporters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("budget_per_month", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "supporter_to_creator",
        sa.Column("supporter_id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("want_to_pay", sa.Boolean(), nullable=False),
        sa.Column("minimum_payment_per_month", sa.Integer(), nullable=False),
        sa.Column("payment_amount_outstanding", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creators.id"],
        ),
        sa.ForeignKeyConstraint(
            ["supporter_id"],
            ["supporters.id"],
        ),
        sa.PrimaryKeyConstraint("supporter_id", "creator_id"),
    )
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("paid_at", app.TzAwareDatetime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("supporter_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "payments_supporter_id_fk", "supporters", ["supporter_id"], ["id"]
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_column("supporter_id")
        batch_op.drop_column("paid_at")

    op.drop_table("supporter_to_creator")
    op.drop_table("supporters")
    # ### end Alembic commands ###
