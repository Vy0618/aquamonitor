# Publicação independente da captura

O runner continua usando `--publish` (ou `BOTTLE_COUNT_API_ENABLED=1`).
`DetectionPipeline.process()` apenas enfileira cruzamentos e agenda publicação.
Uma thread exclusiva executa HTTP; requisições lentas não bloqueiam a câmera.
O intervalo configurado continua controlando o agendamento pelo runner.

`api_client.py` mantém os payloads e executa HTTP; `publisher.py` controla a
thread. Solicitações de publicação são agrupadas, sem criar uma thread por frame.
Cada lote contém apenas os eventos pendentes no início daquela tentativa.
Falhas de rede preservam o evento e seu UUID para a próxima tentativa; HTTP 409
continua confirmando entrega anterior.

`publish_if_due()` agora indica agendamento, não confirmação de entrega.
Ao terminar de produzir eventos, chame `pipeline.close()`. O runner libera a
câmera antes dessa espera, limitada por padrão a cinco segundos. Eventos não
entregues e timeout de encerramento são informados pelo logger em stderr.

A fila permanece em memória: reiniciar o processo perde eventos pendentes.
Esta alteração separa a execução HTTP da captura; persistência SQLite e um
publicador em processo separado são etapas posteriores.
