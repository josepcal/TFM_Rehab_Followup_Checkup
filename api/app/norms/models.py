"""ORM model for reference.metric_norm (UC-09 extension)."""

from sqlalchemy import Column, DateTime, Float, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base

REFERENCE = "reference"


class MetricNorm(Base):
    """ORM for reference.metric_norm — clinical reference ranges for speech metrics."""

    __tablename__ = "metric_norm"
    __table_args__ = {"schema": REFERENCE}

    norm_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    metric_code = Column(Text, nullable=False)
    label = Column(Text, nullable=True)
    unit = Column(Text, nullable=True)
    # direction stored as plain text: higher_better | lower_better | in_range
    direction = Column(Text, nullable=False)
    sex = Column(Text, nullable=True)
    age_min = Column(Integer, nullable=True)
    age_max = Column(Integer, nullable=True)
    good_min = Column(Float, nullable=True)
    good_max = Column(Float, nullable=True)
    poor_min = Column(Float, nullable=True)
    poor_max = Column(Float, nullable=True)
    source = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=text("now()"))
