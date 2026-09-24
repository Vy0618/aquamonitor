# Aqua Monitor

Monitoramento de estações de coleta com visão computacional — rastreamento de garrafas plásticas e outros resíduos em rios usando SSD MobileNet V3 ou YOLOv8 + ByteTrack/LineTracker, com backend FastAPI, MongoDB e dashboard web Leaflet.

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
- [Componente Embarcado — Raspberry Pi](#-componente-embarcado--raspberry-pi)
- [Camada de Dados — MongoDB](#-camada-de-dados--mongodb)
- [Backend — FastAPI](#-backend--fastapi)
- [Visão Computacional](#-visão-computacional)
- [Frontend — Dashboard](#-frontend--dashboard)
- [Fluxo de Dados](#-fluxo-de-dados)
- [Testes Locais](#-testes-locais)
- [Comandos Úteis](#-comandos-úteis)
- [Dependências](#-dependências)
- [Configuração](#-configuração)
- [Notas Importantes](#-notas-importantes)
- [Limitações e Segurança](#-limitações-e-segurança)

---

## 📋 Visão Geral

**Aqua Monitor** é um sistema de monitoramento ambiental que utiliza visão computacional para detectar e rastrear resíduos (garrafas, latas, cartolinas, papéis, plásticos) em corpos d'água. A estação embarcada captura frames de câmera, executa um detector YOLOv8 ou SSD MobileNet, rastreia objetos entre frames e contabiliza cada objeto somente quando ele cruza uma linha horizontal configurada. Para cada cruzamento, um evento é enviado ao backend via HTTP. O backend armazena no MongoDB e o dashboard exibe os resultados em tempo real.

### Tecnologias por camada

| Camada | Tecnologias |
|--------|-------------|
| Estação | Python, OpenCV, Ultralytics/YOLO ou OpenCV DNN/SSD MobileNet, Requests |
| Rastreamento | Associação gulosa por centróide (line_tracker.py) ou ByteTrack |
| GPS opcional | NEO-6M via UART, PySerial e NMEA RMC/GGA |
| API | FastAPI, Pydantic, PyMongo |
| Dados | MongoDB, coleções `stations`, `detection_events` |
| Dashboard | HTML/CSS/ES Modules, Leaflet, leaflet.heat, OpenStreetMap |

### Estado Atual do Projeto (Set/2026)

**Todas as fases concluídas.**

| Fase | Status | Descrição |
|------|--------|-----------|
| 1 | ✅ Concluída | Bibliotecas centrais (`tracker.py`, `geometry.py`, `line_counter.py`, `config.py`) |
| 2 | ✅ Concluída | Integração (`detection_pipeline.py`, `api_client.py`, `object-ident.py`) |
| 3 | ✅ Concluída | Backend completo com endpoints `bottle-count`, `bottle-events` e `detections` |
| 4 | ✅ Concluída | Frontend com `bottle-counter.js` e polling ativo no `main.js` |
| 5 | ✅ Concluída | 3 arquivos de teste com 13 testes unittest |

**Duas arquiteturas de detecção coexistem:**
- **Pipeline legado** (raiz): SSD MobileNet V3 + ByteTrack via `backend/detection/` — endpoint `POST /api/stations/{id}/bottle-events`
- **Sistema embarcado** (RaspberryPi/): YOLOv8 ou SSD MobileNet via `RaspberryPi/monitoring/` — endpoint `POST /api/detections` (contrato ativo)

---

## 🏗️ Arquitetura

### Fluxo da estação embarcada (contrato ativo)

```
Câmera (USB/RPi) → YOLO ou SSD MobileNet → LineTracker → POST /api/detections → FastAPI :8000 → MongoDB
                                                                                                 │
                                                                                   GET /api/stations        │
                                                                                   GET /api/stations/{id}/detections
                                                                                                 │
                                                                                                 ▼
                                                                                          Dashboard Leaflet + Heatmap + Polling 3s
```

### Fluxo do pipeline legado (raiz)

```
Câmera (RPi) → SSD MobileNet V3 (OpenCV DNN) → ByteTrack → LineCounter → POST /api/stations/{id}/bottle-events → FastAPI :8000 → MongoDB
```

### Arquitetura completa (Mermaid)

```mermaid
flowchart LR
    Camera[Câmera USB / OpenCV] --> Detector{Detector}
    Detector -->|YOLO| Tracker[Rastreador por centróide]
    Detector -->|SSD MobileNet| Tracker
    GPS[NEO-6M UART opcional] --> SSD[Monitor SSD]
    Tracker --> Line[Detecção de cruzamento]
    Line --> Local[contagem_residuos.json]
    Line --> Event[Evento de detecção JSON]
    Event -->|POST /api/detections| API[FastAPI :8000]
    API --> Mongo[(MongoDB aquamonitor)]
    Mongo --> API
    API -->|GET /api/stations<br>GET /api/stations/{id}/detections| Dashboard[Dashboard :3000]
```

### Fluxo detalhado

1. O monitor abre a câmera definida em `camera.device_index`.
2. YOLO ou SSD MobileNet gera objetos `Detection` com classe, confiança e caixa delimitadora.
3. `LineTracker` associa cada caixa a um objeto já visto da mesma classe pela distância entre centróides.
4. Ao cruzar a linha horizontal em 55% da altura do frame, o objeto é contado uma única vez.
5. A contagem por categoria é salva localmente em `data/contagem_residuos.json`.
6. O monitor envia um evento HTTP com UUID para `/api/detections`.
7. O backend exige que a estação exista, salva o evento em `detection_events` e rejeita UUIDs repetidos.
8. O dashboard consulta estações e, para a estação selecionada, faz polling do resumo a cada 3 segundos.

No modo SSD, a última posição GPS disponível e o estado online/offline atualizam o documento local `station/station.json`. Esse arquivo **não é sincronizado automaticamente** ao MongoDB pelo código atual.

---

## 📁 Estrutura de Diretórios

```
aquamonitor/
├── backend/
│   ├── app.py                         # FastAPI — rotas CRUD + bottle-count + bottle-events + detections
│   ├── test_detection_events.py       # testes unitários da API/resumos de detecção
│   ├── test_mongodb.py                # imprime documentos da coleção stations
│   ├── test_station_metrics.py        # 4 testes unittest (GET /api/stations com bottle_count)
│   ├── test_bottle_events.py          # 5 testes unittest (ingestão idempotente de events)
│   ├── test_bottle_count.py           # 4 testes unittest (associação métricas↔estações)
│   └── detection/                     # pipeline local legado de visão computacional
│       ├── __init__.py
│       ├── config.py                  # Configurações: COUNTING_LINE, BYTETRACK, ApiConfig
│       ├── geometry.py                # Geometria pura: centroid, signed_distance, crosses_line
│       ├── line_counter.py            # Contagem stateful de cruzamentos de linha
│       ├── tracker.py                 # ByteTrack wrapper (detector-agnostic)
│       ├── detection_pipeline.py      # Orquestra detector → tracker → counter → API
│       ├── api_client.py              # HTTP client para publicar contagem no backend
│       ├── object-ident.py            # Runner principal: câmera → pipeline (com -)
│       └── models/
│           ├── coco.names                 # 90 classes COCO
│           ├── frozen_inference_graph.pb  # Pesos do SSD MobileNet (OpenCV DNN)
│           └── ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt  # Config do modelo
├── dashboard/
│   ├── index.html               # Mapa Leaflet + filtros + uptime + bottle count
│   ├── crud.html                # Formulários POST/DELETE de estações
│   ├── style.css                # Tema escuro monocromático ("BIOS antiga")
│   ├── cadastro-style.css       # Estilos da página de cadastro
│   └── js/
│       ├── api.js               # fetchStations() → GET http://127.0.0.1:8000/api/stations
│       ├── bottle-counter.js    # fetchBottleCount() → GET /api/stations/{id}/bottle-count
│       ├── config.js            # HEATMAP_CONFIG (raios, opacidades, zoom thresholds)
│       ├── main.js              # Orquestrador principal (init map, fetchers, eventos, polling)
│       ├── map.js               # Cria mapa Leaflet [-23.5015, -46.4526] zoom 13
│       ├── heatmap.js           # Intensidade logarítmica, raio adaptativo por zoom
│       ├── markers.js           # Marcadores L.marker com popups (visíveis zoom ≥ 14)
│       ├── filters.js           # Filtros hierárquicos cascata: estado → cidade → distrito
│       ├── crud.js              # POST /api/stations + DELETE /api/stations/{id}
│       ├── uptime.js            # setInterval 1s, conta desde Date.now()
│       └── zoom.js              # L.control top-right mostrando zoom atual
├── RaspberryPi/                           # Componente embarcado (estação)
│   ├── __init__.py                        # Pacote Python RaspberryPi
│   ├── camera/
│   │   ├── __init__.py
│   │   └── webcam_config.py         # Abertura e parâmetros da câmera
│   ├── communication/
│   │   ├── __init__.py
│   │   └── backend_client.py        # Cliente HTTP da estação
│   ├── config/
│   │   ├── __init__.py
│   │   ├── raspberrypi_config.json    # Configuração da estação (central)
│   │   └── requirements.txt           # Dependências embarcadas (ultralytics, opencv, requests, pyserial)
│   ├── data/
│   │   ├── __init__.py
│   │   └── contagem_residuos.json    # Estado local da contagem
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── yolo_detector.py         # Adaptador Ultralytics/YOLO
│   │   └── ssd_mobilenet_detector.py # Adaptador SSD MobileNet/OpenCV DNN
│   ├── gps/
│   │   ├── __init__.py
│   │   └── gps_neo6m.py             # Leitura assíncrona NMEA
│   ├── models/                        # Pesos e rótulos dos detectores
│   │   ├── best (1).pt                # Peso YOLOv8
│   │   ├── frozen_inference_graph.pb  # Pesos SSD MobileNet
│   │   ├── ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
│   │   └── coco.names
│   ├── monitoring/                    # Pontos de entrada dos monitores
│   │   ├── __init__.py
│   │   ├── monitor_residuos.py        # Ponto de entrada YOLO
│   │   └── monitor_ssd_mobilenet.py   # Ponto de entrada SSD MobileNet
│   ├── runtime/
│   │   └── __pycache__/             # Bytecode compilado (Python 3.14)
│   ├── station/                       # Documento local e atualização GPS
│   │   ├── __init__.py
│   │   ├── station.json               # Documento local da estação
│   │   ├── station_document.py        # Leitura, validação e gravação atômica
│   │   └── update_station_location.py # Utilitário de execução única
│   ├── tracking/
│   │   ├── __init__.py
│   │   └── line_tracker.py          # Rastreamento e cruzamento de linha
│   ├── TESTE_LOCAL.md                 # Roteiro rápido de integração local
│   └── README.md                      # Documentação do componente embarcado
├── stations.json                    # Dados de exemplo (estações para importação MongoDB)
├── requirements.txt                 # Dependências backend/pipeline legado
├── .gitignore
└── .venv/ + ultralytics-env/        # Dois venvs (.venv = backend + detecção, ultralytics = YOLOv8/treino)
```

---

## 🔧 Instalação

### Pré-requisitos (Debian / Ubuntu)

```bash
# Atualizar o sistema
sudo apt update && sudo apt upgrade -y

# Python 3.12+, pip e venv
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Dependências do sistema para OpenCV
sudo apt install -y libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1

# MongoDB 6+ (Debian/Ubuntu)
sudo apt install -y curl gnupg
curl -fsSL https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor
echo "deb [signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install -y mongodb-org

# Iniciar o MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Node.js (para executar o dashboard localmente)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

### 1. Clone o repositório

```bash
git clone https://github.com/Vy0618/aquamonitor.git
cd aquamonitor
```

### 2. Ambientes Virtuais Python

```bash
# Ambiente principal (FastAPI + backend + detecção)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Instalar dependências do componente embarcado (obrigatório para monitores YOLO/SSD)
pip install -r RaspberryPi/config/requirements.txt

# Ambiente Ultralytics (YOLOv8/treino — já configurado como ultralytics-env/)
# NÃO é necessário para o pipeline de detecção local (usa .venv)
```

### 3. Verificar arquivos de modelo

```bash
# Linux
test -f RaspberryPi/models/best\(1\).pt
test -f RaspberryPi/models/frozen_inference_graph.pb
test -f RaspberryPi/models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt
test -f RaspberryPi/models/coco.names
```

### 4. MongoDB

```bash
# Verificar se o MongoDB está rodando
sudo systemctl status mongod

# Acessar o shell do MongoDB
mongosh
use aquamonitor
```

### 5. Importar dados de exemplo

```bash
mongoimport --db aquamonitor --collection stations --file stations.json --jsonArray
```

> **Atenção:** O comando pode inserir duplicatas se executado repetidamente; o repositório não fornece script de limpeza ou migração. Confirme antes de reimportar.

### 6. GPS (opcional, para modo SSD em Raspberry Pi física)

- NEO-6M conectado à UART
- Em Linux: o dispositivo serial é `/dev/serial0` (RPi) ou `/dev/ttyUSB0`
- Em teste local, mantenha `gps.enabled: false` no JSON de configuração
- O usuário precisa estar no grupo `video` para acessar a câmera: `sudo usermod -aG video $USER`

---

## 🚀 Uso

### Ordem recomendada

1. Inicie MongoDB.
2. Inicie o backend.
3. Confirme/cadastre a estação.
4. Inicie o dashboard.
5. Inicie um monitor YOLO ou SSD.

### Iniciar Backend (FastAPI)

```bash
cd /home/vyzxc/aquamonitor
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
# ou
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

### Verificar backend

```bash
curl http://127.0.0.1:8000/api/stations
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

# Inserir contagem de garrafas (pipeline legado)
curl -X POST http://127.0.0.1:8000/api/stations/1/bottle-count \
  -H "Content-Type: application/json" \
  -d '{"count":5,"count_by_direction":{"positive":3,"negative":2}}'

# Recuperar última contagem (pipeline legado)
curl http://127.0.0.1:8000/api/stations/1/bottle-count

# Inserir evento de cruzamento — pipeline legado (idempotente)
curl -X POST http://127.0.0.1:8000/api/stations/1/bottle-events \
  -H "Content-Type: application/json" \
  -d '{"event_id":"camera-1-track-42-2026-09-12T12:00:00Z","direction":"positive","timestamp":"2026-09-12T12:00:00Z"}'

# Inserir evento de detecção — contrato ativo (idempotente)
curl -X POST http://127.0.0.1:8000/api/detections \
  -H "Content-Type: application/json" \
  -d '{"event_id":"7f8a9b10-1111-2222-3333-444444444444","station_id":1,"detection_type":"can","confidence":0.92,"track_id":1,"detected_at":"2026-09-18T12:00:00+00:00"}'

# Recuperar resumo de detecções
curl http://127.0.0.1:8000/api/stations/1/detections
```

### Detecção Local (pipeline legado)

```bash
# Sem envio ao backend
.venv/bin/python backend/detection/object-ident.py

# Com envio ao backend (publica a cada 5s para o FastAPI)
.venv/bin/python backend/detection/object-ident.py --publish
```

### Monitor Embarcado (YOLOv8)

```bash
source .venv/bin/activate
python -m RaspberryPi.monitoring.monitor_residuos
```

O terminal deve mostrar `Backend conectado; estação 1 validada.` e depois `Monitor iniciado`. Pressione `Q` ou `Esc` para encerrar.

### Monitor Embarcado (SSD MobileNet)

Com GPS físico:
```bash
python -m RaspberryPi.monitoring.monitor_ssd_mobilenet
```

Em um computador comum, defina temporariamente `gps.enabled` como `false` no JSON antes do comando. O processo deve mostrar `Monitor SSD MobileNet iniciado`.

### Atualização única de localização

```bash
python -m RaspberryPi.station.update_station_location
```

Requer GPS habilitado, PySerial e um fix NMEA válido. Não abre câmera nem publica no backend.

### Executar Testes

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m unittest backend.test_station_metrics -v
.venv/bin/python -m unittest backend.test_bottle_events -v
.venv/bin/python -m unittest backend.test_bottle_count -v
.venv/bin/python -m unittest backend.test_detection_events -v
```

### Dashboard

```bash
cd /home/vyzxc/aquamonitor/dashboard
python -m http.server 3000
# Acesse http://127.0.0.1:3000
```

---

## 📡 Componente Embarcado — Raspberry Pi

### Visão geral

O Aqua Monitor registra resíduos vistos por uma câmera. A estação embarcada captura frames, executa um detector YOLO ou SSD MobileNet, rastreia centróides entre frames e contabiliza um objeto somente quando ele cruza uma linha horizontal configurada. Para cada cruzamento, envia ao backend um evento com categoria, confiança, identificador do rastreamento e data/hora.

```text
Câmera USB → detector (YOLO ou SSD MobileNet) → rastreador de linha
        → contador local → evento HTTP para o backend
                         ↘ documento da estação + GPS (fluxo SSD)
```

O monitor YOLO usa o detector treinado presente no projeto. O monitor SSD MobileNet é uma alternativa que também mantém o documento local da estação e, quando habilitado, incorpora a posição mais recente do GPS.

### Classes configuradas

`bottle`, `can`, `carton`, `paper` e `plastic`.

### Descrição detalhada dos arquivos

#### `README.md`

Apresentação curta desta área. Explica a separação por pastas, aponta onde ficam os componentes principais e identifica os dados persistidos e os pesos de modelo. Não é executado pelo sistema; serve para orientação de quem abre o repositório.

#### `camera/webcam_config.py`

Centraliza a conexão com a webcam USB por meio do OpenCV.

- A classe imutável `WebcamConfig` reúne o índice do dispositivo, largura, altura, taxa de quadros e o backend de vídeo. Os valores padrão são câmera `0`, resolução `1280×720` e `30 FPS`.
- A propriedade `resolution` devolve a largura e altura como uma tupla, no formato esperado por partes da aplicação.
- `open_camera()` cria um `cv2.VideoCapture`. Se não houver backend definido, deixa o OpenCV escolher — na Raspberry Pi, isso normalmente resulta em V4L2. Quando existe um backend explícito, ele o envia ao OpenCV.
- Antes de devolver a câmera, solicita ao driver a resolução e o FPS configurados. A configuração é uma solicitação: o dispositivo pode aceitar valores diferentes dependendo do hardware e driver.
- Caso a câmera não abra, o método encerra com uma mensagem que indica verificar a conexão ou o `device_index`.

Este módulo não faz detecção nem mostra imagens; ele só entrega uma captura de vídeo pronta para os monitores.

#### `communication/backend_client.py`

Implementa a camada HTTP da estação para o backend AquaDetector.

- `BackendConfig` guarda três parâmetros: `base_url`, o caminho de eventos de detecção e o tempo limite das chamadas. A propriedade `detections_url` normaliza uma possível barra final da URL base e monta a URL final de `POST`.
- `BackendClient` cria uma sessão persistente do pacote `requests`, o que permite reaproveitar conexões HTTP entre eventos consecutivos.
- Ao ser construído, ele dá prioridade à variável de ambiente `AQUADETECTOR_API_URL`. Assim, o endereço do backend pode ser trocado na Raspberry Pi sem editar o JSON. Também bloqueia o valor de exemplo `SEU_IP_DO_BACKEND`, para evitar uma inicialização com uma URL não configurada.
- `ensure_station_is_available(station_id)` faz `GET /api/stations`, valida a resposta HTTP e confirma que a lista devolvida contém a estação informada. Falha de conexão, JSON inválido, resposta de erro ou estação ausente viram uma exceção clara.
- `send_detection(event)` faz `POST` do evento como JSON para `/api/detections` (ou o caminho configurado). Se o backend rejeitar a chamada ou a rede falhar, lança uma exceção de comunicação.

O módulo não decide o que foi detectado; apenas verifica a existência da estação e transporta os eventos criados pelos monitores.

#### `config/raspberrypi_config.json`

É a configuração declarativa da estação. Evita que valores de infraestrutura e parâmetros operacionais fiquem espalhados pelo código.

| Campo | Valor atual | Efeito |
|-------|------------|--------|
| `station_id` | `1` | Identificador numérico usado na validação do backend, nos eventos e na contagem persistida |
| `station_document` | sub-objeto | Dados iniciais do documento local. `path` indica o arquivo destino (`station/station.json`); `_id` usa MongoDB Extended JSON (`$oid`); `detections`, `status`, `location` e `administrative` preenchem a estrutura inicial |
| `gps.enabled` | `true` | Habilita/desabilita a leitura do NEO-6M |
| `gps.port` | `/dev/serial0` | Porta serial do GPS |
| `gps.baudrate` | `9600` | Taxa de transmissão |
| `gps.timeout` | — | Timeout de leitura |
| `backend.base_url` | `http://127.0.0.1:8000` | Endereço do backend. `127.0.0.1` significa o próprio dispositivo |
| `backend.detections_path` | `/api/detections` | Endpoint de ingestão |
| `backend.timeout_seconds` | `5` | Timeout de GET/POST |
| `backend.require_connection_on_startup` | `true` | Impede o início se a estação não for encontrada |
| `camera.device_index` | `0` | Índice da câmera OpenCV |
| `camera.width/height/fps` | `1280/720/30` | Parâmetros para `WebcamConfig` |
| `detection.weight_path` | `models/best (1).pt` | Caminho do peso YOLO |
| `detection.confidence_threshold` | `0.45` | Limiar YOLO |
| `detection.input_size` | `640` | Tamanho de entrada da imagem |
| `detection.classes` | `[bottle, can, carton, paper, plastic]` | As cinco classes aceitas |
| `ssd_mobilenet.weights` | `models/frozen_inference_graph.pb` | Pesos TensorFlow SSD |
| `ssd_mobilenet.config` | `models/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt` | Descrição da rede |
| `ssd_mobilenet.labels` | `models/coco.names` | Arquivo de rótulos (opcional) |
| `ssd_mobilenet.confidence_threshold` | `0.45` | Limiar SSD |
| `ssd_mobilenet.input_size` | — | Resolução de rede |

O arquivo contém dados de configuração, não lógica de execução. Os valores de caminho foram definidos quando o código ainda usava a estrutura plana original.

**Variável de ambiente:** `AQUADETECTOR_API_URL` sobrescreve `backend.base_url`. Não há `.env`, senhas, tokens ou chaves de API no código. Não foram identificadas credenciais hardcoded.

#### `config/requirements.txt`

Lista as bibliotecas mínimas do ambiente Python embarcado:

- `ultralytics` — carrega e executa o modelo YOLO
- `opencv-python` — captura vídeo, desenha a interface na imagem e executa a rede SSD por DNN
- `requests` — comunicação HTTP com o backend
- `pyserial` — abre a UART e recebe as frases NMEA do GPS

Os limites `>=` permitem instalar versões posteriores. Dependências indiretas, como NumPy, são instaladas pelos pacotes que as exigem.

#### `data/contagem_residuos.json`

Estado persistido da contagem local de resíduos. O monitor atualiza esse arquivo sempre que identifica um cruzamento novo e novamente ao encerrar.

- `station_id` associa a contagem a uma estação. O arquivo presente informa `61`, enquanto a configuração atual informa `1`; isso é um dado existente que o código carrega como está e não é corrigido automaticamente.
- `counts` contém um acumulador por classe. No estado atual há quatro garrafas (`bottle`) e zero itens nas demais classes.
- `detection_types` registra quais classes faziam parte da contagem.
- `updated_at` é a data/hora UTC da última gravação, em ISO 8601.

A gravação é segura contra interrupção parcial: o monitor escreve primeiro um arquivo temporário com extensão `.tmp` e depois o substitui pelo JSON final.

#### `detection/yolo_detector.py`

Adaptador entre o modelo YOLO do projeto e o restante da aplicação.

- `EXPECTED_CLASSES` declara o vocabulário permitido: garrafa, lata, embalagem cartonada, papel e plástico.
- `Detection` é uma estrutura imutável que representa uma detecção individual: classe, confiança e caixa delimitadora `(x1, y1, x2, y2)`. A propriedade `centroid` calcula o ponto central da caixa; esse ponto é a entrada usada pelo rastreador.
- `YoloDetector` recebe caminho do modelo, confiança mínima, tamanho de imagem, dispositivo opcional e classes autorizadas. Seus padrões são peso em `models/best (1).pt`, limiar `0.45` e entrada de `640` pixels.
- Na inicialização, importa `ultralytics.YOLO` somente quando necessário, permitindo emitir uma mensagem específica se a dependência não estiver instalada. Confirma que o arquivo de pesos existe antes de abrir o modelo.
- `_get_class_names()` adapta o formato da lista/dicionário de nomes exposto pelo Ultralytics para um dicionário.
- `detect(frame)` envia um frame BGR ao YOLO, aplica limiar de confiança, converte as caixas para inteiros e ignora toda classe fora das cinco permitidas. O resultado é uma lista de objetos `Detection`.

Não conta objetos nem comunica o backend: sua responsabilidade termina em transformar uma imagem em detecções filtradas.

#### `detection/ssd_mobilenet_detector.py`

Segunda implementação de detector, baseada em SSD MobileNet TensorFlow e no módulo DNN do OpenCV.

- Reaproveita a estrutura `Detection` do detector YOLO para que o rastreador e o monitor trabalhem da mesma forma independentemente da rede escolhida.
- `DEFAULT_COCO_LABELS` mapeia apenas o ID COCO `44` para `bottle`. Portanto, sem um arquivo de rótulos personalizado, o modo SSD padrão só reconhece garrafas entre as cinco categorias do projeto.
- O construtor confirma a existência dos arquivos `.pb` e `.pbtxt`, abre a rede com `cv2.dnn.readNetFromTensorflow` e guarda limiares, tamanho de entrada, classes permitidas e rótulos.
- `_load_labels()` lê um `labels.txt` opcional. Aceita tanto linhas no formato `id nome` quanto uma classe por linha; ignora linhas vazias e comentários iniciados por `#`.
- `detect(frame)` cria um blob normalizado para o tamanho da rede, executa a inferência e percorre a saída SSD de sete valores por resultado. Filtra confiança baixa e classe não permitida, converte coordenadas normalizadas para pixels e descarta caixas inválidas antes de criar `Detection`.

Para detectar `can`, `carton`, `paper` e `plastic`, o modelo e o arquivo de rótulos precisam ter sido treinados/configurados para essas classes.

#### `gps/gps_neo6m.py`

Controla o GPS u-blox NEO-6M conectado via UART sem interromper o loop da câmera.

- `GpsFix` é uma estrutura imutável com latitude, longitude e horário UTC de recebimento. A propriedade `geojson_coordinates` inverte a ordem para `[longitude, latitude]`, como exige GeoJSON.
- `Neo6mGps` mantém a última posição válida, o último erro, uma trava de concorrência, um evento de parada e uma thread de leitura. O monitor pode continuar processando vídeo enquanto o GPS aguarda dados serialmente.
- `start()` importa `pyserial`, abre a porta configurada e inicia uma thread daemon chamada `neo6m-gps`. Se a biblioteca ou a porta estiver indisponível, devolve um erro explicativo.
- A thread executa `_read_loop()`: lê uma linha da UART, decodifica em ASCII ignorando bytes inválidos, interpreta NMEA e atualiza a última posição. Erros transitórios são guardados em `last_error`, sem parar o monitor.
- `parse_nmea_sentence()` aceita apenas mensagens RMC e GGA de talkers GP ou GN. Para RMC exige status `A`; para GGA exige qualidade de fix diferente de zero. Mensagens malformadas são ignoradas.
- `_nmea_coordinate_to_decimal()` converte o formato NMEA graus+minutos em graus decimais e aplica sinal negativo aos hemisférios Sul e Oeste.

#### `models/best (1).pt`

Arquivo binário de pesos do modelo YOLO utilizado pelo fluxo principal. O Ultralytics o carrega para realizar inferência. Não é um arquivo textual e não deve ser editado manualmente. O sufixo `.pt` indica um checkpoint PyTorch.

#### `monitoring/monitor_residuos.py`

Ponto de entrada do fluxo principal baseado em YOLO. Coordena câmera, detector, rastreamento, persistência de contagem e envio de evento.

- `BASE_DIR`, `CONFIG_FILE` e `COUNTS_FILE` definem, a partir da localização do próprio script, onde o programa espera encontrar sua configuração e contagem. `LINE_Y_RATIO = 0.55` posiciona a linha de contagem a 55% da altura da imagem; `TRACKING_DIRECTION = "both"` conta cruzamentos nos dois sentidos.
- `load_config()` lê o JSON e valida requisitos mínimos: `station_id` positivo e conjunto de classes exatamente igual às cinco esperadas.
- `load_counts()` cria inicialmente todos os contadores zerados e, se houver arquivo salvo, aproveita apenas valores inteiros por classe. Entende um formato antigo em que as contagens estavam na raiz do JSON.
- `save_counts()` monta o documento com timestamp UTC e faz substituição atômica via arquivo temporário.
- `draw_overlay()` desenha a linha amarela de referência, as caixas verdes e suas confianças, e um painel textual com o total de cada classe.
- Em `main()`, o programa lê a configuração, monta o cliente HTTP e, caso exigido, valida a estação no backend. Abre a câmera, carrega o YOLO, restaura a contagem e cria um `LineTracker`.
- Para cada frame, chama o detector e passa as detecções ao rastreador. Cada `Crossing` devolvido incrementa somente uma vez o contador daquele objeto, salva o JSON e gera um evento com UUID, estação, tipo, confiança, ID de rastreamento e data UTC.
- A janela OpenCV mostra o vídeo processado. A tecla `Q` ou `Esc` encerra o loop. O bloco `finally` salva a contagem, libera a câmera e fecha as janelas mesmo se ocorrer uma exceção.

#### `monitoring/monitor_ssd_mobilenet.py`

Ponto de entrada alternativo que substitui YOLO por SSD MobileNet, mas mantém a mesma lógica de contagem e comunicação.

- Reutiliza do monitor YOLO as funções de configuração, contagem e desenho, além das constantes de posição e direção da linha. Isso evita comportamento diferente na contagem entre os dois detectores.
- Antes do loop, valida a estação no backend quando requerido, garante a existência de `station.json` e inicia o GPS caso `gps.enabled` esteja ativo.
- Instancia `SsdMobileNetDetector` usando caminhos e parâmetros da seção `ssd_mobilenet` do JSON. Sem os arquivos `.pb` e `.pbtxt`, falha intencionalmente antes de abrir o monitor.
- No cruzamento, além de salvar a contagem e enviar o mesmo evento HTTP, atualiza o documento da estação: total acumulado, última posição GPS disponível e status `online`.
- Ao encerrar, persiste a contagem, atualiza o documento como `offline`, inclui a última posição disponível, fecha o GPS, libera a câmera e encerra as janelas.

O modo SSD possui integração de estado de estação e GPS que o modo YOLO atual não possui.

#### `runtime/__pycache__/`

Pasta contendo bytecode compilado automaticamente pelo Python para acelerar importações. Os arquivos `.pyc` presentes correspondem a versões Python 3.14 de módulos já executados: cliente de backend, rastreador, configuração da câmera e detector YOLO. Não são código-fonte, não são lidos diretamente por pessoas e podem ser apagados ou recriados pelo Python.

#### `station/station.json`

Documento persistido que representa uma estação individual.

- `_id` armazena um identificador em MongoDB Extended JSON (`$oid`).
- `station_id` é o identificador numérico da estação, atualmente `1`.
- `detections` registra o total consolidado, atualmente `37`.
- `status` informa o estado atual, atualmente `online`.
- `location` é um GeoJSON `Point`; suas coordenadas devem estar na ordem longitude, latitude. O valor presente aponta para `[-46.4526, -23.5015]`.
- `administrative` descreve país, estado, cidade e distrito associados à estação.

`StationDocument` exige que este JSON tenha exatamente esses seis campos de alto nível e valida a forma das coordenadas antes de gravá-lo.

#### `station/station_document.py`

Implementa a persistência e validação de `station.json`.

- A classe `StationDocument` recebe o caminho de destino, o ID da estação e os valores iniciais da configuração.
- `ensure_exists()` lê o documento existente; se ainda não houver arquivo, cria uma versão-base a partir de `station_document` no JSON de configuração.
- `update()` altera somente os valores fornecidos. Para `detections`, guarda o maior valor entre o atual e o novo, impedindo que um contador local antigo reduza o total já registrado. Para GPS, grava um GeoJSON Point; para status, troca o estado textual.
- `_base_document()` constrói o formato inicial com os seis campos exigidos.
- `_read()` abre o JSON e converte erro de leitura ou sintaxe em uma exceção explicativa.
- `_write()` usa o mesmo padrão seguro de arquivo temporário seguido de substituição.
- `_validate()` exige um conjunto exato de campos, `location.type == "Point"`, uma lista de duas coordenadas numéricas e a ordem GeoJSON esperada.

#### `station/update_station_location.py`

Utilitário de execução única para atualizar a posição da estação com o primeiro fix GPS válido recebido.

- Lê a configuração usando a função do monitor YOLO e exige que `gps.enabled` esteja verdadeiro.
- Garante a existência do documento da estação, abre o GPS com porta, baudrate e timeout configurados e avisa que está esperando um fix.
- Enquanto `latest_fix` estiver vazio, aguarda 0,2 segundo por vez. Quando chega uma posição válida, grava apenas localização e status `online` em `station.json` e imprime as coordenadas salvas.
- O bloco `finally` fecha a conexão serial mesmo quando a execução for interrompida com `Ctrl+C` ou ocorrer uma falha.

Não inicia a câmera e não envia evento de detecção ao backend.

#### `tracking/line_tracker.py`

Transforma detecções de frames sucessivos em objetos acompanhados e em eventos de contagem únicos.

- `Point` define um centróide como par `(x, y)`.
- `TrackedObject` mantém o ID interno, classe, centróide atual, centróide anterior, quantidade de frames ausente e se aquele objeto já foi contado.
- `Crossing` é o evento imutável devolvido ao monitor: contém o ID do objeto e sua classe.
- `LineTracker` recebe a coordenada vertical da linha, distância máxima para associar objetos entre frames, quantidade máxima de frames ausentes e direção permitida (`down`, `up` ou `both`). A direção inválida é recusada imediatamente.
- `update(detections)` compara cada detecção com cada objeto ativo da mesma classe. Se a distância entre centróides for no máximo `max_distance`, ela vira candidata a associação. As candidatas são ordenadas por distância; a seleção gulosa garante que cada detecção e cada objeto sejam usados uma única vez no frame.
- Um objeto associado recebe novo centróide e pode disparar `Crossing` se cruzar a linha na direção permitida. A flag `counted` impede que ele seja contado novamente nos frames seguintes.
- Objetos não vistos acumulam `missing_frames`; detecções sem par recebem novos IDs; objetos ausentes além de `max_missing_frames` são removidos.
- `_crossed_line()` identifica uma descida se o `y` anterior estava acima da linha e o novo está sobre/abaixo dela, e uma subida na condição inversa. `_distance()` usa distância euclidiana.

O rastreador não reconhece imagens por si só: depende das caixas produzidas por YOLO ou SSD MobileNet.

### Integração após reorganização física

Os imports foram adaptados para o pacote `RaspberryPi` e cada pasta que contém código passou a ter um `__init__.py`. Os módulos usam imports explícitos, como `RaspberryPi.communication.backend_client`.

`monitor_residuos.py` estabelece a raiz do sistema como a pasta `RaspberryPi/` e resolve a partir dela os caminhos de configuração (`config/raspberrypi_config.json`), dados (`data/contagem_residuos.json`), modelos e documento da estação.

Para que o Python reconheça o pacote, os comandos devem ser executados na raiz do projeto:

```bash
python -m RaspberryPi.monitoring.monitor_residuos
python -m RaspberryPi.monitoring.monitor_ssd_mobilenet
python -m RaspberryPi.station.update_station_location
```

### Configuração (`RaspberryPi/config/raspberrypi_config.json`)

| Campo | Valor atual | Efeito |
|-------|------------|--------|
| `station_id` | `1` | Deve existir na coleção `stations` antes de iniciar o monitor |
| `backend.base_url` | `http://127.0.0.1:8000` | URL do FastAPI. Em uma Pi física, troque pelo IP/hostname do servidor |
| `backend.detections_path` | `/api/detections` | Endpoint de ingestão |
| `backend.timeout_seconds` | `5` | Timeout de GET/POST do cliente embarcado |
| `backend.require_connection_on_startup` | `true` | Impede o início se a estação não for encontrada no backend |
| `camera.device_index` | `0` | Índice da câmera OpenCV |
| `camera.width/height/fps` | `1280/720/30` | Valores solicitados ao driver |
| `gps.enabled` | `true` | O modo SSD tentará abrir `/dev/serial0` |
| `gps.port` | `/dev/serial0` | Porta serial do GPS NEO-6M |
| `gps.baudrate` | `9600` | Taxa de transmissão |
| `detection.confidence_threshold` | `0.45` | Limiar YOLO |
| `detection.input_size` | `640` | Tamanho de entrada da imagem |
| `detection.classes` | `[bottle, can, carton, paper, plastic]` | Classes aceitas |
| `ssd_mobilenet.confidence_threshold` | `0.45` | Limiar SSD |

### Variável de ambiente

| Variável | Obrigatória | Uso |
|----------|------------|-----|
| `AQUADETECTOR_API_URL` | Não | Sobrescreve `backend.base_url` no cliente embarcado. Exemplo: `http://192.168.1.50:8000` |

Não há `.env`, senhas, tokens ou chaves de API configurados no código. Não foram identificadas credenciais hardcoded.

### GPS e rede

- Em teste local Windows, mantenha `gps.enabled: false` para executar o modo SSD sem uma UART NEO-6M
- `127.0.0.1` significa a própria máquina. Em uma Raspberry Pi conectada a um backend separado, defina o IP/hostname do servidor no JSON ou em `AQUADETECTOR_API_URL`
- GeoJSON usa estritamente `[longitude, latitude]`
- Caminho do serial GPS: `COM3` (Windows) / `/dev/ttyUSB0` ou `/dev/serial0` (RPi)

### Limitações conhecidas

- O rastreamento é uma associação gulosa por centróide, não um rastreador de múltiplos objetos sofisticado
- O cliente embarcado lança exceção em falha HTTP; não há fila offline, retry ou backoff
- O documento local `station/station.json` não é sincronizado automaticamente ao MongoDB pelo código atual
- `station.json` pode ter `_id` no formato MongoDB Extended JSON (`{"$oid": "..."}`) que o backend pode rejeitar
- O SSD COCO disponível reconhece apenas `bottle`; as demais categorias (`can`, `carton`, `paper`, `plastic`) exigem modelo/rótulos adequados ou YOLOv8

---

## 🗄️ Camada de Dados — MongoDB

| Parâmetro | Valor |
|-----------|-------|
| **Banco** | `aquamonitor` |
| **Coleções** | `stations`, `bottle_metrics`, `bottle_events`, `detection_events` |
| **Porta** | `27017` |
| **URI** | `mongodb://localhost:27017/aquamonitor` |

### Documento Típico (stations)

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

**`bottle_metrics`** — agregados de contagem (pipeline legado):
```json
{ "station_id": 1, "count": 37, "count_by_direction": {"positive": 20, "negative": 17}, "timestamp": "2026-09-12T14:20:00" }
```

**`bottle_events`** — eventos individuais de cruzamento (pipeline legado, idempotentes):
```json
{ "event_id": "camera-1-track-42-2026-09-12T12:00:00Z", "station_id": 1, "direction": "positive", "timestamp": "2026-09-12T12:00:00Z" }
```

**`detection_events`** — eventos de detecção gerais (contrato ativo do sistema embarcado):
```json
{ "event_id": "7f8a9b10-1111-2222-3333-444444444444", "station_id": 1, "detection_type": "can", "confidence": 0.92, "track_id": 7, "detected_at": "2026-09-18T12:00:00+00:00" }
```

> ⚠️ GeoJSON usa `[longitude, latitude]` — **não** `[latitude, longitude]`.

---

## 🐍 Backend — FastAPI

**Arquivo:** `backend/app.py`
**Dependências:** `fastapi`, `uvicorn`, `pydantic`, `pymongo`, `fastapi.middleware.cors.CORSMiddleware`

### Rotas Implementadas

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/stations` | Criar nova estação (exige `station_id` inteiro positivo e único) |
| `GET` | `/api/stations` | Listar estações com `detections` e `detection_summary` |
| `DELETE` | `/api/stations/{station_id}` | Deletar por station_id |
| `POST` | `/api/stations/{station_id}/bottle-count` | Ingestão de contagem agregada (pipeline legado) |
| `GET` | `/api/stations/{station_id}/bottle-count` | Recuperar última contagem (pipeline legado) |
| `POST` | `/api/stations/{station_id}/bottle-events` | Ingestão de evento individual (idempotente, pipeline legado) |
| `POST` | `/api/detections` | Recebe evento da estação embarcada (contrato ativo) |
| `GET` | `/api/stations/{station_id}/detections` | Retorna `total`, `by_type` e `timestamp` ISO 8601 |

### Modelos Pydantic

**`BottleCountPayload`** (pipeline legado):
```json
{ "count": 5, "count_by_direction": {"positive": 3, "negative": 2} }
```

**`BottleEventPayload`** (pipeline legado):
```json
{ "event_id": "uuid-string", "direction": "positive", "timestamp": "2026-09-12T12:00:00Z" }
```

**`DetectionEventPayload`** (contrato ativo):
```json
{
    "event_id": "uuid-string",
    "station_id": 1,
    "detection_type": "can",
    "confidence": 0.92,
    "track_id": 7,
    "detected_at": "2026-09-18T12:00:00+00:00"
}
```

- `event_id` não pode ser vazio (validador)
- `timestamp`/`detected_at` devem incluir timezone (validador)
- Índice único em `event_id` garante idempotência → DuplicateKeyError retorna HTTP 409

---

## 👁️ Visão Computacional

### Pipeline de Detecção (Legado — raiz)

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

### Módulos de Visão Computacional (Legado)

| Arquivo | Função |
|---------|--------|
| `geometry.py` | Funções puras: `centroid`, `signed_distance`, `crosses_line`, `segments_intersect` |
| `tracker.py` | Wrapper ByteTrack (detector-agnostic) |
| `line_counter.py` | Contagem stateful de cruzamentos |
| `config.py` | Configurações globais (COUNTING_LINE, BYTETRACK, ApiConfig) |
| `detection_pipeline.py` | Orquestra detector → tracker → counter → API |
| `api_client.py` | HTTP client para publicar contagem |
| `object-ident.py` | Runner principal (câmera → pipeline) |

### Pipeline Embarcado (RaspberryPi/)

| Arquivo | Função |
|---------|--------|
| `detection/yolo_detector.py` | Carrega `best (1).pt` via Ultralytics, filtra 5 classes |
| `detection/ssd_mobilenet_detector.py` | Carrega rede TensorFlow `.pb/.pbtxt` com OpenCV DNN |
| `tracking/line_tracker.py` | Associa centróides e emite `Crossing` por objeto (linha em 55% da altura) |
| `monitoring/monitor_residuos.py` | Ponto de entrada YOLO |
| `monitoring/monitor_ssd_mobilenet.py` | Ponto de entrada SSD MobileNet |

### Execução Local (Legado)

```bash
.venv/bin/python backend/detection/object-ident.py
.venv/bin/python backend/detection/object-ident.py --publish
```

---

## 🌐 Frontend — Dashboard

### Arquitetura

Dashboard modular com ES Modules (`main.js` como orquestrador):

| Módulo | Função |
|--------|--------|
| `main.js` | Orquestrador: `createMap()`, `fetchStations()`, `startBottlePolling()` |
| `api.js` | `fetchStations()` → GET `http://127.0.0.1:8000/api/stations` |
| `bottle-counter.js` | `fetchBottleCount(stationId)` → GET `/api/stations/{id}/bottle-count` |
| `map.js` | Mapa Leaflet em `[-23.5015, -46.4526]` zoom 13 |
| `heatmap.js` | Intensidade logarítmica (`Math.log1p`), raio adaptativo por zoom |
| `markers.js` | Marcadores com popup (station_id + detections), visíveis zoom ≥ 14 |
| `filters.js` | Filtros cascata: estado → cidade → distrito |
| `crud.js` | POST/DELETE estações com confirmação |
| `config.js` | `HEATMAP_CONFIG` centralizado |
| `uptime.js` | `setInterval` 1s, contador desde `Date.now()` |
| `zoom.js` | `L.control` top-right mostrando zoom atual |

### Polling de Bottle Count

`main.js` usa `startBottlePolling(stationId, updateStationMetrics, updateVisualization)` com intervalo de **3 segundos**.

### Estilização

- **Tema:** Escuro monocromático ("estética BIOS antiga") com scanlines
- **Mapa:** Grayscale 100% + brightness 35% nos tiles
- **Fonte:** `Courier New` monospace em todo o dashboard
- **Layout:** Mapa fullscreen + painel lateral de 300px

---

## 🔄 Fluxo de Dados Completo

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐
│  CÂMERA  │───▶│  YOLO /  │───▶│  LINE    │───▶│ POST     │    │ FastAPI│
│  (RPi)   │    │ SSD      │    │ TRACKER  │    │ /api     │    │ :8000│
└──────────┘    └──────────┘    └──────────┘    │ /detections│    └──────┘
                                                 │             │
                                                 │ count/event │
                                                 │ (HTTP POST) │
                                                 ▼             │
                                          ┌────────────┐      │
                                          │  MongoDB   │      │
                                          │  aquamonitor│     │
                                          └─────┬──────┘      │
                                                │             │
                                                │ GET /api/stations
                                                │ GET /api/stations/{id}/detections
                                                ▼             │
                                          ┌────────────┐      │
                                          │  Dashboard │      │
                                          │  Leaflet   │      │
                                          │  +Heatmap  │      │
                                          │  +Polling  │      │
                                          │  3s        │      │
                                          └────────────┘      │
```

---

## 🧪 Testes Locais

### Teste de integração HTTP (passo a passo)

#### 1. Ligar o MongoDB

```bash
sudo systemctl start mongod
sudo systemctl status mongod
```

#### 2. Ligar o uvicorn

```bash
source .venv/bin/activate
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Preparar o ambiente

Na raiz do projeto, instale as dependências da parte embarcada:

```bash
source .venv/bin/activate
pip install -r RaspberryPi/config/requirements.txt
```

Confirme que o backend responde e que a estação `1` existe. Se necessário, cadastre-a uma vez:

```bash
curl http://127.0.0.1:8000/api/stations
curl -X POST http://127.0.0.1:8000/api/stations \
  -H "Content-Type: application/json" \
  -d @RaspberryPi/station/station.json
```

> **Problema conhecido:** `station.json` tem `_id` como `{"$oid": "..."}` (MongoDB Extended JSON). O `curl -d @...` envia isso como JSON. O backend pode rejeitar ou aceitar dependendo da versão do pymongo. Se der erro, substitua `_id` por uma string simples no JSON antes de enviar.

#### 4. Validar comunicação HTTP

Envie uma detecção simulado:

```bash
curl -X POST http://127.0.0.1:8000/api/detections \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "'$(uuidgen)'",
    "station_id": 1,
    "detection_type": "can",
    "confidence": 0.92,
    "track_id": 1,
    "detected_at": "'$(date -u +"%Y-%m-%dT%H:%M:%S.%NZ")'"
  }'
```

Verifique se foi registrado:

```bash
curl http://127.0.0.1:8000/api/stations/1/detections
```

A resposta deve mostrar `"total": 1` (ou maior) e `"by_type"` contendo `"can"`.

> **Se `uuidgen` não existir**, use: `"event_id": "test-$(date +%s)"`.

#### 5. Testar o dashboard

Em outro terminal:

```bash
cd /home/vyzxc/aquamonitor/dashboard
python -m http.server 3000
```

Abra `http://127.0.0.1:3000`. A estação deve exibir o total de detecções, as categorias e a última detecção. O painel atualiza a estação selecionada a cada 3 segundos.

> Se o `python` do sistema apontar para Python 3.12 sem os pacotes necessários, use `.venv/bin/python -m http.server 3000`.

#### 6. Executar o monitor com webcam local

Mantenha `backend.base_url` como `http://127.0.0.1:8000`.

**Para SSD MobileNet (OpenCV DNN):**
```bash
source .venv/bin/activate
python -m RaspberryPi.monitoring.monitor_ssd_mobilenet
```

**Para YOLOv8:**
```bash
source .venv/bin/activate
python -m RaspberryPi.monitoring.monitor_residuos
```

**Cuidado com câmera em Linux:** O dispositivo de câmera precisa estar acessível. Verifique com `ls /dev/video*`. Se a câmera não abrir, o usuário pode não estar no grupo `video`:
```bash
sudo usermod -aG video $USER
```

Para verificar se a câmera está acessível antes de executar:
```bash
python -c "import cv2; c = cv2.VideoCapture(0); print('Aberta:', c.isOpened()); c.release()"
```

Pressione `Q` ou `Esc` para encerrar. Cada objeto que cruzar a linha amarela gera um evento em `POST /api/detections`; o dashboard deve refletir a alteração no próximo ciclo de polling.

#### 7. Teste ponta a ponta

1. Inicie MongoDB, backend e dashboard (passos 1-2).
2. Verifique `GET /api/stations`.
3. Rode o monitor com a câmera.
4. Faça um objeto de classe reconhecida cruzar a linha amarela.
5. Observe `Enviado: <classe> (track #<id>)` no terminal.
6. Consulte `GET /api/stations/1/detections`.
7. Clique no ícone `S1` no mapa e confirme total/categorias/horário.

### Testes unitários

```bash
python -m unittest backend.test_detection_events -v
```

Os testes cobrem ingestão de tipos gerais, estação inexistente, duplicação de `event_id`, agregação, localização e normalização de datas legadas. Não há testes automatizados específicos para câmera, YOLO, SSD, GPS ou JavaScript.

### Diferenças específicas de Linux (Mint / Debian Trixie)

| Aspecto | Windows (PowerShell) | Linux (bash) |
|---------|---------------------|--------------|
| Ativar venv | `.\\.venv\\Scripts\\python.exe` | `source .venv/bin/activate` |
| Enviar JSON | `Invoke-RestMethod ... -InFile file.json` | `curl -X POST ... -d @file.json` |
| Gerar UUID | `[guid]::NewGuid().ToString()` | `uuidgen` ou `python -c "import uuid; print(uuid.uuid4())"` |
| Servir dashboard | `Set-Location dashboard; ... -m http.server 3000` | `cd dashboard; python -m http.server 3000` |
| Ver câmera | `Test-Path 'RaspberryPi\\models\\best (1).pt'` | `test -f RaspberryPi/models/best\\(1\\).pt` ou `ls` |
| Permissão de câmera | Não necessário | Usuário precisa estar no grupo `video` |
| Caminho do serial GPS | `COM3` | `/dev/ttyUSB0` ou `/dev/serial0` (RPi) |

> **Nota sobre `device_index`:** Em Linux com V4L2, a câmera pode não estar em `/dev/video0`. Se `cv2.VideoCapture(0)` falhar, verifique os dispositivos disponíveis com `ls /dev/video*` e ajuste `device_index` em `raspberrypi_config.json`.

### Observações

- O SSD MobileNet COCO fornecido reconhece `bottle`; as demais classes dependem do modelo utilizado. O YOLO pode reconhecer as cinco categorias configuradas.
- Ao migrar para a Raspberry Pi física, troque `backend.base_url` pelo IP ou hostname do computador/servidor que executa o FastAPI. `127.0.0.1` na Pi aponta para a própria Pi.
- Um mesmo `event_id` não pode ser enviado duas vezes: a segunda tentativa retorna HTTP 409 para evitar contagem duplicada.

---

## ⚡ Comandos Úteis

### Simular detecções nas 60 estações

Para popular a coleção `detection_events` com um número aleatório de detecções (1-200) por estação, execute no `mongosh`:

```javascript
db.stations.find().forEach(function(station) {
    var stationId = station.station_id;
    var count = Math.floor(Math.random() * 200) + 1;
    for (var i = 0; i < count; i++) {
        db.detection_events.insertOne({
            station_id: stationId,
            detection_type: "bottle",
            confidence: Math.random(),
            track_id: i,
            detected_at: new Date(),
            event_id: "evt_" + stationId + "_" + i + "_" + (Date.now() + i)
        });
    }
});
```

> **Nota:** Este comando insere documentos na coleção `detection_events`, que é a fonte de dados do dashboard. Não atualize o campo `detections` na coleção `stations` diretamente — o backend ignora esse campo.

---

## 📦 Dependências

### Python (Backend)

| Pacote | Versão | Uso |
|--------|--------|-----|
| `fastapi` | ≥0.141.0 | API REST |
| `uvicorn` | ≥0.52.0 | Servidor ASGI |
| `pydantic` | ≥2.0.0 | Models e validação |
| `pymongo` | — | Cliente MongoDB |
| `supervision` | 0.27.0 | ByteTrack tracker |
| `lap` | 0.5.12 | Dependência do ByteTrack |
| `cython-bbox` | 0.1.5 | Dependência do ByteTrack |
| `opencv-python` | — | SSD MobileNet + OpenCV DNN |
| `numpy` | 1.26.4 | Cálculos numéricos |
| `requests` | — | api_client.py HTTP client |

### Python (Embarcado — RaspberryPi/config/requirements.txt)

| Pacote | Versão | Uso |
|--------|--------|-----|
| `ultralytics` | ≥8.0.0 | YOLOv8 detector |
| `opencv-python` | ≥4.8.0 | SSD MobileNet + OpenCV DNN |
| `requests` | ≥2.31.0 | Cliente HTTP da estação |
| `pyserial` | ≥3.5 | GPS NEO-6M via UART |

### JavaScript (Frontend)

| Biblioteca | Versão | Uso |
|------------|--------|-----|
| `leaflet` | 1.9.4 | Mapa interativo |
| `leaflet.heat` | — | Camada de calor |
| OpenStreetMap tiles | — | Tiles do mapa |

### Modelos

- **SSD MobileNet V3 Large COCO** (`frozen_inference_graph.pb`) — Detector OpenCV DNN local
- **YOLOv8** (`best (1).pt`) — Peso do detector YOLOv8

> ⚠️ `requirements.txt` contém apenas as 9 dependências reais do projeto backend. Instale-as com `pip install -r requirements.txt`. As dependências embargadas estão em `RaspberryPi/config/requirements.txt`.

---

## ⚙️ Configuração

O arquivo `RaspberryPi/config/raspberrypi_config.json` é a configuração operacional da estação. Variáveis de ambiente e detalhes estão na seção [Componente Embarcado](#-componente-embarcado--raspberry-pi).

### Variável de ambiente

| Variável | Obrigatória | Uso |
|----------|------------|-----|
| `AQUADETECTOR_API_URL` | Não | Sobrescreve `backend.base_url` no cliente embarcado |

Não há `.env`, senhas, tokens ou chaves de API configurados no código. Não foram identificadas credenciais hardcoded.

---

## 📝 Notas Importantes

1. **`requirements.txt` contém apenas as 9 dependências reais do projeto backend**: fastapi, uvicorn, pydantic, opencv-python, supervision==0.27.0, lap==0.5.12, cython-bbox==0.1.5, numpy==1.26.4, pymongo, requests. Instale-as com `pip install -r requirements.txt`.

2. **`RaspberryPi/config/requirements.txt`** contém as dependências do componente embarcado: ultralytics≥8.0.0, opencv-python≥4.8.0, requests≥2.31.0, pyserial≥3.5.

3. **MongoClient precisa de `serverSelectionTimeoutMS=5000`** para não travar se MongoDB estiver indisponível. O código atual NÃO tem esse timeout (pode causar hang no startup).

4. **Dois venvs:** `.venv` (FastAPI pipeline + detecção) e `ultralytics-env` (YOLOv8/treino). O pipeline de detecção (`object-ident.py`) roda no `.venv` com OpenCVDnnDetector (SSD MobileNet). O `ultralytics-env` é apenas para YOLOv8/treino. O `.venv` também contém tudo para o sistema embarcado.

5. **`object-ident.py` usa OpenCVDnnDetector (SSD MobileNet)**, não YOLOv8 `best.pt`. O `best.pt` existe no projeto mas não é usado pelo código atual do pipeline legado.

6. **O contrato ativo do sistema embarcado usa `POST /api/detections` e `GET /api/stations/{id}/detections`**, não os endpoints `bottle-count`/`bottle-events`.

7. **GeoJSON usa `[longitude, latitude]`** — ordem inversa do padrão GPS.

8. **GET /api/stations retorna `detections` e `detection_summary`** (do contrato ativo), além de `bottle_count` para backward compatibility. `detections` espelha `bottle_count.count`.

9. **`create_station` aceita `dict`**, não Pydantic model. Faz insert_one diretamente SEM verificar duplicidade — station_ids duplicados causarão erro do MongoDB.

10. **`BottleCountPayload` não tem `session_id`** — POST é fire-and-forget.

11. **`LineCounter` não tem `save_state()`/`load_state()`** — estado não persistido em MongoDB.

12. **`event_id` com índice único** em `bottle_events_collection` → DuplicateKeyError retorna HTTP 409 (idempotência).

13. **Testes usam `unittest`** (não pytest). Com Mock para collections MongoDB.

14. **Cuidado com:** `db.dropDatabase()`, `db.collection.drop()`, `deleteMany({})`.

15. **Não exponha MongoDB** à rede sem autenticação e firewall adequado.

16. **Objetos `ObjectId` do MongoDB** não são JSON-serializáveis. Converta para string antes de retornar: `result["_id"] = str(result["_id"])`.

17. O heatmap usa intensidade logarítmica (`Math.log1p`) e raio adaptativo por zoom.

18. Os filtros de localidade são hierárquicos e cascatais (estado → cidade → distrito).

19. A estética do dashboard é monocromática ("BIOS antiga").

20. O repositório não contém unit files `systemd`, serviços Windows, Docker Compose, supervisores de processo ou scripts de reinicialização. A execução atual é manual. Após reinício do computador/Pi ou queda de energia, os processos não voltam automaticamente. **TODO:** definir estratégia de inicialização automática.

21. O SSD COCO disponível reconhece `bottle`; as demais categorias (`can`, `carton`, `paper`, `plastic`) exigem modelo/rótulos adequados ou YOLOv8.

22. O cliente embarcado lança exceção em falha HTTP; não há fila offline, retry ou backoff.

---

## ⚠️ Limitações e Segurança

### Limitações conhecidas

- O rastreamento é uma associação gulosa por centróide, não um rastreador de múltiplos objetos sofisticado
- Cada objeto é contado no máximo uma vez enquanto mantém o mesmo rastreio local
- O SSD COCO disponível reconhece `bottle`; as demais categorias exigem modelo/rótulos adequados
- O cliente embarcado lança exceção em falha HTTP; não há fila offline, retry ou backoff
- CORS do backend aceita qualquer origem; simplifica o desenvolvimento, mas não é política restritiva de produção
- Dashboard e endpoints JS usam `127.0.0.1:8000` fixo
- O documento local `station/station.json` não é sincronizado automaticamente ao MongoDB pelo código atual
- `station.json` pode ter `_id` no formato MongoDB Extended JSON (`{"$oid": "..."}`) que o backend pode rejeitar

### Segurança

- Não há autenticação, autorização ou TLS configurados para a API
- Não exponha a porta 8000 publicamente sem uma camada de segurança adequada
- Não adicione credenciais, pesos proprietários ou dados sensíveis ao Git
- Os padrões de `.gitignore` cobrem arquivos `.env`, mas o projeto não fornece uma implementação de carregamento de `.env`

### Contribuição

Não há política de contribuição, convenção de commits, pull request ou licença definida no repositório. Antes de enviar alterações, execute os testes disponíveis e valide a integração manualmente.

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