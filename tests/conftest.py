
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "painel-api"))

TEST_TOKEN = "token-de-teste"

# Precisa estar no ambiente antes do import do server (lido no import)
os.environ["PAINEL_TOKEN"] = TEST_TOKEN
os.environ["FRONTEND_ORIGIN"] = "*"
os.environ.pop("LISTAS_SQUAD_DATABASE_URL", None)
os.environ["DATABASE_URL"] = "sqlite://"  # placeholder; cada teste ganha o seu via fixture

from sqlalchemy import create_engine  

from db import models, session as db_session 
import server  


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """Banco SQLite isolado por teste, com as tabelas do models.py."""
    engine = create_engine(f"sqlite:///{tmp_path / 'teste.db'}")
    models.Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(db_session, "_engine", engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


@pytest.fixture
def auth():
    return {"X-API-Token": TEST_TOKEN}
