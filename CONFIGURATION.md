# Configuração compartilhada

Edite `aquamonitor.json`, na raiz, para configurar ambos os runners.
As configurações da estação foram consolidadas neste arquivo.
`backend/settings.py` carrega e valida o JSON usando apenas a biblioteca padrão;
`backend/detection/config.py` adapta esses valores às dataclasses do pipeline.

- `station_id`: identidade cadastrada na API.
- `backend`: endereço, timeout, caminho dos eventos, verificação inicial e intervalo de publicação.
- `camera`: índice, resolução e FPS.
- `ssd_mobilenet`: arquivos, entrada, confiança, classes e NMS do adaptador backend.
- `detection`: configuração YOLO.
- `detection_interval_ms`: intervalo de inferência nos dois runners.
- `tracking`: posição proporcional da linha, direção e parâmetros de centróide.
- `bytetrack`: parâmetros exclusivos do rastreador do backend.
- `station_document`: documento local usado pelo monitor em `backend.monitoring`.

Os algoritmos de rastreamento permanecem diferentes. O monitor em `backend.monitoring`
calcula a linha pela altura efetiva do frame; o backend usa a resolução solicitada.
`backend.enabled` controla o envio opcional no runner backend; os monitores em `backend.monitoring` continuam enviando por padrão. `require_connection_on_startup` é
usado pelo monitor em `backend.monitoring`.

Todos os caminhos de arquivos no JSON são relativos à pasta desse JSON, não ao
terminal. Arquivos de configuração alternativos devem fornecer todas as seções.

```bash
python backend/detection/object-ident.py --config aquamonitor.json --publish
python -m backend.monitoring.monitor_residuos --config aquamonitor.json --detector ssd --no-display
```

Precedência: opções específicas da CLI sobre configuração carregada; variáveis
compatíveis sobrescrevem JSON. `AQUAMONITOR_CONFIG` define o arquivo padrão;
`--config` seleciona outro arquivo. `AQUADETECTOR_API_URL` tem prioridade sobre
`BOTTLE_COUNT_API_URL` quando ambas estão definidas. Também são aceitas
`BOTTLE_COUNT_STATION_ID`, `BOTTLE_COUNT_API_ENABLED` e
`BOTTLE_COUNT_PUBLISH_INTERVAL`. Não há carregamento automático de `.env`.

O IP já configurado foi preservado. Use o IP real do servidor, não `0.0.0.0`.

Ambos os runners enviam eventos individuais para `backend.detections_path`
(`/api/detections`). A estação deve estar cadastrada na API. No `object-ident.py`,
os eventos são guardados em memória até a confirmação ou resposta 409 (duplicado);
falhas preservam UUID e horário para a próxima tentativa. Reiniciar o processo
perde pendências. O envio desse runner continua síncrono, no intervalo configurado.
A API e o dashboard não leem este JSON: ele configura a estação.
