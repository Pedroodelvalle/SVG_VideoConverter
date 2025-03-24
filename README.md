# 🧠 APIs Backend - Conty

Este repositório contém todas as APIs desenvolvidas para o backend da plataforma Conty. As APIs são empacotadas individualmente via Docker e orquestradas com Docker Compose, rodando em uma única instância EC2 da AWS.

## 📁 Estrutura

```
/fastapi-apis/
│
├── README.md
├── docker-compose.yml 
├── common/           
│
├── svg_to_video/        # API de SVGs para vídeos
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── svg_to_png/          # API de SVGs para PNGs 
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
│
└── .env                 # Variáveis de ambiente centralizadas.
```


## 🚀 Como rodar localmente

```bash
docker-compose up --build

Acesse:
http://localhost:8000/docs → SVG para Vídeo
http://localhost:8001/docs → SVG para PNG

☁️ Deploy em Produção
A aplicação roda em uma instância EC2 (Amazon Web Services). O deploy é feito com git pull e docker-compose up -d.

👨‍💻 Time responsável
Pedro (Líder de Backend)
Conty Developers

✨ Observações Finais
Toda nova API deve seguir o padrão de:

bash
Copiar
Editar
/nome_api/
├── main.py
├── Dockerfile
├── requirements.txt
└── outros arquivos
E ser declarada no docker-compose.yml para deploy automatizado.

