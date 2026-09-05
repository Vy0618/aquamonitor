# Aqua Monitor

Monitoramento de estações de coleta com visão computacional — rastreamento de garrafas plásticas em rios usando YOLOv8 + ByteTrack.

**Projeto:** Monitoramento de estações de coleta com visão computacional  
**Local:** Afluente do Rio Santos, São Paulo — Brasil  
**Última atualização:** Setembro 2026

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Estrutura de Diretórios](#-estrutura-de-diretórios)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Camada de Dados — MongoDB](#-camada-de-dados--mongodb)
- [Backend — FastAPI](#-backend--fastapi)
- [Visão Computacional](#-visão-computacional)
- [Frontend — Dashboard](#-frontend--dashboard)
- [Fluxo de Dados](#-fluxo-de-dados)
- [Dependências](#-dependências)
- [Notas Importantes](#-notas-importantes)

---

## 📋 Visão Geral

**Aqua Monitor** é um sistema de monitoramento ambiental que utiliza visão computacional para detectar e rastrear garrafas plásticas em corpos d'água. O pipeline captura vídeo de câmeras (RPi), processa frames com YOLOv8 + ByteTrack, conta cruzamentos de linha e publica resultados em tempo real para um dashboard web.

### Estado Atual do Projeto (Set/2026)

| Fase | Status | Descrição |
|------|--------|-----------|
| 1 | ✅ Concluída | Bibliotecas centrais (`tracker.py`, `geometry.py`, `line_counter.py`, `config.py`) |
| 2 | ✅ Concluída | Integração (`detection_pipeline.py`, `api_client.py`, `object-ident.py`) |
| 3 | ⚠️ Parcial | Backend: `api_client.py` existe, endpoint `POST /api/stations/{id}/bottle-count` **não implementado** em `app.py` |
| 4 | ❌ Não iniciada | Frontend: `bottle-counter.js` **não criado** (estética e filtros do dashboard estão completos) |
| 5 | ❌ Não iniciada | Testes: nenhum teste implementado |

**Arquitetura atual:** YOLOv8 + ByteTrack (biblioteca Supervision), pipeline modular e composável, detecção de garrafas com contagem de cruzamento de linha.

---

## 🏗️ Arquitetura

O pipeline de dadoso segue este fluxo:

```
Câmera (RPi) → YOLOv8 + OpenCV DNN → ByteTrack → Line Counter → FastAPI :8000 → MongoDB
                                                                                          │
                                                                          GET /api/stations │
                                                                                          ▼
                                                                   Dashboard Leaflet + Heatmap
```

---

## 📁 Estrutura de Diretórios

```
aquamonitor/
├── backend/
│   ├── app.py                    # FastAPI — 3 rotas CRUD (POST/GET/DELETE /api/stations)
│   ├── test_mongodb.py           # Script de verificação da conexão MongoDB
│   └── detection/
│       ├── __init__.py           # Docstring do módulo
│       ├── config.py             # Configurações: COUNTING_LINE, BYTETRACK, ApiConfig
│       ├── geometry.py           # Geometria pura: centroid, signed_distance, crosses_line
│       ├── line_counter.py       # Contagem stateful de cruzamentos de linha
│       ├── tracker.py            # ByteTrack wrapper (detector-agnostic)
│       ├── detection_pipeline.py # Orquestra detector → tracker → counter → API
│       ├── api_client.py         # HTTP client para publicar contagem no backend
│       ├── object-ident.py       # Runner principal: câmera → pipeline
│       └── models/
│           ├── coco.names                # 80 classes COCO
│           ├── frozen_inference_graph.pb # Pesos do SSD MobileNet (OpenCV DNN)
│           └── ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt  # Config do modelo
├── dashboard/
│   ├── index.html            # Mapa Leaflet + filtros + uptime
│   ├── crud.html             # Formulários POST/DELETE de estações
│   ├── style.css             # Tema escuro monocromático ("BIOS antiga")
│   ├── cadastro-style.css    # Estilos da página de cadastro
│   └── js/
│       ├── api.js            # fetchStations() → GET http://127.0.0.1:8000/api/stations
│       ├── config.js         # HEATMAP_CONFIG (raios, opacidades, zoom thresholds)
│       ├── main.js           # Orquestrador principal (init map, fetchers, eventos)
│       ├── map.js            # Cria mapa Leaflet [-23.5015, -46.4526] zoom 13
│       ├── heatmap.js        # Intensidade logarítmica, raio adaptativo por zoom
│       ├── markers.js        # Marcadores L.marker com popups (visíveis zoom ≥ 14)
│       ├── filters.js        # Filtros hierárquicos cascata: estado → cidade → distrito
│       ├── crud.js           # POST /api/stations + DELETE /api/stations/{id}
│       ├── uptime.js         # setInterval 1s, conta desde Date.now()
│       └── zoom.js           # L.control top-right mostrando zoom atual
├── stations.json             # Dados de exemplo (30 estações × 2 localizações = 60 docs)
├── requirements.txt          # Dependências Python
├── best.pt                   # Peso YOLOv8 (classe 0 = bottle) — NÃO rastrear no git
├── runs/                     # Saídas de detecção YOLO — NÃO rastrear no git
├── tmp/                      # Arquivos temporários matplotlib
└── notes.txt                 # Notas detalhadas do projeto
```

---

## 🔧 Instalação

### Pré-requisitos

- Python 3.12+
- MongoDB 6+
- Node.js (para executar o dashboard localmente)

### 1. Clone o repositório

```bash
git clone https://github.com/Vy0618/aquamonitor.git
cd aquamonitor
```

### 2. Ambiente Virtual Python

```bash
# Ambiente principal (FastAPI + backend)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ambiente Ultralytics (YOLOv8 + ByteTrack)
# Já configurado como ultralytics-env/
```

### 3. MongoDB

```bash
sudo systemctl start mongod
mongosh
use aquamonitor
```

### 4. Importar dados de exemplo

```bash
mongoimport --db aquamonitor --collection stations --file stations.json --jsonArray
```

---

## 🚀 Uso

### Iniciar Backend (FastAPI)

```bash
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### Testar API

```bash
# Listar estações
curl http://127.0.0.1:8000/api/stations

# Criar estação
curl -X POST http://127.0.0.1:8000/api/stations \
  -H "Content-Type: application/json" \
  -d '{"station_id":99,"detections":10,"location":{"type":"Point","coordinates":[-46.0,-23.0]}}'

# Deletar estação
curl -X DELETE http://127.0.0.1:8000/api/stations/99
```

### Detecção Local

```bash
# Sem envio ao backend
ultralytics-env/bin/python backend/detection/object-ident.py

# Com envio ao backend (Fase 3 — requer endpoint implementado)
ultralytics-env/bin/python backend/detection/object-ident.py --publish
```

---

## 🗄️ Camada de Dados — MongoDB

| Parâmetro     | Valor                    |
|---------------|--------------------------|
| **Banco**     | `aquamonitor`            |
| **Coleção**   | `stations`               |
| **Porta**     | `27017`                  |
| **URI**       | `mongodb://localhost:27017/aquamonitor` |

### Documento Típico

```json
{
    "_id": ObjectId("..."),
    "station_id": 1,
    "detections": 37,
    "status": "online",
    "location": {
        "type": "Point",
        "coordinates": [-46.4526, -23.5015]
    },
    "administrative": {
        "country": "Brazil",
        "state": "São Paulo",
        "city": "Santos",
        "district": "Baía de Santos"
    }
}
```

> ⚠️ GeoJSON usa `[longitude, latitude]` — **não** `[latitude, longitude]`.

---

## 🐍 Backend — FastAPI

**Arquivo:** `backend/app.py`  
**Dependências:** `fastapi`, `uvicorn`, `pymongo`, `fastapi.middleware.cors.CORSMiddleware`

### Rotas Implementadas

| Método   | Rota                              | Descrição                    |
|----------|-----------------------------------|------------------------------|
| `POST`   | `/api/stations`                   | Criar nova estação           |
| `GET`    | `/api/stations`                   | Listar todas as estações     |
| `DELETE` | `/api/stations/{station_id}`      | Deletar por station_id       |

### Rotas Planejadas (Fase 3)

| Método   | Rota                                        | Descrição               |
|----------|---------------------------------------------|-------------------------|
| `POST`   | `/api/stations/{station_id}/bottle-count`   | Ingerir contagem        |
| `GET`    | `/api/stations/{station_id}/bottle-count`   | Recuperar contagem      |

---

## 👁️ Visão Computacional

### Pipeline de Detecção

```
1. OpenCVDnnDetector (SSD MobileNet V3 Large via OpenCV DNN)
   - Input: 320×320, Scale: 1.0/127.5, Mean: (127.5, 127.5, 127.5), Swap RB
   - Classes: {"bottle"} (configurável via config.py)

2. ByteTrackTracker (supervision.ByteTrack)
   - Detector-agnostic: aceita qualquer detector que produza Detections
   - Track ID estável entre frames
   - track_activation_threshold=0.25, lost_track_buffer=30

3. LineCounter (contagem de cruzamentos)
   - Line segment: COUNTING_LINE.start=(0,240) → end=(640,240)
   - Direction: "any" (ambos os sentidos)
   - Expira tracks inativos após max_missing_frames=90
   - Cada objeto contado UMA VEZ (_tracked_ids set)

4. DetectionPipeline (orquestração)
   - process(detections) → PipelineResult(tracks, events, total_count)
   - publish_if_due() → POST a cada publish_interval_seconds (default 5s)
```

### Módulos de Visão Computacional

| Arquivo                   | Função                                      |
|---------------------------|---------------------------------------------|
| `geometry.py`             | Funções puras: `centroid`, `signed_distance`, `crosses_line`, `segments_intersect` |
| `tracker.py`              | Wrapper ByteTrack (detector-agnostic)       |
| `line_counter.py`         | Contagem stateful de cruzamentos            |
| `config.py`               | Configurações globais (COUNTING_LINE, BYTETRACK, ApiConfig) |
| `detection_pipeline.py`   | Orquestra detector → tracker → counter → API |
| `api_client.py`           | HTTP client para publicar contagem          |
| `object-ident.py`         | Runner principal (câmera → pipeline)        |

### Execução Local

```bash
ultralytics-env/bin/python backend/detection/object-ident.py
```

---

## 🌐 Frontend — Dashboard

### Arquitetura

Dashboard modular com ES Modules (`main.js` como orquestrador):

| Módulo        | Função                                                |
|---------------|-------------------------------------------------------|
| `main.js`     | Orquestrador: `createMap()`, `fetchStations()`, `createHeatmap()`, `updateMap()` |
| `api.js`      | `fetchStations()` → GET `http://127.0.0.1:8000/api/stations` |
| `map.js`      | Mapa Leaflet em `[-23.5015, -46.4526]` zoom 13       |
| `heatmap.js`  | Intensidade logarítmica (`Math.log1p`), raio adaptativo por zoom |
| `markers.js`  | Marcadores com popup (station_id + detections), visíveis zoom ≥ 14 |
| `filters.js`  | Filtros cascata: estado → cidade → distrito           |
| `crud.js`     | POST/DELETE estações com confirmação                  |
| `config.js`   | `HEATMAP_CONFIG` centralizado                         |
| `uptime.js`   | `setInterval` 1s, contador desde `Date.now()`         |
| `zoom.js`     | `L.control` top-right mostrando zoom atual            |

### Estilização

- **Tema:** Escuro monocromático ("estética BIOS antiga") com scanlines
- **Mapa:** Grayscale 100% + brightness 35% nos tiles
- **Fonte:** `Courier New` monospace em todo o dashboard
- **Layout:** Mapa fullscreen + painel lateral de 300px

---

## 🔄 Fluxo de Dados Completo

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐
│  CÂMERA  │───▶│  YOLOv8  │───▶│  BYTE    │───▶│ Line     │───▶│ FastAPI│
│  (RPi)   │    │ +OpenCV  │    │ TRACK    │    │ Counter  │    │ :8000│
└──────────┘    └──────────┘    └──────────┘    └────┬─────┘    └──────┘
                                                       │
                                                       │ count aggregate
                                                       │ (HTTP POST, se habilitado)
                                                       ▼
                                                ┌────────────┐
                                                │  MongoDB   │
                                                │  aquamonitor│
                                                └─────┬──────┘
                                                      │
                                                      │ GET /api/stations
                                                      ▼
                                                ┌────────────┐
                                                │  Dashboard │
                                                │  Leaflet   │
                                                │  +Heatmap  │
                                                └────────────┘
```

---

## 📦 Dependências

### Python (Backend)

| Pacote               | Versão  | Uso                                |
|----------------------|---------|------------------------------------|
| `fastapi`            | —       | API REST                         |
| `uvicorn`            | —       | Servidor ASGI                     |
| `pymongo`            | —       | Cliente MongoDB                   |
| `python-dotenv`      | —       | Variáveis de ambiente             |
| `supervision`        | 0.27.0  | ByteTrack tracker                 |
| `lap`                | 0.5.12  | Dependência do ByteTrack          |
| `cython-bbox`        | 0.1.5   | Dependência do ByteTrack          |
| `opencv-python`      | —       | YOLOv8 + OpenCV DNN               |
| `numpy`              | 1.26.4  | Cálculos numéricos                |

### JavaScript (Frontend)

| Biblioteca   | Versão   | Uso                          |
|-------------|----------|------------------------------|
| `leaflet`   | 1.9.4    | Mapa interativo              |
| `leaflet.heat` | —      | Camada de calor              |
| OpenStreetMap tiles | — | Tiles do mapa             |

### Modelos

- **YOLOv8** (`best.pt`) — Classe 0 = bottle
- **SSD MobileNet V3 Large COCO** (`frozen_inference_graph.pb`) — Detector OpenCV DNN local

---

## 📝 Notas Importantes

1. O `app.py` é a versão "core" com 3 rotas apenas — a **Fase 3** (bottle-count) não foi implementada. O `api_client.py` faz POST para `/api/stations/{id}/bottle-count`, mas o `app.py` não recebe essa rota.

2. O pipeline de detecção está funcional, mas o `object-ident.py` usa **OpenCV DNN** como detector local, não YOLOv8. O `best.pt` está no projeto mas o código atual usa `frozen_inference_graph.pb`.

3. **MongoDB** é o servidor; **mongosh** é o cliente/terminal.

4. `.venv` isola dependências Python. `ultralytics-env` tem o ambiente para YOLOv8/ByteTrack.

5. **Portas:** MongoDB `27017`, FastAPI `8000`.

6. GeoJSON usa `[longitude, latitude]` — ordem inversa do padrão GPS.

7. O heatmap usa intensidade logarítmica (`Math.log1p`) e raio adaptativo por zoom.

8. Filtros de localidade são hierárquicos e cascatais (estado → cidade → distrito).

9. A estética do dashboard é monocromática ("BIOS antiga").

10. **Cuidado com:** `db.dropDatabase()`, `db.collection.drop()`, `deleteMany({})`.

11. **Não exponha** MongoDB à rede sem autenticação e firewall adequado.

12. `best.pt` e `runs/` estão no `.gitignore` mas foram commitados antes da atualização — remova com:
    ```bash
    git rm --cached best.pt
    git rm -r --cached runs/
    ```

13. `implementation.txt` contém o plano original de 18 fases (Fases 1-2 feitas, 3 parcial).

---

## 🤝 Contribuindo

1. Abra uma issue descrevendo a mudança proposta
2. Fork do repositório
3. Crie uma feature branch (`git checkout -b feature/nova-funcionalidade`)
4. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
5. Push para a branch (`git push origin feature/nova-funcionalidade`)
6. Abra um Pull Request

---

## 📄 Licença

Este projeto é de código aberto. Consulte o arquivo `LICENSE` para mais detalhes.

---

## 📬 Contato

**Vy0618** — [viniciusazevedo1a@gmail.com](mailto:viniciusazevedo1a@gmail.com)

Repositório: [https://github.com/Vy0618/aquamonitor](https://github.com/Vy0618/aquamonitor)
