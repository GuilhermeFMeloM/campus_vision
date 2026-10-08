# =========================================================================
# CampusVision - Production Dockerfile for Google Cloud Run
# =========================================================================
FROM python:3.11-slim

# Evita que o Python gere arquivos .pyc e força o buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Instala dependências do sistema necessárias para compilação e imagens
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python primeiro (aproveita cache de camadas do Docker)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto
COPY . /app/

# Diretório de execução do Django
WORKDIR /app/campusvision_django

# Cria diretórios de arquivos estáticos e uploads
RUN mkdir -p /app/campusvision_django/staticfiles \
    /app/campusvision_django/app/static/uploads

# Coleta os arquivos estáticos (WhiteNoise)
RUN python manage.py collectstatic --noinput

# Expõe a porta padrão do Cloud Run
EXPOSE 8080

# Inicia o servidor com Gunicorn vinculando na porta informada pelo Cloud Run ($PORT)
CMD exec gunicorn campusvision_django.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 2 \
    --threads 4 \
    --timeout 120