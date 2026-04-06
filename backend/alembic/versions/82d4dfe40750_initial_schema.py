"""initial schema (old flat structure)

Revision ID: 82d4dfe40750
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '82d4dfe40750'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 이 revision은 기존 DB에 이미 존재하는 테이블들을 나타냄
    # 실제 DDL 없음 (테이블이 이미 존재)
    pass


def downgrade() -> None:
    pass
