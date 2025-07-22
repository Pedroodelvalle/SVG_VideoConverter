# 🧠 APIs SVG para PNG (com imagem e vídeo) - Feito em Python e pronto para usar em prod. 

Este repositório contém um conjunto de APIs modulares desenvolvidas com **FastAPI**, empacotadas individualmente via **Docker** e orquestradas com **Docker Compose**. 
Ideal para projetos que exigem microsserviços independentes, reutilizáveis e facilmente escaláveis.

Essas APIs podem te ajudar a:
- Converter códigos SVG para PNGs. 
- Converter códigos SVG que possuem links de imagens para PNGs. 
- Converter códigos SVG que possuem links de vídeo para MP4.  

---

## 📁 Arquitetura

```
/fastapi-apis/
│
├── README.md
├── docker-compose.yml 
├── common/                    # Recursos compartilhados entre as APIs
│
├── svg_to_video/              # API para converter SVG + vídeo externo → MP4
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── svg_to_png/                # API para converter SVG → PNG e SVG
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
└── .env                       # Variáveis de ambiente centralizadas
```

---

## 🚀 Como Rodar Localmente

1. Certifique-se de ter o Docker e Docker Compose instalados.
2. No terminal, execute:

```bash
docker-compose up --build
```

3. Acesse a documentação interativa (Swagger UI) das APIs:

- 📹 **SVG para Vídeo:** [`http://localhost:8000/docs`](http://localhost:8000/docs)
- 🖼️ **SVG para PNG:** [`http://localhost:8001/docs`](http://localhost:8001/docs)

---

## ☁️ Deploy em Produção

Este sistema pode ser facilmente hospedado em uma instância Linux utilizando AWS EC2, GCP, Fly.io, entre outros.

Para atualizar a aplicação via SSH:

```bash
git pull
docker-compose up -d
```

---

## 🧩 Padrão de Novas APIs

Toda nova API deve seguir a estrutura:

```bash
/nome_da_api/
├── main.py
├── Dockerfile
├── requirements.txt
└── outros arquivos necessários
```

E ser registrada no `docker-compose.yml` para ser automaticamente incluída no ambiente.

---

## 👥 Contribuidores

Este projeto é aberto a melhorias. Sinta-se à vontade para propor novas APIs, otimizações ou melhorias arquiteturais.

Observação: O criador não está mais fazendo manutenção desse projeto. 

---
