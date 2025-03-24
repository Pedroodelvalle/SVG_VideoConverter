# Etapa base
FROM python:3.11-slim as base

# Configura variáveis de ambiente para otimização e não interatividade
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Atualiza e instala dependências do sistema sem pacotes recomendados
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia o arquivo de dependências separadamente para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências Python sem cache
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código para dentro da imagem
COPY . .

# Documenta a porta que a aplicação usará
EXPOSE 8000

# Comando para iniciar a aplicação com uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
