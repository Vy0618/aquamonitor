# AquaMonitor

Protótipo de visão computacional para detectar garrafas, contar cruzamentos de
uma linha e enviar os eventos para um computador com API, MongoDB e dashboard.
O código da estação e do servidor está em `backend/`, mas sua execução é separada.

## Sumário

- [Arquitetura](#arquitetura)
- [Dashboard](#dashboard)
- [Limitações atuais](#limitações-atuais)
- [Configuração](#configuração)
- [Setup e testes locais](#setup-e-testes-locais)
- [Setup e testes com a Raspberry Pi](#setup-e-testes-com-a-raspberry-pi)
- [Controle dos serviços](#controle-dos-serviços)
- [Comandos úteis e diagnóstico](#comandos-úteis-e-diagnóstico)
- [Imagem e vídeo configuráveis](#imagem-e-vídeo-configuráveis)

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
mesmo evento. O dashboard consulta `GET /api/stations`, atualizando todas as estações e seus
resumos. Uma nova consulta é agendada cinco segundos após a conclusão da anterior;
cada requisição tem timeout de dez segundos.

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

### Execução do monitor e módulos alternativos

O comando disponível é `python -m backend.monitoring.monitor_residuos`, com
`--detector ssd` ou `--detector yolo` (padrão). Usa rastreamento por centróides,
publicação em thread e aceita `--display` / `--no-display`.
`monitor_ssd_mobilenet` e `monitor_ssd_mobilenet_local` são atalhos para o mesmo
monitor SSD; o sufixo `local` não desativa a publicação.

Os módulos `detection_pipeline.py`, `tracker.py`, `line_counter.py` e
`api_client.py` mantêm um pipeline alternativo ByteTrack reutilizável. Contudo,
**`backend/detection/object-ident.py` não existe nesta árvore**: comandos antigos
que usam esse arquivo ou sua opção `--publish` não são executáveis nesta versão.
O monitor principal não usa esse pipeline alternativo.

O monitor tem limite de 32 envios pendentes e encerra se um envio falhar ou o
limite for atingido. O cliente do pipeline ByteTrack mantém uma fila em memória
para repetir falhas com o mesmo UUID. Nenhum deles possui fila persistente.

`backend/data/contagem_residuos.json` preserva contagens locais, mas não comprova
entrega ao servidor. `backend/station/station.json` não é sincronizado com MongoDB.
O total exibido no dashboard vem dos eventos recebidos, não desses arquivos.

## Dashboard

Interface em português brasileiro, estilo terminal, sem etapa de compilação.
O servidor HTTP entrega os arquivos; a API fornece os dados do MongoDB.

- **Busca por ID:** centraliza a estação, abre seus detalhes e muda de Calor para
  Ambos quando necessário. Limpa filtros de localidade que ocultem o resultado.
- **Estado, município e distrito:** filtram as estações e enquadram a localidade.
  Limpar filtros volta a enquadrar todas as estações.
- **Detecções da estação:** identifica o ID selecionado e mostra total, categorias
  e última detecção. Esse total não representa a soma da área filtrada.
- **Sentido das garrafas (no popup da estação):** mostra contagens positivas (de cima para baixo na
  imagem), negativas (de baixo para cima) e sem sentido informado. A linha atual
  é horizontal; os sinais descrevem o movimento na imagem, não a direção
  geográfica da correnteza. O total continua sendo a soma dos eventos, sem subtrair
  os negativos. O monitor conta cada track uma vez.
- **Classificação:** cinco municípios com maior soma de detecções, agrupados por
  município e estado. Considera todas as estações, independentemente dos filtros.
- **Calor (padrão):** pesos lineares, sem pontos zerados, com referência fixa de
  300 detecções. Manchas próximas se somam; a cor não equivale a uma contagem
  exata por estação. Ampliação e sobreposição alteram a distribuição espacial.
- **Estações:** círculos com área proporcional à contagem, limitada na referência
  de 300; valores baixos e zero usam um tamanho mínimo para permitir seleção.
- **Ambos:** calor com pequenos anéis vazados. Os detalhes mostram o total exato.

A escala, as cores e os raios estão em `dashboard/js/config.js`. A legenda acompanha
essa configuração. A atualização automática preserva filtros válidos, ampliação e
posição do mapa; inclui novos cadastros e remove estações excluídas. Se a estação
selecionada desaparecer, o painel limpa a seleção. Falhas de rede preservam os dados
anteriores e exibem aviso e horário da última atualização; há novas tentativas,
inclusive se a primeira consulta falhar. Abas em segundo plano podem atrasar os ciclos.

O horário no cabeçalho indica a última consulta bem-sucedida à API, não a última
comunicação de cada câmera. O tempo de atividade mede a sessão da página no navegador,
não o tempo de execução da API ou da Raspberry Pi. A interface de cadastro/exclusão
fica em `/crud.html`; não há formulário de edição de estação.

## Limitações atuais

Os novos eventos incluem `direction: "positive" | "negative"`. A API armazena o
campo em `detection_events` e retorna `by_direction` (todas as classes) e
`by_type_direction` (por classe) no resumo. Os popups usam apenas a classe `bottle`
nos contadores de sentido; o bloco lateral de sentidos foi removido. Eventos antigos sem esse campo ficam em `unknown`;
não é possível reconstruir seu movimento apenas pela contagem. Não é necessária
migração do banco. Após atualizar, reinicie a API e o monitor e recarregue o
dashboard para que as três partes usem o novo contrato.

- Os totais representam todos os eventos armazenados, sem filtro por período.
  Alterar `stations.detections` ou `stations.json` não muda os totais da API.
- Excluir uma estação não exclui seus eventos. Cadastrar novamente o mesmo ID
  associa os eventos antigos ao novo cadastro e faz os totais reaparecerem.
- A API valida o ID no cadastro, mas não valida integralmente localização e
  campos administrativos. Use GeoJSON `Point` com `[longitude, latitude]` numéricos
  e nomes administrativos consistentes; registros incompletos podem quebrar o mapa.
- A API não tem autenticação e aceita CORS amplo. A execução descrita é de um
  protótipo em ambiente controlado; não representa uma implantação pública pronta.
- Cada consulta geral agrega o histórico de eventos e reúne seus horários.
  O custo cresce com o volume e com cada navegador aberto; não há paginação nem
  resumos pré-calculados. O intervalo do painel não garante atualização em tempo real.
- Não há confirmação de atividade periódica das câmeras, fila persistente de
  envio nem recuperação automática da câmera. Testes simulados não substituem
  medição de precisão e desempenho no equipamento.

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
| `bytetrack` | Parâmetros dos módulos alternativos ByteTrack |

**O JSON atual contém `http://0.0.0.0:8000`. Substitua esse destino ou use as
variáveis dos exemplos abaixo.** `0.0.0.0` serve para o Uvicorn escutar em todas
as interfaces; a estação deve usar um IP ou hostname do servidor.

`AQUADETECTOR_API_URL` sobrescreve o JSON no carregador compartilhado e tem prioridade sobre
`BOTTLE_COUNT_API_URL`. `BOTTLE_COUNT_STATION_ID` sobrescreve a estação.
`AQUAMONITOR_CONFIG` define o arquivo padrão. Não há leitura automática de `.env`.

`backend.enabled`, `BOTTLE_COUNT_API_ENABLED` e
`backend.publish_interval_seconds` controlam o cliente/pipeline ByteTrack. O monitor
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

Os testes do dashboard usam o executor nativo do Node.js, sem `npm install`.
Com Node.js 22 ou superior:

```bash
node --test dashboard/tests/*.mjs
```

Cobrem intensidade do calor, modos do mapa, preservação de filtros e consultas à
API simulada. Node.js é necessário apenas para esses testes, não para servir o painel.
Veja também o [roteiro de validação no navegador](dashboard/VALIDATION.md).

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
python serve_dashboard.py
```

O servidor `serve_dashboard.py` fixa a pasta do dashboard em relação ao próprio
script e desativa o cache dos arquivos. Ao substituir um servidor antigo, pare-o
com Ctrl+C e faça uma recarga forçada no navegador. Para testar sem o cache da
origem anterior, use `python serve_dashboard.py --port 3001` e abra a porta 3001.

Abra `http://127.0.0.1:3000`, selecione a estação 1 e anote sua contagem inicial.
O mapa e suas bibliotecas externas precisam de internet. Cadastros e exclusões
aparecem no próximo ciclo automático, sem recarregar a página.

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

Este tutorial usa **laptop com backend e dashboard** e **Raspberry Pi com
reconhecimento de imagem**. Os comandos são para Bash/Linux; na Pi, use Raspberry
Pi OS de 64 bits. Execute os comandos de cada etapa **na máquina indicada**.

| Máquina | O que executa | O que precisa acessar |
|---|---|---|
| Laptop | MongoDB, FastAPI e servidor do dashboard; navegador | MongoDB local e internet para mapas/bibliotecas |
| Raspberry Pi | Câmera USB, detector SSD/YOLO, rastreador e envio de eventos | API do laptop na porta 8000 |

```text
Raspberry Pi                                  Laptop
câmera USB → detecção → cruzamento ──HTTP──→ FastAPI :8000 → MongoDB :27017
                                                ↑
                                         navegador do laptop
                                         dashboard :3000
```

A Pi envia **eventos JSON**, não vídeo, para `/api/detections`. A câmera fica
conectada à Pi. Não execute o monitor de reconhecimento no laptop neste cenário.
A Pi não precisa executar MongoDB, Uvicorn nem servidor do dashboard. Os arquivos
Python da estação também estão em `backend/`; o nome da pasta não significa que
o servidor deva rodar na Pi.

### 1. Laptop — preparar o ambiente do servidor

Tenha uma cópia atual do repositório. Ajuste `~/aquamonitor` se sua pasta tiver
outro nome. Use Python 3.11 ou superior para a API (`datetime.UTC` é usado no código).

```bash
cd ~/aquamonitor
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'fastapi>=0.141.0' 'uvicorn>=0.52.0' 'pydantic>=2.0.0' pymongo
python -m pip check
```

Em Debian/Ubuntu, instale `python3-venv` e `python3-pip` caso faltem. Se o ambiente
completo já foi preparado, basta ativá-lo. Os quatro pacotes acima correspondem
à parte servidor de `requirements.txt`; o laptop não precisa instalar os modelos,
OpenCV ou Ultralytics para executar somente a API e o painel. A suíte completa de
testes, por outro lado, usa as dependências completas descritas no setup local.

### 2. Laptop — iniciar MongoDB e API

Inicie **uma** instalação do MongoDB. Se `mongod` já estiver instalado:

```bash
sudo systemctl start mongod
systemctl status mongod --no-pager
```

Se não tiver esse serviço, use a alternativa Docker da seção
[Iniciar o MongoDB](#3-iniciar-o-mongodb). Em ambos os casos, o banco deve estar
acessível em `mongodb://localhost:27017/`, endereço fixo de `backend/app.py`.
A porta 27017 não precisa ficar acessível à Pi.

No **terminal 1 do laptop**, mantenha a API executando:

```bash
cd ~/aquamonitor
source .venv/bin/activate
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Em outro terminal do laptop, confirme o acesso local e descubra o IP da rede:

```bash
curl --fail http://127.0.0.1:8000/api/stations
hostname -I
```

`[]` é uma resposta válida se não há estações. Se houver vários IPs, escolha o da
interface conectada à mesma rede da Pi. Neste tutorial, **`192.168.1.100` é um
exemplo do IP do laptop**: substitua pelo IP real. `0.0.0.0` é endereço de escuta,
não o endereço que a Pi deve usar. A API precisa aceitar conexões da Pi na porta
TCP 8000; uma rede de convidados, isolamento entre clientes ou firewall pode
bloqueá-las. Se o IP mudar, atualize a configuração da Pi.

### 3. Laptop — cadastrar a estação da Pi

Antes de iniciar a captura, cadastre o ID que a Pi vai enviar. Exemplo para ID 1:

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/api/stations \
  -H 'Content-Type: application/json' \
  -d '{"station_id":1,"location":{"type":"Point","coordinates":[-46.4526,-23.5015]},"administrative":{"country":"Brazil","state":"São Paulo","city":"Santos","district":"Baía de Santos"}}'
```

Substitua as coordenadas e a localidade pelos dados da estação. A ordem é
`[longitude, latitude]`. HTTP 409 significa que o ID já existe; confira o cadastro
com `GET /api/stations`. Não exclua uma estação existente apenas para repetir o
exemplo: a exclusão mantém os eventos históricos. `stations.json` e o documento
local da Pi não criam cadastro na API automaticamente.

### 4. Laptop — configurar e abrir o dashboard

Como o navegador fica no próprio laptop, use `http://127.0.0.1:8000` como destino
da API nos arquivos JavaScript:

| Arquivo | Valor para este cenário |
|---|---|
| `dashboard/js/api.js` | `const api_url = "http://127.0.0.1:8000/api/stations";` |
| `dashboard/js/crud.js` | URLs de cadastro/exclusão iniciando com `http://127.0.0.1:8000/api/stations` |

**Na cópia revisada, `api.js` contém `http://10.209.77.215:8000/api/stations`,
enquanto `crud.js` usa localhost.** Ajuste os endereços para que ambos apontem
para a mesma API. `aquamonitor.json` e os exports da Pi não configuram o navegador.
`detection-counter.js` não é importado pelo painel atual e não controla suas consultas.

No **terminal 2 do laptop**, inicie o servidor estático:

```bash
cd ~/aquamonitor
source .venv/bin/activate
python serve_dashboard.py
```

Abra **http://127.0.0.1:3000/** no navegador do laptop. Use a busca por ID para
selecionar a estação e anote seu total inicial. O painel consulta todas as estações,
agendando a próxima consulta cinco segundos após terminar a anterior. Não é preciso
recarregar para receber novas detecções. O cabeçalho deve mostrar o horário de
atualização; isso confirma acesso à API, não atividade da câmera.

O servidor sem cache é opcional; também funciona:

```bash
python -m http.server 3000 --bind 127.0.0.1 --directory dashboard
```

Escolha apenas um servidor na porta 3000. Após editar HTML/JS/CSS, faça uma recarga
forçada com Ctrl+Shift+R; se necessário, desative o cache na aba Rede das ferramentas
do navegador. Falhas de importação ou elementos HTML ausentes devem ser conferidas
no console; não significam necessariamente falha de conexão com a API.

### 5. Raspberry Pi — preparar a estação

Copie ou clone a **mesma versão do código**, incluindo `aquamonitor.json`, a pasta
`backend/` e os modelos em `backend/detection/models/`. Crie o ambiente virtual na
própria Pi; não copie a `.venv` do laptop, pois os pacotes dependem da arquitetura.

```bash
cd ~/aquamonitor
uname -m
python3 --version
sudo apt update
sudo apt install python3-venv python3-pip libgl1 libglib2.0-0 curl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-station.txt
python -m pip check
ls -lh backend/detection/models/
```

Em um sistema ARM de 64 bits, `uname -m` deve mostrar `aarch64`. O código do monitor
requer Python 3.10 ou superior; a instalação também depende de versões de Python e
arquitetura atendidas pelos pacotes. `requirements-station.txt` instala OpenCV,
NumPy, Requests e Ultralytics (com suas dependências), para SSD e YOLO. Não instala
os componentes do servidor nem o pipeline alternativo ByteTrack. A compatibilidade
e o desempenho devem ser medidos na Pi; não foram verificados em hardware por esta
revisão.

Para SSD, confira `frozen_inference_graph.pb`, o `.pbtxt` e `coco.names`. Para YOLO,
confira `best (1).pt`. O monitor SSD funciona com OpenCV DNN, sem exigir instalação
separada de TensorFlow. A câmera deve estar acessível por OpenCV/V4L2; não há
captura específica via Picamera2/libcamera.

### 6. Raspberry Pi — configurar conexão, câmera e contagem

Conecte a câmera USB à Pi e confira `camera.device_index` em `aquamonitor.json`
(padrão 0). Feche qualquer outro programa ou serviço que esteja usando essa câmera.

No terminal da Pi que executará o monitor:

```bash
cd ~/aquamonitor
source .venv/bin/activate
export AQUADETECTOR_API_URL=http://192.168.1.100:8000
export BOTTLE_COUNT_STATION_ID=1
curl --fail --max-time 10 "$AQUADETECTOR_API_URL/api/stations"
```

A resposta precisa conter o ID 1. Só prossiga quando essa consulta funcionar.
`127.0.0.1` na Pi aponta para a própria Pi; não use esse endereço como destino da
API do laptop. O JSON atual usa `0.0.0.0`, portanto mantenha o export acima ou edite
`backend.base_url` para o IP real do laptop. O export tem prioridade sobre o JSON.

Revise estes campos **na cópia do JSON da Pi**, preservando as demais seções:

| Campo | Uso neste tutorial |
|---|---|
| `station_id` | Mesmo ID cadastrado no laptop; o export pode sobrescrevê-lo |
| `backend.base_url` | `http://192.168.1.100:8000`, com o IP real do laptop |
| `backend.require_connection_on_startup` | `true`, verifica API e cadastro antes de abrir a câmera |
| `camera.device_index` | Índice da câmera USB; padrão `0` |
| `tracking.line_y_ratio` | `0.55`, linha horizontal a 55% da altura da imagem |
| `tracking.direction` | `both` para ambos os sentidos; `down` ou `up` para restringir |
| `display.enabled` | `false` para operação sem janela |

O monitor publica automaticamente; `backend.enabled=false` não desativa seu envio.
Ele não aceita `--publish`. Os exports valem apenas no terminal atual; em systemd,
configure `Environment=` na unidade ou edite o JSON. O documento
`backend/station/station.json` preserva dados existentes: confira também o ID e a
localidade desse arquivo ao preparar outra estação. Não reutilize o arquivo de
contagens de uma estação diferente como se fosse uma instalação nova.

### 7. Raspberry Pi — iniciar o reconhecimento

No mesmo terminal, para detectar garrafas com SSD:

```bash
python -m backend.monitoring.monitor_residuos --detector ssd --no-display
```

Para usar o modelo YOLO do projeto, execute **em vez do comando anterior**:

```bash
python -m backend.monitoring.monitor_residuos --detector yolo --no-display
```

O SSD incluído reconhece `bottle` entre as categorias do projeto. O adaptador YOLO
aceita garrafa, lata, papelão, papel e plástico; a capacidade real depende do modelo
treinado. O YOLO está configurado para CPU. Sem `--detector`, o padrão é YOLO.

Para ajustar o enquadramento em uma sessão gráfica da Pi, substitua `--no-display`
por `--display`. A janela é exibida na Pi; não há transmissão de vídeo ao dashboard
do laptop. Em SSH sem sessão gráfica, mantenha `--no-display`. Interrompa com Ctrl+C;
com janela, também é possível usar Q ou Esc. Execute um monitor por câmera.

### 8. Validar o fluxo completo e encerrar

1. No laptop, anote a contagem inicial da estação selecionada.
2. Na câmera da Pi, passe uma garrafa pela linha; apenas aparecer na imagem não
   gera evento. O terminal deve mostrar `Contado: bottle ...`.
3. No laptop, aguarde o próximo ciclo do painel ou consulte:

   ```bash
   curl --fail http://127.0.0.1:8000/api/stations/1/detections
   ```

4. Confira o aumento de `total` e `by_type.bottle`. Com ambos os sentidos habilitados,
   `by_type_direction.bottle.positive` corresponde a cima → baixo na imagem e
   `negative` a baixo → cima. Cada track conta uma vez. Eventos antigos ficam em
   `unknown`; a interface atual mostra sentidos no popup, não em um bloco lateral.
5. Para encerrar normalmente, pare primeiro o monitor na Pi e aguarde seus envios;
   depois interrompa API e dashboard no laptop com Ctrl+C, se foram iniciados
   manualmente. Se houver serviços instalados, use a seção de controle dos serviços.

Em falha HTTP ou limite de 32 envios pendentes, o monitor encerra: restaure a
conexão e reinicie-o. O painel tenta reconectar automaticamente, mas o monitor não.
Contagens locais salvas não são reenviadas ao servidor nem comprovam entrega.

### Acesso opcional ao painel por outro dispositivo

Isso não é necessário quando o navegador fica no laptop. Para acesso pela rede,
inicie `python serve_dashboard.py --bind 0.0.0.0` **no laptop** e configure tanto
`api.js` quanto as duas URLs de `crud.js` com o IP real do laptop. Abra
`http://192.168.1.100:3000` no outro dispositivo; as portas 3000 e 8000 precisam
estar acessíveis a ele. Não use `127.0.0.1` no JavaScript nesse caso. Mudar somente
o bind do servidor estático não muda o destino das requisições da página.

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
# Ajuda do monitor
python -m backend.monitoring.monitor_residuos --help

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
| Dashboard antigo após alteração | Conferir a pasta servida e o cache do navegador, conforme abaixo |
| Mapa sem manchas | Conferir eventos na API; estações zeradas não geram calor |

### Arquivos antigos no navegador

Execute o servidor a partir da raiz correta. Para eliminar ambiguidade, use um
caminho absoluto (ajuste ao seu clone):

```bash
python /home/vyzxc/aquamonitor/serve_dashboard.py
curl -s http://127.0.0.1:3000/ | grep -E 'mapMode|systemStatus'
```

Os dois identificadores devem existir no HTML atual. Se estiverem ausentes, confira
qual processo usa a porta 3000 e qual pasta ele serve. Se estiverem presentes,
abra as ferramentas do navegador (F12), marque **Desativar cache** na aba **Rede**
e recarregue com Ctrl+Shift+R. A opção vale enquanto as ferramentas estão abertas.
A atualização automática de dados não substitui o recarregamento após editar JS/CSS/HTML.

### Documentos históricos

`reproduction.md`, `rpi-server-communication.md` e `implementation.txt` preservam
instruções ou planos antigos, incluindo `object-ident.py` e rotas `bottle-count`
que não existem na API atual. Para executar, use este README e os documentos
atualizados abaixo. `RELATORIO.md` explica a origem das contagens; seus exemplos
com eventos aleatórios são apenas para uma base de testes.

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
