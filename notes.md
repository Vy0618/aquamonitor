# Aqua Monitor — Notas do Projeto

> **Projeto:** Monitoramento de estações de coleta com visão computacional  
> **Local:** Afluente do Rio Santos, São Paulo — Brasil  
> **Última atualização:** Setembro 2026  
> **Status:** Todas as fases concluídas ✅

---

## 1. Estrutura de Diretórios

```
aquamonitor/
├── backend/
│   ├── app.py                    # FastAPI — 6 rotas (CRUD + bottle-count + bottle-events)
│   ├── test_mongodb.py           # Script de verificação da conexão MongoDB (find + print)
│   ├── test_station_metrics.py   # 4 testes unittest (GET /api/stations com bottle_count)
│   ├── test_bottle_events.py     # 5 testes unittest (ingestão idempotente de events)
│   ├── test_bottle_count.py      # 4 testes unittest (associação métricas↔estações)
│   └── detection/
│       ├── __init__.py           # Docstring do módulo
│       ├── config.py             # Configurações: COUNTING_LINE, BYTETRACK, ApiConfig
│       ├── geometry.py           # Geometria pura: centroid, signed_distance, crosses_line, segments_intersect
│       ├── line_counter.py       # Contagem stateful de cruzamentos de linha + reset()
│       ├── tracker.py            # ByteTrack wrapper (detector-agnostic), classe Detection
│       ├── detection_pipeline.py # Orquestra detector → tracker → counter → API
│       ├── api_client.py         # HTTP client para publicar contagem no backend (timeout=3)
│       ├── object-ident.py       # Runner principal: câmera → pipeline
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
│       ├── main.js           # Orquestrador principal (init map, fetchers, polling)
│       ├── map.js            # Cria mapa Leaflet [-23.5015, -46.4526] zoom 13
│       ├── heatmap.js        # Intensidade log1p, raio adaptativo por zoom
│       ├── markers.js        # Marcadores L.marker com popups (visíveis zoom ≥ 14)
│       ├── filters.js        # Filtros hierárquicos cascata: estado → cidade → distrito
│       ├── crud.js           # POST /api/stations + DELETE /api/stations/{id}
│       ├── uptime.js         # setInterval 1s, conta desde Date.now()
│       └── zoom.js           # L.control top-right mostrando zoom atual
├── stations.json             # Dados de exemplo (30 estações × 2 localizações = 60 docs)
├── requirements.txt          # 10 deps: fastapi, uvicorn, pydantic, supervision==0.27.0, lap==0.5.12, cython-bbox==0.1.5, numpy==1.26.4, pymongo, requests
├── .gitignore
├── notes.txt                 # Este arquivo
└── .venv/ + ultralytics-env/  # Dois venvs (.venv = backend + detecção, ultralytics = YOLOv8/treino)
```

---

## 2. Camada de Dados — MongoDB (`aquamonitor`)

**Banco:** `aquamonitor`  
**Porta padrão:** `27017`  
**URI:** `mongodb://localhost:27017/aquamonitor`

### Coleções

| Coleção | Descrição |
|---|---|
| `stations` | Dados das estações de coleta |
| `bottle_metrics` | Agregados de contagem de garrafas |
| `bottle_events` | Eventos individuais de cruzamento (idempotentes) |

### Documentos Típicos

**`stations`:**
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

**`bottle_metrics`:**
```json
{
    "station_id": 1,
    "count": 37,
    "count_by_direction": {"positive": 20, "negative": 17},
    "timestamp": "2026-09-12T14:20:00"
}
```

**`bottle_events`:**
```json
{
    "event_id": "camera-1-track-42-2026-09-12T12:00:00Z",
    "station_id": 1,
    "direction": "positive",
    "timestamp": "2026-09-12T12:00:00Z"
}
```

### Índices

- `station_id_timestamp_desc` em `bottle_metrics` — para lookup eficiente do último métrico por estação
- `unique_bottle_event_id` em `bottle_events` — para idempotência (`DuplicateKeyError` → HTTP 409)

> ⚠️ GeoJSON usa `[longitude, latitude]` — **não** `[latitude, longitude]`.

---

## 3. Backend — FastAPI (Python)

**Arquivo:** `backend/app.py`  
**Dependências:** `fastapi`, `uvicorn`, `pydantic`, `pymongo`, `fastapi.middleware.cors.CORSMiddleware`

### Rotas Implementadas

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/stations` | Criar nova estação (aceita `dict`, não Pydantic model) |
| `GET` | `/api/stations` | Listar todas as estações com `bottle_count` da aggregation |
| `DELETE` | `/api/stations/{station_id}` | Deletar por station_id (str → int interno) |
| `POST` | `/api/stations/{station_id}/bottle-count` | Ingestão de contagem agregada |
| `GET` | `/api/stations/{station_id}/bottle-count` | Recuperar última contagem |
| `POST` | `/api/stations/{station_id}/bottle-events` | Ingestão de evento individual com idempotência |

### Modelos Pydantic

**`BottleCountPayload`:** `{count: int, count_by_direction: dict[str, int]}`

**`BottleEventPayload`:** `{event_id: str, direction: Literal["positive","negative"], timestamp: datetime}`
- `event_id`: validador — não pode ser blank
- `timestamp`: validador — deve incluir timezone

### Detalhes de Implementação

- `GET /api/stations` usa MongoDB aggregation (`$sort` + `$group`) para batch-fetch do último métrico por estação — **não** N+1 queries
- Quando não existe `bottle_metrics`, `bottle_count` retorna `{"count": 0, "positive": 0, "negative": 0, "timestamp": null}`
- `serialize_bottle_count()` converte timestamp para `timestamp.isoformat()` inline
- Campos na resposta `GET /api/stations`: `station_id`, `location`, `administrative`, `detections` (= `bottle_count.count` para backward compatibility), `bottle_count`
- `create_station` **NÃO** verifica duplicidade via `find_one` — faz `insert_one` diretamente. Estações com `station_id` duplicada causarão erro do MongoDB sem tratamento de `DuplicateKeyError`
- `MongoClient` **NÃO** tem `serverSelectionTimeoutMS=5000` — pode causar **hang** no startup se MongoDB estiver indisponível

### Imports Duplicados em `app.py` (cosmético, não afeta funcionamento)

- `from typing import Literal` importado 2×
- `from pydantic import BaseModel` importado 2×
- `from pymongo import ASCENDING, DESCENDING, MongoClient` e depois `from pymongo import ASCENDING, MongoClient` em linhas separadas

---

## 4. Visão Computacional — Detecção e Rastreamento

### Pipeline Atual (`object-ident.py` → `detection_pipeline.py`)

```
Câmera (RPi) → SSD MobileNet V3 (OpenCV DNN) → ByteTrack → LineCounter → FastAPI :8000 → MongoDB
```

#### 1. OpenCVDnnDetector
- **Modelo:** SSD MobileNet V3 Large (OpenCV DNN, `coco.names`)
- **Input:** 320×320, Scale: 1.0/127.5, Mean: (127.5, 127.5, 127.5), Swap RB
- **Classes de interesse:** `{"bottle"}` (configurável via `config.py`)
- Retorna `list[Detection]` com `class_id` começando em 1 (índice COCO), ajustado para 0-based via `class_names[int(class_id) - 1]`

#### 2. ByteTrackTracker (`tracker.py`)
- Wrapper em torno de `supervision.ByteTrack`
- Detector-agnostic: aceita qualquer detector que produza `Detections`
- Track ID estável entre frames
- Configuração em `config.py`: `track_activation_threshold=0.25`, `lost_track_buffer=30`, `minimum_matching_threshold=0.8`, `frame_rate=30`, `minimum_consecutive_frames=1`
- Importação de `numpy`/`supervision` deferida (`RuntimeError` se não instalado)
- `Detection` dataclass: `{xyxy, confidence, class_id, class_name}`

#### 3. LineCounter (`line_counter.py`)
- Segmento de linha: `COUNTING_LINE.start=(0,240)` → `end=(640,240)` (horizontal no meio do frame 640×480)
- Direction: `"any"` (conta ambos os sentidos)
- `count_by_direction`: `{"positive": N, "negative": N}`
- Expira tracks inativos após `max_missing_frames=90`
- Cada objeto contado **uma vez** (`_counted_ids` set previne duplo count)
- Possui método `reset()` que limpa `count`, `count_by_direction`, `_frame`, `_states`, `_counted_ids`
- Retorna `list[CrossingEvent]`: `{track_id, point, direction, class_name}`
- `TrackedObject` dataclass: `{track_id, xyxy, class_name}`

#### 4. DetectionPipeline (`detection_pipeline.py`)
- `PipelineResult` dataclass: `{tracks, crossing_events, total_count}`
- `process(detections)` → retorna `PipelineResult(tracks, events, total_count)`
  - Chama `tracker.update()`, `counter.update()`, E `self.publish_if_due()` internamente
- `publish_if_due(force=False)` → retorna `bool`, POST para backend a cada `publish_interval_seconds` (padrão 5s)
- Endpoint de destino: `/api/stations/{station_id}/bottle-count`
- `finally` block em `object-ident.py` chama `pipeline.publish_if_due(force=True)` antes do cleanup

#### 5. geometry.py — Funções Puras (sem estado)
| Função | Entrada | Saída |
|---|---|---|
| `centroid(xyxy)` | `(x1, y1, x2, y2)` | `Point` |
| `signed_distance(point, line)` | ponto, linha | `float` |
| `side_of_line(point, line)` | ponto, linha | `-1/0/1` |
| `crosses_line(previous, current, line)` | dois pontos, linha | `bool` |
| `segments_intersect(a, b)` | duas linhas | `bool` |

### Configuração (`config.py`)

**`CountingLineConfig`:** `start=(0,240)`, `end=(640,240)`, `direction="any"`, `classes_to_count=frozenset({"bottle"})`, `max_missing_frames=90`

**`ApiConfig`:** `base_url`, `station_id`, `publish_interval_seconds`, `enabled`
- Variáveis de ambiente: `BOTTLE_COUNT_API_URL`, `BOTTLE_COUNT_STATION_ID`, `BOTTLE_COUNT_PUBLISH_INTERVAL`, `BOTTLE_COUNT_API_ENABLED`
- `enabled` padrão: `False` (setar `BOTTLE_COUNT_API_ENABLED=1` para habilitar)

### Interface `config.py` ↔ `api_client.py`
- `BottleCountApiClient.__init__` recebe `ApiConfig`, lê `config.base_url` e `config.station_id`
- `BottleCountApiClient.publish(count, count_by_direction)` envia POST para `{base_url}/api/stations/{station_id}/bottle-count`
- Timeout de 3 segundos nas requisições HTTP
- Retorna `bool` (`True` se publicou com sucesso, `False` se falhou)

### Execução Local

```bash
.venv/bin/python backend/detection/object-ident.py
# ou com --publish para habilitar envio ao backend
```

**Argumentos de `object-ident.py`:**

| Argumento | Padrão | Descrição |
|---|---|---|
| `--camera INT` | `0` | Índice da câmera OpenCV |
| `--width INT` | `640` | Largura do frame |
| `--height INT` | `480` | Altura do frame |
| `--detection-interval FLOAT` | `0.25` | Intervalo entre detecções (segundos) |
| `--confidence FLOAT` | `0.45` | Threshold de confiança da detecção |
| `--nms FLOAT` | `0.2` | Threshold de Non-Maximum Suppression |
| `--publish` | `False` | Habilita envio ao backend |

---

## 5. Frontend — Dashboard (Leaflet / JavaScript)

### Arquitetura Modular

ES Modules com `main.js` como orquestrador.

### HTML

**`index.html`:**
- Header: "AQUA MONITOR" + SYSTEM STATUS: ONLINE
- Aside: UPTIME + filtros hierárquicos (Estado → Cidade → Distrito)
- `#map`: container Leaflet fullscreen
- `<script type="module" src="./js/main.js">`
- Sidebar tem `#bottleCount`, `#countDirections`, `#bottleStatus`

**`crud.html`:** Formulários POST/DELETE de estações com confirmação

### Módulos JS

| Módulo | Função |
|---|---|
| `main.js` | Orquestrador: `createMap()`, `fetchStations()`, `selectStation()`, `startBottlePolling()` |
| `api.js` | `fetchStations()` → GET `http://127.0.0.1:8000/api/stations` |
| `bottle-counter.js` | `fetchBottleCount(stationId)` → GET `/api/stations/{id}/bottle-count` |
| `map.js` | Mapa Leaflet em `[-23.5015, -46.4526]`, zoom 13, tiles OpenStreetMap |
| `heatmap.js` | Intensidade `log1p`, raio adaptativo por zoom (4 faixas: state/regional/neighborhood/close) |
| `markers.js` | Marcadores `L.marker` com popup (station_id + detections), visíveis zoom ≥ 14 |
| `filters.js` | Filtros cascata com `populateSelect`, `matchesAdministrativeFilter` |
| `crud.js` | POST `/api/stations` e DELETE `/api/stations/{id}` com confirmação |
| `config.js` | `HEATMAP_CONFIG` centralizado |
| `uptime.js` | `setInterval` 1s, contador desde `Date.now()` |
| `zoom.js` | `L.control` top-right |

### Estilização

- Tema escuro monocromático ("estética BIOS antiga") com scanlines
- Grayscale 100% + brightness 35% nos tiles do mapa
- Fonte `Courier New` monospace em todo o dashboard
- Mapa em tela cheia com painel lateral de 300px

### Fluxo de Polling

```
main.js usa startBottlePolling(stationId, updateStationMetrics, updateVisualization) com intervalo de 3s
  → fetchBottleCount(stationId) → GET /api/stations/{id}/bottle-count
  → updateStationMetrics atualiza station.bottle_count e station.detections no array in-memory
  → updateVisualization() re-renderiza heatmap e markers
  → Polling limpa intervalo anterior antes de criar novo (clearInterval)
  → updateBottleCountDisplay mostra count, positive/negative arrows, e status (online/loading/no-data/polling error)
```

### `HEATMAP_CONFIG` (`config.js`)

```javascript
{
    minOpacity: 0.45,
    blur: 25,
    maxZoom: 18,
    municipal: { maxZoom: 16 },
    highZoom: { minZoom: 17, maxDetections: 300 },
    markers: { minZoom: 14 },
    radius: { state: 25, regional: 38, neighborhood: 32, close: 25 }
}
```

---

## 6. Fluxo de Dados Completo

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐
│  CÂMERA  │───▶│  SSD     │───▶│  BYTE    │───▶│ Line     │───▶│ FastAPI│
│  (RPi)   │    │ MobileNet│    │ TRACK    │    │ Counter  │    │ :8000 │
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

## 7. Arquivos de Configuração e Documentação

| Arquivo | Descrição |
|---|---|
| `requirements.txt` | 10 dependências reais (não é `pip freeze` do sistema) |
| `.gitignore` | Python cache, `.venv`, `ultralytics-env`, `best.pt`, `runs/`, `tmp/`, `.env`, imagens JPEG |
| `stations.json` | 60 documentos de exemplo para importar com `mongoimport` |
| `dashboard/VALIDATION.md` | Checklist de validação manual da dashboard (7 itens) |
| `rpi-server-communication.md` | Guia de integração Raspberry Pi ↔ Servidor |
| `README.md` | Documentação completa do projeto (504 linhas) |
| `reproduction.md` | Guia de reprodução do ambiente em outras máquinas |

### `requirements.txt` (conteúdo)

```
fastapi>=0.141.0
uvicorn>=0.52.0
pydantic>=2.0.0
pymongo
opencv-python
supervision==0.27.0
lap==0.5.12
cython-bbox==0.1.5
numpy==1.26.4
requests
```

---

## 8. Comandos Úteis

### Iniciar Backend
```bash
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

### MongoDB
```bash
sudo systemctl start mongod
mongosh
use aquamonitor
db.stations.find().pretty()
```

### Importar Dados de Exemplo
```bash
mongoimport --db aquamonitor --collection stations --file stations.json --jsonArray
```

### Testar API
```bash
curl http://127.0.0.1:8000/api/stations
curl -X POST http://127.0.0.1:8000/api/stations \
  -H "Content-Type: application/json" \
  -d '{"station_id":99,"detections":10,"location":{"type":"Point","coordinates":[-46.0,-23.0]}}'
curl -X POST http://127.0.0.1:8000/api/stations/1/bottle-count \
  -H "Content-Type: application/json" \
  -d '{"count":5,"count_by_direction":{"positive":3,"negative":2}}'
curl http://127.0.0.1:8000/api/stations/1/bottle-count
curl -X POST http://127.0.0.1:8000/api/stations/1/bottle-events \
  -H "Content-Type: application/json" \
  -d '{"event_id":"test-1","direction":"positive","timestamp":"2026-09-12T12:00:00Z"}'
```

### Detecção Local
```bash
.venv/bin/python backend/detection/object-ident.py
.venv/bin/python backend/detection/object-ident.py --publish
.venv/bin/python backend/detection/object-ident.py --camera 0 --width 640 --height 480 --detection-interval 0.25 --confidence 0.45 --nms 0.2
```

> **Não** é necessário usar `ultralytics-env` para detecção — o pipeline usa `OpenCVDnnDetector` com `opencv-python` que está no `.venv`. `ultralytics-env` é apenas para YOLOv8/treino.

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

## 9. Dependências Principais

### Python (backend)
- `fastapi`, `uvicorn`, `pydantic`, `pymongo`, `fastapi.middleware.cors.CORSMiddleware`
- `supervision==0.27.0` (ByteTrack)
- `lap==0.5.12`, `cython-bbox==0.1.5` (dependências do ByteTrack)
- `opencv-python`, `numpy==1.26.4` (SSD MobileNet + OpenCV DNN)
- `requests` (`api_client.py` HTTP client)

### JavaScript (frontend)
- `leaflet@1.9.4`, `leaflet.heat`, OpenStreetMap tiles

### Modelos
- SSD MobileNet V3 Large COCO (`frozen_inference_graph.pb`) para detector local

---

## 10. Notas Importantes

### Bugs e Avisos

1. `app.py` tem imports duplicados (cosmético, não afeta funcionamento): `typing.Literal` importado 2×, `pydantic.BaseModel` importado 2×, `pymongo` importado em linhas conflitantes

2. `MongoClient` precisa de `serverSelectionTimeoutMS=5000` para não travar se MongoDB estiver indisponível. O atual **não** tem esse timeout

3. `create_station` **NÃO** verifica duplicidade via `find_one` — faz `insert_one` diretamente. Estações com `station_id` duplicada causarão erro do MongoDB sem tratamento de `DuplicateKeyError`

4. O campo `detections` na resposta `GET /api/stations` espelha `bottle_count.count` para backward compatibility

5. `BottleCountPayload` **NÃO** tem `session_id` — POST é fire-and-forget

6. `LineCounter` TEM método `reset()` que limpa `count`, `count_by_direction`, `_frame`, `_states`, `_counted_ids`. **NÃO** tem `save_state()`/`load_state()` — estado não persistido em MongoDB

7. Não existe função `_to_iso()` em `app.py` — timestamps serializados inline em `serialize_bottle_count()`

8. Não existe modelo `StationCreate` — `create_station` aceita `dict`, não Pydantic model

9. `object-ident.py` usa `sys.path.insert` quando executado como script (`__package__ in {None, ""}`). Se der `ModuleNotFoundError` para `supervision`, verifique se o venv correto está ativo

10. `ObjectId` retornado por MongoDB não é JSON-serializável. Converta para string: `result["_id"] = str(result["_id"])` em qualquer rota que retorne documento completo do `find_one`

### Segurança

11. Não exponha MongoDB à rede sem autenticação e firewall adequado

12. Cuidado com `db.dropDatabase()`, `db.collection.drop()`, `deleteMany({})`

13. `requirements.txt` lista apenas as dependências reais do projeto — verifique antes de adicionar novas dependências

### Ambientes

14. USE `.venv` PARA O BACKEND E DETECÇÃO (pipeline usa `OpenCVDnnDetector`). USE `ultralytics-env` APENAS PARA YOLOv8/treino
    - `.venv` tem: `fastapi/uvicorn/pymongo/supervision/opencv-python/numpy/requests`
    - `ultralytics-env` tem: YOLOv8 para treino
    - Verifique com: `python -c "import supervision; print(supervision.__version__)"`

15. `object-ident.py` usa `OpenCVDnnDetector` (SSD MobileNet), **NÃO** `YOLOv8 best.pt`. O `best.pt` existe no projeto mas não é usado pelo código atual

16. O heatmap usa intensidade logarítmica (`Math.log1p`) e raio adaptativo por zoom

17. Os filtros de localidade são hierárquicos e cascatais (estado → cidade → distrito)

18. A estética do dashboard é monocromática ("BIOS antiga")

19. Quando verificar estado do git após `git restore`, evite loops infinitos de `git status --short`. Se o output for idêntico em chamadas consecutivas, o working tree está estável — avance

20. `api_client.py` usa `timeout=3` nas requisições POST para evitar hangs

21. `DetectionPipeline.process()` chama `publish_if_due()` internamente além do `finally` block. `publish_if_due` retorna `bool` e avança o schedule mesmo após erro de rede

---

## 11. Testes Unitários

**3 arquivos de teste, 13 testes `unittest` no total:**

| Arquivo | Testes | Descrição |
|---|---|---|
| `test_station_metrics.py` | 4 | GET `/api/stations` com/sem `bottle_count`, múltiplas estações, índice |
| `test_bottle_events.py` | 5 | Idempotência, índice único, duplicate key, unknown station, validação |
| `test_bottle_count.py` | 4 | POST armazena métrica, rejeita estação desconhecida, zero count, último métrico |

Todos usam `unittest` (não pytest), com `Mock` para collections MongoDB.

```bash
.venv/bin/python -m unittest discover -v
```

---

## 12. Pipeline de Detecção — Detalhes Adicionais

- `OpenCVDnnDetector.detect()` retorna `list[Detection]` com `class_id` começando em 1 (índice COCO), ajustado para 0-based pelo `class_names[int(class_id) - 1]`
- `DetectionPipeline` usa `api_config` criado uma única vez via `ApiConfig(...)` com `args.publish or API.enabled`
- `draw_overlay()` desenha retângulos verdes nos tracks, linha laranja `COUNTING_LINE`, e contador `"Garrafas: N"`
- O `finally` block de `object-ident.py` chama `pipeline.publish_if_due(force=True)` antes do cleanup para garantir que a última contagem seja enviada ao backend

---

## 13. Cuidados com Arquivos Removidos do Git

Os seguintes arquivos foram removidos do repositório:
- `git.txt` (removido do repo)
- `implementation.txt` (removido do repo)

**Não referencie esses arquivos em notas ou documentação.**

---

*Notas atualizadas: Setembro 2026*
