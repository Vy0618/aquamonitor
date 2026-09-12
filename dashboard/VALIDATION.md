# Validação manual da dashboard

Não há infraestrutura de testes JavaScript no projeto. Após iniciar MongoDB,
FastAPI e o servidor estático da dashboard, valide o seguinte:

1. Consulte `GET /api/stations` e confirme que cada estação possui
   `bottle_count` e que `detections === bottle_count.count`.
2. Para uma estação com `bottle_count.count: 37`, confirme que heatmap, popup e
   sidebar mostram 37.
3. Confirme que uma estação sem métrica mostra intensidade zero, contagem zero
   e o estado `no data` sem quebrar o mapa.
4. Clique em outro marcador e confirme que a sidebar passa a fazer polling da
   estação selecionada.
5. Publique uma nova métrica e confirme, após no máximo três segundos, que a
   sidebar, popup e heatmap são atualizados.
6. Com filtros e diferentes níveis de zoom, confirme que o conjunto exibido e
   os raios do heatmap mantêm o comportamento anterior.
7. Pare a API temporariamente e confirme que a sidebar mostra `polling error`.

Comandos de apoio:

```bash
curl -s http://127.0.0.1:8000/api/stations
curl -s http://127.0.0.1:8000/api/stations/1/bottle-count
```
