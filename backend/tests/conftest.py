import os
import sys
import tempfile
from pathlib import Path

# Base de datos SQLite temporal para las pruebas (se configura antes de importar la app)
_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def base_limpia():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
