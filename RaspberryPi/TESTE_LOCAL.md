# Teste local da integração Raspberry Pi → backend → dashboard

Este roteiro executa o software embarcado **no computador**, sem Raspberry Pi física. Ele pressupõe que o MongoDB e o backend FastAPI já estejam em execução.

## 1. Preparar o ambiente

Na raiz do projeto, instale as dependências da parte embarcada no ambiente Python que será usado no teste:

```powershell
.\.venv\Scripts\python.exe -m pip install -r RaspberryPi\config\requirements.txt
```

Confirme que o backend responde e que a estação `1` existe. Se necessário, cadastre-a uma vez:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/stations
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/stations -ContentType 'application/json' -InFile RaspberryPi\station\station.json
```

## 2. Validar somente a comunicação HTTP

Envie uma detecção simulada. A resposta esperada é `Detection ingested successfully` e status HTTP 201.

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

O segundo comando deve mostrar `total: 1` (ou maior) e `by_type` contendo `can`.

## 3. Testar o dashboard

Em outro terminal, sirva a pasta do dashboard:

```powershell
Set-Location dashboard
..\.venv\Scripts\python.exe -m http.server 3000
```

Abra `http://127.0.0.1:3000`. A estação deve exibir o total de detecções, as categorias e a última detecção. O painel atualiza a estação selecionada a cada 3 segundos.

## 4. Executar o monitor com webcam local

Mantenha `backend.base_url` como `http://127.0.0.1:8000` enquanto o monitor e o backend estiverem no mesmo computador. O monitor utiliza a câmera padrão (`device_index: 0`).

Para YOLO:

```powershell
.\.venv\Scripts\python.exe -m RaspberryPi.monitoring.monitor_residuos
```

Para SSD MobileNet:

```powershell
.\.venv\Scripts\python.exe -m RaspberryPi.monitoring.monitor_ssd_mobilenet
```

Pressione `Q` ou `Esc` para encerrar. Cada objeto que cruzar a linha amarela gera um evento em `POST /api/detections`; o dashboard deve refletir a alteração no próximo ciclo de polling.

## Observações

- O SSD MobileNet COCO fornecido reconhece `bottle`; as demais classes dependem do modelo utilizado. O YOLO pode reconhecer as cinco categorias configuradas.
- Ao migrar para a Raspberry Pi física, troque `backend.base_url` pelo IP ou hostname do computador/servidor que executa o FastAPI. `127.0.0.1` na Pi aponta para a própria Pi.
- Um mesmo `event_id` não pode ser enviado duas vezes: a segunda tentativa retorna HTTP 409 para evitar contagem duplicada.
