# AquaMonitor

Protótipo de visão computacional para detectar garrafas, contar cruzamentos de
uma linha e enviar os eventos para um computador com API, MongoDB e dashboard.
O código da estação e do servidor está em `backend/`, mas sua execução é separada.

## Sumário

- [Arquitetura](#arquitetura)
- [Configuração](#configuração)
- [Setup e testes locais](#setup-e-testes-locais)
- [Setup e testes com a Raspberry Pi](#setup-e-testes-com-a-raspberry-pi)
- [Controle dos serviços](#controle-dos-serviços)
- [Comandos úteis e diagnóstico](#comandos-úteis-e-diagnóstico)

## Arquitetura

```text
Estação: computador de teste ou Raspberry Pi
Câmera USB → detector SSD/YOLO → rastreador → cruzamento da linha
                                                  ├→ contagem JSON local
                                                  └→ envio HTTP em thread
                                                              ↓
Computador: FastAPI :8000 → MongoDB aquamonitor → resumo de detecções
                                  ↑                       ↓
                             API consulta         dashboard :3000
```

Esse é o fluxo de `backend.monitoring.monitor_residuos`. A captura mantém o
frame mais recente em uma thread, a inferência ocorre em intervalos configurados
e outro trabalhador envia um evento por cruzamento a `POST /api/detections`.
O monitor salva contagens por classe e atualiza o documento local da estação.

A API verifica o cadastro da estação, valida o evento e armazena UUID, classe,
confiança, track e horário. O índice único de `event_id` impede duplicação desse
mesmo evento. O dashboard consulta o resumo da estação selecionada a cada três
segundos e mostra mapa, contagem por categoria e horário da última detecção.

### Organização do código

| Caminho | Responsabilidade |
|---|---|
| `aquamonitor.json` | Configuração compartilhada da estação |
| `backend/settings.py` | Leitura, validação e resolução de caminhos do JSON |
| `backend/app.py` | API FastAPI; banco `aquamonitor`, coleções `stations` e `detection_events` |
| `backend/camera/` | Captura USB com OpenCV e manutenção do último frame |
| `backend/detection/` | Adaptadores SSD/YOLO, modelos e pipeline alternativo ByteTrack |
| `backend/tracking/` | Associação de objetos por centróide e cruzamento horizontal |
| `backend/monitoring/` | Comandos de execução do monitor SSD/YOLO |
| `backend/communication/` | Cliente HTTP usado pelo monitor |
| `backend/station/` | Documento local da estação e sua persistência |
| `backend/tests/`, `backend/test_*.py` | Testes do monitor, configuração, publicação e API |
| `dashboard/` | HTML, CSS e JavaScript; Leaflet, mapa, filtros e cadastro de estações |

Os pesos ficam em `backend/detection/models/`. O SSD usa `.pb`, `.pbtxt` e
`coco.names`; o YOLO usa `best (1).pt`. Entre as categorias configuradas do projeto,
o SSD incluído trabalha com `bottle`. O adaptador YOLO filtra `bottle`, `can`,
`carton`, `paper` e `plastic`; reconhecer essas classes depende do checkpoint.

### Dois pontos de entrada

| Entrada | Rastreador | Envio e interface |
|---|---|---|
| `python -m backend.monitoring.monitor_residuos --detector ssd` | Centróides | Envia automaticamente em thread; aceita `--no-display` |
| `python backend/detection/object-ident.py --publish` | ByteTrack | Envia de forma síncrona a cada intervalo; exige janela gráfica |

O primeiro será usado nos tutoriais. Sem `--detector`, seu padrão é **YOLO**.
`monitor_ssd_mobilenet` e `monitor_ssd_mobilenet_local` são atalhos para o mesmo
monitor SSD; o sufixo `local` não desativa a publicação.

O monitor tem limite de 32 envios pendentes e encerra se um envio falhar ou o
limite for atingido. O runner ByteTrack mantém uma fila em memória para repetir
falhas com o mesmo UUID. Nenhum deles possui fila persistente de eventos.

`backend/data/contagem_residuos.json` preserva contagens locais, mas não comprova
entrega ao servidor. `backend/station/station.json` não é sincronizado com MongoDB.
O total exibido no dashboard vem dos eventos recebidos, não desses arquivos.

## Configuração

Edite `aquamonitor.json` ou selecione outro arquivo com `--config CAMINHO`.
Os caminhos de modelos e do documento da estação são relativos à pasta do JSON.
A API e o dashboard não leem esse arquivo.

| Campo | Uso atual |
|---|---|
| `station_id` | Estação que deve existir na API |
| `backend.base_url` | Destino HTTP: localhost no teste local, IP do computador na Pi |
| `backend.detections_path` | `/api/detections` |
| `backend.timeout_seconds` | Timeout das requisições |
| `backend.require_connection_on_startup` | Monitor verifica servidor e estação antes de abrir a câmera |
| `camera` | Índice, resolução e FPS solicitados; padrão atual 0, 640×480 e 15 FPS |
| `detection_interval_ms` | Intervalo de inferência; atual 250 ms |
| `ssd_mobilenet` / `detection` | Configuração do SSD / YOLO |
| `tracking` | Linha proporcional, direção e associação por centróide |
| `bytetrack` | Parâmetros exclusivos do runner ByteTrack |

**O JSON atual contém `http://0.0.0.0:8000`. Substitua esse destino ou use as
variáveis dos exemplos abaixo.** `0.0.0.0` serve para o Uvicorn escutar em todas
as interfaces; a estação deve usar um IP ou hostname do servidor.

`AQUADETECTOR_API_URL` sobrescreve o JSON nos dois runners e tem prioridade sobre
`BOTTLE_COUNT_API_URL`. `BOTTLE_COUNT_STATION_ID` sobrescreve a estação.
`AQUAMONITOR_CONFIG` define o arquivo padrão. Não há leitura automática de `.env`.

`backend.enabled`, `BOTTLE_COUNT_API_ENABLED`, `--publish` e
`backend.publish_interval_seconds` controlam o runner ByteTrack. O monitor
SSD/YOLO publica sempre, inclusive com `backend.enabled=false`.

## Setup e testes locais

Neste cenário, câmera, MongoDB, API e navegador ficam no **mesmo computador**.
Execute a partir da raiz do repositório, em terminais separados para os processos.
Os exemplos usam Bash/Linux.

### 1. Preparar o ambiente

Use Python 3.11 ou 3.12 para o ambiente completo com `numpy==1.26.4`.
Em Debian/Ubuntu, com esses pacotes disponíveis:

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

Se o Python padrão tiver outra versão, use um interpretador 3.11/3.12 instalado
para criar o ambiente. Ative `.venv` em cada terminal que executar Python.
No Windows, use `py -3.11 -m venv .venv` e `.venv\Scripts\Activate.ps1` no PowerShell;
o monitor seleciona DirectShow para a câmera, enquanto no Linux usa V4L2.

Confira que os modelos foram copiados:

```bash
ls -lh backend/detection/models/
```

### 2. Executar os testes automatizados

```bash
python -m unittest backend.test_detection_events backend.test_detection_publishing backend.test_settings backend.tests.test_monitor backend.tests.test_image_processing -v
```

Não exigem câmera nem servidor MongoDB: usam simulações de captura, envio e banco.
Um teste carrega o SSD real com imagem sintética. O teste YOLO não valida o modelo
em hardware. `backend/test_mongodb.py` é uma consulta ao banco real; não use
`unittest discover` indiscriminadamente na pasta `backend/`.

### 3. Iniciar o MongoDB

A API usa `mongodb://localhost:27017/` fixo no código e precisa dele já disponível.
Escolha **uma** das opções, conforme sua instalação.

Se o serviço `mongod` já estiver instalado:

```bash
sudo systemctl start mongod
sudo systemctl status mongod
```

Se preferir usar uma instalação Docker já disponível, crie um container de teste:

```bash
docker run -d --name aquamonitor-mongo \
  -p 127.0.0.1:27017:27017 \
  -v aquamonitor-mongo-data:/data/db mongo:7
```

Nos próximos testes, use `docker start aquamonitor-mongo`, sem recriar o container.
Não inicie as duas opções na mesma porta.

### 4. Iniciar a API — terminal 1

```bash
source .venv/bin/activate
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Abra `http://127.0.0.1:8000/docs`. Em outro terminal, verifique:

```bash
curl --fail http://127.0.0.1:8000/api/stations
```

### 5. Cadastrar a estação de teste

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/api/stations \
  -H 'Content-Type: application/json' \
  -d '{"station_id":1,"location":{"type":"Point","coordinates":[-46.4526,-23.5015]},"administrative":{"country":"Brazil","state":"São Paulo","city":"Santos","district":"Baía de Santos"}}'
```

Se retornar 409, a estação já existe; confira a lista antes de repetir o cadastro.
O ID precisa coincidir com `station_id` do monitor. O arquivo `stations.json` da
raiz não é importado automaticamente. Alternativamente, use o formulário
`http://127.0.0.1:3000/crud.html` após iniciar o dashboard.

### 6. Iniciar o dashboard — terminal 2

```bash
source .venv/bin/activate
python -m http.server 3000 --bind 127.0.0.1 --directory dashboard
```

Abra `http://127.0.0.1:3000`, selecione a estação 1 e anote sua contagem inicial.
O mapa e suas bibliotecas externas precisam de internet. Se a página já estava
aberta antes de cadastrar a estação, recarregue-a.

### 7. Iniciar o monitor — terminal 3

Conecte uma câmera USB, feche outros programas que a estejam usando e execute:

```bash
source .venv/bin/activate
export AQUADETECTOR_API_URL=http://127.0.0.1:8000
python -m backend.monitoring.monitor_residuos --detector ssd --display
```

No PowerShell, use `$env:AQUADETECTOR_API_URL="http://127.0.0.1:8000"` antes do
mesmo comando Python. Para executar sem janela, acrescente `--no-display`.
Para testar o outro modelo, substitua `ssd` por `yolo`.

### 8. Conferir o resultado

Passe uma quantidade conhecida de garrafas pela linha amarela, uma por vez.
O monitor deve imprimir `Contado: bottle ...`. Confirme o incremento no dashboard
ou consulte:

```bash
curl --fail http://127.0.0.1:8000/api/stations/1/detections
```

Compare o **aumento** de `total` e `by_type.bottle` com a contagem inicial. Uma
garrafa apenas visível, sem cruzar a linha, não gera evento. Detecção e rastreamento
podem perder objetos ou atribuir novos IDs; ajuste posição, iluminação e confiança.
Encerre o monitor com `q`, `Esc` ou Ctrl+C; sem janela, use Ctrl+C. Execute apenas
um monitor por câmera e arquivo de contagens.

## Setup e testes com a Raspberry Pi

Neste cenário, **o computador executa MongoDB, API e dashboard**. A **Pi executa
apenas o monitor**, conectado a uma câmera USB e à mesma rede do computador.

### 1. Preparar o computador servidor

Siga as etapas locais de instalação, MongoDB, API e cadastro. Mantenha Uvicorn
com `--host 0.0.0.0 --port 8000`. Descubra o IP da interface na rede da Pi:

```bash
hostname -I
```

Nos exemplos seguintes, `192.168.1.100` é apenas um exemplo: substitua pelo IP
real. A porta TCP 8000 deve estar acessível da Pi. O MongoDB continua local ao
servidor; a estação não se conecta diretamente a ele.

### 2. Preparar a Pi

Use Raspberry Pi OS de 64 bits e Python com pacotes disponíveis para sua
arquitetura. Copie ou clone o repositório **incluindo os modelos** e entre na raiz:

```bash
cd ~/aquamonitor
sudo apt update
sudo apt install python3-venv python3-pip libgl1 libglib2.0-0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-station.txt
python -m pip check
```

Esse arquivo atende ao monitor SSD/YOLO e inclui Ultralytics; não instala a API,
MongoDB ou ByteTrack. A compatibilidade das dependências e o desempenho devem ser
validados no equipamento. Não é necessário executar a suíte completa da API na Pi.
A captura atual usa OpenCV/V4L2; não há integração específica com Picamera2.

### 3. Configurar e testar a rede

Na Pi, edite `aquamonitor.json` com o IP do servidor e o `station_id` cadastrado,
ou sobrescreva os valores no terminal:

```bash
export AQUADETECTOR_API_URL=http://192.168.1.100:8000
export BOTTLE_COUNT_STATION_ID=1
curl --fail "$AQUADETECTOR_API_URL/api/stations"
```

A resposta deve conter a estação 1. `127.0.0.1` na Pi significa a própria Pi;
`0.0.0.0` não identifica seu laptop. Esses exports valem para o terminal atual;
serviços systemd precisam deles em `Environment=` ou da configuração no JSON.

### 4. Iniciar a detecção

No mesmo terminal:

```bash
python -m backend.monitoring.monitor_residuos --detector ssd --no-display
```

Esse comando funciona sem interface gráfica, inclusive por SSH. Para ver a linha
e as caixas numa sessão gráfica da Pi, use `--display`. O monitor verifica
o cadastro da estação antes de abrir a câmera e publica automaticamente.

### 5. Validar no computador

Mantenha o dashboard aberto **no computador servidor**, em `http://127.0.0.1:3000`.
Anote o total inicial, passe garrafas na câmera da Pi e confira o incremento.
Aguarde a conclusão do envio e o próximo ciclo de consulta do painel.

Para abrir o dashboard em outro dispositivo, sirva-o com:

```bash
python -m http.server 3000 --bind 0.0.0.0 --directory dashboard
```

Também substitua `http://127.0.0.1:8000` pelo IP do computador em
`dashboard/js/api.js`, `dashboard/js/detection-counter.js` e `dashboard/js/crud.js`.
Depois abra `http://192.168.1.100:3000`. Mudar apenas o bind não altera o destino
das requisições feitas pelo navegador.

## Controle dos serviços

Os comandos abaixo pressupõem unidades systemd já instaladas. Substitua o nome
caso tenha usado outro: por exemplo, `dashboard.service` em vez de
`aquamonitor-dashboard.service`. Confira as unidades disponíveis:

```bash
systemctl list-unit-files 'aquamonitor*' 'dashboard.service' 'mongod.service'
```

### Computador: API, dashboard e MongoDB

```bash
# Iniciar
sudo systemctl start mongod.service aquamonitor-api.service aquamonitor-dashboard.service

# Consultar o estado dos processos
systemctl status mongod.service aquamonitor-api.service aquamonitor-dashboard.service --no-pager

# Interromper API e dashboard
sudo systemctl stop aquamonitor-api.service aquamonitor-dashboard.service

# Interromper MongoDB, se não estiver sendo usado por outras aplicações
sudo systemctl stop mongod.service

# Reiniciar a API após atualizar código ou configuração do serviço
sudo systemctl restart aquamonitor-api.service

# Acompanhar logs da API; Ctrl+C sai da consulta sem parar o serviço
sudo journalctl -u aquamonitor-api.service -f
```

Se você criou `aquamonitor.target` para agrupar os três serviços:

```bash
sudo systemctl start aquamonitor.target
sudo systemctl stop aquamonitor.target
sudo systemctl restart aquamonitor.target
systemctl status aquamonitor.target --no-pager
systemctl list-dependencies aquamonitor.target
```

Parar ou reiniciar o target só se propaga aos serviços se eles tiverem
`PartOf=aquamonitor.target`. O target ativo não garante que todos os processos
estejam funcionando: consulte também o estado individual dos serviços.

### Raspberry Pi: monitor da câmera

Para o serviço de captura chamado `aquamonitor.service`:

```bash
sudo systemctl start aquamonitor.service
sudo systemctl stop aquamonitor.service
sudo systemctl restart aquamonitor.service
systemctl status aquamonitor.service --no-pager
sudo journalctl -u aquamonitor.service -f
```

Pare esse serviço antes de iniciar o monitor manualmente, para evitar duas
instâncias usando a mesma câmera.

### Inicialização automática e alterações nas unidades

```bash
# Exemplo na Pi: iniciar agora e também nos próximos boots
sudo systemctl enable --now aquamonitor.service

# Parar e desabilitar a inicialização automática
sudo systemctl disable --now aquamonitor.service

# Após editar um arquivo .service ou um override
sudo systemctl daemon-reload
sudo systemctl restart aquamonitor.service

# Mostrar a configuração efetiva e os logs do boot atual
systemctl cat aquamonitor.service
sudo journalctl -u aquamonitor.service -b --no-pager
```

No computador, use o nome da unidade correspondente. `stop` interrompe a execução
atual, mas mantém a configuração de inicialização no boot. `daemon-reload` relê
as unidades e não reinicia os processos sozinho. Alterações apenas no código ou
em `aquamonitor.json` exigem reiniciar o processo, sem `daemon-reload`.

## Comandos úteis e diagnóstico

```bash
# Ajuda do monitor e do runner alternativo
python -m backend.monitoring.monitor_residuos --help
python backend/detection/object-ident.py --help

# Arquivo de configuração alternativo
python -m backend.monitoring.monitor_residuos --config aquamonitor.json --detector ssd --no-display

# Atalho SSD (mesmo fluxo e publicação)
python -m backend.monitoring.monitor_ssd_mobilenet --no-display

# Testes isolados do monitor, com dependências da estação
python -m unittest backend.tests.test_monitor backend.tests.test_image_processing -v

# Consulta ao MongoDB real, no computador servidor
python backend/test_mongodb.py
```

| Sintoma | Verificação |
|---|---|
| Conexão recusada ou timeout | IP real do computador, API ativa na porta 8000, rede e firewall |
| Estação não encontrada | Cadastrar o mesmo `station_id`; arquivos JSON locais não criam cadastro |
| Qt/Wayland ao abrir janela | Executar o monitor com `--no-display` ou usar sessão gráfica compatível |
| Câmera não abre | Índice em `camera.device_index`, conexão, permissões e uso por outro processo |
| Modelo não encontrado | Presença dos pesos e caminhos relativos ao arquivo de configuração |
| Contagem local diferente do painel | Painel soma eventos recebidos; JSON local pode conter histórico ou envios que falharam |
| Erro `.flatten()` no `object-ident.py` | O runner atual ainda assume arrays em frames vazios; para este tutorial use o monitor SSD |

A execução ByteTrack é uma alternativa existente, não o caminho deste tutorial.
Seu envio pode bloquear temporariamente a captura e o código atual ainda possui
o tratamento incompleto de saída vazia do OpenCV. Não há reinício automático de
câmera nem fila SQLite. Dados pendentes em memória se perdem ao encerrar.

Mais detalhes: [configuração](CONFIGURATION.md) e [monitor](backend/MONITOR.md).


## Imagem e vídeo configuráveis

No `aquamonitor.json`:

```json
"display": {
  "enabled": false
},
"image_processing": {
  "enabled": true,
  "max_width": 640,
  "max_height": 480
}
```

O monitor SSD/YOLO lê essas duas seções. `display.enabled=false` executa captura,
contagem e envio sem janela nem desenho de caixas/textos, evitando também a cópia
do frame destinada à prévia. Use Ctrl+C para encerrar. As opções `--display` e
`--no-display` sobrescrevem o JSON; reinicie o monitor ao alterar o arquivo.

`image_processing` limita a imagem enviada ao detector, preservando sua proporção,
sem ampliá-la e usando interpolação de área. O processamento ocorre somente nos
frames destinados à inferência. As caixas retornam às coordenadas originais antes
do rastreamento: a linha, a distância máxima e a prévia continuam na resolução da
captura. Esse limite não força o formato negociado pela câmera.

O limite padrão 640×480 preserva frames já capturados nesse tamanho. Para testar
uma redução maior, configure 320×240. Reduzir dimensões pode perder detalhes de
garrafas pequenas; compare a contagem antes e depois. Com `enabled=false`, o frame
original vai diretamente ao detector. Não foram adicionados filtros de nitidez,
cor ou contraste que alterem a imagem do modelo.

O tamanho interno do modelo permanece em `ssd_mobilenet.input_width/input_height`
ou `detection.image_size`. Portanto, redimensionar a imagem anterior à inferência
não garante diminuir o custo da rede neural e pode acrescentar uma operação de
resize. O ganho real precisa ser medido na Pi; a execução sem vídeo elimina o
trabalho de desenho e apresentação independentemente desse ajuste.

O documento local `backend/station/station.json` é gravado somente ao iniciar
(`online`) e ao encerrar o monitor (`offline`, com a contagem final).
Não há gravação desse documento a cada cruzamento. Uma interrupção abrupta ou
queda de energia pode impedir a atualização final. O arquivo de contagens
`backend/data/contagem_residuos.json` continua sendo salvo nos cruzamentos.
