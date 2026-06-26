"""Legacy location for the metric-definition seed integration test.

The default suite is intentionally database-free.  The real PostgreSQL-backed
coverage for this seed lives in ``tests/integration/test_metric_definition_seed.py``
and is gated by ``RUN_INTEGRATION=1``.
"""

import pytest

pytest.skip(
    "metric_definition seed checks require PostgreSQL; run tests/integration/test_metric_definition_seed.py",
    allow_module_level=True,
)
