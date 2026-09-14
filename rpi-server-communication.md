==============================================================================
AQUA MONITOR — COMUNICACAO RASPBERRY PI ↔ SERVIDOR
Guia de integracao para planejamento de comunicacao
==============================================================================
Data: Setembro 2026
Objetivo: Documentar como a Raspberry Pi (camera/deteccao) conversa com o
          computador-servidor (FastAPI + MongoDB + Dashboard) para que outra
          IA possa planejar ou replanejar a comunicacao entre as duas maquinas.

==============================================================================
1. VISAO GERAL DA ARQUITETURA
==============================================================================

ROLE DO SERVIDOR (computador com MongoDB + FastAPI):
  - Recebe dados de contagem de garrafas
  - Armazena estações, métricas e eventos no MongoDB
  - Serve a API REST para o dashboard Leaflet
  - Responde queries de estações com seus últimos bottle_counts

ROLE DA RASPBERRY PI (plataforma embarcada com câmera):
  - Executa o pipeline de detecção: OpenCVDnnDetector → ByteTrack → LineCounter
  - Envia agregados de contagem via HTTP POST para o servidor
  - Recebe apenas: endereço do servidor, station_id, e se publicação está habilitada
  - NÃO precisa conectar ao MongoDB diretamente
  - NÃO precisa ter FastAPI instalado

DIRECAO DA COMUNICACAO:
  Raspberry Pi ──(HTTP POST)──▶ Servidor :8000 ──(GET)──▶ Dashboard

  A comunicação é UNIDIRECIONAL da Pi para o Servidor (dados de contagem).
  O Dashboard consome do Servidor via GET.
  A Pi NÃO recebe comandos do Dashboard (ainda).

==============================================================================
2. FLUXO DETALHADO DE COMUNICACAO
==============================================================================

2.1 CONFIGURACAO INICIAL
─────────────────────────

Na Raspberry Pi, os parâmetros de conexão vêm de environment variables:

  BOTTLE_COUNT_API_URL        → URL do servidor FastAPI
                              Default: http://127.0.0.1:8000
                              Na RPi: http://<IP_DO_SERVIDOR>:8000

  BOTTLE_COUNT_STATION_ID     → ID numérico da estação na Pi
                              Default: 1
                              Deve ser único por estação física

  BOTTLE_COUNT_PUBLISH_INTERVAL → Intervalo entre POSTs (segundos)
                              Default: 5
                              Em segundos

  BOTTLE_COUNT_API_ENABLED    → "1" para habilitar envio, "0" para desabilitar
                              Default: "0" (desabilitado por padrão!)

Estas variáveis são lidas em:
  backend/detection/config.py → ApiConfig dataclass

Na prática, na Raspberry Pi, o comando seria:

  export BOTTLE_COUNT_API_URL="http://192.168.1.100:8000"  # IP do servidor
  export BOTTLE_COUNT_STATION_ID="1"
  export BOTTLE_COUNT_PUBLISH_INTERVAL="5"
  export BOTTLE_COUNT_API_ENABLED="1"
  .venv/bin/python backend/detection/object-ident.py --publish

Alternativamente, pode-se construir o ApiConfig direto no código:

  api_config = ApiConfig(
      base_url="http://192.168.1.100:8000",
      station_id=1,
      publish_interval_seconds=5,
      enabled=True,   # equivalente a --publish
  )

2.2 PIPELINE DE DETECCAO (roda na Raspberry Pi)
───────────────────────────────────────────────

  ┌────────────┐
  │ Câmera RPi │──▶ frame de vídeo (640×480)
  └─────┬──────┘
        │
        ▼
  ┌────────────┐    detect() a cada 0.25s
  │ OpenCV DNN │──▶ lista[Detection] com xyxy, confidence, class_id
  │ (SSD       │    Filtro: apenas class_name == "bottle"
  │ MobileNet) │
  └─────┬──────┘
        │
        ▼
  ┌────────────┐    update() com lista de Detections
  │ ByteTrack  │──▶ lista[TrackedObject] com track_id estável
  │ (supervision│    Cada track tem xyxy, track_id, class_name
  │  ByteTrack)│
  └─────┬──────┘
        │
        ▼
  ┌────────────┐    update() com TrackedObject[]
  │ LineCounter│───▶ lista[CrossingEvent] se cruzaram a linha
  │            │    self.count acumula o total
  │            │    self.count_by_direction = {"positive": N, "negative": M}
  └─────┬──────┘
        │
        ▼
  ┌──────────────────────┐
  │ DetectionPipeline    │──▶ process(detections) é chamado a cada frame
  │                      │    Chama: tracker.update(), counter.update(),
  │                      │    E self.publish_if_due() (a cada 5s se habilitado)
  │                      │
  │ publish_if_due()     │──▶ BottleCountApiClient.publish(count, directions)
  │                      │    Se habilitado E intervalo atingido:
  │                      │    → HTTP POST para {base_url}/api/stations/{station_id}/bottle-count
  └──────────────────────┘

2.3 ENVIO HTTP POST (RPi → Servidor)
─────────────────────────────────────

Endpoint: POST http://<SERVIDOR>:8000/api/stations/{station_id}/bottle-count
Content-Type: application/json

Payload:
{
    "count": <int>,              // total de garrafas contadas desde o último POST (ou acumulado?)
    "count_by_direction": {
        "positive": <int>,       // cruzaram da direita para a esquerda
        "negative": <int>        // cruzaram da esquerda para a direita
    }
}

Exemplo real:
{
    "count": 5,
    "count_by_direction": {"positive": 3, "negative": 2}
}

Resposta esperada (sucesso):
{
    "message": "Bottle count ingested successfully",
    "id": "<ObjectId>",
    "station_id": 1,
    "count": 5
}

Observacoes importantes:
  - Timeout de 3 segundos na requisicao HTTP (requests.post timeout=3)
  - Se o servidor nao responder ou der erro, a Pi LOGA um warning e continua
  - publish_if_due avança o schedule mesmo após erro (evita storm de retries)
  - Retorna bool: True se publicou com sucesso, False se falhou
  - Nenhum retry automático — apenas avança o relógio

2.4 O QUE ACONTECE NO SERVIDOR AO RECEBER O POST
──────────────────────────────────────────────────

O endpoint POST /api/stations/{station_id}/bottle-count:

  1. Verifica se a estação existe no MongoDB (stations_collection.find_one)
     → Se NÃO existe: HTTP 404 "Station not found"
     → Se existe: continua

  2. Cria documento:
     {
         "station_id": <int>,
         "count": <int>,
         "count_by_direction": {"positive": <int>, "negative": <int>},
         "timestamp": <datetime com UTC>
     }

  3. Insere no bottle_metrics_collection

  4. Retorna confirmação com inserted_id como string

IMPORTANTE: O servidor NÃO valida se count >= 0 ou se directions fazem sentido.
            Pydantic apenas garante que count é int e count_by_direction é dict[str,int].

2.5 LEITURA PELO DASHBOARD (Servidor → Browser)
────────────────────────────────────────────────

O dashboard faz polling a cada 3 segundos:

  1. GET /api/stations
     → Retorna TODAS as estações com seu último bottle_count (via MongoDB aggregation)
     → Campo "detections" = bottle_count.count (backward compatibility)
     → Se sem métrica: count=0, positive=0, negative=0, timestamp=null

  2. GET /api/stations/{station_id}/bottle-count
     → Retorna o ÚLTIMO bottle_count daquela estação específica
     → Se não existe: count=0 com zeros e timestamp=null

  O dashboard atualiza:
     - sidebar com contagem total e setas positive/negative
     - heatmap com intensidade logarítmica baseada na contagem
     - marcadores no mapa com popups contando detecções

2.6 EVENTOS INDIVIDUAIS (OPCIONAL — não está sendo usado pela Pi)
────────────────────────────────────────────────────────────────

A Pi NÃO envia eventos individuais de cruzamento. Ela envia apenas agregados.

Se fosse implementado, o fluxo seria:
  Endpoint: POST /api/stations/{station_id}/bottle-events
  Payload: { "event_id": "uuid", "direction": "positive", "timestamp": "2026-09-12T12:00:00Z" }
  Idempotência: event_id com índice único → DuplicateKeyError = HTTP 409

Para enviar eventos individuais, a Pi precisaria:
  1. Gerar event_id único (formato: "{station_id}-track-{track_id}-{iso_timestamp}")
  2. Saber a direção do cruzamento (LineCounter já produz CrossingEvent)
  3. Fazer POST individual para cada cruzamento

Mas o código ATUAL da Pi não faz isso — só envia agregados a cada 5s.

==============================================================================
3. RESUMO DAS ROTAS E SEUS PAPEIS NA COMUNICACAO
==============================================================================

┌───────────────────────────────────────────────────────────────────────────┐
│ ROTA                        │ MÉTODO │ REMETENTE    │ DESTINO    │ AÇÃO  │
├─────────────────────────────┼────────┼──────────────┼────────────┼───────┤
│ /api/stations               │ POST   │ RPi ou UI    │ Servidor   │ Criar │
│ /api/stations               │ GET    │ Dashboard    │ Servidor   │ Listar│
│ /api/stations/{id}          │ DELETE │ Dashboard    │ Servidor   │ Deletar│
│ /api/stations/{id}/bottle-count │ POST │ RPi          │ Servidor   │ Receber│
│ /api/stations/{id}/bottle-count │ GET  │ Dashboard    │ Servidor   │ Ler    │
│ /api/stations/{id}/bottle-events    │ POST │ N/A (não     │ Servidor   │ Receber│
│                                        │ usado pela Pi)│            │       │
└───────────────────────────────────────────────────────────────────────────┘

Fluxo RPi → Servidor (ativo):
  1. RPi executa object-ident.py com --publish (ou BOTTLE_COUNT_API_ENABLED=1)
  2. Pipeline detecta garrafas, conta cruzamentos
  3. A cada 5 segundos (publish_interval), BottleCountApiClient faz POST
  4. Servidor recebe, valida, salva no MongoDB
  5. Servidor retorna {message, id, station_id, count}
  6. RPi ignora a resposta (não faz nada com ela)

Fluxo Servidor → Dashboard (via polling):
  1. Dashboard carrega, faz GET /api/stations
  2. Renderiza mapa, heatmap, marcadores
  3. A cada 3 segundos faz GET /api/stations/{id}/bottle-count
  4. Atualiza sidebar, heatmap, marcadores

==============================================================================
4. CONFIGURACAO PRATICA PARA RPi ↔ SERVIDOR
==============================================================================

4.1 NA RASPBERRY PI
───────────────────────────────────────────

A Pi precisa ter instalado:
  - Python 3.12+
  - .venv com opencv-python, supervision==0.27.0, lap==0.5.12, cython-bbox==0.1.5, numpy==1.26.4, requests
  - Modelos: coco.names, frozen_inference_graph.pb, ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt

O que a Pi NÃO precisa ter:
  - ❌ FastAPI / uvicorn / pydantic / pymongo
  - ❌ MongoDB
  - ❌ Node.js / Leaflet / dashboard
  - ❌ YOLOv8 / best.pt (o pipeline usa SSD MobileNet via OpenCV DNN)

O comando de execução na Pi é com .venv, NÃO ultralytics-env:
  .venv/bin/python backend/detection/object-ident.py --publish

Variáveis de ambiente obrigatórias (exportar antes de rodar):
  export BOTTLE_COUNT_API_URL="http://<IP_SERVIDOR>:8000"
  export BOTTLE_COUNT_STATION_ID="1"
  export BOTTLE_COUNT_PUBLISH_INTERVAL="5"
  export BOTTLE_COUNT_API_ENABLED="1"

Comando de execução na Pi:
  .venv/bin/python backend/detection/object-ident.py --publish
  (ou sem --publish, mas com BOTTLE_COUNT_API_ENABLED=1)

4.2 NO SERVIDOR
───────────────────────────────────────────

O que o servidor precisa ter instalado:
  - MongoDB 6+ rodando e acessível à Pi pela rede
  - FastAPI backend rodando em :8000
  - (Opcional) Dashboard servindo em :3000

Variáveis de ambiente: NENHUMA necessária (tudo usa defaults de localhost)

4.3 REDE
───────────────────────────────────────────

A Pi precisa alcançar o servidor na porta 8000:
  - Na mesma rede Wi-Fi/LAN: usar IP local do servidor (ex: 192.168.1.100)
  - Ping para verificar conectividade antes de iniciar
  - Se o servidor usar firewall, liberar porta 8000

O servidor precisa de MongoDB acessível (localhost, não precisa expor para rede):
  - A Pi conversa com o Servidor (FastAPI) — não com o MongoDB diretamente
  - O Servidor conversa com o MongoDB localmente

CUIDADO: MongoClient em app.py NÃO tem serverSelectionTimeoutMS — pode causar hang
se o MongoDB estiver indisponível.

==============================================================================
5. PONTOS DE FALHA E CONTINGÊNCIAS
==============================================================================

5.1 SERVIDOR FORA DO AR
─────────────────────────
  - A Pi tenta POST → timeout de 3s → LOG warning → continua detectando
  - publish_if_due avança o schedule (não tenta de novo imediatamente)
  - Dados de contagem SÃO PERDIDOS (não há fila local de retry)
  - A Pi continua rodando o pipeline normalmente (detecção e contagem)
  - Quando o servidor voltar, a Pi volta a enviar normalmente (apenas dados novos)

Mitigação possível:
  - Implementar fila local de requisições não enviadas na Pi
  - Usar um arquivo de queue (.json ou .sqlite) para persistir counts não enviados
  - Na inicialização, verificar se há counts pendentes e enviar antes do ciclo normal

5.2 REDE INTERROMPIDA
──────────────────────
  - Mesmo comportamento: timeout 3s, warning log, continua
  - Sem retry automático
  - Sem backoff exponencial

5.3 ESTAÇÃO NÃO EXISTE NO SERVIDOR
───────────────────────────────────
  - POST /api/stations/{id}/bottle-count → HTTP 404 "Station not found"
  - A Pi não recebe 404 diretamente — recebe bool False do publish_if_due
  - O BottleCountApiClient NÃO levanta exceção para HTTP 4xx — só retorna False
  - Nenhum log específico de "station not found" na Pi (apenas o warning genérico)

5.4 DADOS EM CONFLITO
─────────────────────
  - Se a estação não tiver station_id cadastrado no MongoDB, o POST é rejeitado
  - É responsabilidade da Pi ter a estação cadastrada ANTES de começar a detectar
  - O cadastro pode ser feito via dashboard (POST /api/stations) ou diretamente no MongoDB

==============================================================================
6. FORMATOS DE DADOS PARA COMUNICACAO
==============================================================================

6.1 ENVIO (RPi → Servidor)
───────────────────────────

POST /api/stations/{station_id}/bottle-count
Headers: Content-Type: application/json
Body:
{
    "count": <int>,
    "count_by_direction": {
        "positive": <int>,
        "negative": <int>
    }
}

Restrições Pydantic:
  - count: obrigatório, inteiro (não valida >= 0)和平
  - count_by_direction: obrigatório, dict[str, int]
  - Nenhum campo de session_id ou metadados de detecção é enviado

6.2 RESPOSTA (Servidor → RPi)
─────────────────────────────

Sucesso (200):
{
    "message": "Bottle count ingested successfully",
    "id": "<ObjectId string>",
    "station_id": <int>,
    "count": <int>
}

Erro (404):
{
    "detail": "Station not found"
}

A Pi ignora a resposta — não faz nada com ela.

6.3 QUERY DO DASHBOARD (Servidor → Dashboard)
───────────────────────────────────────────────

GET /api/stations → [
    {
        "station_id": <int>,
        "location": {"type": "Point", "coordinates": [lon, lat]},
        "administrative": {"country": "Brazil", "state": "Sao Paulo", ...},
        "detections": <int>,        // = bottle_count.count
        "bottle_count": {
            "count": <int>,
            "positive": <int>,
            "negative": <int>,
            "timestamp": <ISO string ou null>
        }
    },
    ...
]

GET /api/stations/{id}/bottle-count →
{
    "station_id": <int>,
    "count": <int>,
    "count_by_direction": {"positive": <int>, "negative": <int>},
    "timestamp": <ISO string ou null>
}

==============================================================================
7. RESUMO EXECUTIVO PARA COMUNICACAO RPI-SERVIDOR
==============================================================================

A comunicação é SIMPLES e UNIDIRECIONAL:

  RPi envia ──HTTP POST──▶ Servidor :8000 :8000
  │                        │
  │ Payload: {count,       │ Salva no MongoDB
  │   count_by_direction}  │ Retorna {message, id}
  │                        │
  │ A cada 5s (config)     │
  │ Timeout: 3s            │
  │ Retry: nenhum          │
  │ Se erro: continua      │
  └────────────────────────┘

Configuração mínima para conectar a RPi ao servidor:
  1. Definir BOTTLE_COUNT_API_URL para o IP do servidor
  2. Definir BOTTLE_COUNT_STATION_ID (único por RPi)
  3. Definir BOTTLE_COUNT_API_ENABLED=1 (ou usar --publish)
  4. Garantir que a estação está cadastrada no servidor ANTES de começar
  5. Garantir conectividade de rede entre RPi e servidor (porta 8000 aberta)

Sem mais configuração. O resto é automático.

======================================================================================================================================================================
