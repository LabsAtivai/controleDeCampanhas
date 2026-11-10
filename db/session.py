import os
from core.config import ROOT

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import models

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada no ambiente.")

sqlite = DATABASE_URL.startswith('sqlite')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600,
                       connect_args={'check_same_thread': False, 'timeout': 30} if sqlite else {'connect_timeout': 10})
SessionLocal = sessionmaker(bind=engine)

def create_tables():
    """Only for isolated databases. Production schema changes use manage migrate."""
    models.Base.metadata.create_all(bind=engine)
