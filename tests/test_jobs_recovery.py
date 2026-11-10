import json
import threading
from datetime import datetime, timedelta
from core.time import utcnow

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core import jobs
from db.models import Job, JobLog, RunLease
from db.session import engine
from rotina.acao import CollectionError


def test_worker_persists_result_and_logs(monkeypatch):
    id = jobs.enqueue('campanhas', actor='test')
    def action(*args):
        print('Processando conta de teste')
        return {'collected': 1}
    monkeypatch.setattr(jobs, 'execute', action)
    assert jobs.work_once()
    with Session(engine) as db:
        job = db.get(Job, id)
        assert job.status == 'completed'
        assert json.loads(job.result)['collected'] == 1
        assert len(db.scalars(select(JobLog)).all()) >= 3


def test_worker_partial_and_failed_states(monkeypatch):
    id = jobs.enqueue('campanhas')
    def fail(*args):
        raise CollectionError('Falha parcial', {'collected': 1, 'failed': ['b']})
    monkeypatch.setattr(jobs, 'execute', fail)
    jobs.work_once()
    with Session(engine) as db:
        assert db.get(Job, id).status == 'partial'


def test_concurrent_workers_are_serialized(monkeypatch):
    jobs.enqueue('campanhas')
    started, finish = threading.Event(), threading.Event()
    def block(*args):
        started.set()
        assert finish.wait(10)
    monkeypatch.setattr(jobs, 'execute', block)
    worker = threading.Thread(target=jobs.work_once)
    worker.start()
    assert started.wait(10)
    try:
        assert not jobs.work_once()
    finally:
        finish.set()
        worker.join(10)
    assert not worker.is_alive()


def test_crashed_job_becomes_interrupted(monkeypatch):
    id = jobs.enqueue('campanhas')
    with Session(engine) as db:
        db.execute(update(Job).where(Job.id == id).values(status='running'))
        db.execute(update(RunLease).values(owner='dead', expires_at=utcnow() - timedelta(seconds=1)))
        db.commit()
    assert not jobs.work_once()
    with Session(engine) as db:
        assert db.get(Job, id).status == 'interrupted'


def test_logs_keep_working_after_5000(client, admin):
    id = jobs.enqueue('campanhas')
    with Session(engine) as db:
        db.add_all([JobLog(job_id=id, message=str(i), created_at=utcnow()) for i in range(5101)])
        db.commit()
    response = client.get('/api/logs?since=5000').json
    assert len(response['lines']) == 101
    assert response['cursor'] == 5101


def test_scheduler_idempotency_and_timezone():
    from app import tick
    from zoneinfo import ZoneInfo
    now = datetime(2026, 11, 10, 1, 0, tzinfo=ZoneInfo('America/Sao_Paulo'))
    assert len(tick(now)) == 1
    assert tick(now) == []
    with Session(engine) as db:
        job = db.scalar(select(Job))
        assert json.loads(job.params)['data'] == '2026-11-09'


def test_failed_job_can_be_retried_with_original_parameters(client, admin):
    id = jobs.enqueue('custom', {'inicio': '2026-01-01', 'fim': '2026-01-02'})
    with Session(engine) as db:
        db.execute(update(Job).where(Job.id == id).values(status='failed'))
        db.commit()
    response = client.post(f'/api/jobs/{id}/retry', headers=admin)
    assert response.status_code == 202
    with Session(engine) as db:
        assert json.loads(db.get(Job, response.json['job_id']).params)['inicio'] == '2026-01-01'
