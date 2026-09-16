# Aqua Monitor

Monitoramento de estações de coleta com visão computacional — rastreamento de garrafas plásticas em rios usando SSD MobileNet V3 + ByteTrack.

**Projeto:** Monitoramento de estações de coleta com visão computacional  
**Local:** Afluente do Rio Santos, São Paulo — Brasil  
**Última atualização:** Setembro 2026  
**Status:** Todas as fases concluídas ✅

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

**Aqua Monitor** é um sistema de monitoramento ambiental que utiliza visão computacional para detectar e rastrear garrafas plásticas em corpos d'água. O pipeline captura vídeo de câmeras (RPi), processa frames com SSD MobileNet V3 + ByteTrack, conta cruzamentos de linha e publica resultados em tempo real para um dashboard web.

### Estado Atual do Projeto (Set/2026)

**Todas as fases concluídas.**

| Fase | Status | Descrição |
|------|--------|-----------|
| 1 | ✅ Concluída | Bibliotecas centrais (`tracker.py`, `geometry.py`, `line_counter.py`, `config.py`) |
| 2 | ✅ Concluída | Integração (`detection_pipeline.py`, `api_client.py`, `object-ident.py`) |
| 3 | ✅ Concluída | Backend completo com endpoints `bottle-count` e `bottle-events` |
| 4 | ✅ Concluída | Frontend com `bottle-counter.js` e polling ativo no `main.js` |
| 5 | ✅ Concluída | 3 arquivos de teste com 13 testes unittest |

**Arquitetura atual:** SSD MobileNet V3 + ByteTrack (biblioteca Supervision), pipeline modular e composável, detecção de garrafas com contagem de cruzamento de linha.

---

## 🏗️ Arquitetura

O pipeline segue este fluxo:

```
Câmera (RPi) → SSD MobileNet V3 (OpenCV DNN) → ByteTrack → LineCounter → FastAPI :8000 → MongoDB
                                                                                                    │
                                                                          GET /api/stations          │
                                                                                                    ▼
                                                                             Dashboard Leaflet + Heatmap + Polling 3s
```

---

## 📁 Estrutura de Diretórios

```
aquamonitor/
├── backend/
│   ├── app.py                    # FastAPI — 6 rotas (CRUD + bottle-count + bottle-events)
│   ├── test_mongodb.py           # Script de verificação da conexão MongoDB
│   ├── test_station_metrics.py   # 4 testes unittest (GET /api/stations com bottle_count)
│   ├── test_bottle_events.py     # 5 testes unittest (ingestão idempotente de events)
│   ├── test_bottle_count.py      # 4 testes unittest (associação métricas↔estações)
│   └── detection/
│       ├── __init__.py           # Docstring do módulo
│       ├── config.py             # Configurações: COUNTING_LINE, BYTETRACK, ApiConfig
│       ├── geometry.py           # Geometria pura: centroid, signed_distance, crosses_line
│       ├── line_counter.py       # Contagem stateful de cruzamentos de linha
│       ├── tracker.py            # ByteTrack wrapper (detector-agnostic)
│       ├── detection_pipeline.py # Orquestra detector → tracker → counter → API
│       ├── api_client.py         # HTTP client para publicar contagem no backend
│       ├── object-ident.py       # Runner principal: câmera → pipeline (com -)
│       └── models/
│           ├── coco.names                # 90 classes COCO
│           ├── frozen_inference_graph.pb # Pesos do SSD MobileNet (OpenCV DNN)
│           └── ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt  # Config do modelo
├── dashboard/
│   ├── index.html            # Mapa Leaflet + filtros + uptime + bottle count
│   ├── crud.html             # Formulários POST/DELETE de estações
│   ├── style.css             # Tema escuro monocromático ("BIOS antiga")
│   ├── cadastro-style.css    # Estilos da página de cadastro
│   └── js/
│       ├── api.js            # fetchStations() → GET http://127.0.0.1:8000/api/stations
│       ├── bottle-counter.js # fetchBottleCount() → GET /api/stations/{id}/bottle-count
│       ├── config.js         # HEATMAP_CONFIG (raios, opacidades, zoom thresholds)
│       ├── main.js           # Orquestrador principal (init map, fetchers, eventos, polling)
│       ├── map.js            # Cria mapa Leaflet [-23.5015, -46.4526] zoom 13
│       ├── heatmap.js        # Intensidade logarítmica, raio adaptativo por zoom
│       ├── markers.js        # Marcadores L.marker com popups (visíveis zoom ≥ 14)
│       ├── filters.js        # Filtros hierárquicos cascata: estado → cidade → distrito
│       ├── crud.js           # POST /api/stations + DELETE /api/stations/{id}
│       ├── uptime.js         # setInterval 1s, conta desde Date.now()
│       └── zoom.js           # L.control top-right mostrando zoom atual
├── stations.json             # Dados de exemplo (30 estações × 2 localizações = 60 docs)
├── requirements.txt          # 9 deps: fastapi, uvicorn, pydantic, supervision==0.27.0, lap==0.5.12, cython-bbox==0.1.5, numpy==1.26.4, pymongo, requests
├── .gitignore
└── .venv/ + ultralytics-env/  # Dois venvs (.venv = backend + detecção, ultralytics = YOLOv8/treino)
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

### 2. Ambientes Virtuais Python

```bash
# Ambiente principal (FastAPI + backend)
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic pymongo supervision==0.27.0 lap==0.5.12 cython-bbox==0.1.5 opencv-python numpy==1.26.4 requests

# Ambiente Ultralytics (YOLOv8/treino — já configurado como ultralytics-env/)
# NÃO é necessário para o pipeline de detecção local (usa .venv)
```
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

# Inserir contagem de garrafas
curl -X POST http://127.0.0.1:8000/api/stations/1/bottle-count \
  -H "Content-Type: application/json" \
  -d '{"count":5,"count_by_direction":{"positive":3,"negative":2}}'

# Recuperar última contagem
curl http://127.0.0.1:8000/api/stations/1/bottle-count

# Inserir evento de cruzamento (idempotente)
curl -X POST http://127.0.0.1:8000/api/stations/1/bottle-events \
  -H "Content-Type: application/json" \
  -d '{"event_id":"camera-1-track-42-2026-09-12T12:00:00Z","direction":"positive","timestamp":"2026-09-12T12:00:00Z"}'
```

### Detecção Local

```bash
# Sem envio ao backend
.venv/bin/python backend/detection/object-ident.py

# Com envio ao backend (publica a cada 5s para o FastAPI)
.venv/bin/python backend/detection/object-ident.py --publish
```

### Executar Testes

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m unittest backend.test_station_metrics -v
.venv/bin/python -m unittest backend.test_bottle_events -v
.venv/bin/python -m unittest backend.test_bottle_count -v
```

### Dashboard

```bash
cd /home/vyzxc/aquamonitor/dashboard
python -m http.server 3000
# Acesse http://127.0.0.1:3000
```

---

## 🗄️ Camada de Dados — MongoDB

| Parâmetro     | Valor                                |
|---------------|--------------------------------------|
| **Banco**     | `aquamonitor`                       |
| **Coleções**  | `stations`, `bottle_metrics`, `bottle_events` |
| **Porta**     | `27017`                             |
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

### Collections

**`bottle_metrics`** — agregados de contagem:
```json
{ "station_id": 1, "count": 37, "count_by_direction": {"positive": 20, "negative": 17}, "timestamp": "2026-09-12T14:20:00" }
```

**`bottle_events`** — eventos individuais de cruzamento (idempotentes):
```json
{ "event_id": "camera-1-track-42-2026-09-12T12:00:00Z", "station_id": 1, "direction": "positive", "timestamp": "2026-09-12T12:00:00Z" }
```

> ⚠️ GeoJSON usa `[longitude, latitude]` — **não** `[latitude, longitude]`.

---

## 🐍 Backend — FastAPI

**Arquivo:** `backend/app.py`  
**Dependências:** `fastapi`, `uvicorn`, `pydantic`, `pymongo`, `fastapi.middleware.cors.CORSMiddleware`

### Rotas Implementadas

| Método   | Rota                                        | Descrição                               |
|----------|---------------------------------------------|-----------------------------------------|
| `POST`   | `/api/stations`                             | Criar nova estação                      |
| `GET`    | `/api/stations`                             | Listar estações com `bottle_count`      |
| `DELETE` | `/api/stations/{station_id}`               | Deletar por station_id                  |
| `POST`   | `/api/stations/{station_id}/bottle-count`  | Ingestão de contagem agregada           |
| `GET`    | `/api/stations/{station_id}/bottle-count`  | Recuperar última contagem               |
| `POST`   | `/api/stations/{station_id}/bottle-events` | Ingestão de evento individual (idempotente) |

### Modelos Pydantic

**`BottleCountPayload`**
```json
{ "count": 5, "count_by_direction": {"positive": 3, "negative": 2} }
```

**`BottleEventPayload`**
```json
{ "event_id": "uuid-string", "direction": "positive", "timestamp": "2026-09-12T12:00:00Z" }
```

- `event_id` não pode ser vazio (validador)
- `timestamp` deve incluir timezone (validador)
- Índice único em `event_id` garante idempotência → DuplicateKeyError retorna HTTP 409

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
   - Cada objeto contado UMA VEZ (_counted_ids set)

4. DetectionPipeline (orquestração)
   - process(detections) → PipelineResult(tracks, events, total_count)
   - publish_if_due() → POST a cada publish_interval_seconds (default 5s)
```

### Módulos de Visão Computacional

| Arquivo                    | Função                                              |
|----------------------------|-----------------------------------------------------|
| `geometry.py`             | Funções puras: `centroid`, `signed_distance`, `crosses_line`, `segments_intersect` |
| `tracker.py`              | Wrapper ByteTrack (detector-agnostic)               |
| `line_counter.py`         | Contagem stateful de cruzamentos                    |
| `config.py`               | Configurações globais (COUNTING_LINE, BYTETRACK, ApiConfig) |
| `detection_pipeline.py`   | Orquestra detector → tracker → counter → API        |
| `api_client.py`           | HTTP client para publicar contagem                  |
| `object-ident.py`         | Runner principal (câmera → pipeline)                |

### Execução Local

```bash
.venv/bin/python backend/detection/object-ident.py
.venv/bin/python backend/detection/object-ident.py --publish
```

---

## 🌐 Frontend — Dashboard

### Arquitetura

Dashboard modular com ES Modules (`main.js` como orquestrador):

| Módulo        | Função                                                |
|---------------|-------------------------------------------------------|
| `main.js`     | Orquestrador: `createMap()`, `fetchStations()`, `startBottlePolling()` |
| `api.js`      | `fetchStations()` → GET `http://127.0.0.1:8000/api/stations` |
| `bottle-counter.js` | `fetchBottleCount(stationId)` → GET `/api/stations/{id}/bottle-count` |
| `map.js`      | Mapa Leaflet em `[-23.5015, -46.4526]` zoom 13       |
| `heatmap.js`  | Intensidade logarítmica (`Math.log1p`), raio adaptativo por zoom |
| `markers.js`  | Marcadores com popup (station_id + detections), visíveis zoom ≥ 14 |
| `filters.js`  | Filtros cascata: estado → cidade → distrito           |
| `crud.js`     | POST/DELETE estações com confirmação                  |
| `config.js`   | `HEATMAP_CONFIG` centralizado                         |
| `uptime.js`   | `setInterval` 1s, contador desde `Date.now()`         |
| `zoom.js`     | `L.control` top-right mostrando zoom atual            |

### Polling de Bottle Count

`main.js` usa `startBottlePolling(stationId, updateStationMetrics, updateVisualization)` com intervalo de **3 segundos**:
1. `fetchBottleCount(stationId)` → GET `/api/stations/{id}/bottle-count`
2. `updateStationMetrics` atualiza `station.bottle_count` e `station.detections` no array in-memory
3. `updateVisualization()` re-renderiza heatmap e markers

### Estilização

- **Tema:** Escuro monocromático ("estética BIOS antiga") com scanlines
- **Mapa:** Grayscale 100% + brightness 35% nos tiles
- **Fonte:** `Courier New` monospace em todo o dashboard
- **Layout:** Mapa fullscreen + painel lateral de 300px

---

## 🔄 Fluxo de Dados Completo

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐
│  CÂMERA  │───▶│  SSD     │───▶│  BYTE    │───▶│ Line     │───▶│ FastAPI│
│  (RPi)   │    │ MobileNet│    │ TRACK    │    │ Counter  │    │ :8000│
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
                                                │  +Polling  │
                                                └────────────┘
```

---

## 📦 Dependências

### Python (Backend)

| Pacote            | Versão   | Uso                                |
|-------------------|----------|------------------------------------|
| `fastapi`        | ≥0.141.0 | API REST                           |
| `uvicorn`        | ≥0.52.0  | Servidor ASGI                      |
| `pydantic`       | ≥2.0.0   | Models e validação                 |
| `pymongo`        | —        | Cliente MongoDB                    |
| `supervision`    | 0.27.0   | ByteTrack tracker                  |
| `lap`            | 0.5.12   | Dependência do ByteTrack          |
| `cython-bbox`    | 0.1.5    | Dependência do ByteTrack          |
| `opencv-python`  | —        | SSD MobileNet + OpenCV DNN         |
| `numpy`          | 1.26.4   | Cálculos numéricos                 |
| `requests`       | —        | api_client.py HTTP client          |

### JavaScript (Frontend)

| Biblioteca     | Versão | Uso                    |
|---------------|--------|------------------------|
| `leaflet`    | 1.9.4  | Mapa interativo        |
| `leaflet.heat` | —    | Camada de calor        |
| OpenStreetMap tiles | — | Tiles do mapa     |

### Modelos

- **SSD MobileNet V3 Large COCO** (`frozen_inference_graph.pb`) — Detector OpenCV DNN local

> ⚠️ `requirements.txt` contém apenas as 9 dependências reais do projeto. Instale-as com `pip install -r requirements.txt`.

---

## 📝 Notas Importantes

1. **`requirements.txt` contém apenas as 9 dependências reais do projeto**: fastapi, uvicorn, pydantic, opencv-python, supervision==0.27.0, lap==0.5.12, cython-bbox==0.1.5, numpy==1.26.4, pymongo, requests.

2. **MongoClient precisa de `serverSelectionTimeoutMS=5000`** para não travar se MongoDB estiver indisponível. O código atual NÃO tem esse timeout (pode causar hang no startup).

3. **Dois venvs:** `.venv` (FastAPI pipeline + detecção) e `ultralytics-env` (YOLOv8/treino). O pipeline de detecção (object-ident.py) roda no `.venv` com OpenCVDnnDetector (SSD MobileNet). O `ultralytics-env` é apenas para YOLOv8/treino.

4. **`object-ident.py` usa OpenCVDnnDetector (SSD MobileNet)**, não YOLOv8 `best.pt`. O `best.pt` existe no projeto mas não é usado pelo código atual.

5. **GeoJSON usa `[longitude, latitude]`** — ordem inversa do padrão GPS.

6. **GET /api/stations retorna `bottle_count`** de MongoDB aggregation (`$sort` + `$group`), não lookup individual. `detections` espelha `bottle_count.count` para backward compatibility.

7. **`create_station` aceita `dict`**, não Pydantic model. Faz insert_one diretamente SEM verificar duplicidade — station_ids duplicados causarão erro do MongoDB.

8. **`BottleCountPayload` não tem `session_id`** — POST é fire-and-forget.

9. **`LineCounter` não tem `save_state()`/`load_state()`** — estado não persistido em MongoDB.

10. **`event_id` com índice único** em `bottle_events_collection` → DuplicateKeyError retorna HTTP 409 (idempotência).

11. **Testes usam `unittest`** (não pytest). Com Mock para collections MongoDB.

12. **Cuidado com:** `db.dropDatabase()`, `db.collection.drop()`, `deleteMany({})`.

13. **Não exponha MongoDB** à rede sem autenticação e firewall adequado.

14. **Objetos `ObjectId` do MongoDB** não são JSON-serializáveis. Converta para string antes de retornar: `result["_id"] = str(result["_id"])`.

15. O heatmap usa intensidade logarítmica (`Math.log1p`) e raio adaptativo por zoom.

16. Os filtros de localidade são hierárquicos e cascatais (estado → cidade → distrito).

17. A estética do dashboard é monocromática ("BIOS antiga").

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
