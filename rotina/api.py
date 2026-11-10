"""Snov.io transport. Never logs upstream bodies, tokens or credential-bearing URLs."""
import time
import httpx
import pandas as pd
from rotina import credentials_api

class SnovError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status

def _request(method, path, **kwargs):
    for attempt in range(4):
        try:
            response = httpx.request(method, f'https://api.snov.io{path}', timeout=30, **kwargs)
        except httpx.TransportError:
            if attempt == 3:
                raise SnovError('Snov.io indisponível após 4 tentativas.') from None
            time.sleep(2 ** attempt)
            continue
        if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
            time.sleep(2 ** attempt)
            continue
        if response.status_code >= 400:
            raise SnovError(f'Snov.io retornou HTTP {response.status_code}.', response.status_code)
        try:
            return response.json()
        except ValueError:
            raise SnovError('Resposta inválida do Snov.io.') from None

def gera_token(client_id, client_secret):
    data = _request('POST', '/v1/oauth/access_token', data={
        'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': client_secret})
    if not isinstance(data, dict) or not isinstance(data.get('access_token'), str):
        raise SnovError('Snov.io não retornou um token válido.')
    return data['access_token']

def campanhas(token):
    data = _request('GET', '/v1/get-user-campaigns', headers={'Authorization': f'Bearer {token}'})
    if not isinstance(data, list):
        raise SnovError('Formato inesperado na lista de campanhas.')
    frame = pd.DataFrame(data)
    if not frame.empty and not {'id', 'campaign', 'status'}.issubset(frame.columns):
        raise SnovError('Campanhas sem os campos obrigatórios.')
    return frame

def senhas(ids=None):
    return pd.DataFrame(credentials_api.get_active_clients(ids),
        columns=['id', 'email', 'client_id', 'client_secret', 'email_snovio']).rename(columns={
        'email': 'Email', 'client_id': 'Client id', 'client_secret': 'Client Secret', 'email_snovio': 'Email Snovio'})

def contas_ativas(historico=False):
    from db.crud import get_campanhas_ativas
    return get_campanhas_ativas(historico=historico)

def get_campaign_analytics(token, id, inicio, final):
    data = _request('GET', '/v2/statistics/campaign-analytics', params={
        'access_token': token, 'campaign_id': str(id), 'date_from': inicio, 'date_to': final})
    fields = {'total_contacted', 'emails_sent', 'delivered', 'email_opens', 'link_clicks', 'email_replies'}
    if not isinstance(data, dict) or not fields.issubset(data):
        raise SnovError('Métricas incompletas na resposta do Snov.io.')
    for field in fields:
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or int(value) != value:
            raise SnovError(f'Métrica inválida: {field}.')
    return data

def user_lists(token, id):
    return pd.DataFrame(_request('GET', '/v1/emails-sent', params={'access_token': token, 'campaignId': int(id)}))
