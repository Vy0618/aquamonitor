# Documento local da estação

`station_document.py` cria, consulta e atualiza um documento JSON usando apenas
a biblioteca padrão do Python. Não acessa MongoDB, rede, câmera ou GPS.

Execute na raiz do projeto. Para iniciar usando um documento existente:

```sh
python -m backend.station_document init data/station.json < RaspberryPi/station/station.json
python -m backend.station_document show data/station.json
printf '%s\n' '{"status":"offline","detections":42}' | python -m backend.station_document update data/station.json
printf '%s\n' '{"location":{"type":"Point","coordinates":[-46.4526,-23.5015]}}' | python -m backend.station_document update data/station.json
```

O arquivo de entrada de `init` é um documento individual, não o array de
`stations.json` nem a configuração completa da Raspberry Pi. O exemplo acima
copia também a identidade e os totais da estação: use os dados da estação desejada.

Campos obrigatórios: `_id` no formato `{"$oid":"24 dígitos hexadecimais"}`,
`station_id` inteiro positivo, `detections` inteiro não negativo, `status`
(`online` ou `offline`), `location` GeoJSON Point e `administrative` com
`country`, `state`, `city` e `district` como textos não vazios.

`init` falha se o destino já existir. `update` exige um documento existente,
preserva `_id` e `station_id` e não reduz o total acumulado de detecções.
Objetos como `location` e `administrative` são substituídos por completo.
Entradas inválidas não alteram o arquivo. Arquivos corrompidos geram erro,
sem reiniciar silenciosamente os dados.

Os comandos imprimem somente JSON em stdout; erros vão para stderr, com saída 1
(erros de argumentos usam saída 2). A saída de sucesso é 0.
Também é possível importar `create_document`, `read_document` e `update_document`
de `backend.station_document`.

A gravação usa arquivo temporário no mesmo diretório, sincroniza seu conteúdo
e publica o documento completo de forma atômica. Use **um único escritor por
arquivo**: não há bloqueio para coordenar atualizações concorrentes. A ferramenta
não sincroniza alterações com a API e não é uma fila de eventos de detecção.
