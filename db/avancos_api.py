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
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

_TTL = 60  # segundos de cache — avanço novo aparece no painel em até 1 min
_cache = {}
_lock = threading.Lock()


def _base_url() -> str:
    return os.environ.get("AVANCOS_API_URL", "http://207.244.249.157:3098/api").rstrip("/")


def _cached(chave, carrega):
    with _lock:
        hit = _cache.get(chave)
        if hit and time.time() - hit[0] < _TTL:
            return hit[1]
    valor = carrega()
    with _lock:
        _cache[chave] = (time.time(), valor)
    return valor


def _norm(texto) -> str:
    return (texto or "").strip().lower()


# Nomes no sistema de avanços que não casam sozinhos com a credencial:
# chave normalizada (_chave) -> cliente da credencial.
_ALIASES = {
    "linkmochilas": "linkpromocional",  # mesma conta Snov.io (linkpromocional2@ativa.ai)
    "madelogstica": "made",             # "Made Logística" vem com encoding quebrado
}


def _chave(texto) -> str:
    """Minúsculo, sem acento nem pontuação — 'Sindmóveis' e 'sindmoveis' casam."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def _sem_sufixo(texto) -> str:
    """'Sindmóveis [Geral]' / 'Made Logística - Reativação' -> nome base."""
    return re.split(r"\s*(?:\[|\s-\s)", texto or "", maxsplit=1)[0]


def _get(path: str, **params):
    resp = requests.get(f"{_base_url()}{path}", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def mapa_conta_cliente() -> dict:
    """snovEmail (minúsculo) -> nome do cliente."""
    def carrega():
        return {_norm(c["snovEmail"]): c["cliente"].strip() for c in _get("/credenciais") if c.get("snovEmail")}
    return _cached("credenciais", carrega)


def cliente_da_conta(conta: str) -> str:
    """Nome do cliente da conta; sem credencial cadastrada, a própria conta."""
    return mapa_conta_cliente().get(_norm(conta), conta)


def contas_do_cliente(cliente: str) -> list:
    alvo = _norm(cliente)
    return [conta for conta, nome in mapa_conta_cliente().items() if _norm(nome) == alvo]


def _indice_clientes() -> dict:
    """chave -> cliente canônico (nome na credencial), por nome e por usuário do
    e-mail Snov.io (madelogistica@ativa.ai casa com 'Made Logística')."""
    def carrega():
        indice = {}
        for conta, nome in mapa_conta_cliente().items():
            indice.setdefault(_chave(nome), nome)
            indice.setdefault(_chave(conta.split("@")[0]), nome)
        for alias, nome in _ALIASES.items():
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
        registros, pagina = [], 1
        while True:
            resp = _get("/avancos", limit=200, page=pagina, **filtros)
            registros.extend(resp["dados"])
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
    """Nutrição não conta pro semáforo (decisão do negócio)."""
    return not _chave(tipo).startswith("nutri")


def tem_vinculo(cliente: str) -> bool:
    """True se o cliente existe nas credenciais do sistema de avanços."""
    alvo = _norm(cliente)
    return any(_norm(nome) == alvo for nome in mapa_conta_cliente().values())


def avancos_por_cliente_dia(inicio: str = None, fim: str = None, so_semaforo: bool = False) -> dict:
    """{cliente_canônico_normalizado: {'YYYY-MM-DD': quantidade}} num intervalo.
    so_semaforo=True descarta os tipos que não contam pro semáforo (Nutrição)."""
    saida = defaultdict(lambda: defaultdict(int))
    for r in _avancos(inicio, fim):
        if so_semaforo and not _conta_no_semaforo(r.get("tipo")):
            continue
        saida[resolve_cliente(r["cliente"])][str(r["dataAvanco"])[:10]] += 1
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
    ontem, _, tres_dias_atras = janela_status()
    por_cliente = avancos_por_cliente_dia(inicio=tres_dias_atras, fim=ontem, so_semaforo=True)
    return {cliente: status_avanco(dias) for cliente, dias in por_cliente.items()}
