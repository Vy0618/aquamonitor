# Monitor embarcado AquaMonitor

Código da estação para Windows e Linux (incluindo Raspberry Pi OS **64 bits**), Python 3.10 ou superior e câmera USB compatível com OpenCV. Use uma sessão gráfica para visualizar o vídeo; por SSH/servidor use `--no-display`. Câmeras CSI que só expõem libcamera/Picamera2 não são suportadas por este capturador USB.

## Instalação

Execute a partir da raiz do repositório.

Windows (PowerShell):

```powershell
py -3 -m venv RaspberryPi/.venv
RaspberryPi/.venv/Scripts/python.exe -m pip install -r RaspberryPi/config/requirements.txt
RaspberryPi/.venv/Scripts/python.exe -m RaspberryPi.monitoring.monitor_residuos
```

Linux / Raspberry Pi OS:

```bash
python3 -m venv RaspberryPi/.venv
RaspberryPi/.venv/bin/python -m pip install -r RaspberryPi/config/requirements.txt
RaspberryPi/.venv/bin/python -m RaspberryPi.monitoring.monitor_residuos
```

No Linux, instale os pacotes de sistema `python3-venv`, `libgl1` e `libglib2.0-0` se estiverem ausentes; permita acesso do usuário à câmera. No Windows, permita acesso de aplicativos desktop à câmera. Não use `opencv-python-headless` para executar com janela. Instalação de PyTorch/Ultralytics depende de haver pacotes disponíveis para a arquitetura e versão de Python escolhidas.

## Configuração e execução

Edite `RaspberryPi/config/raspberrypi_config.json`:

- `station_id`: identificador de uma estação já cadastrada no backend.
- `backend.base_url`: endereço do backend. `127.0.0.1` significa o próprio computador/Pi. Também aceita a variável de ambiente `AQUADETECTOR_API_URL`.
- `camera`: índice 0, resolução solicitada **640×480**, **15 FPS**. O driver pode negociar outros valores. `backend` opcional aceita um identificador OpenCV; por padrão usa DirectShow no Windows e V4L2 no Linux.
- `detection_interval_ms`: **250 ms**, no máximo quatro inferências por segundo. A captura continua entre inferências e só mantém o frame mais recente. Se a inferência demorar mais de 250 ms, a frequência efetiva será menor; não há inferências simultâneas nem recuperação em rajada de intervalos perdidos.
- `detection.image_size`: **320**, entrada reduzida do YOLO, executado em CPU. O modelo treinado é `models/best (1).pt` e permite bottle, can, carton, paper e plastic. Valide a precisão com resíduos reais: objetos pequenos/distantes e objetos muito rápidos podem exigir ajustes.
- `tracking.line_y_ratio`: **0.55**, calculado sobre a altura real do frame. A linha amarela com contorno preto é desenhada em todos os frames exibidos, mesmo sem detecções. Se a resolução mudar, o tracker é reiniciado para evitar cruzamentos artificiais.
- `tracking.max_distance`: 90 pixels entre observações; `max_missing_frames`: quatro ciclos de detecção sem associação antes de remover um track. A contagem ocorre uma vez por track, nos sentidos definidos por `direction` (`both`, `up`, `down`).
- `station_document`: dados e coordenadas fixos da estação; o documento local existente preserva sua localização. Esse arquivo não é sincronizado automaticamente com o backend.

Com o Python do ambiente ativado:

```bash
python -m RaspberryPi.monitoring.monitor_residuos
python -m RaspberryPi.monitoring.monitor_residuos --no-display
python -m RaspberryPi.monitoring.monitor_residuos --detector ssd
python -m RaspberryPi.monitoring.monitor_residuos --config RaspberryPi/config/raspberrypi_config.json
```

Q, ESC, fechar a janela ou Ctrl+C encerram o monitor. Os módulos `monitor_ssd_mobilenet` e `monitor_ssd_mobilenet_local` são entradas equivalentes para SSD e usam o mesmo fluxo, inclusive publicação HTTP. O SSD COCO incluído detecta apenas **bottle** entre as categorias do projeto. Para as cinco categorias, use o YOLO padrão. A escolha de detector é explícita e não muda automaticamente após uma falha.

## Persistência e comunicação

Cada cruzamento salva as contagens em `RaspberryPi/data/contagem_residuos.json` (pasta criada automaticamente) e envia um evento com UUID e a confiança do objeto correto para `POST /api/detections`. Um único trabalhador HTTP evita bloquear a captura; o limite é 32 envios em memória. Erros de rede ou limite excedido encerram o monitor com mensagem de erro. Não há reenvio automático nem fila persistente: contagem local não comprova entrega ao backend. Ao encerrar normalmente, os envios pendentes são aguardados.

Os arquivos de contagem e estação usam substituição atômica. Contagens inválidas geram erro, preservando o arquivo para recuperação. O total histórico do documento da estação não é reduzido; contagens por classe refletem o arquivo de contagens. Execute apenas uma instância por estação/arquivo de contagem.

## Verificação

```bash
python -m unittest discover -s RaspberryPi/tests -v
```

Os testes usam frames sintéticos e câmera/HTTP simulados para verificar os dois sistemas, agendamento, linha visível, contagem, persistência e encerramento. Para validar o equipamento, execute o monitor, confira a resolução real impressa, atravesse a linha com um resíduo nos dois sentidos e confirme uma contagem por track e o evento no backend. A taxa e a precisão finais precisam ser medidas na câmera e Raspberry Pi físicas.
