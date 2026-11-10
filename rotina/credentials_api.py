"""Cliente do sistema de credenciais (snov-am-api) — substitui a leitura da aba
"contas" do Google Sheets. Mesmo padrão usado no painel_listas
(services/credentialsApi.js): busca as contas ativas e, pra cada uma, descriptografa
as credenciais Snov.io via endpoint interno.
"""
import os
import time

import httpx


def _client() -> httpx.Client:
    base_url = os.environ.get("CREDENTIALS_API_URL")
    api_key = os.environ.get("CREDENTIALS_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError(
            "CREDENTIALS_API_URL e CREDENTIALS_API_KEY precisam estar definidos no ambiente."
        )
    return httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=30)


def _get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET com retry em 429 (rate limit da API de credenciais)."""
    for tentativa in range(6):
        try:
            res = client.get(url, **kwargs)
        except httpx.TransportError:
            time.sleep(5 * (tentativa + 1))
            continue
        if res.status_code != 429:
            res.raise_for_status()
            return res
        time.sleep(float(res.headers.get("Retry-After", 5 * (tentativa + 1))))
    raise RuntimeError(f"Falha ao consultar {url} após 6 tentativas")


def _fetch_active_accounts(client: httpx.Client) -> list[dict]:
    # A API ordena só por created_at (empates em contas criadas em lote), então a
    # paginação pode repetir/pular contas. Junta por id e repete a varredura com
    # page_size diferente (muda o corte dos empates) até fechar o total.
    accounts: dict[str, dict] = {}
    total = None
    for size in (100, 99, 50, 33, 25, 10, 7, 3):
        page = 1
        while True:
            res = _get(client, "/api/accounts", params={"status": "ACTIVE", "page": page, "page_size": size})
            data = res.json()
            total = data["total"]
            for item in data["items"]:
                accounts[item["id"]] = item
            if page * size >= total or not data["items"]:
                break
            page += 1
        if len(accounts) >= total:
            break
    if len(accounts) < total:
        # Ainda faltam contas: particiona a busca por substring do e-mail (q), cada
        # fatia é pequena o bastante pra paginar sem depender da ordenação da API
        for termo in "abcdefghijklmnopqrstuvwxyz0123456789":
            page = 1
            while True:
                res = _get(client, "/api/accounts", params={"status": "ACTIVE", "q": termo, "page": page, "page_size": 100})
                data = res.json()
                for item in data["items"]:
                    accounts[item["id"]] = item
                if page * 100 >= data["total"] or not data["items"]:
                    break
                page += 1
            if len(accounts) >= total:
                break
    if len(accounts) < total:
        print(f"[AVISO] Paginação incompleta: {len(accounts)}/{total} contas ativas (corrigir ordenação da API)", flush=True)
    return list(accounts.values())


def _fetch_credentials(client: httpx.Client, account_id: str) -> dict:
    res = _get(client, f"/api/internal/accounts/{account_id}/credentials")
    return res.json()


def get_active_clients() -> list[dict]:
    """Retorna uma lista de dicts: id, email, client_id, client_secret, email_snovio, senha."""
    with _client() as client:
        accounts = _fetch_active_accounts(client)
        clients = []
        for account in accounts:
            creds = _fetch_credentials(client, account["id"])
            clients.append(
                {
                    "id": account["id"],
                    "email": account["email"],
                    "client_id": creds["snov_id"],
                    "client_secret": creds["snov_secret"],
                    "email_snovio": creds["snov_email"],
                    "senha": creds["snov_password"],
                }
            )
        return clients
