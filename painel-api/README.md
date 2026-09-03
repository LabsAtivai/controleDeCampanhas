# Painel API

API Flask que dispara manualmente as rotinas de extração (`rotina/acao.py`). Deploy independente do scheduler (`../docker-compose.yml`) — não precisa mexer nele.

## Deploy no VPS

```bash
cd painel-api
cp .env.example .env
# edite .env: defina PAINEL_TOKEN forte e FRONTEND_ORIGIN com o domínio do Vercel
docker compose up -d --build
```

Exponha a porta 8000 atrás do seu reverse proxy HTTPS existente (ex: `api-relatorios.seudominio.com` → `localhost:8000`).

## Endpoints

Todos (exceto `/api/health`) exigem header `X-API-Token: <PAINEL_TOKEN>`.

- `GET  /api/health`
- `GET  /api/status`
- `GET  /api/logs?since=N`
- `POST /api/run/campanhas`
- `POST /api/run/dia-anterior`
- `POST /api/run/custom` — body `{"inicio": "YYYY-MM-DD", "fim": "YYYY-MM-DD"}` (fim opcional, máx 31 dias)
- `POST /api/run/planilhas`

Só um job roda por vez (lock); disparo concorrente retorna 409.

## Dependências

O build usa `context: ..` (raiz do repo) porque `server.py` importa `rotina/` e `db/`, e precisa do arquivo de credenciais `sheets.googleapis.com-python.json` já presente na raiz.
