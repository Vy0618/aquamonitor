# Validação do dashboard

Execute os testes na raiz, com Node.js 22 ou superior; não é necessário instalar
pacotes npm:

```bash
node --test dashboard/tests/*.mjs
```

Os testes simulam API, DOM e camadas do mapa. Não validam a aparência nem executam
Leaflet em um navegador real. Para a verificação visual, inicie MongoDB, FastAPI e
o servidor estático seguindo o [README](../README.md).

## Conferência manual

1. Consulte `GET /api/stations`: cada estação deve conter `detection_summary`
   (`total`, `by_type`, `timestamp`), com `detections` igual ao total. Coordenadas
   devem estar no formato `[longitude, latitude]`.
2. Abra o painel: o modo inicial deve ser **Calor**. Estações zeradas não geram
   manchas. Compare contagens distintas; a referência fixa é 300, sem renormalizar
   ao filtrar. A sobreposição soma contribuições, portanto cores não representam
   uma contagem exata por estação.
3. Alterne entre **Calor**, **Estações** e **Ambos**. Confira círculos proporcionais
   no modo Estações, pequenos anéis no modo Ambos e legendas correspondentes.
4. Busque um ID existente, inclusive de estação zerada: o mapa deve aproximá-la,
   permitir visualizar os detalhes e mostrar o ID junto ao total no painel.
   Teste também entrada vazia e ID inexistente.
5. Selecione estado, município e distrito. Confira o enquadramento e as opções
   dependentes. Busque um ID oculto pelo filtro e confira a limpeza dos filtros.
6. Confira a classificação: soma por município e estado, ordem decrescente,
   limitada a cinco municípios e independente dos filtros locais.
7. Com uma base de testes, cadastre/exclua uma estação em `/crud.html`. Aguarde o
   próximo ciclo: filtros, mapa e classificação devem atualizar sem recarregar.
   Filtros ainda válidos, posição e ampliação devem permanecer. A exclusão da
   estação selecionada deve limpar seu indicador e contagens no painel.
8. Gere um evento pelo monitor. Confira a atualização dos totais da estação,
   popup, classificação e calor. O painel consulta todas as estações, não apenas
   a selecionada. Cada ciclo aguarda cinco segundos após a conclusão do anterior,
   mais a duração da próxima requisição; não é um prazo máximo de cinco segundos.
9. Interrompa temporariamente a API do ambiente de testes: os dados anteriores
   devem permanecer e o cabeçalho deve indicar falha. Reinicie a API e confira a
   recuperação automática. Repita abrindo a página com a API inicialmente parada.
10. Confira a interface em tela estreita, a rolagem lateral, navegação por teclado,
    foco visível e mensagens em português. O tempo de atividade reinicia ao
    recarregar a página; não representa a atividade da estação.
11. Com `tracking.direction: "both"`, atravesse a linha com uma garrafa de cima
    para baixo e depois com outra de baixo para cima: confira os incrementos em
    **Positivo** e **Negativo**, respectivamente, no painel e popup. Cada track é
    contado uma vez; voltar com o mesmo track não deve contar novamente. Eventos
    antigos aparecem em **Não informado**; eventos de outras classes não aumentam
    os contadores de sentido das garrafas. Confira `direction` nos novos eventos
    e `detection_summary.by_type_direction.bottle` na resposta da API.

## Consultas de apoio

```bash
curl --fail http://127.0.0.1:8000/api/stations
curl --fail http://127.0.0.1:8000/api/stations/1/detections
```

Ajuste o ID conforme o cadastro. O total é calculado a partir de eventos individuais
em `detection_events`. Alterar `stations.detections` não produz novas contagens.
Os endpoints antigos `bottle-count` não existem nesta versão.
