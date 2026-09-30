# Configuração compartilhada

Edite `aquamonitor.json`, na raiz, para configurar a estação. O carregador
`backend/settings.py` valida o arquivo e resolve caminhos em relação à pasta do
JSON. A API e o dashboard não leem esse arquivo.

| Seção/campo | Uso |
|---|---|
| `station_id` | Identidade já cadastrada na API |
| `backend` | Endereço, timeout, caminho de eventos e verificação inicial |
| `camera` | Índice, resolução e FPS solicitados; backend OpenCV opcional |
| `ssd_mobilenet` | Modelo, configuração, classes, confiança e tamanho de entrada SSD |
| `detection` | Modelo, classes, confiança e tamanho de entrada YOLO |
| `detection_interval_ms` | Intervalo mínimo entre inferências do monitor |
| `tracking` | Linha proporcional, direção e associação por centróide |
| `station_document` | Documento local, independente do cadastro no MongoDB |
| `display.enabled` | Habilita a prévia; `--display` / `--no-display` têm prioridade |
| `image_processing` | Redimensionamento anterior à inferência, mantendo proporção |
| `bytetrack` | Parâmetros dos módulos alternativos de rastreamento |

```bash
python -m backend.monitoring.monitor_residuos --config aquamonitor.json --detector ssd --no-display
```

Sem `--detector`, o monitor usa YOLO. Os atalhos `monitor_ssd_mobilenet` e
`monitor_ssd_mobilenet_local` selecionam SSD e também publicam eventos.
O monitor calcula a linha sobre a altura real do frame. As caixas de imagens
reduzidas são convertidas de volta às coordenadas da captura antes do rastreamento.

## Endereço e precedência

Use o IP ou hostname real do servidor, não `0.0.0.0` (valor presente no JSON atual).
Para execução local:

```bash
export AQUADETECTOR_API_URL=http://127.0.0.1:8000
```

- `--config` seleciona um arquivo; `AQUAMONITOR_CONFIG` define o padrão.
- `AQUADETECTOR_API_URL` sobrescreve `backend.base_url` e tem prioridade sobre
  `BOTTLE_COUNT_API_URL`.
- `BOTTLE_COUNT_STATION_ID` sobrescreve o ID.
- `BOTTLE_COUNT_API_ENABLED` e `BOTTLE_COUNT_PUBLISH_INTERVAL` sobrescrevem campos
  usados pelo cliente/pipeline alternativo ByteTrack.
- Não há carregamento automático de `.env`. Reinicie o monitor após alterar JSON
  ou variáveis de ambiente.

## Publicação e módulos alternativos

O monitor SSD/YOLO publica um evento por cruzamento em `/api/detections`, mesmo com
`backend.enabled=false`. `backend.require_connection_on_startup` controla somente
sua verificação inicial. Um trabalhador envia em thread; falhas ou mais de 32
pendências encerram o monitor. Não há fila persistente nem reenvio automático.

`backend/detection/config.py` adapta o JSON às dataclasses do pipeline ByteTrack.
Esse pipeline usa publicação síncrona com intervalo, preserva eventos falhos em
memória e aceita 409 como confirmação de duplicação. **Não existe um executável
`backend/detection/object-ident.py` nesta versão**; a antiga opção `--publish`
não pertence ao monitor atual.

`ssd_mobilenet.nms_threshold` permanece no JSON, mas o adaptador SSD atual não o
utiliza. A confiança e as classes permitidas são aplicadas; não há etapa adicional
de NMS configurável nesse adaptador.

Veja o [README](README.md) para instalação, operação do dashboard e limitações;
[backend/MONITOR.md](backend/MONITOR.md) detalha captura e persistência.
