"""Importa todos los modelos para poblar Base.metadata (Alembic / create_all)."""
from app.iam import models as _iam        # noqa: F401
from app.clinical import models as _clin   # noqa: F401
from app.catalog import models as _cat     # noqa: F401
from app.analysis import models as _ana    # noqa: F401
from app.recording import models as _rec   # noqa: F401
from app.metrics import models as _met      # noqa: F401
from app.reporting import models as _rep    # noqa: F401
from app import jobs as _jobs               # noqa: F401
