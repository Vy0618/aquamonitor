# Referência detalhada dos arquivos do sistema embarcado

Este documento descreve cada arquivo presente em `RaspberryPi/` e como as partes compõem uma estação embarcada de detecção de resíduos. A estação captura imagens, identifica materiais, acompanha o movimento de cada objeto, conta uma passagem pela linha de referência, persiste a contagem localmente e transmite um evento ao backend.

## Visão do fluxo principal

```text
Câmera USB → detector (YOLO ou SSD MobileNet) → rastreador de linha
        → contador local → evento HTTP para o backend
                         ↘ documento da estação + GPS (fluxo SSD)
```

O monitor YOLO usa o detector treinado presente no projeto. O monitor SSD MobileNet é uma alternativa que também mantém o documento local da estação e, quando habilitado, incorpora a posição mais recente do GPS.

## `README.md`

É a apresentação curta desta área. Explica a separação por pastas, aponta onde ficam os componentes principais e identifica os dados persistidos e os pesos de modelo. Ele não é executado pelo sistema; serve para orientação de quem abre o repositório.

## `camera/webcam_config.py`

Centraliza a conexão com a webcam USB por meio do OpenCV.

- A classe imutável `WebcamConfig` reúne o índice do dispositivo, largura, altura, taxa de quadros e o backend de vídeo. Os valores padrão são câmera `0`, resolução `1280×720` e `30 FPS`.
- A propriedade `resolution` devolve a largura e altura como uma tupla, no formato esperado por partes da aplicação.
- `open_camera()` cria um `cv2.VideoCapture`. Se não houver backend definido, deixa o OpenCV escolher — na Raspberry Pi, isso normalmente resulta em V4L2. Quando existe um backend explícito, ele o envia ao OpenCV.
- Antes de devolver a câmera, solicita ao driver a resolução e o FPS configurados. A configuração é uma solicitação: o dispositivo pode aceitar valores diferentes dependendo do hardware e driver.
- Caso a câmera não abra, o método encerra com uma mensagem que indica verificar a conexão ou o `device_index`.

Esse módulo não faz detecção nem mostra imagens; ele só entrega uma captura de vídeo pronta para os monitores.

## `communication/backend_client.py`

Implementa a camada HTTP da estação para o backend AquaDetector.

- `BackendConfig` guarda três parâmetros: `base_url`, o caminho de eventos de detecção e o tempo limite das chamadas. A propriedade `detections_url` normaliza uma possível barra final da URL base e monta a URL final de `POST`.
- `BackendClient` cria uma sessão persistente do pacote `requests`, o que permite reaproveitar conexões HTTP entre eventos consecutivos.
- Ao ser construído, ele dá prioridade à variável de ambiente `AQUADETECTOR_API_URL`. Assim, o endereço do backend pode ser trocado na Raspberry Pi sem editar o JSON. Também bloqueia o valor de exemplo `SEU_IP_DO_BACKEND`, para evitar uma inicialização com uma URL não configurada.
- `ensure_station_is_available(station_id)` faz `GET /api/stations`, valida a resposta HTTP e confirma que a lista devolvida contém a estação informada. Falha de conexão, JSON inválido, resposta de erro ou estação ausente viram uma exceção clara.
- `send_detection(event)` faz `POST` do evento como JSON para `/api/detections` (ou o caminho configurado). Se o backend rejeitar a chamada ou a rede falhar, lança uma exceção de comunicação.

O módulo não decide o que foi detectado; apenas verifica a existência da estação e transporta os eventos criados pelos monitores.

## `config/raspberrypi_config.json`

É a configuração declarativa da estação. Ele evita que valores de infraestrutura e parâmetros operacionais fiquem espalhados pelo código.

- `station_id`: identificador numérico da estação usado na validação do backend, nos eventos e na contagem persistida. O valor atual é `1`.
- `station_document`: dados iniciais do documento local da estação. `path` indica o arquivo que deve receber esse documento; `_id` usa MongoDB Extended JSON, pois `ObjectId` não existe em JSON puro; `detections`, `status`, `location` e `administrative` preenchem a estrutura inicial. A localização é GeoJSON e, portanto, usa `[longitude, latitude]`, nesta ordem.
- `gps`: habilita ou desabilita a leitura do NEO-6M e informa porta serial, taxa de transmissão e timeout. A porta atual é `/dev/serial0`, com `9600` baud.
- `backend`: define endereço, endpoint de eventos, tempo limite e se a estação precisa confirmar a conexão com o backend antes de iniciar. O endereço `127.0.0.1` significa o próprio dispositivo; em uma instalação com servidor separado, essa configuração ou a variável de ambiente precisa apontar para o IP/host do backend.
- `camera`: fornece os parâmetros que instanciam `WebcamConfig`.
- `detection`: configura o fluxo YOLO: caminho do peso, confiança mínima, tamanho de entrada e as cinco classes aceitas: `bottle`, `can`, `carton`, `paper` e `plastic`.
- `ssd_mobilenet`: configura a alternativa SSD, incluindo o arquivo de pesos TensorFlow `.pb`, sua descrição `.pbtxt`, um arquivo opcional de rótulos, limiar de confiança, resolução de rede e classes aceitas.

O arquivo contém dados de configuração, não lógica de execução. Os valores de caminho foram definidos quando o código ainda usava a estrutura plana original; veja a observação de integração ao fim deste documento.

## `config/requirements.txt`

Lista as bibliotecas mínimas do ambiente Python embarcado.

- `ultralytics`: carrega e executa o modelo YOLO.
- `opencv-python`: captura vídeo, desenha a interface na imagem e executa a rede SSD por DNN.
- `requests`: executa a comunicação HTTP com o backend.
- `pyserial`: abre a UART e recebe as frases NMEA do GPS.

Os limites `>=` permitem instalar versões posteriores. Dependências indiretas, como NumPy, são instaladas pelos pacotes que as exigem.

## `data/contagem_residuos.json`

É o estado persistido da contagem local de resíduos. O monitor atualiza esse arquivo sempre que identifica um cruzamento novo e novamente ao encerrar.

- `station_id` associa a contagem a uma estação. O arquivo presente informa `61`, enquanto a configuração atual informa `1`; isso é um dado existente que o código carrega como está e não é corrigido automaticamente.
- `counts` contém um acumulador por classe. No estado atual há quatro garrafas (`bottle`) e zero itens nas demais classes.
- `detection_types` registra quais classes faziam parte da contagem.
- `updated_at` é a data/hora UTC da última gravação, em ISO 8601.

A gravação é segura contra interrupção parcial: o monitor escreve primeiro um arquivo temporário com extensão `.tmp` e depois o substitui pelo JSON final.

## `detection/yolo_detector.py`

É o adaptador entre o modelo YOLO do projeto e o restante da aplicação.

- `EXPECTED_CLASSES` declara o vocabulário permitido no sistema: garrafa, lata, embalagem cartonada, papel e plástico.
- `Detection` é uma estrutura imutável que representa uma detecção individual: classe, confiança e caixa delimitadora `(x1, y1, x2, y2)`. A propriedade `centroid` calcula o ponto central da caixa; esse ponto é a entrada usada pelo rastreador.
- `YoloDetector` recebe caminho do modelo, confiança mínima, tamanho de imagem, dispositivo opcional e classes autorizadas. Seus padrões são peso em `models/best (1).pt`, limiar `0.45` e entrada de `640` pixels.
- Na inicialização, ele importa `ultralytics.YOLO` somente quando necessário, permitindo emitir uma mensagem mais específica se a dependência não estiver instalada. Também confirma que o arquivo de pesos existe antes de abrir o modelo.
- `_get_class_names()` adapta o formato da lista/dicionário de nomes exposto pelo Ultralytics para um dicionário.
- `detect(frame)` envia um frame BGR ao YOLO, aplica limiar de confiança, converte as caixas para inteiros e ignora toda classe fora das cinco permitidas. O resultado é uma lista de objetos `Detection`.

Ele não conta objetos e não comunica o backend: sua responsabilidade termina em transformar uma imagem em detecções filtradas.

## `detection/ssd_mobilenet_detector.py`

Oferece uma segunda implementação de detector, baseada em SSD MobileNet TensorFlow e no módulo DNN do OpenCV.

- Reaproveita a estrutura `Detection` do detector YOLO para que o rastreador e o monitor trabalhem da mesma forma independentemente da rede escolhida.
- `DEFAULT_COCO_LABELS` mapeia apenas o ID COCO `44` para `bottle`. Portanto, sem um arquivo de rótulos personalizado, o modo SSD padrão só reconhece garrafas entre as cinco categorias do projeto.
- O construtor confirma a existência dos arquivos `.pb` e `.pbtxt`, abre a rede com `cv2.dnn.readNetFromTensorflow` e guarda limiares, tamanho de entrada, classes permitidas e rótulos.
- `_load_labels()` lê um `labels.txt` opcional. Aceita tanto linhas no formato `id nome` quanto uma classe por linha; ignora linhas vazias e comentários iniciados por `#`.
- `detect(frame)` cria um blob normalizado para o tamanho da rede, executa a inferência e percorre a saída SSD de sete valores por resultado. Ele filtra confiança baixa e classe não permitida, converte coordenadas normalizadas para pixels e descarta caixas inválidas antes de criar `Detection`.

Para detectar `can`, `carton`, `paper` e `plastic`, o modelo e o arquivo de rótulos precisam ter sido treinados/configurados para essas classes.

## `gps/gps_neo6m.py`

Controla o GPS u-blox NEO-6M conectado via UART sem interromper o loop da câmera.

- `GpsFix` é uma estrutura imutável com latitude, longitude e horário UTC de recebimento. A propriedade `geojson_coordinates` inverte a ordem para `[longitude, latitude]`, como exige GeoJSON.
- `Neo6mGps` mantém a última posição válida, o último erro, uma trava de concorrência, um evento de parada e uma thread de leitura. Por isso, o monitor pode continuar processando vídeo enquanto o GPS aguarda dados serialmente.
- `start()` importa `pyserial`, abre a porta configurada e inicia uma thread daemon chamada `neo6m-gps`. Se a biblioteca ou a porta estiver indisponível, devolve um erro explicativo.
- A thread executa `_read_loop()`: lê uma linha da UART, decodifica em ASCII ignorando bytes inválidos, interpreta NMEA e atualiza a última posição. Erros transitórios são guardados em `last_error`, sem parar o monitor.
- `close()` sinaliza parada, aguarda a thread por no máximo `timeout + 1` segundos, fecha a serial e limpa as referências.
- `parse_nmea_sentence()` aceita apenas mensagens RMC e GGA de talkers GP ou GN. Para RMC exige status `A`; para GGA exige qualidade de fix diferente de zero. Mensagens malformadas, sem fix ou de outro tipo são ignoradas.
- `_nmea_coordinate_to_decimal()` converte o formato NMEA graus+minutos em graus decimais e aplica sinal negativo aos hemisférios Sul e Oeste.

## `models/best (1).pt`

É o arquivo binário de pesos do modelo YOLO utilizado pelo fluxo principal. O Ultralytics o carrega para realizar inferência. Não é um arquivo textual e não deve ser editado manualmente. O sufixo `.pt` normalmente indica um checkpoint PyTorch.

## `monitoring/monitor_residuos.py`

É o ponto de entrada do fluxo principal baseado em YOLO. Coordena câmera, detector, rastreamento, persistência de contagem e envio de evento.

- `BASE_DIR`, `CONFIG_FILE` e `COUNTS_FILE` definem, a partir da localização do próprio script, onde o programa espera encontrar sua configuração e contagem. `LINE_Y_RATIO = 0.55` posiciona a linha de contagem a 55% da altura da imagem; `TRACKING_DIRECTION = "both"` conta cruzamentos nos dois sentidos.
- `load_config()` lê o JSON e valida requisitos mínimos: `station_id` positivo e conjunto de classes de detecção exatamente igual às cinco classes esperadas. Não valida todos os demais campos em profundidade.
- `load_counts()` cria inicialmente todos os contadores zerados e, se houver arquivo salvo, aproveita apenas valores inteiros por classe. Também entende um formato antigo em que as contagens estavam na raiz do JSON.
- `save_counts()` monta o documento de contagem com timestamp UTC e faz a substituição atômica via arquivo temporário.
- `draw_overlay()` desenha a linha amarela de referência, as caixas verdes e suas confianças, e um painel textual com o total de cada classe.
- Em `main()`, o programa lê a configuração, monta o cliente HTTP e, caso exigido, valida a estação no backend. Em seguida, abre a câmera, carrega o YOLO, restaura a contagem e cria um `LineTracker`.
- Para cada frame, chama o detector e passa as detecções ao rastreador. Cada `Crossing` devolvido incrementa somente uma vez o contador daquele objeto, salva o JSON e gera um evento com UUID, estação, tipo, confiança, ID de rastreamento e data UTC.
- A janela OpenCV mostra o vídeo processado. A tecla `Q` ou `Esc` encerra o loop. O bloco `finally` salva a contagem, libera a câmera e fecha as janelas mesmo se ocorrer uma exceção.

## `monitoring/monitor_ssd_mobilenet.py`

É o ponto de entrada alternativo que substitui YOLO por SSD MobileNet, mas mantém a mesma lógica de contagem e comunicação.

- Reutiliza do monitor YOLO as funções de configuração, contagem e desenho, além das constantes de posição e direção da linha. Isso evita comportamento diferente na contagem entre os dois detectores.
- Antes do loop, valida a estação no backend quando requerido, garante a existência de `station.json` e inicia o GPS caso `gps.enabled` esteja ativo.
- Instancia `SsdMobileNetDetector` usando caminhos e parâmetros da seção `ssd_mobilenet` do JSON. Sem os arquivos `.pb` e `.pbtxt`, ele falha intencionalmente antes de abrir o monitor.
- No cruzamento, além de salvar a contagem e enviar o mesmo evento HTTP, atualiza o documento da estação: total acumulado, última posição GPS disponível e status `online`.
- Ao encerrar, persiste a contagem, atualiza o documento como `offline`, inclui a última posição disponível, fecha o GPS, libera a câmera e encerra as janelas.

Assim, o modo SSD possui uma integração de estado de estação e GPS que o modo YOLO atual não possui.

## `runtime/__pycache__/`

Esta pasta contém bytecode compilado automaticamente pelo Python para acelerar importações. Os arquivos `.pyc` ali presentes correspondem a versões Python 3.14 de módulos que já foram executados: cliente de backend, rastreador, configuração da câmera e detector YOLO.

- Eles não são código-fonte, não são lidos diretamente por pessoas e podem ser apagados ou recriados pelo Python.
- Não representam configuração, modelo ou dado de negócio; são apenas cache de execução.

## `station/station.json`

É o documento persistido que representa uma estação individual.

- `_id` armazena um identificador em MongoDB Extended JSON (`$oid`).
- `station_id` é o identificador numérico da estação, atualmente `1`.
- `detections` registra o total consolidado, atualmente `37`.
- `status` informa o estado atual, atualmente `online`.
- `location` é um GeoJSON `Point`; suas coordenadas devem sempre estar na ordem longitude, latitude. O valor presente aponta para `[-46.4526, -23.5015]`.
- `administrative` descreve país, estado, cidade e distrito associados à estação.

`StationDocument` exige que este JSON tenha exatamente esses seis campos de alto nível e valida a forma das coordenadas antes de gravá-lo.

## `station/station_document.py`

Implementa a persistência e validação de `station.json`.

- A classe `StationDocument` recebe o caminho de destino, o ID da estação e os valores iniciais da configuração.
- `ensure_exists()` lê o documento existente; se ainda não houver arquivo, cria uma versão-base a partir de `station_document` no JSON de configuração.
- `update()` altera somente os valores fornecidos. Para `detections`, guarda o maior valor entre o atual e o novo, impedindo que um contador local antigo reduza o total já registrado. Para GPS, grava um GeoJSON Point; para status, troca o estado textual.
- `_base_document()` constrói o formato inicial com os seis campos exigidos.
- `_read()` abre o JSON e converte erro de leitura ou sintaxe em uma exceção explicativa.
- `_write()` usa o mesmo padrão seguro de arquivo temporário seguido de substituição.
- `_validate()` exige um conjunto exato de campos, `location.type == "Point"`, uma lista de duas coordenadas numéricas e a ordem GeoJSON esperada.

## `station/update_station_location.py`

É um utilitário de execução única para atualizar a posição da estação com o primeiro fix GPS válido recebido.

- Lê a configuração usando a função do monitor YOLO e exige que `gps.enabled` esteja verdadeiro.
- Garante a existência do documento da estação, abre o GPS com porta, baudrate e timeout configurados e avisa que está esperando um fix.
- Enquanto `latest_fix` estiver vazio, aguarda 0,2 segundo por vez. Quando chega uma posição válida, grava apenas localização e status `online` em `station.json` e imprime as coordenadas salvas.
- O bloco `finally` fecha a conexão serial mesmo quando a execução for interrompida com `Ctrl+C` ou ocorrer uma falha.

Ele não inicia a câmera e não envia evento de detecção ao backend.

## `tracking/line_tracker.py`

Transforma detecções de frames sucessivos em objetos acompanhados e em eventos de contagem únicos.

- `Point` define um centróide como par `(x, y)`.
- `TrackedObject` mantém o ID interno, classe, centróide atual, centróide anterior, quantidade de frames ausente e se aquele objeto já foi contado.
- `Crossing` é o evento imutável devolvido ao monitor: contém o ID do objeto e sua classe.
- `LineTracker` recebe a coordenada vertical da linha, distância máxima para associar objetos entre frames, quantidade máxima de frames ausentes e direção permitida (`down`, `up` ou `both`). A direção inválida é recusada imediatamente.
- `update(detections)` compara cada detecção com cada objeto ativo da mesma classe. Se a distância entre centróides for no máximo `max_distance`, ela vira candidata a associação. As candidatas são ordenadas por distância; a seleção gulosa garante que cada detecção e cada objeto sejam usados uma única vez no frame.
- Um objeto associado recebe novo centróide e pode disparar `Crossing` se cruzar a linha na direção permitida. A flag `counted` impede que ele seja contado novamente nos frames seguintes.
- Objetos não vistos acumulam `missing_frames`; detecções sem par recebem novos IDs; objetos ausentes além de `max_missing_frames` são removidos.
- `_crossed_line()` identifica uma descida se o `y` anterior estava acima da linha e o novo está sobre/abaixo dela, e uma subida na condição inversa. `_distance()` usa distância euclidiana.

O rastreador não reconhece imagens por si só: ele depende das caixas produzidas por YOLO ou SSD MobileNet.

## Integração após a reorganização física

Os imports foram adaptados para o pacote `RaspberryPi` e cada pasta que contém código passou a ter um `__init__.py`. Os módulos usam imports explícitos, como `RaspberryPi.communication.backend_client`, em vez de dependerem de arquivos na mesma pasta.

`monitor_residuos.py` estabelece a raiz do sistema como a pasta `RaspberryPi/` e resolve a partir dela os caminhos de configuração (`config/raspberrypi_config.json`), dados (`data/contagem_residuos.json`), modelos e documento da estação. A configuração também passou a declarar `station/station.json` como caminho do documento local.

Para que o Python reconheça o pacote, os comandos devem ser executados na raiz do projeto:

```bash
python -m RaspberryPi.monitoring.monitor_residuos
python -m RaspberryPi.monitoring.monitor_ssd_mobilenet
python -m RaspberryPi.station.update_station_location
```
