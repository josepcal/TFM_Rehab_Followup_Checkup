# Deploy-time import point for approved technician-authored analysis functions.
# Existing reference functions remain imported until their own SDD change
# replaces or versions them; runtime module loading is intentionally forbidden.
from app.analysis.functions import voice  # noqa: F401
