# MRX SCAN - Sistema de Classificacao de Sucata Eletronica

## Overview
Sistema de scanner por camera para classificacao de sucata eletronica usando OpenCLIP para geracao de embeddings e comparacao por similaridade coseno.

## Current State
- Sistema funcional com FastAPI
- Motor de embeddings OpenCLIP ViT-B-32 carregado
- Interface web disponivel na porta 5000
- Banco de dados PostgreSQL conectado

## Architecture
- **Backend**: FastAPI com Uvicorn
- **ML Model**: OpenCLIP ViT-B-32 (laion2b_s34b_b79k)
- **Database**: PostgreSQL via SQLAlchemy
- **Frontend**: HTML/CSS/JavaScript (templates/index.html)

## Key Files
- `main.py` - Servidor FastAPI principal
- `embedding_engine.py` - Motor de embeddings OpenCLIP
- `database.py` - Configuracao e modelos do banco de dados
- `templates/index.html` - Interface web
- `dataset/` - Diretorio com imagens de treinamento por classe
- `embeddings/` - Cache de embeddings gerados

## Running the Application
O servidor inicia automaticamente via workflow na porta 5000:
```bash
cd /home/runner/workspace && source .pythonlibs/bin/activate && python main.py
```

## API Endpoints
- `GET /` - Interface web principal
- `POST /scan` - Escanear e classificar imagem
- `GET /dataset/classes` - Listar classes disponiveis
- `POST /dataset/upload` - Upload de imagem para classe
- `POST /dataset/create` - Criar nova classe
- `POST /dataset/retrain` - Retreinar embeddings
- `GET /health` - Health check

## Dependencies
Instaladas via pip no virtualenv .pythonlibs:
- fastapi, uvicorn, python-multipart
- torch, torchvision (CPU version)
- open-clip-torch, timm
- pillow, opencv-python-headless, numpy, scipy
- sqlalchemy, psycopg2-binary

## Recent Changes
- 2025-12-16: Projeto importado do GitHub e corrigido para Replit
- Removido Docker/containerizacao
- Configurado pyproject.toml simplificado
- Instaladas dependencias via pip (torch CPU)
- Configurado workflow para inicializacao automatica
