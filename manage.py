"""Explicit lifecycle commands. Importing the application never changes its schema."""
import argparse
import getpass
import gzip
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from core.time import utcnow
from pathlib import Path

from sqlalchemy import DateTime, Date, select, func
from sqlalchemy.orm import Session

from core.config import ROOT
from db.models import Base, User
from db.session import engine


def backup(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    try:
        with engine.connect() as conn:
            if engine.dialect.name == 'mysql':
                conn = conn.execution_options(isolation_level='REPEATABLE READ')
            with conn.begin(), gzip.open(temporary, 'wt', encoding='utf-8') as output:
                output.write(json.dumps({'format': 'ativa-backup-1', 'created_at': utcnow().isoformat()}) + '\n')
                for table in Base.metadata.sorted_tables:
                    for row in conn.execute(select(table)).mappings():
                        output.write(json.dumps({'table': table.name, 'row': dict(row)}, default=str, ensure_ascii=False) + '\n')
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def restore(source, replace=False):
    with gzip.open(source, 'rt', encoding='utf-8') as input:
        header = json.loads(next(input))
        if header.get('format') != 'ativa-backup-1':
            raise ValueError('Formato de backup inválido.')
        records = [json.loads(line) for line in input]
    with engine.begin() as conn:
        if not replace:
            occupied = [table.name for table in Base.metadata.sorted_tables
                        if conn.scalar(select(func.count()).select_from(table))]
            if occupied:
                raise ValueError('Restaure em banco vazio ou use --replace explicitamente após backup.')
        else:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
        grouped = {}
        for record in records:
            if record['table'] not in Base.metadata.tables:
                raise ValueError('Backup contém tabela desconhecida.')
            grouped.setdefault(record['table'], []).append(record['row'])
        for table in Base.metadata.sorted_tables:
            for row in grouped.get(table.name, []):
                for column in table.columns:
                    value = row.get(column.name)
                    if value is not None and isinstance(column.type, DateTime):
                        row[column.name] = datetime.fromisoformat(value)
                    elif value is not None and isinstance(column.type, Date):
                        row[column.name] = datetime.fromisoformat(value).date()
                conn.execute(table.insert().values(**row))
        from db.models import Job, RunLease
        conn.execute(RunLease.__table__.update().values(owner=None, expires_at=datetime(1970, 1, 1)))
        conn.execute(Job.__table__.update().where(Job.status == 'running').values(
            status='interrupted', error='Execução interrompida pela restauração do backup.', finished_at=utcnow()))
        conn.execute(User.__table__.update().values(session_version=User.session_version + 1))


def bootstrap():
    from core.security import save_user
    email, password = os.getenv('ADMIN_EMAIL'), os.getenv('ADMIN_PASSWORD')
    if email and password:
        with Session(engine) as db:
            exists = db.scalar(select(User).where(User.email == email.strip().lower()))
        if not exists:
            save_user(email, password, 'admin')
    with Session(engine) as db:
        if not db.scalar(select(User).where(User.active.is_(True), User.role == 'admin')):
            raise RuntimeError('Configure ADMIN_EMAIL e ADMIN_PASSWORD ou crie um administrador com manage user.')


def main():
    parser = argparse.ArgumentParser(description='Operação do Controle de Campanhas')
    sub = parser.add_subparsers(dest='command', required=True)
    migrate = sub.add_parser('migrate')
    migrate.add_argument('--resolve-duplicates', action='store_true')
    user = sub.add_parser('user')
    user.add_argument('email')
    user.add_argument('--role', choices=['viewer', 'admin'], default='viewer')
    user.add_argument('--inactive', action='store_true')
    for command in ['backup', 'restore']:
        item = sub.add_parser(command)
        item.add_argument('path')
        if command == 'restore':
            item.add_argument('--replace', action='store_true')
    sub.add_parser('backup-loop')
    sub.add_parser('check')
    args = parser.parse_args()
    if args.command == 'migrate':
        from db.migrations import migrate
        migrate(args.resolve_duplicates)
        bootstrap()
        print('Migração concluída.')
    elif args.command == 'user':
        from core.security import save_user
        password = getpass.getpass('Senha (mínimo 12 caracteres): ')
        if password != getpass.getpass('Confirme a senha: '):
            raise ValueError('Senhas diferentes.')
        save_user(args.email, password, args.role, not args.inactive)
        print('Usuário salvo; sessões anteriores invalidadas.')
    elif args.command == 'backup':
        backup(args.path)
        print('Backup concluído. Proteja o arquivo: contém dados e hashes de acesso.')
    elif args.command == 'restore':
        restore(args.path, args.replace)
        print('Restauração concluída. Reinicie os serviços e revise jobs pendentes.')
    elif args.command == 'backup-loop':
        directory = Path(os.getenv('BACKUP_DIRECTORY', '/backups'))
        while True:
            try:
                path = directory / (utcnow().strftime('%Y%m%dT%H%M%SZ') + '.jsonl.gz')
                backup(path)
                for existing in directory.glob('*.jsonl.gz'):
                    if datetime.fromtimestamp(existing.stat().st_mtime) < datetime.now() - timedelta(days=14):
                        existing.unlink()
                print('Backup diário concluído.', flush=True)
            except Exception as exc:
                print(f'Backup falhou: {type(exc).__name__}', flush=True)
            time.sleep(86400)
    elif args.command == 'check':
        from db.migrations import ready
        print(json.dumps({'database': ready(), 'google_enabled': os.getenv('GOOGLE_SHEETS_ENABLED', 'true'),
            'credentials_configured': bool(os.getenv('CREDENTIALS_API_URL') and os.getenv('CREDENTIALS_API_KEY')),
            'advances_configured': bool(os.getenv('AVANCOS_API_URL')), 'secret_configured': len(os.getenv('SECRET_KEY', '')) >= 32}))


if __name__ == '__main__':
    main()
