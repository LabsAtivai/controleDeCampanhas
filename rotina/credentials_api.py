"""Cliente do sistema de credenciais (snov-am-api) — substitui a leitura da aba
"contas" do Google Sheets. Mesmo padrão usado no painel_listas
(services/credentialsApi.js): busca as contas ativas e, pra cada uma, descriptografa
as credenciais Snov.io via endpoint interno.
"""
import os

import httpx


def _client() -> httpx.Client:
    base_url = os.environ.get("CREDENTIALS_API_URL")
    api_key = os.environ.get("CREDENTIALS_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError(
            "CREDENTIALS_API_URL e CREDENTIALS_API_KEY precisam estar definidos no ambiente."
        )
    return httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=30)


def _fetch_active_accounts(client: httpx.Client) -> list[dict]:
    accounts: list[dict] = []
    page = 1
    page_size = 100
    while True:
        res = client.get("/api/accounts", params={"status": "ACTIVE", "page": page, "page_size": page_size})
        res.raise_for_status()
        data = res.json()
        accounts.extend(data["items"])
        if len(accounts) >= data["total"] or not data["items"]:
            break
        page += 1
    return accounts


def _fetch_credentials(client: httpx.Client, account_id: str) -> dict:
    res = client.get(f"/api/internal/accounts/{account_id}/credentials")
    res.raise_for_status()
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
