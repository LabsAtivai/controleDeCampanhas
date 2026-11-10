"""Durable queue shared by API, scheduler and worker. No HTTP request runs a job."""
import contextlib
import io
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from core.time import utcnow

from sqlalchemy import or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import audit, redact
from db.models import Job, JobLog, RunLease
from db.session import engine

TERMINAL = {'completed', 'partial', 'failed', 'interrupted'}


def enqueue(action, params=None, actor='scheduler', schedule_key=None):
    job_id = str(uuid.uuid4())
    with Session(engine) as db:
        if schedule_key:
            existing = db.scalar(select(Job).where(Job.schedule_key == schedule_key))
            if existing:
                return existing.id
        db.add(Job(id=job_id, action=action, params=json.dumps(params or {}), actor=actor,
                   schedule_key=schedule_key, status='queued', created_at=utcnow()))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not schedule_key:
                raise
            return db.scalar(select(Job.id).where(Job.schedule_key == schedule_key))
    audit(actor, 'job.queued', {'id': job_id, 'action': action, 'params': params or {}})
    return job_id


def serialize(job):
    return {key: (getattr(job, key).isoformat() + 'Z' if isinstance(getattr(job, key), datetime) else getattr(job, key))
            for key in ('id', 'action', 'actor', 'status', 'created_at', 'started_at', 'finished_at', 'heartbeat_at', 'error')} | {
                'result': json.loads(job.result) if job.result else None}


def list_jobs(limit=100):
    with Session(engine) as db:
        return [serialize(j) for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit))]


def log(job_id, message):
    message = redact(message).strip()
    if message:
        with Session(engine) as db:
            db.add(JobLog(job_id=job_id, message=message[:8000], created_at=utcnow()))
            db.commit()


class JobStream(io.TextIOBase):
    def __init__(self, job_id):
        self.job_id, self.pending = job_id, ''

    def write(self, text):
        self.pending += text
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            log(self.job_id, line)
        if len(self.pending) > 8000:
            log(self.job_id, self.pending)
            self.pending = ''
        return len(text)

    def flush(self):
        if self.pending:
            log(self.job_id, self.pending)
            self.pending = ''


def execute(action, params):
    from rotina import acao
    if action == 'campanhas':
        return acao.extrai_campanhas(params.get('ids'))
    if action == 'dia-anterior':
        return acao.extrai_dia_anterior()
    if action == 'custom':
        from rotina import api
        credentials = api.senhas()
        day = datetime.strptime(params['inicio'], '%Y-%m-%d').date()
        end = datetime.strptime(params['fim'], '%Y-%m-%d').date()
        results, failures = [], []
        while day <= end:
            try:
                results.append(acao.extrai_dia_anterior_custom(day, params.get('contas'), credenciais=credentials))
            except acao.CollectionError as exc:
                results.append(exc.result)
                failures.append(day.isoformat())
            day += timedelta(days=1)
        if failures:
            result = {'dias': results, 'failed_days': failures, 'collected': sum(d.get('collected', 0) for d in results)}
            raise acao.CollectionError('Intervalo com dias incompletos; consulte o resultado.', result)
        return {'dias': results}
    if action == 'planilhas':
        return acao.atualiza_planilhas_controle()
    if action == 'diario':
        return {'campanhas': acao.extrai_campanhas(), 'metricas': acao.extrai_dia_anterior_custom(params['data']) if params.get('data') else acao.extrai_dia_anterior(),
                'planilhas': acao.atualiza_planilhas_controle()}
    raise ValueError('Ação desconhecida.')


def work_once():
    owner = str(uuid.uuid4())
    # MySQL advisory lock is pinned to a connection and released by the server on crash.
    connection = engine.connect() if engine.dialect.name == 'mysql' else None
    stop = threading.Event()
    beat = None
    try:
        if connection and not connection.scalar(text("SELECT GET_LOCK('ativa_campaign_worker', 0)")):
            return False
        now = utcnow()
        with Session(engine) as db:
            acquired = db.execute(update(RunLease).where(RunLease.id == 1,
                or_(RunLease.owner.is_(None), RunLease.expires_at < now)).values(owner=owner, expires_at=now + timedelta(seconds=90))).rowcount
            db.commit()
            if not acquired:
                return False
            # The previous process lost its lease. Never silently retry a partly published job.
            db.query(Job).filter(Job.status == 'running').update({'status': 'interrupted', 'finished_at': now, 'error': 'Executor interrompido; revise e reprocesse a execução.'})
            job = db.scalar(select(Job).where(Job.status == 'queued').order_by(Job.created_at, Job.id).limit(1))
            if not job:
                db.commit()
                return False
            job.status, job.started_at, job.heartbeat_at = 'running', now, now
            job_id, action, params = job.id, job.action, json.loads(job.params)
            db.commit()

        def heartbeat():
            while not stop.wait(15):
                try:
                    with Session(engine) as db:
                        tick = utcnow()
                        db.execute(update(RunLease).where(RunLease.id == 1, RunLease.owner == owner).values(expires_at=tick + timedelta(seconds=90)))
                        db.execute(update(Job).where(Job.id == job_id).values(heartbeat_at=tick))
                        db.commit()
                except Exception:
                    # A MySQL advisory lock still prevents another executor from entering.
                    continue

        beat = threading.Thread(target=heartbeat, daemon=True)
        beat.start()
        stream = JobStream(job_id)
        result, error, status = None, None, 'completed'
        try:
            log(job_id, f'Iniciando {action}')
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                result = execute(action, params)
        except Exception as exc:
            status = 'partial' if getattr(exc, 'partial', False) else 'failed'
            result = getattr(exc, 'result', None)
            error = redact(exc)
            log(job_id, error)
        finally:
            stream.flush()
        with Session(engine) as db:
            db.execute(update(Job).where(Job.id == job_id).values(status=status, finished_at=utcnow(),
                result=json.dumps(result, default=str, ensure_ascii=False) if result is not None else None, error=error))
            db.commit()
        log(job_id, f'Finalizado: {status}')
        if status != 'completed':
            notify_failure(job_id, status)
        return True
    finally:
        stop.set()
        if beat:
            beat.join(timeout=20)
        with Session(engine) as db:
            db.execute(update(RunLease).where(RunLease.id == 1, RunLease.owner == owner).values(owner=None, expires_at=utcnow()))
            db.commit()
        if connection:
            try:
                connection.execute(text("SELECT RELEASE_LOCK('ativa_campaign_worker')"))
            finally:
                connection.close()


def notify_failure(job_id, status):
    url = os.getenv('ALERT_WEBHOOK_URL')
    if url:
        import httpx
        try:
            httpx.post(url, json={'system': 'controle-campanhas', 'job_id': job_id, 'status': status}, timeout=10).raise_for_status()
        except Exception:
            log(job_id, 'Falha ao entregar alerta; verifique o webhook de monitoramento.')


def main():
    from db.migrations import ready
    if not ready():
        raise RuntimeError('Execute python -m manage migrate primeiro.')
    while True:
        if not work_once():
            time.sleep(2)


if __name__ == '__main__':
    main()
