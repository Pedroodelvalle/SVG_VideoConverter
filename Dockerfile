FROM python:3.10-slim

# Instala dependências básicas + ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório da app
WORKDIR /app

# Copia os arquivos
COPY . /app

# Instala dependências do Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expõe porta
EXPOSE 8000

# Comando para rodar a app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
