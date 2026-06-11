"""seed ftm data

Revision ID: 0002_seed
Revises: 0001_baseline
"""
import json
from pathlib import Path

from alembic import op
from sqlalchemy.orm import Session

import seed

revision = "0002_seed"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

JSON_PATH = Path(seed.__file__).resolve().parent / "patient_sessions.json"


def upgrade() -> None:
    with open(JSON_PATH, encoding="utf-8") as fh:
        sessions = json.load(fh)
    objs, _ = seed.build_all(sessions)
    s = Session(bind=op.get_bind())
    s.add_all(objs)
    s.flush()


def downgrade() -> None:
    pass