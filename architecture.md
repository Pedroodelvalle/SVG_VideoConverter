# Arquitetura de APIs - [APIs_Backend_Conty]

Este documento descreve a arquitetura atual das APIs utilizadas no Backend da Conty, com foco em modularidade, escalabilidade e manutenção simplificada. O sistema é estruturado como um mono-repositório com múltiplas APIs, cada uma isolada em seu próprio container Docker, rodando em uma única instância EC2 da AWS.

---

## 📆 Estrutura de Diretórios (Mono-Repo)

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

---

## 🔧 Tecnologias Utilizadas

- **Python + FastAPI**: framework principal de todas as APIs
- **Docker**: empacotamento de cada API em containers independentes
- **Docker Compose**: orquestração local e em produção
- **Amazon EC2**: hospedagem das APIs (instância t2.micro no momento)
- **FFmpeg**: manipulação de vídeos
- **CairoSVG**: conversão de SVG para PNG

---

## 🚀 APIs Disponíveis

### 1. `svg_to_video` (porta 8000)
- Função: Converte SVG + vídeo externo em MP4
- Stack: FastAPI + FFmpeg
- Endpoints principais: `/generate-video`

### 2. `svg_to_png` (porta 8001)
- Função: Converte SVG estático para imagem PNG
- Stack: FastAPI + CairoSVG
- Endpoints principais: `/generate-png`

---

## 🔸 Acesso via EC2

- `http://<IP_EC2>:8000` → SVG to Video
- `http://<IP_EC2>:8001` → SVG to PNG

---

## 🛠️ Deploy & Manutenção

```bash
# Build de todas as imagens
sudo docker-compose build

# Subir todos os serviços em background
sudo docker-compose up -d

# Ver containers rodando
sudo docker ps

# Parar todos os serviços
sudo docker-compose down
```

---

## 🔄 Escalabilidade Futura

- Substituir EC2 atual por instância com mais CPU/RAM (ex.: `t3.medium`, `c5.large`)
- Separar APIs mais pesadas em instâncias dedicadas
- Migrar para **ECS** ou **Kubernetes** se houver alta demanda
- Automatizar deploy com CI/CD
- Servir domínios personalizados com NGINX e HTTPS

---

## 📍 Boas Práticas Adotadas

- APIs isoladas em containers distintos
- Estrutura de pasta modular para separação clara de responsabilidades
- Porta exclusiva para cada API
- Código compartilhado movido para pasta `common/`
- Uso futuro de .env para configurações sensíveis

---

## 📃 Observações

- O projeto está em fase de crescimento, mas estruturado para escalar rapidamente.
- Toda nova API deve ser criada em seu próprio diretório com `main.py`, `Dockerfile`, `requirements.txt`.
- Adições devem ser refletidas no `docker-compose.yml` para facilitar deploy unificado.

---

**✨ Atualizado em:** [24/03/2025]  
**Time de responsáveis pela arquitetura:** [Conty-Developers]