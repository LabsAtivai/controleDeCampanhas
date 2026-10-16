# Build context é a raiz do repo (../), pois server.py depende de rotina/ e db/
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && pip install \
        "flask>=3.0.0" \
        "gunicorn>=23.0.0" \
        "httpx>=0.28.1" \
        "pandas>=2.3.1" \
        "pygsheets>=2.0.6" \
        "pymysql>=1.1.1" \
        "sqlalchemy>=2.0.43" \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Sao_Paulo
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# 1 worker é obrigatório: STATE, RUN_LOCK e LOG_BUFFER vivem na memória do processo.
# Com 2+ workers cada um teria o seu (dois jobs ao mesmo tempo, status e logs divergentes).
# Roda a partir de /app (raiz do repo): db/, rotina/ e as credenciais do Sheets são achados
# a partir daí; --pythonpath só acrescenta painel-api/ pra achar o server.py.
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:8000", "--pythonpath", "painel-api", "server:create_app()"]
