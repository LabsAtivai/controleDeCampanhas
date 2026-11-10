"""Starts a complete local installation with its own database, never the remote DB."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from dotenv import dotenv_values
    env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / '.env').items() if v is not None}}
    directory = ROOT / 'data'
    directory.mkdir(exist_ok=True)
    env.update(DATABASE_URL='sqlite:///' + str(directory / 'local.db').replace('\\', '/'),
               COOKIE_SECURE='false', TRUST_PROXY='false', LISTAS_SQUAD_DATABASE_URL='',
               GOOGLE_SHEETS_ENABLED='false', PYTHONUNBUFFERED='1')
    if not env.get('ADMIN_EMAIL') or not env.get('ADMIN_PASSWORD'):
        raise RuntimeError('Prepare o administrador: uv run python tools/setup_env.py --admin-email seu@email.com')
    subprocess.run([sys.executable, '-m', 'manage', 'migrate'], cwd=ROOT, env=env, check=True)
    worker_log = open(directory / 'worker.log', 'a', encoding='utf-8')
    worker = subprocess.Popen([sys.executable, '-m', 'core.jobs'], cwd=ROOT, env=env,
                              stdout=worker_log, stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        os.environ.update(env)
        from webapp import create_app
        from waitress import serve
        print('Sistema local: http://127.0.0.1:8000/login.html', flush=True)
        print('Banco local separado. Google Sheets desabilitado neste modo. Sem dados fictícios.', flush=True)
        serve(create_app(), host='127.0.0.1', port=8000, threads=8)
    finally:
        worker.terminate()
        worker.wait(timeout=30)
        worker_log.close()


if __name__ == '__main__':
    main()
