"""Versioned, restartable schema migration; never silently removes historical data."""
import json
from datetime import datetime
from core.time import utcnow

from sqlalchemy import func, inspect, select, text
from sqlalchemy.schema import CreateColumn
from sqlalchemy.orm import Session

from db.models import Base, Dados, Avanco, DataRepair, SchemaMigration, RunLease, ClientAlias, Campanha
from db.session import engine

VERSION = '0001_integrity_and_operations'


def migrate(resolve_duplicates=False):
    Base.metadata.create_all(engine)
    if 'source_json' not in {c['name'] for c in inspect(engine).get_columns('campanhas')}:
        ddl = str(CreateColumn(Campanha.__table__.c.source_json).compile(dialect=engine.dialect))
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE campanhas ADD COLUMN ' + ddl))
    for model, keys in ((Dados, ('id_conta', 'data')), (Avanco, ('conta', 'data'))):
        with Session(engine) as session:
            columns = [getattr(model, k) for k in keys]
            groups = session.execute(select(*columns).group_by(*columns).having(func.count() > 1)).all()
            if groups and not resolve_duplicates:
                raise RuntimeError(f'{len(groups)} grupos duplicados em {model.__tablename__}. Faça backup e execute migrate --resolve-duplicates para arquivar os anteriores e manter o último id.')
            for group in groups:
                query = select(model).filter_by(**dict(zip(keys, group))).order_by(model.id.desc())
                for row in session.scalars(query).all()[1:]:
                    payload = {c.name: getattr(row, c.name) for c in model.__table__.columns}
                    session.add(DataRepair(source_table=model.__tablename__, source_id=row.id,
                                           payload=json.dumps(payload, default=str), created_at=utcnow()))
                    session.delete(row)
            session.commit()
        existing = {i['name'] for i in inspect(engine).get_indexes(model.__tablename__)}
        for index in model.__table__.indexes:
            if index.name not in existing:
                index.create(engine)
    with Session(engine) as session:
        if not session.get(RunLease, 1):
            session.add(RunLease(id=1, owner=None, expires_at=datetime(1970, 1, 1)))
        if not session.get(SchemaMigration, VERSION):
            for alias, canonical in {'linkmochilas': 'linkpromocional', 'madelogstica': 'made'}.items():
                if not session.get(ClientAlias, alias):
                    session.add(ClientAlias(alias=alias, canonical=canonical))
            session.add(SchemaMigration(version=VERSION, applied_at=utcnow()))
        session.commit()


def ready():
    with Session(engine) as session:
        return session.get(SchemaMigration, VERSION) is not None
