# Relatório: Detecções não exibidas no dashboard (valor zerado)

## Resumo

Ao atualizar o campo `detections` diretamente na coleção `stations` via `mongosh`, as alterações não foram refletidas no dashboard. As estações aparecem normalmente, mas o número de detecções permanece zerado.

## Raiz do problema

O backend **não lê** o campo `detections` da coleção `stations` para exibir no dashboard. Ele calcula o total de detecções de uma forma diferente da esperada.

### Fluxo de dados do dashboard

1. O dashboard chama `GET /api/stations`
2. No `backend/app.py`, o endpoint `get_stations()` (linha 121-134) faz o seguinte:
   - Chama `detection_summary_for_stations()` que **agrega documentos da coleção `detection_events`** via MongoDB aggregation pipeline
   - Para cada estação no `stations_collection`, pega o resultado da agregação (`summary["total"]`) e descarta o campo `detections` que existe no documento da estação

```python
# backend/app.py, linha 121-134
@app.get("/api/stations")
def get_stations():
    summaries = detection_summary_for_stations()  # lê de detection_events
    result = []
    for station in stations_collection.find():
        summary = summaries.get(station["station_id"], {"total": 0, ...})
        result.append({
            ...
            "detections": summary["total"],  # <-- vem de detection_events, NÃO de station["detections"]
            ...
        })
    return result
```

### O que aconteceu

- O comando mongosh atualizou `stations.detections` na coleção `stations` (campo do documento da estação)
- A coleção `detection_events` permaneceu **vazia** (sem documentos)
- `detection_summary_for_stations()` retornou `{"total": 0}` para todas as estações
- O dashboard exibiu `0` para todas as detecções

### Dados no dashboard dependem de qual coleção?

| O que o dashboard exibe | Fonte |
|---|---|
| Nomes, localização, cidade, distrito das estações | `stations` collection |
| **Número de detecções** | **`detection_events` collection (agregação)** |
| Tipos de detecção e última detecção | `detection_events` collection |

## Solução

Para que as detecções apareçam no dashboard, é necessário inserir documentos na coleção `detection_events`, e não apenas atualizar o campo `detections` na coleção `stations`.

Substitua o conteúdo de `contagem.txt` pelo seguinte comando, que insere um número aleatório de eventos de detecção (1-200) por estação na coleção `detection_events`:

```javascript
db.stations.find().forEach(function(station) {
    var stationId = station.station_id;
    var count = Math.floor(Math.random() * 200) + 1;
    for (var i = 0; i < count; i++) {
        db.detection_events.insertOne({
            station_id: stationId,
            detection_type: "bottle",
            confidence: Math.random(),
            track_id: i,
            detected_at: new Date(),
            event_id: "evt_" + stationId + "_" + i + "_" + Date.now()
        });
    }
});
```

**Alternativa rápida** (sem inserir eventos individuais, apenas populando o `detection_events` com contagens agrupadas):

```javascript
db.stations.find().forEach(function(station) {
    var stationId = station.station_id;
    var count = Math.floor(Math.random() * 200) + 1;
    db.detection_events.insertOne({
        station_id: stationId,
        detection_type: "bottle",
        confidence: 1.0,
        track_id: 0,
        detected_at: new Date(),
        event_id: "evt_" + stationId + "_" + Date.now()
    });
});
```

## Nota

A coleção `detection_events` é usada para armazenar eventos individuais de detecção (cada passagem de um objeto pela câmera). O campo `detections` na coleção `stations` existe no banco de dados mas **não é utilizado** pela API — é um campo morto que o backend ignora completamente.
