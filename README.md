# AquaMonitor

Protótipo de visão computacional para detectar garrafas, contar cruzamentos de
uma linha e enviar os eventos para um computador com API, PostgreSQL e dashboard.
O código da estação e do servidor está em `backend/`, mas sua execução é separada.

## Sumário

- [Arquitetura](#arquitetura)
- [Contador de testes](#contador-de-testes)
- [Dashboard](#dashboard)
- [Limitações atuais](#limitações-atuais)
- [Configuração](#configuração)
- [Banco de dados PostgreSQL](#banco-de-dados-postgresql)
- [Migração do MongoDB para PostgreSQL](#migração-do-mongodb-para-postgresql)
- [Setup e testes locais](#setup-e-testes-locais)
- [Setup e testes entre máquinas](#setup-e-testes-entre-máquinas)
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
Computador: FastAPI :8000 → PostgreSQL aquamonitor → resumo de detecções
                                  ↑                       ↓
                             API consulta         dashboard :3000
```

Esse é o fluxo de `backend.monitoring.monitor_residuos`. A captura mantém o
frame mais recente em uma thread, a inferência ocorre em intervalos configurados
e outro trabalhador envia um evento por cruzamento a `POST /api/detections`.
O monitor salva contagens por classe e atualiza o documento local da estação.

A API verifica se a estação está ativa, valida o evento e armazena identificador
do evento, classe, confiança, track, sentido e horário. Os monitores geram UUIDs;
a API aceita identificadores textuais não vazios. A chave primária `event_id`
impede duplicação do mesmo evento e retorna HTTP 409 em uma nova tentativa.
O dashboard consulta `GET /api/stations`, atualizando todas as estações e seus
resumos. Uma nova consulta é agendada cinco segundos após a conclusão da anterior;
cada requisição tem timeout de dez segundos.

### Organização do código

| Caminho | Responsabilidade |
|---|---|
| `aquamonitor.json` | Configuração compartilhada da estação |
| `backend/settings.py` | Leitura, validação e resolução de caminhos do JSON |
| `backend/app.py` | API FastAPI; banco PostgreSQL `aquamonitor`, tabelas `stations` e `detection_events` |
| `backend/camera/` | Captura USB com OpenCV e manutenção do último frame |
| `backend/detection/` | Adaptadores SSD/YOLO, tipos compartilhados e modelos |
| `backend/tracking/` | Associação de objetos por centróide e cruzamento horizontal |
| `backend/monitoring/` | Comandos de execução do monitor SSD/YOLO |
| `backend/communication/` | Cliente HTTP usado pelo monitor |
| `backend/station/` | Documento local da estação e sua persistência |
| `backend/tests/`, `backend/test_*.py` | Testes do monitor, configuração, publicação e API |
| `dashboard/` | HTML, CSS e JavaScript; Leaflet, mapa, filtros e cadastro de estações |

Os pesos ficam em `backend/detection/models/`. O SSD usa `.pb`, `.pbtxt` e
`coco.names`; o YOLO usa `best (1).pt`. O SSD está configurado para `bottle` e
`cell phone`; celulares só são rastreados e contados com `--testes`. O checkpoint
YOLO incluído conhece `bottle`, `can`, `carton`, `paper` e `plastic`. Nos dois
modos, `detection_types` filtra as classes reconhecidas pelo modelo; adicionar
um nome à lista não ensina uma classe nova aos pesos.

### Contador de testes

`detection.detection_types` (YOLO) e `ssd_mobilenet.detection_types` (SSD)
selecionam quais classes reconhecidas pelo modelo serão rastreadas. Objetos fora
dessa lista continuam sendo ignorados. Não adicione `testes` nessas listas:
`testes` é um contador, habilitado somente com o argumento `--testes`, para
objetos selecionados que não sejam `bottle`, `can`, `carton`, `paper` ou `plastic`.
Use os nomes exatos das classes do modelo: no SSD incluído, por exemplo,
`cell phone` contém um espaço.

Por exemplo, o JSON atual permite `bottle` e `cell phone` no SSD. Ao cruzar a
linha, uma garrafa incrementa `bottle` e, com `--testes`, um celular incrementa
`testes`. Sem esse argumento, objetos fora das cinco classes de resíduos são
ignorados antes do rastreamento e o contador `testes` não aparece na prévia.
Contagens de teste anteriores permanecem salvas. A prévia e o rastreador
preservam o nome real do objeto; o contador salvo e o evento
enviado à API usam `testes` para os objetos de teste. A regra vale para os dois
modos e mantém os limites de confiança e a contagem uma vez por track.

Para testar com celulares, reinicie o monitor usando:

```bash
python -m backend.monitoring.monitor_residuos --detector ssd --display --testes

# Mesmo teste sem janela
python -m backend.monitoring.monitor_residuos --detector ssd --no-display --testes
```

O argumento também funciona com `--detector yolo` e nos atalhos
`monitor_ssd_mobilenet` e `monitor_ssd_mobilenet_local`. Para desativá-lo,
encerre o monitor e inicie novamente sem `--testes`.

Eventos publicados como `testes` aparecem no resumo `by_type.testes` e entram
no total histórico da estação, no calor e na classificação do dashboard.
Retirar o argumento impede novos eventos de teste, mas não remove os já gravados.

O YOLO `best (1).pt` incluído só conhece as cinco classes de resíduos. Para
reconhecer celulares em YOLO, é necessário usar pesos que conheçam essa classe
e incluí-la em `detection.detection_types`. Alterar a lista não treina o modelo.

### Execução do monitor

O comando principal é `python -m backend.monitoring.monitor_residuos`, com
`--detector ssd` ou `--detector yolo` (padrão). Usa rastreamento por centróides,
publicação em thread e aceita `--display` / `--no-display`, além de `--testes`
para habilitar a contagem de objetos de teste.
`monitor_ssd_mobilenet` e `monitor_ssd_mobilenet_local` são atalhos para a mesma
função principal com SSD; não contêm outra implementação e não desativam o envio.

Há um único fluxo de detecção e publicação. O monitor tem limite de 32 envios
pendentes e encerra se um envio falhar ou o limite for atingido. Não há reenvio
automático nem fila persistente. O pipeline alternativo ByteTrack foi removido
após conferir que não era importado pelo monitor principal.

`backend/data/contagem_residuos.json` preserva contagens locais, mas não comprova
entrega ao servidor. `backend/station/station.json` não é sincronizado com PostgreSQL.
O total exibido no dashboard vem dos eventos recebidos, não desses arquivos.

## Dashboard

Interface em português brasileiro, estilo terminal, sem etapa de compilação.
O servidor HTTP entrega os arquivos; a API fornece os dados do PostgreSQL.

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
- **Ambos:** calor com anéis vazados, usando a mesma escala de tamanho proporcional
  às detecções do modo Estações. Os detalhes mostram o total exato.

A referência de contagem, as cores e o raio das manchas estão em
`dashboard/js/config.js`. O tamanho das estações é calculado em
`dashboard/js/markers.js`: diâmetro mínimo de 8 pixels e máximo de 48 pixels,
com área proporcional à contagem entre esses limites. A mesma escala vale
para Estações e Ambos; filtrar localidades não recalcula a referência de 300.
A legenda acompanha o modo e a referência configurada.

A troca entre Calor, Estações e Ambos preserva os filtros ativos e atualiza as
camadas com a mesma lista de estações filtradas. A camada de calor é recolocada
no mapa antes de receber novos dados, e desenhos pendentes são cancelados ao
removê-la. Isso corrige o travamento ao voltar de Estações para Ambos ou Calor,
inclusive em trocas rápidas.

A atualização automática preserva filtros válidos, ampliação e
posição do mapa; inclui novos cadastros e remove estações excluídas. Se a estação
selecionada desaparecer, o painel limpa a seleção. Falhas de rede preservam os dados
anteriores e exibem aviso e horário da última atualização; há novas tentativas,
inclusive se a primeira consulta falhar. Abas em segundo plano podem atrasar os ciclos.

Para conferir a troca de camadas, selecione estado, município e distrito e
alterne Estações → Ambos → Calor → Ambos. Os filtros devem continuar ativos;
Estações e Ambos devem mostrar tamanhos diferentes para contagens diferentes.
Busque também uma estação oculta pelo filtro: a busca deve limpar os filtros
necessários e, se estiver em Calor, mudar para Ambos. Após atualizar os arquivos
do dashboard, recarregue com Ctrl+Shift+R para carregar o JavaScript novo.

O horário no cabeçalho indica a última consulta bem-sucedida à API, não a última
comunicação de cada câmera. O tempo de atividade mede a sessão da página no navegador,
não o tempo de execução da API ou da Raspberry Pi. A interface de cadastro/exclusão
fica em `/crud.html`; não há formulário de edição de estação.

## Limitações atuais

Os novos eventos incluem `direction: "positive" | "negative"`. A API armazena o
campo em `detection_events` e retorna `by_direction` (todas as classes) e
`by_type_direction` (por classe) no resumo. Os popups usam apenas a classe `bottle`
nos contadores de sentido; o bloco lateral de sentidos foi removido. Eventos antigos sem esse campo ficam em `unknown`;
não é possível reconstruir seu movimento apenas pela contagem. O esquema
PostgreSQL criado pela API já inclui `direction`, que aceita `NULL`. A criação
automática das tabelas não transfere dados de uma instalação MongoDB. Após
atualizar, reinicie a API e o monitor e recarregue o dashboard.

- Os totais representam todos os eventos armazenados, sem filtro por período.
  O total é calculado de `detection_events`; não há coluna `stations.detections`
  no PostgreSQL. Os arquivos locais da estação não alteram os totais da API.
- Excluir uma estação define `stations.is_active = FALSE`, preservando seu cadastro
  e seus eventos. Ela deixa de aparecer na listagem e não pode receber detecções.
  Cadastrar novamente o mesmo ID reativa a estação, atualiza localização e campos
  administrativos e faz os totais históricos reaparecerem.
- A API valida o ID no cadastro, mas não valida integralmente localização e
  campos administrativos. Use GeoJSON `Point` com `[longitude, latitude]` numéricos
  e nomes administrativos consistentes; registros incompletos podem quebrar o mapa.
- A API não tem autenticação e aceita CORS amplo. A execução descrita é de um
  protótipo em ambiente controlado; não representa uma implantação pública pronta.
- Cada consulta geral agrupa os eventos com SQL (`COUNT` e `MAX`) por estação,
  classe e sentido, retornando o horário mais recente de cada grupo.
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
| `ssd_mobilenet.detection_types` / `detection.detection_types` | Classes procuradas no modelo ativo; objetos fora das cinco classes de resíduos exigem `--testes` para entrar na contagem |
| `display.enabled` | Exibição de vídeo; `--display` e `--no-display` sobrescrevem o JSON |
| `image_processing` | Limites de tamanho do frame enviado ao detector |
| `tracking` | Linha proporcional, direção e associação por centróide |

O JSON usa `http://127.0.0.1:8000` para execução local. Na estação remota, use
um IP ou hostname do servidor. `0.0.0.0` serve para o Uvicorn escutar em todas
as interfaces; não é o endereço de destino dos clientes.

`AQUADETECTOR_API_URL` sobrescreve o JSON e tem prioridade sobre
`BOTTLE_COUNT_API_URL`. `BOTTLE_COUNT_STATION_ID` sobrescreve a estação.
`AQUAMONITOR_CONFIG` define o arquivo padrão. Não há leitura automática de `.env`.

O monitor publica cada cruzamento. `backend.enabled`,
`backend.publish_interval_seconds`, `bytetrack`, `BOTTLE_COUNT_API_ENABLED` e
`BOTTLE_COUNT_PUBLISH_INTERVAL` foram retirados do fluxo e da configuração:
serviam apenas ao pipeline paralelo. Não há opção `--publish`.

## Banco de dados PostgreSQL

O servidor usa `psycopg` 3, instalado por `psycopg[binary]>=3.2.0` em
`requirements-server.txt`. MongoDB e PyMongo não são dependências da API atual.
Somente a API conecta ao banco; a estação e o dashboard usam HTTP.

| Configuração | Valor ou comportamento |
|---|---|
| Variável da API | `AQUAMONITOR_DATABASE_URL` |
| URL padrão, se a variável estiver ausente | `postgresql://postgres:postgres@localhost:5432/aquamonitor` |
| Banco do roteiro manual de testes | `aquamonitor_local_test` (separado do padrão `aquamonitor`) |
| Porta usada nos exemplos | `5432` |
| Carregamento de configuração | Ambiente do processo da API; não lê `aquamonitor.json` nem carrega `.env` automaticamente |
| Extensão geográfica | PostGIS não é necessário; coordenadas ficam em colunas numéricas |

O usuário e o banco precisam existir antes de iniciar o Uvicorn. No startup,
`initialize_database()` em `backend/app.py` cria as tabelas e o índice abaixo
quando ainda não existem. O usuário da conexão precisa de permissão para criar
esses objetos. O startup também acrescenta `stations.is_active` se essa coluna
estiver ausente; não é um mecanismo geral de migração de esquemas antigos.

| Tabela | Colunas e restrições principais |
|---|---|
| `stations` | `station_id` é chave primária `BIGINT` positiva; `longitude` e `latitude` são `DOUBLE PRECISION`; `country`, `state`, `city` e `district` são textos; `is_active` é booleano obrigatório, com padrão `TRUE` |
| `detection_events` | `event_id` é chave primária `TEXT`; `station_id` referencia `stations`; `detection_type` tem até 100 caracteres; `confidence` fica entre 0 e 1; `track_id` é não negativo; `detected_at` usa `TIMESTAMPTZ`; `direction` aceita `positive`, `negative` ou `NULL` |

O índice `station_id_detected_at_desc` cobre `(station_id, detected_at DESC)`.
A API reconstrói `location` como GeoJSON `Point` com `[longitude, latitude]` e
`administrative` como objeto JSON nas respostas; esses objetos não são armazenados
como documentos no banco. Os resumos usam `COUNT(*)` e `MAX(detected_at)` sobre
os eventos, com horários retornados em UTC. `direction = NULL` aparece como
`unknown` nos resumos. Não há tabela de totais acumulados.

## Migração do MongoDB para PostgreSQL

A mudança da conexão não importa coleções antigas. Esta árvore não fornece um
script de migração MongoDB → PostgreSQL. Uma instalação nova começa sem estações
e sem eventos; os arquivos locais do monitor não são importados automaticamente.

Para preservar uma instalação anterior:

1. Interrompa os monitores e a API antiga para estabilizar os dados e faça um backup
   do MongoDB antes de preparar a transferência.
2. Prepare o PostgreSQL conforme o setup abaixo e inicie a nova API para criar o
   esquema. Use uma base de destino separada para validar a importação.
3. Exporte e transforme os cadastros: preserve `station_id`, separe
   `location.coordinates` em `longitude` e `latitude` e mapeie `administrative`
   para as colunas de mesmo nome. Cadastre as estações antes dos eventos por causa
   da chave estrangeira. `_id`/`ObjectId` do MongoDB não têm coluna correspondente.
4. Transfira os eventos preservando `event_id`, `station_id`, `detection_type`,
   `confidence`, `track_id` e `detected_at`. Converta os horários para instantes
   com fuso explícito. Preserve `direction` quando informado e use `NULL` quando
   ausente. Resolva IDs duplicados e referências a estações ausentes antes da carga.
   A API permite cadastrar estações e publicar eventos pelas rotas documentadas
   em `/docs`; uma carga SQL exige transformar os dados para o esquema acima.
5. Compare cadastros, quantidades de eventos, totais por estação e última detecção
   entre origem e destino. Contadores agregados antigos, sem eventos individuais,
   não permitem reconstruir horários, tracks ou sentidos; não os converta em
   eventos artificiais. Os totais atuais dependem dos eventos importados.
6. Configure `AQUAMONITOR_DATABASE_URL` no processo ou serviço da nova API, valide
   as consultas e retome os monitores apontando para ela. Preserve o backup da
   origem até concluir a validação.

O script legado `backend/test_mongodb.py` e o export de exemplo `stations.json`
foram removidos. Nenhum teste ou comando de execução atual usa PyMongo ou acessa
MongoDB. A transferência de uma instalação anterior deve ser preparada fora do
fluxo de execução e validada antes de apontar a API para a base de destino.

## Setup e testes locais

Neste roteiro, PostgreSQL, API, câmera e navegador ficam no **mesmo computador**.
Use uma cópia de desenvolvimento do projeto e um banco exclusivo para testes.
Os comandos abaixo usam Bash em Debian/Ubuntu e devem ser executados na pasta
que contém `aquamonitor.json`, os arquivos `requirements-*.txt`, `backend/` e
`dashboard/`.
Ajuste `~/aquamonitor` ao caminho da sua cópia.

### 1. Preparar o ambiente e escolher as dependências

Use Python 3.11 ou superior para a API. Python 3.12 foi usado na validação da
limpeza; OpenCV, PyTorch e Ultralytics também precisam atender à versão de Python
e à arquitetura da máquina.

```bash
cd ~/aquamonitor
sudo apt update
sudo apt install python3-venv python3-pip libgl1 libglib2.0-0 curl
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-server.txt -r requirements-cv.txt
python -m pip check
```

| Arquivo | Quando instalar |
|---|---|
| `requirements-server.txt` | API PostgreSQL e cliente HTTP dos testes de integração; dashboard usa a biblioteca padrão do Python |
| `requirements-cv.txt` | Estação: câmera, SSD/YOLO, processamento de imagem e comunicação HTTP, sem componentes da API |

Os dois arquivos ficam na raiz e são independentes. Para servidor e estação na
mesma máquina, ou para a suíte completa de testes, instale ambos como no comando
acima. Para testar apenas a API com PostgreSQL descartável, basta o arquivo do
servidor. `requirements-cv.txt` inclui Ultralytics e suas dependências de
inferência, mesmo quando os testes simulam os resultados do YOLO. O mesmo arquivo
fixa PyTorch `2.10.0+cpu` e Torchvision `0.25.0+cpu`, obtidos do índice oficial
CPU, para evitar instalar CUDA/cuDNN tanto no computador Linux x86_64 quanto na
estação Linux ARM64. Não é preciso um requirements diferente por máquina.

Instalar essa seleção CPU não remove automaticamente bibliotecas NVIDIA que já
estejam no ambiente. Versões atuais do Ultralytics também podem instalar
`nvidia-ml-py`, um pacote pequeno de monitoramento, separado das bibliotecas CUDA.
A seleção CPU se refere ao PyTorch; não transforma os testes simulados em uma
validação do modelo real na Raspberry Pi.

Execute os comandos a partir da raiz `aquamonitor/`, onde está este README.
Os imports internos usam o pacote `backend`, sem prefixos `aquamonitorPH` ou
`comparacao`. Inicie o monitor com `python -m backend.monitoring.monitor_residuos`
e os testes com `python -m unittest`; não execute os arquivos internos diretamente
por caminho. Ative `.venv` em cada terminal que executar Python.

MongoDB, PyMongo,
Supervision e ByteTrack não fazem parte deste setup. Não há compilação do
dashboard, `npm install` ou instalação separada de TensorFlow para o SSD.

### 2. Executar os testes antes de iniciar os serviços

```bash
python -m unittest discover -s backend -t . -v
```

Essa execução não abre câmera nem conecta ao banco da aplicação. Na validação
das alterações, passaram **41 testes unitários**; os **12 testes PostgreSQL**
são ignorados nessa execução e executados na próxima etapa. Os testes cobrem
contrato dos eventos, configuração, linha e sentidos, associação de confiança
ao objeto, envio, contagens locais e encerramento. Incluem o argumento `--testes`,
a ausência de contagem de celulares sem ele, o agrupamento de objetos de teste
nos dois modos e a preservação de classes distintas durante o rastreamento.
Um teste carrega o SSD real com imagem sintética. O adaptador YOLO usa resultados simulados; os
pesos reais e a precisão na câmera precisam do teste manual ao final.

Para o dashboard, com Node.js 22 ou superior:

```bash
node --test dashboard/tests/*.mjs
```

Na validação das correções do dashboard, passaram **7 testes**. Eles verificam
filtros, atualização da API, intensidade do calor, escala proporcional dos
marcadores nos dois modos e troca de camadas com cancelamento de desenhos
pendentes. Node.js é necessário apenas para os testes; o painel é servido pelo
Python.

Também foi validado em navegador real com Leaflet e 50 estações simuladas:
trocas normais e rápidas de camadas, filtro por município, busca de estação
oculta pelo filtro e atualização automática. Os anéis de Ambos mantiveram os
mesmos tamanhos de Estações, sem erros de JavaScript. Essa verificação usou
respostas simuladas da API; a integração com banco e câmera segue as etapas
abaixo. Consulte o [roteiro do dashboard](dashboard/VALIDATION.md) para repetir
a conferência manual.

### 3. Validar a API com PostgreSQL descartável

Instale os binários de servidor e cliente PostgreSQL:

```bash
sudo apt install postgresql postgresql-client
ls /usr/lib/postgresql/
python scripts/test_postgresql.py --pg-bin /usr/lib/postgresql/16/bin
```

Troque `16` pela versão instalada. Se `initdb` e `pg_ctl` já estiverem no `PATH`,
use apenas `python scripts/test_postgresql.py`. Execute como **usuário comum**,
com a venv ativa; `initdb` não aceita execução como root.

O runner cria seu próprio cluster em diretório temporário, sem escuta TCP, e
usa somente um socket Unix exclusivo. Ele ignora as variáveis de conexão
herdadas, cria `aquamonitor_test`, executa os testes e encerra/remove esse cluster.
Não exige que o serviço PostgreSQL do sistema esteja ativo. **Não passe uma URL
de banco existente nem inicie o Uvicorn para esta etapa.**

Na validação após a correção dos imports, passaram **12 testes de integração**,
com HTTP via ASGI
`TestClient` e SQL real: persistência, duplicação inclusive concorrente, resumos
por classe/sentido, horários com fuso, restrições, reinicialização e
exclusão/reativação de estações. Esse runner usa Linux/Unix.

### 4. Criar um banco separado para o teste manual

O cluster da etapa anterior é removido ao terminar e não alimenta o dashboard.
Para o teste interativo com API, navegador e câmera, use outro banco dedicado:

```bash
sudo systemctl start postgresql
sudo -u postgres createuser --pwprompt aquamonitor_dev
sudo -u postgres createdb --owner=aquamonitor_dev aquamonitor_local_test
```

Esses comandos são para a primeira criação. Se o usuário e o banco de testes já
existirem, reutilize-os sem repetir `createuser` e `createdb`. Não use uma base de
produção nem altere a senha do usuário administrativo `postgres` para seguir o
roteiro. Os exemplos abaixo usam `SENHA` como marcador: substitua pela senha do
usuário `aquamonitor_dev`. Caracteres reservados da senha na URI, como `@`, `:` e
`/`, precisam de codificação percentual.

#### Iniciar o banco após a primeira criação

Nas próximas execuções, inicie apenas o serviço PostgreSQL e confira seu estado:

```bash
sudo systemctl start postgresql
systemctl status postgresql --no-pager
```

O usuário `aquamonitor_dev`, o banco `aquamonitor_local_test` e seus dados
permanecem salvos entre as execuções. Não repita `createuser` ou `createdb`.
Se o serviço já estiver ativo, o comando `start` mantém sua execução.

Depois, siga a etapa 5 para definir `AQUAMONITOR_DATABASE_URL`, confirmar a
conexão com `psql` e iniciar a API. Iniciar o PostgreSQL não inicia a API nem o
dashboard.

### 5. Iniciar a API — terminal 1

```bash
cd ~/aquamonitor
source .venv/bin/activate
export AQUAMONITOR_DATABASE_URL='postgresql://aquamonitor_dev:SENHA@127.0.0.1:5432/aquamonitor_local_test'
psql "$AQUAMONITOR_DATABASE_URL" -c 'SELECT current_database(), current_user;'
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Confirme que `psql` mostrou **aquamonitor_local_test**. Mantenha o Uvicorn aberto;
a API cria as tabelas e os índices no startup. Abra **http://127.0.0.1:8000/docs**.
O export precisa estar no terminal que inicia a API; `.env` e `aquamonitor.json`
não configuram sua conexão PostgreSQL. Reinicie a API após mudar a variável.

### 6. Cadastrar a estação — terminal auxiliar

```bash
cd ~/aquamonitor
source .venv/bin/activate
curl --fail-with-body http://127.0.0.1:8000/api/stations
curl --fail-with-body -X POST http://127.0.0.1:8000/api/stations \
  -H 'Content-Type: application/json' \
  -d '{"station_id":1,"location":{"type":"Point","coordinates":[-46.4526,-23.5015]},"administrative":{"country":"Brazil","state":"São Paulo","city":"Santos","district":"Baía de Santos"}}'
curl --fail-with-body http://127.0.0.1:8000/api/stations/1/detections
```

Uma listagem inicial `[]` é válida. Use as coordenadas reais da estação no cadastro,
na ordem `[longitude, latitude]`. HTTP 409 no cadastro significa que esse ID já
está ativo; confira a listagem e reutilize-o para o teste. Não é necessário
excluir/recriar a estação para repetir a validação. Uma base nova retorna total
zero; uma base de testes reutilizada pode ter histórico. Os arquivos locais da
estação não criam esse cadastro e não definem o total da API.

### 7. Iniciar e conferir o dashboard — terminal 2

```bash
cd ~/aquamonitor
source .venv/bin/activate
python serve_dashboard.py
```

Abra **http://127.0.0.1:3000/** e busque o ID 1. O cadastro/exclusão também fica em
**http://127.0.0.1:3000/crud.html**. Na configuração fornecida com esta versão,
`dashboard/js/api.js` e as duas URLs de `dashboard/js/crud.js` apontam para
`http://127.0.0.1:8000/api/stations`; confira esses destinos se tiver editado sua
cópia anteriormente. O navegador precisa de internet para Leaflet e os mapas.

O cabeçalho deve mostrar o horário da última consulta bem-sucedida. O painel
consulta a API novamente cinco segundos após concluir a consulta anterior; não
é necessário recarregar para receber eventos. Anote o total inicial da estação.
Após editar HTML/JS/CSS, use Ctrl+Shift+R para carregar os arquivos novos.

### 8. Conferir ingestão e duplicação sem câmera — opcional

No terminal auxiliar, com a venv ativa e **a API do banco de testes acima**
executando, este comando cria um evento sintético com ID novo e tenta repeti-lo:

```bash
python - <<'PYCODE'
from datetime import datetime, timezone
import uuid
import requests

base = "http://127.0.0.1:8000"
summary_url = f"{base}/api/stations/1/detections"
before_response = requests.get(summary_url, timeout=10)
before_response.raise_for_status()
before = before_response.json()["total"]
event = {
    "event_id": str(uuid.uuid4()), "station_id": 1,
    "detection_type": "bottle", "confidence": 0.9, "track_id": 1,
    "direction": "positive", "detected_at": datetime.now(timezone.utc).isoformat(),
}
first = requests.post(f"{base}/api/detections", json=event, timeout=10)
assert first.status_code == 201, first.text
duplicate = requests.post(f"{base}/api/detections", json=event, timeout=10)
assert duplicate.status_code == 409, duplicate.text
after_response = requests.get(summary_url, timeout=10)
after_response.raise_for_status()
after = after_response.json()
assert after["total"] == before + 1, after
print("Ingestão: 201; duplicação: 409; total aumentou uma vez.")
print(after)
PYCODE
```

Pare qualquer monitor durante esse teste para que nenhum outro evento altere a
comparação. O evento sintético permanece **no banco de testes** e aparece no
painel; anote a nova contagem antes do teste da câmera. A suíte descartável da
etapa 3 valida exclusão/reativação sem modificar essa base interativa.

### 9. Iniciar o monitor — terminal 3

Conecte a câmera USB e feche outros programas ou serviços que estejam usando-a.
Confira os modelos na cópia do projeto:

```bash
cd ~/aquamonitor
source .venv/bin/activate
ls -lh backend/detection/models/
export AQUADETECTOR_API_URL=http://127.0.0.1:8000
export BOTTLE_COUNT_STATION_ID=1
python -m backend.monitoring.monitor_residuos --detector ssd --display
```

O SSD precisa de `frozen_inference_graph.pb`,
`ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt` e `coco.names`. Para testar YOLO,
encerre o SSD e substitua `--detector ssd` por `--detector yolo`; ele usa
`best (1).pt` e executa em CPU. Sem `--detector`, o padrão é YOLO. Para operação
sem janela, **substitua** `--display` por `--no-display`.
Para usar o celular configurado no SSD como objeto de teste, acrescente
`--testes`. Sem esse argumento, apenas as cinco classes de resíduos podem
ser rastreadas e contadas.

Revise `camera.device_index`, `station_id` e os dados de `station_document` em
`aquamonitor.json`. O arquivo `backend/station/station.json`, se existir,
preserva seus dados locais; confira também seu ID e localização. O exemplo pode
conter uma contagem histórica local diferente da contagem do banco. Para outra
estação, prepare uma cópia de execução própria; o caminho de contagens do monitor
é fixo em `backend/data/contagem_residuos.json`. Não compartilhe essa cópia entre
dois monitores nem apague contagens existentes apenas para zerar um teste.

### 10. Validar a contagem e encerrar

1. Anote os totais atuais da estação no painel ou em
   `GET /api/stations/1/detections`.
2. Passe uma garrafa por vez pela linha amarela. Apenas aparecer na imagem não
   gera evento. O terminal deve mostrar `Contado: bottle ...`.
3. Compare o **incremento**, não o total absoluto, em `total` e `by_type.bottle`.
   Com `tracking.direction: "both"`, cima → baixo incrementa
   `by_type_direction.bottle.positive`; baixo → cima incrementa `negative`.
   Cada track conta uma vez, e os negativos também somam ao total.
4. Confira o popup da estação, o calor e a classificação no próximo ciclo de
   atualização. Se necessário, consulte a API com o `curl` da etapa 6.
5. Encerre primeiro o monitor com Q, Esc ou Ctrl+C e aguarde os envios. Depois
   interrompa dashboard e API com Ctrl+C nos respectivos terminais.

Falhas HTTP ou 32 envios pendentes encerram o monitor: corrija a conexão e
reinicie-o. O painel tenta reconectar sozinho; o monitor não. Os arquivos locais
não reenviam automaticamente eventos perdidos.

### Alternativa no Windows

Para API e monitor, use um Python compatível com as dependências e câmera USB.
No PowerShell, a preparação equivalente é:

```powershell
cd C:\caminho\para\aquamonitor
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-server.txt -r requirements-cv.txt
python -m unittest discover -s backend -t . -v
```

Instale e prepare PostgreSQL separadamente, com o usuário e banco de testes da
etapa 4. Em cada novo terminal, ative a venv. No terminal da API:

```powershell
$env:AQUAMONITOR_DATABASE_URL="postgresql://aquamonitor_dev:SENHA@127.0.0.1:5432/aquamonitor_local_test"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

No terminal do monitor:

```powershell
$env:AQUADETECTOR_API_URL="http://127.0.0.1:8000"
$env:BOTTLE_COUNT_STATION_ID="1"
python -m backend.monitoring.monitor_residuos --detector ssd --display
```

O monitor seleciona DirectShow no Windows e V4L2 no Linux. Os blocos Bash deste
README não devem ser colados diretamente no PowerShell; para chamadas HTTP, use
`curl.exe` ou a interface `/docs`. O runner PostgreSQL descartável usa socket Unix:
execute essa etapa em um ambiente Linux, como WSL, com sua própria venv e
binários PostgreSQL, sem copiar a venv do Windows.

## Setup e testes entre máquinas

O mesmo monitor principal funciona em outro computador ou em uma Raspberry Pi
com câmera USB. Não há instalação separada em `Embedded/` ou `RaspberryPi/`,
nem dependência de GPS. Use a **mesma versão do código** nas máquinas envolvidas.

### 1. Definir os papéis e os endereços

Neste exemplo, **A** tem IP `192.168.1.100`, **B** captura a câmera e **C** é um
navegador opcional em outro dispositivo. Substitua o IP pelo endereço real de A.

| Máquina | Executa | Instalação Python | Destino que utiliza |
|---|---|---|---|
| A — servidor | PostgreSQL, API e servidor estático | `requirements-server.txt` | API conecta ao PostgreSQL local |
| B — estação | Câmera, SSD/YOLO, rastreador e envio HTTP | `requirements-cv.txt` | `http://192.168.1.100:8000` |
| A — navegador local | Dashboard no próprio servidor | Nenhum pacote adicional | JavaScript consulta `http://127.0.0.1:8000` |
| C — navegador remoto, opcional | Dashboard no navegador | Nenhum Python necessário | JavaScript consulta `http://192.168.1.100:8000` |

```text
B: câmera USB → SSD/YOLO → linha ──HTTP──→ A: API :8000 → PostgreSQL :5432
                                            ↑
                               A ou C: navegador ← dashboard :3000 em A
```

A estação envia eventos JSON, não vídeo. A porta **8000** de A precisa estar
acessível a B. A porta **3000** só precisa estar acessível a outras máquinas se
o navegador for remoto. O PostgreSQL pode continuar restrito a A; B e C não
conectam à porta 5432.

`127.0.0.1` sempre aponta para a própria máquina que faz a conexão.
`0.0.0.0` é endereço de escuta do servidor, não destino da estação ou navegador.

### 2. Em A — preparar e testar o servidor

Em Debian/Ubuntu:

```bash
cd ~/aquamonitor
sudo apt update
sudo apt install python3-venv python3-pip postgresql postgresql-client curl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-server.txt
python -m pip check
hostname -I
```

A não precisa instalar os modelos, OpenCV ou Ultralytics para servir apenas a
API e o painel. Para executar a suíte automatizada também em A, instale
`requirements-cv.txt` e siga as etapas 2 e 3 do
[setup local](#setup-e-testes-locais). Isso instala as dependências de visão
computacional, incluindo Ultralytics/PyTorch; os testes não abrem câmera nem
executam inferência YOLO real. Para executar somente os testes PostgreSQL da
etapa 3, `requirements-server.txt` é suficiente e não são necessários modelos.
Para a suíte completa, mantenha também os três arquivos do modelo SSD em
`backend/detection/models/`: um dos testes carrega esse modelo real, mesmo que A
não execute o monitor.

Prepare o usuário `aquamonitor_dev` e o banco `aquamonitor_local_test` conforme a
etapa 4 do setup local. No **terminal 1 de A**, inicie a API na rede:

```bash
cd ~/aquamonitor
source .venv/bin/activate
export AQUAMONITOR_DATABASE_URL='postgresql://aquamonitor_dev:SENHA@127.0.0.1:5432/aquamonitor_local_test'
psql "$AQUAMONITOR_DATABASE_URL" -c 'SELECT current_database(), current_user;'
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Em outro terminal de A:

```bash
curl --fail-with-body http://127.0.0.1:8000/api/stations
```

Cadastre o ID 1 com o comando da etapa 6 do setup local ou usando
**http://127.0.0.1:8000/docs**. A estação deve existir **antes** de iniciar B.
Para várias estações, use IDs distintos e cadastre cada uma. Uma estação
excluída precisa ser recadastrada para voltar a receber eventos.

### 3. Em A — configurar o dashboard para o navegador escolhido

Os arquivos JavaScript são servidos por A e executados na máquina do navegador.
Ajuste **na cópia de A** estes três destinos:

| Local | Navegador em A | Navegador em C ou na estação B |
|---|---|---|
| `dashboard/js/api.js`: `api_url` | `http://127.0.0.1:8000/api/stations` | `http://192.168.1.100:8000/api/stations` |
| `dashboard/js/crud.js`: URL de cadastro | `http://127.0.0.1:8000/api/stations` | `http://192.168.1.100:8000/api/stations` |
| `dashboard/js/crud.js`: URL de exclusão | Prefixo `http://127.0.0.1:8000/api/stations/` | Prefixo `http://192.168.1.100:8000/api/stations/` |

Na exclusão, preserve a interpolação do ID que já existe no código. Para atender
navegadores locais e remotos com os mesmos arquivos, use o IP de A nas três URLs;
o navegador local também precisa conseguir alcançar esse IP. Mudar exports do
shell ou `aquamonitor.json` não altera as URLs do JavaScript.

No **terminal 2 de A**, para navegador somente local:

```bash
cd ~/aquamonitor
source .venv/bin/activate
python serve_dashboard.py
```

Abra **http://127.0.0.1:3000/** em A. Para permitir navegador remoto, substitua o
último comando por:

```bash
python serve_dashboard.py --bind 0.0.0.0
```

Em C, abra **http://192.168.1.100:3000/** e
**http://192.168.1.100:3000/crud.html**. Confira a atualização e o cadastro na
mesma API. Uma página que abre sem dados pode ter a porta 3000 acessível e a URL
ou porta 8000 incorreta. Após mudar as URLs, faça Ctrl+Shift+R no navegador.

### 4. Em B — preparar a estação e testar a rede

Copie/clone a mesma versão do projeto, incluindo `aquamonitor.json`, `backend/`
e os modelos em `backend/detection/models/`. Crie a venv **em B**: não copie a
venv de A, de outro sistema operacional ou de outra arquitetura.

Em Linux; para Raspberry Pi, use Raspberry Pi OS de 64 bits:

```bash
cd ~/aquamonitor
uname -m
python3 --version
sudo apt update
sudo apt install python3-venv python3-pip libgl1 libglib2.0-0 curl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-cv.txt
python -m pip check
ls -lh backend/detection/models/
export AQUADETECTOR_API_URL=http://192.168.1.100:8000
export BOTTLE_COUNT_STATION_ID=1
curl --fail-with-body --max-time 10 "$AQUADETECTOR_API_URL/api/stations"
```

A resposta deve conter o ID 1. Só inicie a câmera depois que essa consulta
funcionar. Se falhar, confira IP de A, bind `0.0.0.0` da API, porta 8000,
firewall e isolamento da rede Wi-Fi; confirme também a consulta local em A.
Não abra a porta PostgreSQL para resolver um erro de conexão da estação.

Na Pi ARM de 64 bits, `uname -m` deve mostrar `aarch64`. A instalação depende de
pacotes disponíveis para a versão de Python e arquitetura escolhidas. O monitor
USB usa OpenCV/V4L2; não tem capturador próprio Picamera2/libcamera. A precisão
e o desempenho na Pi física não foram validados nesta revisão.

Para uma estação Windows, use a preparação PowerShell do setup local instalando
apenas `requirements-cv.txt`. Defina
`$env:AQUADETECTOR_API_URL="http://192.168.1.100:8000"` e
`$env:BOTTLE_COUNT_STATION_ID="1"` no terminal do monitor. Não é necessário
instalar PostgreSQL, FastAPI ou Uvicorn em B para executar a estação.

### 5. Em B — conferir configuração e iniciar a câmera

Conecte a câmera USB em B e confira a configuração **da cópia de B**:

| Campo | Valor ou verificação |
|---|---|
| `station_id` | ID cadastrado em A; o export pode sobrescrevê-lo |
| `backend.base_url` | IP real de A; `AQUADETECTOR_API_URL` tem prioridade |
| `backend.require_connection_on_startup` | `true` para validar API e cadastro antes da câmera |
| `camera.device_index` | Índice da câmera USB; padrão `0` |
| `tracking.line_y_ratio` | Linha horizontal; padrão `0.55` da altura real |
| `tracking.direction` | `both`, `down` ou `up` |
| `station_document.path` | Documento local da estação; confira ID e localização se o arquivo já existir |
| `display.enabled` | `false` para operação sem janela |

Mantenha um diretório de execução e arquivos de estado próprios por estação.
As contagens locais não são importadas no PostgreSQL. Os exports valem somente
no terminal atual; repita-os ao reabrir o terminal ou configure-os na unidade
systemd, se usar serviço.

No mesmo terminal de B, execute um dos detectores:

```bash
python -m backend.monitoring.monitor_residuos --detector ssd --no-display
```

Para YOLO, encerre o monitor anterior e use:

```bash
python -m backend.monitoring.monitor_residuos --detector yolo --no-display
```

O SSD incluído trabalha com `bottle`; o YOLO filtra `bottle`, `can`, `carton`,
`paper` e `plastic`, conforme as classes do checkpoint. Não há opção `--publish`:
o envio é automático. Execute apenas um monitor por câmera e arquivo de contagens.

Se B tiver sessão gráfica local, substitua `--no-display` por `--display` para
ajustar a linha e o enquadramento. A janela abre em B; o dashboard não recebe o
vídeo. Em SSH sem sessão gráfica, mantenha `--no-display`.

### 6. Validar ponta a ponta e encerrar

1. No navegador em A ou C, busque a estação de B e anote seu total inicial.
2. Passe uma garrafa pela linha da câmera em B e confira `Contado: bottle ...`.
3. Em B ou C, confirme o evento consultando A:

   ```bash
   curl --fail-with-body http://192.168.1.100:8000/api/stations/1/detections
   ```

4. Confira o incremento em `total`, `by_type.bottle` e no sentido correspondente
   de `by_type_direction.bottle`. O painel deve refletir a mesma mudança no
   próximo ciclo. Se a API mudou e o painel não, confira as três URLs do
   JavaScript e a aba Rede/console do navegador.
5. Para várias estações, repita o teste por ID e confira que só a estação que
   enviou o evento teve seu total incrementado.
6. Encerre primeiro o monitor em B e aguarde os envios; depois pare dashboard e
   API em A. Se houver serviços instalados, use os comandos da seção seguinte.

O dashboard tenta recuperar falhas de consulta automaticamente. O monitor
encerra após falha de envio ou fila cheia; restaure a conexão e reinicie-o.
Não considere o JSON local como confirmação de entrega. Se o IP de A mudar,
atualize os destinos da estação e do JavaScript conforme o cenário.

## Controle dos serviços

O repositório fornece unidades systemd em `deploy/systemd/` para iniciar
PostgreSQL, API e dashboard com um comando. O reconhecimento da câmera continua
manual. O setup manual das seções anteriores não instala essas unidades.

### Instalar a inicialização conjunta nesta máquina

As unidades fornecidas usam o usuário Linux `vyzxc`, a pasta
`/home/vyzxc/aquamonitor` e o Python de `.venv/bin/python`. Em outra máquina,
ajuste `User`, `WorkingDirectory`, `ExecStartPre` e `ExecStart` nos arquivos
`.service`, além de `project_dir` e do usuário verificado em `install.sh`.

Antes de instalar, a `.venv` deve conter `requirements-server.txt`, e o usuário
PostgreSQL `aquamonitor_dev` deve poder acessar o banco **aquamonitor** e criar
suas tabelas. Os serviços reutilizam o banco existente; não criam usuário ou
banco e não executam instalações de dependências.

A conexão fica no arquivo local `deploy/systemd/.env.api`, ignorado pelo Git.
Ele já foi preparado nesta cópia com as credenciais informadas. Em um clone novo:

```bash
cp deploy/systemd/.env.example deploy/systemd/.env.api
chmod 600 deploy/systemd/.env.api
nano deploy/systemd/.env.api
```

Preencha `AQUAMONITOR_DATABASE_URL` com o usuário `aquamonitor_dev`, a senha real
e o banco `aquamonitor`, conforme o modelo. O instalador copia esse arquivo
para `/etc/aquamonitor/api.env`, com permissão `600`, somente na primeira
instalação. Reinstalações preservam a configuração já existente nesse destino.

Pare a API e o dashboard que estiverem abertos nos terminais, liberando as
portas 8000 e 3000. A partir da raiz do projeto, instale e inicie:

```bash
sudo bash deploy/systemd/install.sh
sudo systemctl start aquamonitor.target
```

Abra **http://127.0.0.1:3000/** para o dashboard e
**http://127.0.0.1:8000/docs** para a API. Os serviços escutam somente nesta
máquina, como no setup local. A câmera não é iniciada pelo target.

A API aguarda uma conexão PostgreSQL válida por até 60 segundos antes de abrir
o Uvicorn. A API e o dashboard reiniciam em caso de falha, com intervalo de cinco
segundos. Seus processos executam como `vyzxc`, sem precisar ativar a `.venv`
no terminal. A senha é carregada pelo systemd a partir de `api.env`.

Nas próximas execuções, basta usar:

```bash
sudo systemctl start aquamonitor.target
sudo systemctl stop aquamonitor.target
sudo systemctl restart aquamonitor.target
systemctl status aquamonitor-api.service aquamonitor-dashboard.service --no-pager
sudo journalctl -u aquamonitor-api.service -u aquamonitor-dashboard.service -f
```

`stop aquamonitor.target` para API e dashboard e mantém o PostgreSQL disponível.
Para parar também o banco, execute `sudo systemctl stop postgresql` depois.
Para iniciar o conjunto automaticamente ao ligar o computador:

```bash
sudo systemctl enable --now aquamonitor.target
```

Para alterar credenciais depois da instalação, execute
`sudoedit /etc/aquamonitor/api.env` e depois
`sudo systemctl restart aquamonitor-api.service`. Para atualizar as unidades do
repositório, rode novamente o instalador e reinicie o target. O instalador apenas
grava as unidades e recarrega o systemd; não inicia os serviços nem habilita o
boot automaticamente.

### Conferir unidades disponíveis

Os comandos seguintes também servem para instalações próprias. Substitua os
nomes se usou outros, como `dashboard.service`. Confira as unidades disponíveis:

```bash
systemctl list-unit-files 'aquamonitor*' 'dashboard.service' 'postgresql.service'
```

### Computador: API, dashboard e PostgreSQL

```bash
# Iniciar
sudo systemctl start postgresql.service aquamonitor-api.service aquamonitor-dashboard.service

# Consultar o estado dos processos
systemctl status postgresql.service aquamonitor-api.service aquamonitor-dashboard.service --no-pager

# Interromper API e dashboard
sudo systemctl stop aquamonitor-api.service aquamonitor-dashboard.service

# Interromper PostgreSQL, se não estiver sendo usado por outras aplicações
sudo systemctl stop postgresql.service

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

### Conferir o Uvicorn iniciado manualmente

Se a API foi iniciada no terminal com `python -m uvicorn`, confira o processo
e a resposta HTTP:

```bash
pgrep -af uvicorn
curl -i --max-time 10 http://127.0.0.1:8000/api/stations
```

`pgrep` mostra se há um processo com esse nome; uma resposta HTTP 200 confirma
que a rota da API respondeu. Quando a API é executada como serviço, use
`systemctl status aquamonitor-api.service --no-pager` e os logs mostrados acima.

### Máquina da estação: monitor da câmera

O target fornecido não inclui um serviço de câmera. Se você instalou por conta
própria um serviço de captura chamado `aquamonitor.service`, use:

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
# Exemplo na estação Linux: iniciar agora e também nos próximos boots
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

No servidor, use o nome da unidade correspondente. Configure
`AQUAMONITOR_DATABASE_URL` na unidade da API, por `Environment=` ou
`EnvironmentFile=`; exports no terminal não configuram serviços. Na unidade da
estação, configure o endereço da API e o ID usados pelo monitor. `stop` interrompe a execução
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

# Objetos de teste selecionados no JSON, com contador testes habilitado
python -m backend.monitoring.monitor_residuos --detector ssd --display --testes

# Testes isolados do monitor, com dependências da estação
python -m unittest backend.tests.test_monitor backend.tests.test_count_categories backend.tests.test_image_processing -v

# No terminal com AQUAMONITOR_DATABASE_URL configurada:
# Verificar conexão e listar as tabelas após o primeiro startup da API
psql "$AQUAMONITOR_DATABASE_URL" -c 'SELECT current_database(), current_user;'
psql "$AQUAMONITOR_DATABASE_URL" -c '\dt'

# Conferir cadastros, incluindo estações desativadas
psql "$AQUAMONITOR_DATABASE_URL" -c 'SELECT station_id, is_active FROM stations ORDER BY station_id;'

# Conferir totais persistidos e última detecção por estação
psql "$AQUAMONITOR_DATABASE_URL" -c 'SELECT station_id, COUNT(*) AS total, MAX(detected_at) AS last_detected_at FROM detection_events GROUP BY station_id ORDER BY station_id;'
```

| Sintoma | Verificação |
|---|---|
| API não inicia por falha no banco | Conferir `AQUAMONITOR_DATABASE_URL` no processo da API, serviço PostgreSQL e porta 5432; testar com `psql` |
| `role "vyzxc" does not exist` ou nome do usuário Linux no erro do `psql` | Definir `AQUAMONITOR_DATABASE_URL` no mesmo terminal, com o usuário `aquamonitor_dev` e o banco corretos; uma URL vazia faz o `psql` usar os padrões locais |
| `password authentication failed` ou banco inexistente | Conferir usuário, senha codificada na URI, nome do banco e regras de autenticação do PostgreSQL |
| `permission denied for schema` ou tabelas ausentes | Conferir proprietário/permissões do banco e logs do startup que cria as tabelas |
| `relation` ou coluna ausente após reutilizar banco antigo | Comparar o esquema com `initialize_database()`; `CREATE TABLE IF NOT EXISTS` não atualiza todas as colunas de tabelas preexistentes |
| `ModuleNotFoundError: backend` ou `aquamonitorPH` | Executar a partir da raiz com os comandos `python -m` deste README e usar a versão atual dos testes, cujos imports começam por `backend` |
| `ModuleNotFoundError: psycopg` | Ativar a `.venv` correta e instalar `requirements-server.txt` |
| Conexão recusada ou timeout HTTP | IP real do computador, API ativa na porta 8000, rede e firewall |
| Estação não encontrada | Cadastrar o mesmo `station_id`; arquivos JSON locais não criam cadastro |
| Qt/Wayland ao abrir janela | Executar o monitor com `--no-display` ou usar sessão gráfica compatível |
| Câmera não abre | Índice em `camera.device_index`, conexão, permissões e uso por outro processo |
| Modelo não encontrado | Presença dos pesos e caminhos relativos ao arquivo de configuração |
| Celular não é contado | Usar SSD, manter `cell phone` em `ssd_mobilenet.detection_types`, iniciar com `--testes` e cruzar a linha; o checkpoint YOLO incluído não conhece celulares |
| Contagem local diferente do painel | Painel soma eventos recebidos; JSON local pode conter histórico ou envios que falharam |
| Dashboard antigo após alteração | Conferir a pasta servida e o cache do navegador, conforme abaixo |
| Mapa sem manchas | Conferir eventos na API; estações zeradas não geram calor |
| Travamento ao alternar camadas ou anéis com tamanho fixo em Ambos | Usar as versões atualizadas de `heatmap.js`, `markers.js` e `main.js`; recarregar com Ctrl+Shift+R e repetir a troca com os filtros ativos |

### Arquivos antigos no navegador

Execute o servidor a partir da raiz correta. Para eliminar ambiguidade, use um
caminho absoluto (ajuste ao seu clone):

```bash
python /caminho/para/aquamonitor/serve_dashboard.py
curl -s http://127.0.0.1:3000/ | grep -E 'mapMode|systemStatus'
```

Os dois identificadores devem existir no HTML atual. Se estiverem ausentes, confira
qual processo usa a porta 3000 e qual pasta ele serve. Se estiverem presentes,
abra as ferramentas do navegador (F12), marque **Desativar cache** na aba **Rede**
e recarregue com Ctrl+Shift+R. A opção vale enquanto as ferramentas estão abertas.
A atualização automática de dados não substitui o recarregamento após editar JS/CSS/HTML.

### Organização atual do projeto

Esta versão mantém o fluxo em `backend/` e `dashboard/`. Não depende de árvores
`Embedded/`, `RaspberryPi/` ou de GPS. Raspberry Pi continua sendo um equipamento
compatível com o monitor USB principal; não há uma segunda implementação para ela.

Mais detalhes: [monitor](backend/MONITOR.md) e
[comparação, remoções e resultados](COMPARACAO_VALIDACAO.md).

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
