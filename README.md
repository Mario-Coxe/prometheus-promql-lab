# Laboratório Prometheus + PromQL (Application Support Engineer)

## Pré-requisito

Docker Desktop a funcionar no Mac. No terminal, confirma `docker --version` e `docker compose version`.

## 1. Arrancar

```bash
docker compose up --build -d
docker compose ps
```

Abre:
- API: http://localhost:3000/health
- Endpoint de métricas: http://localhost:3000/metrics
- Prometheus: http://localhost:9090
- Estado dos targets: http://localhost:9090/targets

Espera cerca de 15 segundos. O target `api` deverá apresentar `UP`.

## 2. Entender a arquitetura

```
Browser / curl ---> API Node.js (localhost:3000)
                       | expõe GET /metrics
                       v
                  Prometheus (localhost:9090)
                  scrape a cada 5 segundos
                       |
                       v
                  PromQL / Graph
```

Dentro da rede do Docker Compose, o Prometheus usa `api:3000`, não `localhost:3000`. Os containers descobrem-se pelo nome do serviço.

## 3. Gerar dados e erros

```bash
./traffic.sh
```

O script envia 25 chamadas para `/ok` (200), 25 para `/error` (500) e 5 para `/slow` (200, aproximadamente 1,2 s). Assim, aparecem métricas de sucesso, erro e latência. Os erros são intencionais.

```bash
docker compose logs api --tail=20
```

## 4. Consultar métricas com PromQL

Vai ao Prometheus, insere cada expressão no campo de consulta e clica em **Execute**; usa **Table** ou **Graph**.

```
up{job="api"}
demo_http_requests_total
sum(rate(demo_http_requests_total[1m]))
sum(rate(demo_http_requests_total{status="500"}[1m]))
100 * sum(rate(demo_http_requests_total{status="500"}[1m])) / sum(rate(demo_http_requests_total[1m]))
histogram_quantile(0.95, sum by (le) (rate(demo_http_request_duration_seconds_bucket{route="/slow"}[1m])))
process_resident_memory_bytes / 1024 / 1024
```

Consulta `queries.promql` para mais exemplos. As funções `rate()` precisam de pelo menos duas amostras, e uma janela maior ajuda a estabilizar a leitura. Depois de alguns minutos sem tráfego, as taxas podem regressar a zero.

## 5. Simular indisponibilidade real

```bash
docker compose stop api
```

Depois de pelo menos duas recolhas (cerca de 10 segundos), executa:

```
up{job="api"}
```

Esperado: `0`. A métrica `up` indica **se o Prometheus conseguiu recolher métricas**, não prova por si só que todas as funcionalidades estão saudáveis.

Vai a http://localhost:9090/alerts. A regra `ApiIndisponivel` deve chegar a **FIRING** após o período configurado (`for: 15s`); a transição depende do ciclo de avaliação de 5 segundos. Esta regra não envia notificações (não há Alertmanager neste laboratório).

Recupera:

```bash
docker compose start api
```

Confirma que `up{job="api"}` volta a `1` e a regra deixa de disparar.

## 6. Limpar o laboratório

```bash
docker compose down
```

Para apagar **também os dados guardados** do Prometheus:

```bash
docker compose down -v
```

## Conceitos fundamentais

- **Target**: endpoint que o Prometheus recolhe.
- **Scrape**: recolha periódica de métricas via HTTP.
- **Counter**: valor cumulativo; `rate` transforma-o em taxa por segundo.
- **Histogram**: distribuição de durações, permitindo obter p95 aproximado.
- **Labels**: dimensões usadas para filtrar e agrupar séries temporais.
- **PromQL**: linguagem para investigar métricas.
- **Alert rule**: expressão PromQL que entra em `PENDING` e depois `FIRING` se continuar verdadeira durante `for`.

## Resposta curta de entrevista

> "Instrumentei uma API Node.js para expor métricas HTTP em `/metrics`. Configurei o Prometheus para recolher essas métricas a cada 5 segundos e utilizei PromQL para medir o tráfego, a taxa de erros 500, a latência p95 e a disponibilidade do target. Simulei uma falha e confirmei o estado do alerta."

Este projeto é um laboratório local, não uma configuração endurecida para produção. Em produção, protege o endpoint de métricas, revê retenção, segurança, cardinalidade das labels e o dimensionamento.
