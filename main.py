"""Manual CLI enqueues durable jobs; it never bypasses the shared executor."""
import argparse
from core.jobs import enqueue
from core.validation import period
from db.avancos_api import hoje_sp

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inicio', required=True)
    parser.add_argument('--fim')
    args = parser.parse_args()
    start, end = period(args.inicio, args.fim or args.inicio, max_days=31)
    if end >= hoje_sp():
        raise ValueError('Selecione dias fechados anteriores a hoje.')
    job_id = enqueue('custom', {'inicio':start.isoformat(), 'fim':end.isoformat()}, actor='cli')
    print('Execução enfileirada: ' + job_id)

if __name__ == '__main__':
    main()
