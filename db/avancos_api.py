"""Integração com o sistema de avanços (avancos-backend, NestJS). Lê avanços e
credenciais via HTTP — o usuário do painel não tem grant no banco avancos_comerciais.

O sistema de avanços identifica o cliente por nome ("cliente"); o painel
identifica por conta Snov.io (e-mail @ativa.ai). A ponte é credenciais_clientes
(cliente <-> snovEmail).
"""
import os
import re
import threading
import unicodedata
import time
import hashlib
import json
from contextvars import ContextVar
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from core.config import integration_url

_warnings = ContextVar('integration_warnings', default=None)
_request_cache = ContextVar('integration_request_cache', default=None)


class IntegrationUnavailable(RuntimeError):
    pass


def begin_request():
    _warnings.set([])
    _request_cache.set({})


def warn(message):
    messages = _warnings.get()
    if messages is None:
        messages = []
        _warnings.set(messages)
    if message not in messages:
        messages.append(message)


def warnings():
    return list(_warnings.get() or [])

_TTL = 60  # segundos de cache — avanço novo aparece no painel em até 1 min
_cache = {}
_lock = threading.Lock()


def _base_url() -> str:
    value = os.environ.get('AVANCOS_API_URL', '').rstrip('/')
    if not value:
        raise IntegrationUnavailable('Integração de avanços não configurada.')
    return integration_url(value)


def _cached(chave, carrega):
    # One upstream attempt per dependency per HTTP request, including failures.
    # Without this, an unavailable mapping could trigger one timeout per campaign.
    memo = _request_cache.get()
    if memo is not None and chave in memo:
        ok, value = memo[chave]
        if not ok:
            raise IntegrationUnavailable('Integração indisponível nesta consulta.')
        return value
    try:
        value = _load_cached(chave, carrega)
    except IntegrationUnavailable:
        if memo is not None:
            memo[chave] = (False, None)
        raise
    if memo is not None:
        memo[chave] = (True, value)
    return value


def _load_cached(chave, carrega):
    from sqlalchemy.orm import Session
    from db.session import engine
    from db.models import IntegrationCache
    from db.upsert import upsert
    key = hashlib.sha256(json.dumps(chave, sort_keys=True).encode()).hexdigest()
    with _lock:
        hit = _cache.get(chave)
    if not hit:
        with Session(engine) as db:
            saved = db.get(IntegrationCache, key)
            if saved:
                hit = (saved.updated_at.replace(tzinfo=ZoneInfo('UTC')).timestamp(), json.loads(saved.value))
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    before = len(warnings())
    try:
        valor = carrega()
    except (requests.RequestException, ValueError, KeyError, TypeError, IntegrationUnavailable):
        if hit and time.time() - hit[0] <= int(os.getenv('INTEGRATION_MAX_STALE_SECONDS', '86400')):
            stamp = datetime.fromtimestamp(hit[0], ZoneInfo('UTC')).isoformat()
            warn(f'Integração {str(chave).split(chr(44))[0]} indisponível: exibindo cache de {stamp}.')
            return hit[1]
        warn(f'Integração {str(chave).split(chr(44))[0]} indisponível; valores não representam zero.')
        raise IntegrationUnavailable('Integração indisponível e sem cache válido.') from None
    # Never refresh the age of a derived result computed from a stale dependency.
    if len(warnings()) > before:
        return valor
    with engine.begin() as conn:
        upsert(conn, IntegrationCache.__table__, {'key': key, 'value': json.dumps(valor), 'updated_at': datetime.fromtimestamp(time.time(), ZoneInfo('UTC')).replace(tzinfo=None)}, ['key'])
        from sqlalchemy import delete, select
        oldest = conn.execute(select(IntegrationCache.key).order_by(IntegrationCache.updated_at.desc()).offset(1000)).scalars().all()
        if oldest:
            conn.execute(delete(IntegrationCache).where(IntegrationCache.key.in_(oldest)))
    with _lock:
        if len(_cache) >= 1000:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[chave] = (time.time(), valor)
    return valor


def _norm(texto) -> str:
    return (texto or "").strip().lower()


# Nomes no sistema de avanços que não casam sozinhos com a credencial:
# chave normalizada (_chave) -> cliente da credencial.
def _aliases():
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from db.models import ClientAlias
    from db.session import engine
    with Session(engine) as db:
        return {row.alias: row.canonical for row in db.scalars(select(ClientAlias))}


def _chave(texto) -> str:
    """Minúsculo, sem acento nem pontuação — 'Sindmóveis' e 'sindmoveis' casam."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def _sem_sufixo(texto) -> str:
    """'Sindmóveis [Geral]' / 'Made Logística - Reativação' -> nome base."""
    return re.split(r"\s*(?:\[|\s-\s)", texto or "", maxsplit=1)[0]


def _get(path: str, **params):
    key = os.getenv('AVANCOS_API_KEY')
    if not key:
        raise IntegrationUnavailable('Chave da integração de avanços não configurada.')
    headers = {os.getenv('AVANCOS_API_KEY_HEADER', 'X-API-Key'): key}
    resp = requests.get(f"{_base_url()}{path}", params=params, headers=headers, timeout=(5, 20))
    resp.raise_for_status()
    return resp.json()


def mapa_conta_cliente() -> dict:
    """snovEmail (minúsculo) -> nome do cliente."""
    def carrega():
        rows = _get('/integracoes/painel/v1/clientes')['clientes']
        return {_norm(c['snovEmail']): c['cliente'].strip() for c in rows if c.get('snovEmail')}
    return _cached("credenciais", carrega)


def cliente_da_conta(conta: str) -> str:
    """Nome do cliente da conta; sem credencial cadastrada, a própria conta."""
    try:
        return mapa_conta_cliente().get(_norm(conta), conta)
    except IntegrationUnavailable:
        return conta


def contas_do_cliente(cliente: str) -> list:
    alvo = _norm(cliente)
    try:
        return [conta for conta, nome in mapa_conta_cliente().items() if _norm(nome) == alvo]
    except IntegrationUnavailable:
        return []


def _indice_clientes() -> dict:
    """chave -> cliente canônico (nome na credencial), por nome e por usuário do
    e-mail Snov.io (madelogistica@ativa.ai casa com 'Made Logística')."""
    def carrega():
        indice = {}
        for conta, nome in mapa_conta_cliente().items():
            indice.setdefault(_chave(nome), nome)
            indice.setdefault(_chave(conta.split("@")[0]), nome)
        for alias, nome in _aliases().items():
            indice[alias] = nome
        return indice
    return _cached("indice", carrega)


def resolve_cliente(nome_avanco: str) -> str:
    """Normalizado do cliente canônico do avanço. Tenta o nome inteiro, depois o
    nome sem sufixo de campanha; sem match, o próprio nome normalizado."""
    indice = _indice_clientes()
    for candidato in (nome_avanco, _sem_sufixo(nome_avanco)):
        canonico = indice.get(_chave(candidato))
        if canonico:
            return _norm(canonico)
    return _norm(nome_avanco)


def _avancos(inicio: str = None, fim: str = None, cliente: str = None) -> list:
    def carrega():
        filtros = {}
        if inicio:
            filtros["dataInicio"] = inicio
        if fim:
            filtros["dataFim"] = fim
        if cliente:
            filtros["cliente"] = cliente
        registros, pagina, vistos = [], 1, set()
        while True:
            resp = _get("/avancos", limit=200, page=pagina, **filtros)
            rows = resp['dados']
            page_ids = {r['id'] for r in rows}
            if pagina > 1 and (not rows or page_ids.issubset(vistos)):
                raise IntegrationUnavailable('Paginação de avanços incompleta.')
            registros.extend(r for r in rows if r['id'] not in vistos)
            vistos.update(page_ids)
            if pagina > 2000:
                raise IntegrationUnavailable('Consulta muito extensa; selecione um período menor.')
            if pagina >= resp.get("totalPaginas", 1):
                return registros
            pagina += 1
    return _cached(("avancos", inicio, fim, cliente), carrega)


def _nomes_brutos() -> dict:
    """{nome no sistema de avanços: total histórico} — 1 chamada só."""
    return _cached("opcoes", lambda: {o["valor"]: int(o["total"]) for o in _get("/avancos/opcoes")["clientes"]})


def hoje_sp() -> date:
    """Data de hoje em America/Sao_Paulo, independente do fuso do servidor."""
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def _conta_no_semaforo(tipo) -> bool:
    """Tipos configuráveis; padrão corresponde à decisão documentada: Interessado."""
    types = {_chave(t) for t in os.getenv('SEMAFORO_TIPOS', 'Interessado').split(',')}
    return _chave(tipo) in types


def tem_vinculo(cliente: str) -> bool:
    """True se o cliente existe nas credenciais do sistema de avanços."""
    alvo = _norm(cliente)
    try:
        return any(_norm(nome) == alvo for nome in mapa_conta_cliente().values())
    except IntegrationUnavailable:
        return False


def avancos_por_cliente_dia(inicio: str = None, fim: str = None, so_semaforo: bool = False) -> dict:
    """{cliente_canônico_normalizado: {'YYYY-MM-DD': quantidade}} num intervalo.
    so_semaforo=True descarta os tipos que não contam pro semáforo (Nutrição)."""
    saida = defaultdict(lambda: defaultdict(int))
    if not inicio and not fim:
        fim = hoje_sp().isoformat()
        inicio = (hoje_sp() - timedelta(days=365)).isoformat()
    cursor = None
    while True:
        params = {'dataInicio': inicio, 'dataFim': fim}
        if cursor:
            params['cursor'] = cursor
        response = _get('/integracoes/painel/v1/resumo', **params)
        for row in response.get('dias', []):
            name = resolve_cliente(row['cliente'])
            count = sum(int(v) for tipo, v in row['porTipo'].items() if not so_semaforo or _conta_no_semaforo(tipo))
            saida[name][str(row['data'])[:10]] += count
        cursor = response.get('proximaPagina')
        if not cursor:
            break
    return saida


def avancos_dia_do_cliente(cliente: str, inicio: str = None, fim: str = None) -> dict:
    """{'YYYY-MM-DD': quantidade} de um cliente, juntando as variantes de nome dele
    (busca por nome no servidor — não baixa o histórico inteiro)."""
    alvo = _norm(cliente)
    vistos, por_dia = set(), defaultdict(int)
    for bruto in (n for n in _nomes_brutos() if resolve_cliente(n) == alvo):
        for r in _avancos(inicio, fim, cliente=bruto):
            if r["id"] in vistos or resolve_cliente(r["cliente"]) != alvo:
                continue
            vistos.add(r["id"])
            por_dia[str(r["dataAvanco"])[:10]] += 1
    return por_dia


def total_por_cliente(inicio: str = None, fim: str = None) -> dict:
    """{cliente_canônico_normalizado: total no período}. Sem período (geral), usa o
    total histórico do sistema de avanços sem paginar tudo."""
    if inicio or fim:
        return {c: sum(d.values()) for c, d in avancos_por_cliente_dia(inicio, fim).items()}
    saida = defaultdict(int)
    for nome, total in _nomes_brutos().items():
        saida[resolve_cliente(nome)] += total
    return saida


def janela_status() -> tuple:
    """Últimos 3 dias fechados: ontem, anteontem e 3 dias atrás. Hoje não conta."""
    hoje = hoje_sp()
    return tuple((hoje - timedelta(days=n)).isoformat() for n in (1, 2, 3))


def status_avanco(por_dia: dict) -> str:
    """Semáforo: verde = 2+ avanços na janela, amarelo = 1, vermelho = nenhum."""
    total = sum(por_dia.get(d, 0) for d in janela_status())
    if total >= 2:
        return "verde"
    if total == 1:
        return "amarelo"
    return "vermelho"


def status_por_cliente() -> dict:
    """{cliente_normalizado: status} — janela fixa, independe do período da tela."""
    response = _get('/integracoes/painel/v1/status', dias=3, excluirHoje='true')
    return {_norm(row['cliente']): row['status'] for row in response['registros']}
