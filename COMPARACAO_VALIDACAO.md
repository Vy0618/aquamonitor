# Comparação e validação da versão PH

Revisão de 29/10/2026. Referência: `../aquamonitorV/`. Todas as alterações de
projeto foram feitas em `aquamonitorPH/`; a referência foi conferida por SHA-256
antes e depois, sem alterações. Não houve push nem acesso a banco existente.

## Rastreio antes da remoção

| Entrada | Dependências necessárias e configuração |
|---|---|
| `uvicorn backend.app:app` | FastAPI, Pydantic e Psycopg; `AQUAMONITOR_DATABASE_URL`; startup PostgreSQL cria `stations`, `detection_events`, coluna `is_active` e índice por estação/horário |
| `python -m backend.monitoring.monitor_residuos` | `settings`, `camera.webcam_config`, `camera.image_processing`, `detection.types`, `detection.yolo_detector`, import tardio de `detection.ssd_mobilenet_detector`, `tracking.line_tracker`, `communication.backend_client`, `station.station_document` |
| `monitor_ssd_mobilenet` e `monitor_ssd_mobilenet_local` | Encaminham à função `main` do monitor principal com SSD; preservados como atalhos sem implementação paralela |
| `aquamonitor.json` | Modelos SSD/YOLO, captura, contagem, endereço HTTP, apresentação e documento local; caminhos resolvidos em relação ao arquivo de configuração |
| `serve_dashboard.py` → `dashboard/index.html` → `js/main.js` | `api`, `labels`, `config`, `filters`, `heatmap`, `map`, `markers`, `uptime`, `zoom`, `station-search`, `city-ranking`; `markers` também usa `directions` |
| `dashboard/crud.html` | `js/crud.js` e `cadastro-style.css`; usa as rotas de cadastro e exclusão da mesma API |

O monitor principal importa `detection.types`, não `detection.tracker`. Sua
publicação usa `communication.backend_client`, não `detection.api_client`. O
pipeline ByteTrack só era alcançado pelo executável paralelo `object-ident.py`
e por `test_detection_publishing.py`; `test_settings.py` também importava seu
adaptador de configuração para testar a linha. Esses testes foram adaptados ao
rastreador e ao cliente HTTP do monitor principal, preservando os cenários úteis.
O JavaScript `detection-counter.js` não era importado pelo HTML nem pelos módulos
do dashboard. `stations.json` era um export de exemplo sem leitor no fluxo.

Os imports quebrados `comparacao.aquamonitor.backend` foram substituídos por
`backend`, permitindo executar a PH independentemente da pasta da referência.
Todos os imports internos retidos foram conferidos após a limpeza.

## Arquivos removidos

Caminhos relativos à PH:

| Arquivo | Motivo |
|---|---|
| `backend/test_mongodb.py` | Script que conectava diretamente ao MongoDB antigo; substituído por testes PostgreSQL isolados |
| `backend/detection/object-ident.py` | Executável alternativo ByteTrack |
| `backend/detection/api_client.py` | Cliente exclusivo do pipeline alternativo, com fila/repetição próprias |
| `backend/detection/config.py` | Configuração exclusiva do pipeline alternativo |
| `backend/detection/detection_pipeline.py` | Orquestração alternativa de detecção/contagem/publicação |
| `backend/detection/geometry.py` | Geometria usada exclusivamente pelo contador alternativo |
| `backend/detection/line_counter.py` | Contador do pipeline alternativo; o principal usa `tracking/line_tracker.py` |
| `backend/detection/tracker.py` | Adaptador ByteTrack; não é o rastreador do monitor principal |
| `dashboard/js/detection-counter.js` | Consulta paralela de resumo sem importador no painel |
| `stations.json` | Export de exemplo com metadados MongoDB, sem importação ou leitura automática |

Também foram removidos os 12 bytecodes Python 3.14 que vieram na cópia:

- `backend/__pycache__/{__init__,app,test_detection_events,test_mongodb}.cpython-314.pyc`
- `backend/detection/__pycache__/{__init__,api_client,config,detection_pipeline,geometry,line_counter,object-ident,tracker}.cpython-314.pyc`

A PH recebida já não continha as pastas `Embedded/`, `RaspberryPi/` nem módulos
GPS. Não houve remoção dessas pastas nesta revisão. O monitor principal continua
compatível com uma Raspberry Pi como equipamento, usando câmera USB e HTTP.

## Configuração e dependências

Foram retirados `bytetrack`, `backend.enabled`, `backend.publish_interval_seconds`,
`BOTTLE_COUNT_API_ENABLED` e `BOTTLE_COUNT_PUBLISH_INTERVAL`, exclusivos do caminho
paralelo. O `ssd_mobilenet.nms_threshold` também foi retirado do exemplo: o
adaptador SSD preservado não o consultava. A publicação principal continua
obrigatória por cruzamento e sem reenvio automático, como na referência.

As dependências estão organizadas em dois arquivos independentes na raiz:

- `requirements-server.txt`: API PostgreSQL e `httpx` para seus testes de integração.
- `requirements-cv.txt`: estação SSD/YOLO, captura, processamento e comunicação HTTP.

Para instalar servidor e estação ou executar a suíte completa, instale ambos.
Os testes PostgreSQL isolados precisam somente do arquivo do servidor. Os
resultados de validação abaixo registram o ambiente utilizado na revisão da
limpeza; o teste do adaptador YOLO simula a inferência real.

Não são mais necessários PyMongo, Supervision, LAP ou cython-bbox. Os modelos e
os módulos de câmera, processamento de imagem, detecção, rastreamento e envio
principais foram preservados. Os oito módulos do fluxo principal listados abaixo
são equivalentes à referência por comparação AST, normalizando apenas o prefixo
dos imports:

- `backend/monitoring/monitor_residuos.py`
- `backend/camera/webcam_config.py`
- `backend/camera/image_processing.py`
- `backend/detection/types.py`
- `backend/detection/ssd_mobilenet_detector.py`
- `backend/detection/yolo_detector.py`
- `backend/tracking/line_tracker.py`
- `backend/communication/backend_client.py`

## Diferenças funcionais restantes em relação à referência

| Área | Referência V | PH resultante |
|---|---|---|
| Persistência | Documentos MongoDB | PostgreSQL com colunas, chave estrangeira, restrições e `TIMESTAMPTZ`; startup PostgreSQL preservado |
| Contrato principal | Cadastro/listagem/exclusão e ingestão/resumos | Mesmas rotas, métodos, códigos de sucesso e campos de eventos/resumos para cadastros completos; HTTP 409 para evento duplicado e HTTP 404 para estação ausente |
| Campo `id` nas respostas de criação | String do ObjectId interno | String de `station_id` no cadastro e `event_id` na ingestão; `event_id` e `station_id` continuam explícitos |
| Exclusão | Remove cadastro; mantém eventos | Desativa com `is_active=false`; mantém cadastro e eventos para cumprir a chave estrangeira; fica invisível e rejeita novos eventos até ser recadastrada |
| Recadastro após exclusão | Novo documento, eventos antigos voltam a contar | Reativa a mesma chave, atualiza dados administrativos/localização e recupera o mesmo histórico |
| Resumos e horários | Agregação MongoDB, tolerância a datas legadas inválidas/mistas | `COUNT`/`MAX` SQL com horários tipados; datas legadas precisam de conversão antes da importação; sentidos ausentes continuam `unknown` |
| Cadastro incompleto | Pode retornar `administrative: null` quando omitido | Retorna objeto administrativo vazio; aceita apenas o subconjunto de campos do esquema relacional |
| ID booleano em cadastro | A verificação `isinstance(..., int)` aceita `true` | PH já rejeitava booleano com 422; validação preservada |
| Destino HTTP de exemplo | JSON `0.0.0.0` e painel apontando a IP fixo, CRUD em localhost | JSON e todos os clientes do dashboard usam `127.0.0.1`; estação/navegador remotos devem usar o IP do servidor |
| Documento local | Exige metadado `_id`/`$oid` sem uso na contagem | Documento novo não depende desse metadado; leitura de arquivo local antigo descarta somente `_id`, preservando contagem e localização |
| Caminhos paralelos | Módulos ByteTrack ainda presentes | Removidos; contador por centróide, SSD/YOLO, intervalo, fila de 32, direção, confiança, persistência local e encerramento preservados |

Os valores de `detections`, status e coordenadas do exemplo local não foram
zerados. A limpeza retirou apenas `_id` desse exemplo. Nenhum monitor foi
executado sobre os arquivos de estado da cópia; os testes usam diretórios próprios.

A migração PostgreSQL foi mantida em `backend/app.py`, sem alterações ao SQL ou
aos endpoints nesta revisão. Não existe importador automático MongoDB → PostgreSQL.
O README descreve a transferência e a validação necessárias para dados antigos.

## Resultados de validação

Ambiente: Python 3.12, Node.js 24.22.2, PostgreSQL 16.15, Psycopg 3.3.6,
FastAPI 0.162.0, Pydantic 2.14.1, NumPy 1.26.4 e OpenCV 4.11.0.86.
Como o host não tinha PostgreSQL instalado nem sudo sem senha, os pacotes Ubuntu
foram extraídos em `/tmp`, sem instalação de serviço. A venv de teste também fica
em `/tmp`. Nenhuma conexão a dados existentes foi necessária.

| Verificação | Resultado |
|---|---|
| `python -m unittest discover -s backend -t . -v` | 32 testes unitários passaram; 12 testes SQL ignorados nesta execução e executados separadamente abaixo |
| `python scripts/test_postgresql.py --pg-bin .../postgresql/16/bin` | 12 testes de integração passaram, com ASGI TestClient e PostgreSQL real |
| `node --test dashboard/tests/*.mjs` | 7 testes passaram |
| `python -m pip check` | Sem dependências quebradas no ambiente usado |
| `--help` do monitor principal e dos dois atalhos SSD | As três entradas carregaram corretamente |
| Imports Python/JavaScript, links locais e sintaxe dos exemplos Bash | Conferidos sem referência a módulos removidos ou arquivos ausentes |
| Comparação dos oito módulos principais e dos modelos com V | Lógica principal equivalente por AST; conteúdo dos modelos preservado |
| Integridade da referência | Mesmos arquivos e hashes SHA-256 antes/depois |

Os testes SQL cobrem persistência de todos os campos/sentidos, duplicação global
de eventos, quatro envios concorrentes do mesmo evento (um 201 e três 409),
resumos por estação/classe/sentido, horários com fusos diferentes, cadastro
vazio/duplicado, validação 422/404, restrições SQL, reinicialização e criação
idempotente do esquema, adição de `is_active` e exclusão/reativação com histórico.

O runner cria um cluster temporário com `listen_addresses` vazio e socket Unix
exclusivo, ignora variáveis de conexão herdadas e remove o cluster após os testes.
Os testes recusam uma URL que não corresponda a esse ambiente. Nenhum teste SQL
foi executado contra a URL padrão da API ou contra banco real de aplicação.

Não houve validação visual em navegador nem teste com câmera ou Raspberry Pi
física. O SSD real foi carregado e inferiu um frame sintético vazio; o adaptador
YOLO foi testado com resultados simulados, sem executar seus pesos reais. A
biblioteca Starlette emitiu aviso de depreciação sobre seu suporte a `httpx`, sem
falhas nos testes. Precisão e desempenho em equipamento continuam por medir.
