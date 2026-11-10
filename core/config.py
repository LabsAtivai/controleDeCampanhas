import os
from pathlib import Path
import ipaddress
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)


def enabled(name, default=False):
    return os.getenv(name, str(default)).lower() in {'true', '1', 'yes'}


def integration_url(value):
    parsed = urlparse(value or '')
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Endereço de integração inválido; configure URL sem credenciais embutidas.')
    if parsed.scheme == 'http' and not enabled('ALLOW_INSECURE_INTEGRATIONS'):
        hostname = parsed.hostname
        try:
            internal = ipaddress.ip_address(hostname).is_private or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            internal = hostname == 'localhost' or '.' not in hostname
        if not internal:
            raise ValueError('Integrações públicas devem usar HTTPS. Para uma exceção explícita, configure ALLOW_INSECURE_INTEGRATIONS=true.')
    return value


def google_client():
    import pygsheets
    path = Path(os.getenv('GOOGLE_CREDENTIALS_FILE', ROOT / 'sheets.googleapis.com-python.json'))
    if not path.is_file():
        raise RuntimeError('Credencial Google não encontrada; configure GOOGLE_CREDENTIALS_FILE.')
    # Accept service-account JSON or the existing authorized-user OAuth file.
    import json
    kind = json.loads(path.read_text(encoding='utf-8')).get('type')
    if kind == 'service_account':
        return pygsheets.authorize(service_account_file=str(path))
    from google.oauth2.credentials import Credentials
    data = json.loads(path.read_text(encoding='utf-8'))
    if 'refresh_token' in data:
        return pygsheets.authorize(custom_credentials=Credentials.from_authorized_user_info(data))
    return pygsheets.authorize(credentials_directory=str(path.parent))


def master_sheet_id():
    value = os.getenv('GOOGLE_MASTER_SHEET_ID', '')
    if not value:
        raise RuntimeError('Configure GOOGLE_MASTER_SHEET_ID.')
    return value
