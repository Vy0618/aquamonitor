# Aqua Monitor — sistema embarcado Raspberry Pi

Este documento descreve o componente embarcado do Aqua Monitor e sua integração com o backend FastAPI, MongoDB e dashboard web do repositório. É a referência para instalar, configurar, executar e testar uma estação de monitoramento em um computador ou Raspberry Pi.

> Escopo: esta documentação é fiel ao código atual. O diretório raiz contém documentação histórica que menciona endpoints de contagem de garrafas; o contrato ativo é o descrito aqui, baseado em eventos gerais de detecção em `POST /api/detections`.

## Índice

1. [Visão geral](#visão-geral)
2. [Arquitetura e fluxo](#arquitetura-e-fluxo)
3. [Estrutura e mapa do código](#estrutura-e-mapa-do-código)
4. [Requisitos](#requisitos)
5. [Instalação do zero](#instalação-do-zero)
6. [Configuração](#configuração)
7. [Banco de dados e API](#banco-de-dados-e-api)
8. [Como executar](#como-executar)
9. [Testes](#testes)
10. [Operação contínua, logs e troubleshooting](#operação-contínua-logs-e-troubleshooting)
11. [Reprodução em outro dispositivo](#reprodução-em-outro-dispositivo)
12. [Limitações, segurança e contribuição](#limitações-segurança-e-contribuição)

## Visão geral

O Aqua Monitor registra resíduos vistos por uma câmera. A estação embarcada captura frames, executa um detector YOLO ou SSD MobileNet, rastreia centróides entre frames e contabiliza um objeto somente quando ele cruza uma linha horizontal configurada. Para cada cruzamento, envia ao backend um evento com categoria, confiança, identificador do rastreamento e data/hora.

As classes configuradas são:

`bottle`, `can`, `carton`, `paper` e `plastic`.

O backend armazena os eventos no MongoDB e o dashboard consulta um resumo por estação. O mapa apresenta um ícone para cada estação; ao clicar nele, exibe total, categorias e a última detecção.

Tecnologias efetivamente usadas:

| Camada | Tecnologias |
| --- | --- |
| Estação | Python, OpenCV, Ultralytics/YOLO ou OpenCV DNN/SSD MobileNet, Requests |
| Rastreamento | Algoritmo local de associação gulosa por centróide |
| GPS opcional | NEO-6M via UART, PySerial e NMEA RMC/GGA |
| API | FastAPI, Pydantic e PyMongo |
| Dados | MongoDB, coleções `stations` e `detection_events` |
| Dashboard | HTML/CSS/ES Modules, Leaflet, leaflet.heat e OpenStreetMap |

## Arquitetura e fluxo

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
    API -->|GET /api/stations\nGET /api/stations/{id}/detections| Dashboard[Dashboard :3000]
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

No modo SSD, a última posição GPS disponível e o estado online/offline também atualizam apenas o documento local `station/station.json`. Esse arquivo **não é sincronizado automaticamente** ao MongoDB pelo código atual.

## Estrutura e mapa do código

```text
aquamonitor/
├── backend/
│   ├── app.py                         # API FastAPI e acesso ao MongoDB
│   ├── test_detection_events.py       # testes unitários da API/resumos
│   ├── test_mongodb.py                # imprime documentos da coleção stations
│   └── detection/                     # pipeline local legado de visão computacional
├── dashboard/
│   ├── index.html                     # mapa e painel de detecções
│   ├── crud.html                      # cadastro/remoção manual de estações
│   ├── style.css                      # estilo e ícone de estação
│   └── js/                            # módulos do dashboard
├── RaspberryPi/
│   ├── camera/webcam_config.py        # abertura e parâmetros da câmera
│   ├── communication/backend_client.py# cliente HTTP da estação
│   ├── config/
│   │   ├── raspberrypi_config.json    # configuração da estação
│   │   └── requirements.txt           # dependências embarcadas
│   ├── data/contagem_residuos.json    # estado local da contagem
│   ├── detection/                     # adaptadores YOLO e SSD MobileNet
│   ├── gps/gps_neo6m.py               # leitura assíncrona NMEA
│   ├── models/                        # pesos e rótulos dos detectores
│   ├── monitoring/                    # pontos de entrada dos monitores
│   ├── station/                       # documento local e atualização GPS
│   ├── tracking/line_tracker.py       # rastreamento e cruzamento de linha
│   ├── TESTE_LOCAL.md                 # roteiro rápido de integração local
│   └── README.md                      # este documento
├── requirements.txt                   # dependências backend/pipeline legado
└── stations.json                      # dados de estações para importação MongoDB
```

### Arquivos relevantes da estação

| Arquivo | Responsabilidade |
| --- | --- |
| `monitoring/monitor_residuos.py` | Ponto de entrada YOLO; captura, detecta, rastreia, persiste e envia eventos. |
| `monitoring/monitor_ssd_mobilenet.py` | Alternativa SSD; também mantém documento local e GPS. |
| `detection/yolo_detector.py` | Carrega `best (1).pt` via Ultralytics e filtra as cinco classes esperadas. |
| `detection/ssd_mobilenet_detector.py` | Carrega rede TensorFlow `.pb/.pbtxt` com OpenCV DNN. |
| `tracking/line_tracker.py` | Associa centróides e emite um `Crossing` por objeto. |
| `communication/backend_client.py` | Valida a estação com `GET /api/stations` e publica eventos HTTP. |
| `camera/webcam_config.py` | Abre `cv2.VideoCapture` e solicita resolução/FPS. |
| `gps/gps_neo6m.py` | Thread daemon que lê RMC/GGA válidos de GPS NEO-6M. |
| `station/station_document.py` | Lê, valida e grava o documento local da estação com substituição atômica. |
| `station/update_station_location.py` | Utilitário de execução única que aguarda um fix GPS e atualiza `station.json`. |
| `config/raspberrypi_config.json` | Fonte central de IDs, rede, câmera, GPS e detectores. |

## Requisitos

### Software

- Python: versão mínima **não declarada** pelo projeto. Para executar o sistema completo, use Python 3.11 ou superior: o backend importa `datetime.UTC`, disponível a partir dessa versão.
- MongoDB em execução, acessível pelo backend em `mongodb://localhost:27017/`.
- Dependências da estação: `ultralytics`, `opencv-python`, `requests` e `pyserial`.
- Dependências do backend: consulte `requirements.txt` na raiz.
- Para servir o dashboard, basta Python; Node.js não é exigido pelo repositório.
- Acesso à internet é necessário para os recursos remotos carregados pelo dashboard: Leaflet, leaflet.heat e tiles OpenStreetMap.

### Hardware

| Componente | Obrigatório | Uso |
| --- | --- | --- |
| Computador ou Raspberry Pi | Sim | Executa o monitor. |
| Câmera USB ou câmera disponível ao OpenCV | Sim para monitor real | Fonte dos frames. |
| NEO-6M conectado à UART | Opcional | Localização no modo SSD. |
| Rede para o backend | Sim, salvo teste sem publicação | Publicação de eventos. |
| Modelo `best (1).pt` | Sim para YOLO | Peso do detector YOLO. |
| `frozen_inference_graph.pb`, `.pbtxt`, `coco.names` | Sim para SSD | Modelo, configuração e rótulos SSD. |

## Instalação do zero

Os comandos abaixo devem ser executados na raiz do repositório.

### Windows / teste local

```powershell
git clone <URL_DO_REPOSITORIO>
Set-Location aquamonitor
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r RaspberryPi\config\requirements.txt
```

Verifique os arquivos de modelo:

```powershell
Test-Path 'RaspberryPi\models\best (1).pt'
Test-Path 'RaspberryPi\models\frozen_inference_graph.pb'
Test-Path 'RaspberryPi\models\ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'
Test-Path 'RaspberryPi\models\coco.names'
```

### Raspberry Pi / Linux

```bash
git clone <URL_DO_REPOSITORIO>
cd aquamonitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r RaspberryPi/config/requirements.txt
```

O repositório não contém instruções de instalação do sistema operacional, drivers de câmera ou habilitação da UART. Esses passos são **A confirmar** conforme o modelo da Raspberry Pi e a distribuição instalada.

### Banco e estações

Inicie o MongoDB conforme a instalação local. Exemplo de importação, se o utilitário `mongoimport` estiver instalado:

```powershell
mongoimport --db aquamonitor --collection stations --file stations.json --jsonArray
```

O comando pode inserir duplicatas se executado repetidamente; o repositório não fornece script de limpeza ou migração. Confirme antes de reimportar.

## Configuração

O arquivo `RaspberryPi/config/raspberrypi_config.json` é a configuração operacional da estação.

| Campo | Valor atual | Efeito |
| --- | --- | --- |
| `station_id` | `1` | Deve existir na coleção `stations` antes de iniciar o monitor. |
| `backend.base_url` | `http://127.0.0.1:8000` | URL do FastAPI. Em uma Pi física, troque pelo IP/hostname do servidor. |
| `backend.detections_path` | `/api/detections` | Endpoint de ingestão. |
| `backend.timeout_seconds` | `5` | Timeout de GET/POST do cliente embarcado. |
| `backend.require_connection_on_startup` | `true` | Impede o início se a estação não for encontrada no backend. |
| `camera.device_index` | `0` | Índice da câmera OpenCV. |
| `camera.width/height/fps` | `1280/720/30` | Valores solicitados ao driver. |
| `gps.enabled` | `true` | O modo SSD tentará abrir `/dev/serial0`. |
| `detection.confidence_threshold` | `0.45` | Limiar YOLO. |
| `ssd_mobilenet.confidence_threshold` | `0.45` | Limiar SSD. |

### Variável de ambiente

| Variável | Obrigatória | Uso |
| --- | --- | --- |
| `AQUADETECTOR_API_URL` | Não | Sobrescreve `backend.base_url` no cliente embarcado. Exemplo: `http://192.168.1.50:8000`. |

Não há `.env`, senhas, tokens ou chaves de API configurados no código. Não foram identificadas credenciais hardcoded.

### GPS e rede

- Em teste local Windows, mantenha `gps.enabled: false` para executar o modo SSD sem uma UART NEO-6M. Restaure o valor conforme a estação física.
- `127.0.0.1` significa a própria máquina. Em uma Raspberry Pi conectada a um backend separado, defina o IP/hostname do servidor no JSON ou em `AQUADETECTOR_API_URL`.
- GeoJSON usa estritamente `[longitude, latitude]`.

## Banco de dados e API

O backend usa MongoDB local, banco `aquamonitor`.

| Coleção | Origem | Campos relevantes |
| --- | --- | --- |
| `stations` | `stations.json` ou `POST /api/stations` | `station_id`, `location`, `administrative`. |
| `detection_events` | `POST /api/detections` | `event_id`, `station_id`, `detection_type`, `confidence`, `track_id`, `detected_at`. |

Na inicialização, o backend cria índice único em `event_id` e índice por `station_id, detected_at`. Eventos novos são armazenados com `detected_at` como `datetime` BSON. A leitura também normaliza dados legados armazenados como string ISO 8601.

### Rotas ativas

| Método | Rota | Resultado |
| --- | --- | --- |
| `POST` | `/api/stations` | Cria estação; exige `station_id` inteiro positivo e único. |
| `GET` | `/api/stations` | Lista estações com `detections` e `detection_summary`. |
| `DELETE` | `/api/stations/{station_id}` | Remove uma estação. |
| `POST` | `/api/detections` | Recebe evento da estação; retorna 201 ou 409 em UUID repetido. |
| `GET` | `/api/stations/{station_id}/detections` | Retorna `total`, `by_type` e `timestamp` ISO 8601. |

Exemplo de evento compatível:

```json
{
  "event_id": "7f8a9b10-1111-2222-3333-444444444444",
  "station_id": 1,
  "detection_type": "can",
  "confidence": 0.92,
  "track_id": 7,
  "detected_at": "2026-09-18T12:00:00+00:00"
}
```

## Como executar

### Ordem recomendada

1. Inicie MongoDB.
2. Inicie o backend.
3. Confirme/cadastre a estação.
4. Inicie o dashboard.
5. Inicie um monitor YOLO ou SSD.

### Backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

Em Linux:

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

Verificação:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/stations
```

### Dashboard

```powershell
Set-Location dashboard
..\.venv\Scripts\python.exe -m http.server 3000
```

Abra `http://127.0.0.1:3000`. O dashboard chama o backend em `http://127.0.0.1:8000`; portanto, pela configuração atual, navegador e backend precisam estar na mesma máquina.

### Monitor YOLO

```powershell
Set-Location C:\caminho\para\aquamonitor
.\.venv\Scripts\python.exe -m RaspberryPi.monitoring.monitor_residuos
```

O terminal deve mostrar `Backend conectado; estação 1 validada.` e depois `Monitor iniciado`. Pressione `Q` ou `Esc` para encerrar.

### Monitor SSD MobileNet

Com GPS físico:

```powershell
.\.venv\Scripts\python.exe -m RaspberryPi.monitoring.monitor_ssd_mobilenet
```

Em um computador comum, defina temporariamente `gps.enabled` como `false` no JSON antes do comando anterior. O processo deve mostrar `Monitor SSD MobileNet iniciado`.

### Atualização única de localização

```powershell
.\.venv\Scripts\python.exe -m RaspberryPi.station.update_station_location
```

Requer GPS habilitado, PySerial e um fix NMEA válido. Não abre câmera nem publica no backend.

## Testes

### Testes unitários existentes

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_detection_events -v
```

Os testes cobrem ingestão de tipos gerais, estação inexistente, duplicação de `event_id`, agregação, localização e normalização de datas legadas. Não há testes automatizados específicos para câmera, YOLO, SSD, GPS ou JavaScript.

### Teste de integração HTTP

```powershell
$body = @{
  event_id = [guid]::NewGuid().ToString()
  station_id = 1
  detection_type = 'can'
  confidence = 0.92
  track_id = 1
  detected_at = [DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json

Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/detections -ContentType 'application/json' -Body $body
Invoke-RestMethod http://127.0.0.1:8000/api/stations/1/detections
```

Critérios de sucesso:

- o POST retorna `Detection ingested successfully`;
- o GET retorna `total` maior que zero e `by_type.can`;
- o mapa, após no máximo 3 segundos, mostra a nova contagem ao selecionar a estação 1.

### Teste ponta a ponta

1. Inicie MongoDB, backend e dashboard.
2. Verifique `GET /api/stations`.
3. Rode o monitor com a câmera.
4. Faça um objeto de classe reconhecida cruzar a linha amarela.
5. Observe `Enviado: <classe> (track #<id>)` no terminal.
6. Consulte `GET /api/stations/1/detections`.
7. Clique no ícone `S1` no mapa e confirme total/categorias/horário.

Consulte também [TESTE_LOCAL.md](TESTE_LOCAL.md) para o roteiro reduzido.

## Operação contínua, logs e troubleshooting

### Estado atual de execução contínua

O repositório não contém unit files `systemd`, serviços Windows, Docker Compose, supervisores de processo ou scripts de reinicialização. A execução atual é manual. Após reinício do computador/Pi ou queda de energia, os processos não voltam automaticamente.

**TODO / A confirmar:** definir a estratégia de inicialização automática adequada ao sistema operacional antes de uma implantação contínua.

### Logs observáveis

| Componente | Evidência de funcionamento |
| --- | --- |
| Backend/Uvicorn | startup do servidor e requisições HTTP. |
| Monitor YOLO | `Backend conectado...`, `Monitor iniciado...`, `Enviado: ...`. |
| Monitor SSD | `Monitor SSD MobileNet iniciado...`; falhas GPS ficam em `Neo6mGps.last_error`, sem log automático. |
| Dashboard | erros de API aparecem no console do navegador; painel mostra `polling error`. |

| Problema | Como verificar | Ação compatível com o projeto |
| --- | --- | --- |
| Monitor para antes de abrir | Confira URL, backend e se a estação existe. | Ajuste `base_url`/variável e cadastre a estação. |
| HTTP 404 ao enviar evento | `station_id` não está em `stations`. | Importe `stations.json` ou crie a estação via API/dashboard. |
| HTTP 409 | `event_id` repetido. | Gere um novo UUID; os monitores já usam `uuid.uuid4()`. |
| Câmera não abre | Erro cita `device_index`. | Confira cabo/permissão e ajuste `camera.device_index`. |
| SSD não inicia | Arquivo de modelo/rótulo ausente ou GPS UART indisponível. | Confira os caminhos; em PC, desabilite GPS. |
| YOLO não inicia | Ultralytics ou peso ausente. | Instale requirements e confirme `models/best (1).pt`. |
| Dashboard sem dados | Console mostra erro ou backend não está em 8000. | Inicie FastAPI e confirme `GET /api/stations`. |
| Ícone não aparece | Estação sem `location.coordinates` válida. | Corrija/cadastre a estação com GeoJSON `[longitude, latitude]`. |
| Sem tiles do mapa | Falha de rede com OpenStreetMap/CDNs. | Restabeleça internet; não há tiles locais no repositório. |

## Reprodução em outro dispositivo

```text
Máquina/Pi nova
  → Python + MongoDB + câmera (+ GPS opcional)
  → clone e ambiente virtual
  → requirements do backend e RaspberryPi
  → modelos em RaspberryPi/models
  → importar/cadastrar stations
  → configurar URL da API, câmera e GPS
  → testar POST/GET
  → iniciar backend, dashboard e monitor
```

Para desenvolvimento em computador, use `127.0.0.1` e desabilite GPS no modo SSD. Para uma Raspberry Pi, troque a URL pelo IP do backend, valide a câmera, habilite/configure UART conforme o sistema operacional e execute o monitor a partir da raiz do repositório.

## Limitações, segurança e contribuição

### Limitações conhecidas

- O rastreamento é uma associação gulosa por centróide, não um rastreador de múltiplos objetos mais sofisticado.
- Cada objeto é contado no máximo uma vez enquanto mantém o mesmo rastreio local.
- O SSD COCO disponível reconhece `bottle`; as demais categorias exigem modelo/rótulos adequados.
- O cliente embarcado lança exceção em falha HTTP; não há fila offline, retry ou backoff.
- CORS do backend aceita qualquer origem; isso simplifica o desenvolvimento, mas não é uma política restritiva de produção.
- Dashboard e endpoints JS usam `127.0.0.1:8000` fixo.

### Segurança

Não há autenticação, autorização ou TLS configurados para a API. Não exponha a porta 8000 publicamente sem uma camada de segurança adequada. Não adicione credenciais, pesos proprietários ou dados sensíveis ao Git. Os padrões de `.gitignore` cobrem arquivos `.env`, mas o projeto não fornece uma implementação de carregamento de `.env`.

### Contribuição

Não há política de contribuição, convenção de commits, pull request ou licença definida no repositório. Antes de enviar alterações, execute os testes disponíveis e valide a integração manualmente. A licença ainda não está definida.

### Autoria

O último commit disponível no Git é atribuído a `Vy0618`. Não há uma definição de equipe ou responsabilidades no repositório.
