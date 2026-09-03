# Usar Python oficial como base
FROM python:3.11-slim

# Instalar tzdata para timezone e dependências Python
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && pip install \
        "apscheduler>=3.11.0" \
        "cryptography>=45.0.7" \
        "httpx>=0.28.1" \
        "pandas>=2.3.1" \
        "pygsheets>=2.0.6" \
        "pymysql>=1.1.1" \
        "sqlalchemy>=2.0.43" \
    && rm -rf /var/lib/apt/lists/*

# Definir timezone
ENV TZ=America/Sao_Paulo
ENV PYTHONUNBUFFERED=1

# Criar diretório da aplicação
WORKDIR /app


# Copiar o código
COPY . .

# Rodar a aplicação
CMD ["python", "-u", "app.py"]
