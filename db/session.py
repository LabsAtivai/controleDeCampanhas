import os

from sqlalchemy import create_engine
from db import models

_engine = None


def get_engine():
    """Engine criado sob demanda (na primeira chamada), não no import — assim
    os módulos podem ser importados sem DATABASE_URL (ex: testes)."""
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL não configurada no ambiente.")
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,       # Testa conexão antes de usar
            pool_recycle=3600,        # Recicla conexões a cada 1h
            connect_args={
                "connect_timeout": 10  # Timeout de conexão em segundos
            }
        )
    return _engine


def __getattr__(name):
    # Compatibilidade com `from db.session import engine` em scripts antigos
    if name == "engine":
        return get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def create_tables():
    models.Base.metadata.create_all(bind=get_engine())
