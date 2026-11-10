"""Prepare local secrets without printing them or contacting any external service."""
import re
import secrets
import argparse
from dotenv import dotenv_values
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--admin-email')
    args = parser.parse_args()
    path = ROOT / '.env'
    content = path.read_text(encoding='utf-8-sig') if path.exists() else (ROOT / '.env.example').read_text(encoding='utf-8')
    values = dotenv_values(stream=__import__('io').StringIO(content))
    legacy = ROOT / 'painel-api/.env'
    if legacy.exists():
        for key, value in dotenv_values(legacy).items():
            if value and not values.get(key) and key not in {'ADMIN_PASSWORD', 'SECRET_KEY'}:
                content += '\n' + key + '=' + __import__('json').dumps(value) + '\n'
                values[key] = value
    if not re.search(r'^SECRET_KEY=.{32,}$', content, re.M):
        content = re.sub(r'^SECRET_KEY=.*\n?', '', content, flags=re.M)
        content += '\nSECRET_KEY=' + secrets.token_urlsafe(48) + '\n'
    if args.admin_email:
        content = re.sub(r'^ADMIN_EMAIL=.*\n?', '', content, flags=re.M)
        content += '\nADMIN_EMAIL=' + args.admin_email.strip().lower() + '\n'
        if not values.get('ADMIN_PASSWORD'):
            password = secrets.token_urlsafe(24)
            content = re.sub(r'^ADMIN_PASSWORD=.*\n?', '', content, flags=re.M)
            content += '\nADMIN_PASSWORD=' + password + '\n'
            directory = ROOT / 'data'
            directory.mkdir(exist_ok=True)
            access = directory / 'primeiro-acesso.txt'
            access.write_text('E-mail: ' + args.admin_email.strip().lower() + '\nSenha inicial: ' + password +
                '\nArquivo local privado, ignorado pelo Git. Altere a senha após o primeiro acesso.\n', encoding='utf-8')
            access.chmod(0o600)
    path.write_text(content, encoding='utf-8')
    path.chmod(0o600)
    print('Arquivo .env preparado. Nenhuma credencial existente foi revogada.')


if __name__ == '__main__':
    main()
