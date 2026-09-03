import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import models

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada no ambiente.")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # Testa conexão antes de usar
    pool_recycle=3600,        # Recicla conexões a cada 1h
    connect_args={
        "connect_timeout": 10  # Timeout de conexão em segundos
    }
)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

def create_tables():
    models.Base.metadata.create_all(bind=engine)