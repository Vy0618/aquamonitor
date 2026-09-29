# AquaMonitor

Protótipo para detectar garrafas em uma câmera, contar cruzamentos de uma linha
virtual e enviar os eventos para um computador com API, MongoDB e dashboard.

## Arquitetura

```text
Estação (computador de teste ou Raspberry Pi)
Câmera → SSD MobileNet → ByteTrack → LineCounter → fila em memória
                                                      ↓
                                            thread de envio HTTP
                                                      ↓
Computador:                         FastAPI → MongoDB → dashboard
```

- `backend/detection/object-ident.py`: captura, detector SSD e visualização.
- `backend/detection/detection_pipeline.py`: rastreamento, contagem e agendamento.
- `backend/detection/publisher.py`: envio em segundo plano, sem bloquear a captura.
- `backend/app.py`: API de estações e eventos; usa MongoDB em `localhost:27017`,
  banco `aquamonitor`.
- `dashboard/`: interface estática com mapa e contagem por estação.
- `backend/station_document.py`: ferramenta independente para documento local;
  ainda não participa automaticamente do fluxo de detecção.

Os eventos são enviados para `POST /api/detections`, com UUID, identificação da
estação, classe, confiança, ID de rastreamento e horário. Falhas de rede mantêm
os eventos na memória para nova tentativa. Reiniciar o processo perde pendências.
Não há fila SQLite. A contagem ocorre no cruzamento, não a cada frame detectado.

## Testes locais

### 1. Preparar Python e dependências

Execute os comandos na raiz do repositório. Use Python **3.11 ou 3.12** e uma
câmera USB reconhecida pelo OpenCV. O runner atual exige sessão gráfica.

Em Debian/Ubuntu ou Raspberry Pi OS com esses pacotes disponíveis:

```bash
sudo apt update
sudo apt install python3-venv python3-pip libgl1 libglib2.0-0
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Se o Python padrão não for 3.11/3.12, crie o ambiente com `python3.11 -m venv .venv`
ou `python3.12 -m venv .venv`, desde que esse interpretador esteja instalado.
Ative o ambiente em cada novo terminal. O arquivo de dependências atende ao
protótipo completo; a estação não precisa executar os componentes de servidor.

Os três arquivos SSD devem estar em `backend/detection/models/`:
`frozen_inference_graph.pb`, `ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt` e
`coco.names`. Não é necessário instalar YOLO, PyTorch ou CUDA.

### 2. Executar testes automatizados

Não exigem câmera nem uma instância MongoDB; as operações da API são simuladas.

```bash
python -m unittest backend.test_detection_events backend.test_detection_publishing backend.test_background_publisher backend.test_station_document -v
```

Não use descoberta indiscriminada: `backend/test_mongodb.py` é um utilitário que
consulta um MongoDB real, não um teste isolado.

### 3. Iniciar MongoDB e API

É necessário um MongoDB acessível em `localhost:27017` **no computador servidor**.
Se Docker já estiver instalado, uma opção para o teste é:

```bash
docker run -d --name aquamonitor-mongo -p 127.0.0.1:27017:27017 -v aquamonitor-mongo-data:/data/db mongo:7
```

Nas próximas execuções, use `docker start aquamonitor-mongo`.
Se já houver MongoDB nessa porta, use a instância existente.

Em um terminal com o ambiente virtual ativo:

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Abra `http://127.0.0.1:8000/docs` para explorar a API.

### 4. Cadastrar a estação

Em outro terminal:

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/api/stations \
  -H 'Content-Type: application/json' \
  -d '{"station_id":1,"location":{"type":"Point","coordinates":[-46.4526,-23.5015]},"administrative":{"country":"Brazil","state":"São Paulo","city":"Santos","district":"Baía de Santos"}}'
```

A estação precisa existir antes do envio. HTTP 409 neste cadastro significa que
esse `station_id` já existe; consulte `GET /api/stations` para confirmar.

### 5. Testar câmera e envio

Primeiro, sem envio (em um terminal sem `BOTTLE_COUNT_API_ENABLED=1`):

```bash
BOTTLE_COUNT_API_ENABLED=0 python backend/detection/object-ident.py --camera 0
```

Depois, com API e MongoDB ativos:

```bash
BOTTLE_COUNT_API_URL=http://127.0.0.1:8000 \
BOTTLE_COUNT_STATION_ID=1 \
python backend/detection/object-ident.py --camera 0 --publish
```

Passe uma garrafa pela linha e pressione `q` na janela para sair. Use inicialmente
640 × 480: a linha padrão vai de `(0, 240)` a `(640, 240)`. Mudar `--width` ou
`--height` não reposiciona a linha; ajuste `COUNTING_LINE` em
`backend/detection/config.py` quando necessário.

O envio é agendado a cada cinco segundos por padrão. Consulte o resultado:

```bash
curl --fail http://127.0.0.1:8000/api/stations/1/detections
```

### 6. Abrir o dashboard

Em outro terminal, no computador servidor:

```bash
python -m http.server 3000 --bind 127.0.0.1 --directory dashboard
```

Abra `http://127.0.0.1:3000` **no computador que executa a API**. Selecione a
estação e confira a atualização do resumo. O mapa usa recursos externos e requer
internet para carregar seus componentes e mapas.

O JavaScript usa `http://127.0.0.1:8000` em `dashboard/js/api.js`,
`dashboard/js/detection-counter.js` e `dashboard/js/crud.js`. Para acessar o painel
por outro computador, substitua esses endereços pelo IP do servidor e disponibilize
o servidor estático na rede com `--bind 0.0.0.0`.

## Testes na Raspberry Pi

### No computador servidor

Mantenha MongoDB, API e dashboard como no teste local. A API deve usar
`--host 0.0.0.0`. Descubra o IP da interface conectada à mesma rede da Pi:

```bash
hostname -I
```

Nos exemplos seguintes, `192.168.1.100` representa esse IP: substitua pelo valor
real. A porta TCP 8000 precisa estar acessível da Pi. O dashboard pode continuar
aberto no próprio servidor.

### Na Raspberry Pi

1. Use um sistema de 64 bits e Python 3.11/3.12 como base para este setup.
2. Copie ou clone o repositório, incluindo os arquivos do modelo SSD.
3. Crie o ambiente virtual e instale `requirements.txt` conforme o setup local.
4. Conecte a câmera USB e execute o runner em uma sessão gráfica da Pi.

A instalação e o desempenho em ARM precisam ser verificados no equipamento;
este guia não representa uma validação física da Raspberry Pi.
O runner usa `cv2.VideoCapture`: câmeras CSI/Picamera2 não têm integração específica.
Não use `opencv-python-headless` com o runner atual, que chama `imshow()`.

Antes da câmera, verifique a comunicação:

```bash
curl --fail http://192.168.1.100:8000/api/stations
```

Confirme que a estação 1 aparece e inicie:

```bash
source .venv/bin/activate
BOTTLE_COUNT_API_URL=http://192.168.1.100:8000 \
BOTTLE_COUNT_STATION_ID=1 \
BOTTLE_COUNT_PUBLISH_INTERVAL=5 \
python backend/detection/object-ident.py --camera 0 --width 640 --height 480 --publish
```

A Pi executa apenas a detecção e o envio; não precisa iniciar MongoDB, FastAPI
ou dashboard. Um terminal SSH sem acesso à sessão gráfica não basta para o
runner atual. Não há opção de execução sem janela implementada.

Para validar, anote o total inicial no servidor, passe uma quantidade conhecida
de garrafas pela linha e compare o aumento da contagem após a publicação.
Garrafas precisam cruzar a linha, e erros de detecção/rastreamento podem causar
perdas ou duplicações. Ajuste câmera, confiança e intervalo de inferência.

## Comandos úteis

Todos os comandos Python abaixo pressupõem o ambiente virtual ativo.

| Objetivo | Comando |
|---|---|
| Ver opções do runner | `python backend/detection/object-ident.py --help` |
| Trocar câmera | `python backend/detection/object-ident.py --camera 1` |
| Ajustar inferência | `python backend/detection/object-ident.py --confidence 0.45 --nms 0.2 --detection-interval 0.25` |
| Listar estações | `curl --fail http://127.0.0.1:8000/api/stations` |
| Consultar contagem | `curl --fail http://127.0.0.1:8000/api/stations/1/detections` |
| Conferir dependências | `python -m pip check` |
| Consultar documentos no MongoDB real | `python backend/test_mongodb.py` |
| Iniciar MongoDB já criado no Docker | `docker start aquamonitor-mongo` |
| Parar MongoDB do teste | `docker stop aquamonitor-mongo` |
| Ver ajuda do documento local | `python -m backend.station_document --help` |

Variáveis lidas pelo runner (exporte antes de iniciar; `.env` não é carregado automaticamente):

| Variável | Padrão | Finalidade |
|---|---|---|
| `BOTTLE_COUNT_API_URL` | `http://127.0.0.1:8000` | URL da API no computador |
| `BOTTLE_COUNT_STATION_ID` | `1` | Estação previamente cadastrada |
| `BOTTLE_COUNT_PUBLISH_INTERVAL` | `5` | Intervalo de publicação em segundos |
| `BOTTLE_COUNT_API_ENABLED` | `0` | `1` habilita envio; alternativa a `--publish` |

Detalhes adicionais: [publicação](backend/detection/PUBLISHING.md) e
[documento local da estação](backend/STATION_DOCUMENT.md).
