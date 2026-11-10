"""Queues yesterday's closed-day collection once, with bounded catch-up after restarts."""
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.jobs import enqueue
from db.models import Job
from db.session import engine

def tick(now=None):
    now = now or datetime.now(ZoneInfo('America/Sao_Paulo'))
    if now.hour < 1:
        return []
    target = now.date() - timedelta(days=1)
    with Session(engine) as db:
        last = db.scalar(select(Job.schedule_key).where(Job.schedule_key.like('daily:%')).order_by(Job.schedule_key.desc()).limit(1))
    first = datetime.fromisoformat(last.split(':', 1)[1]).date() + timedelta(days=1) if last else target
    first = max(first, target - timedelta(days=6))
    ids = []
    while first <= target:
        ids.append(enqueue('diario', {'data': first.isoformat()}, schedule_key='daily:' + first.isoformat()))
        first += timedelta(days=1)
    return ids

def main():
    from db.migrations import ready
    if not ready():
        raise RuntimeError('Execute python -m manage migrate primeiro.')
    while True:
        tick()
        time.sleep(30)

if __name__ == '__main__':
    main()
