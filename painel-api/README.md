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

No container a API roda com gunicorn, **sempre com 1 worker** (`-w 1 --threads 8`): o estado do job, o lock e o buffer de logs ficam na memória do processo. Fora do Docker, no Linux/WSL, a partir da raiz do repo:

```bash
PAINEL_TOKEN=... gunicorn -w 1 --threads 8 -b 0.0.0.0:8000 --pythonpath painel-api "server:create_app()"
```

O gunicorn não roda no Windows; lá use o servidor de desenvolvimento do Flask, a partir da raiz do repo (o `PYTHONPATH` é pra achar `db/` e `rotina/`):

```powershell
$env:PYTHONPATH = "."; $env:PAINEL_TOKEN = "..."; python painel-api/server.py
```

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

## Testes

Na raiz do repo:

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt pytest
.venv/Scripts/python -m pytest
```

Os testes nunca leem o `.env`: `DATABASE_URL` é forçada para um SQLite temporário e Snov.io, Sheets e o sistema de credenciais são mockados. As queries cross-DB de `/api/squads` e `/api/analise-contas` (`tests/test_dashboard_mysql.py`) só rodam com um **MySQL descartável**:

```bash
TEST_DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ .venv/Scripts/python -m pytest -m mysql
```

Se `dadoscampanha.dados` já tiver dados reais, a suíte aborta em vez de mexer neles.

Smoke **só-leitura** contra o MySQL real (`tests/test_dashboard_readonly.py`): só faz GET, abre a sessão com `SET SESSION TRANSACTION READ ONLY` e aborta se ela não ficar read-only. Confere o formato do JSON e a sanidade dos números, não os valores:

```bash
TEST_READONLY_DATABASE_URL=<mesma URL de LISTAS_SQUAD_DATABASE_URL> .venv/Scripts/python -m pytest -m readonly_db -v
```

## Dependências

O build usa `context: ..` (raiz do repo) porque `server.py` importa `rotina/` e `db/`, e precisa do arquivo de credenciais `sheets.googleapis.com-python.json` já presente na raiz.
