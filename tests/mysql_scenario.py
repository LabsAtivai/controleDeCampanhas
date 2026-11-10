import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.migrations import migrate
from db.models import Base, Dados, Job
from db.session import engine
from db.crud import atualiza_registros
from core import jobs
from manage import backup, restore


def main():
    # MYSQL_TEST_URL is only accepted for an explicitly named disposable database.
    if not engine.url.database.endswith('_test'):
        raise RuntimeError('O nome do banco descartável deve terminar em _test.')
    Base.metadata.drop_all(engine)
    migrate()
    row = {'conta':'test@example.test','campanha':'Teste','id_conta':'100','data':'2026-01-01',
        'total_contacted':10,'emails_sent':10,'delivered':10,'email_opens':1,'link_clicks':1,'email_replies':0}
    atualiza_registros(pd.DataFrame([row]))
    row['emails_sent'] = 20
    atualiza_registros(pd.DataFrame([row]))
    with Session(engine) as db:
        rows = db.scalars(select(Dados)).all()
        assert len(rows) == 1 and rows[0].emails_sent == 20
    job_id = jobs.enqueue('campanhas')
    jobs.execute = lambda *args: {'collected': 1}
    assert jobs.work_once()
    from db import avancos_api
    assert len(avancos_api._cached('large-payload-test', lambda: 'a' * 100000)) == 100000
    with Session(engine) as db:
        assert db.get(Job, job_id).status == 'completed'
    path = backup(Path(sys.argv[1]) / 'mysql.jsonl.gz')
    restore(path, replace=True)
    with Session(engine) as db:
        assert db.scalar(select(Dados)).emails_sent == 20
    print('MySQL migration/upsert/worker/backup/restore: OK')
    engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        from core.security import redact
        print(type(exc).__name__ + ': ' + redact(exc))
        sys.exit(1)
