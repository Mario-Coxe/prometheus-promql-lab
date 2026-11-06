const express = require('express');
const client = require('@prometheus-io/client');

const app = express();
client.collectDefaultMetrics();

const requests = new client.Counter({
  name: 'demo_http_requests_total',
  help: 'Total HTTP requests received by the demo API',
  labelNames: ['method', 'route', 'status'],
});

const duration = new client.Histogram({
  name: 'demo_http_request_duration_seconds',
  help: 'Duration of demo API HTTP requests in seconds',
  labelNames: ['method', 'route', 'status'],
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
});

const knownRoutes = new Set(['/health', '/ok', '/error', '/slow']);

app.use((req, res, next) => {
  if (req.path === '/metrics') return next();
  const started = process.hrtime.bigint();

  res.on('finish', () => {
    const route = knownRoutes.has(req.path) ? req.path : '/other';
    const labels = { method: req.method, route, status: String(res.statusCode) };
    requests.inc(labels);
    duration.observe(labels, Number(process.hrtime.bigint() - started) / 1e9);
  });

  next();
});

app.get('/health', (req, res) => res.json({ status: 'ok' }));
app.get('/ok', (req, res) => res.json({ message: 'Operação concluída' }));

app.get('/error', (req, res) => {
  console.error(`${new Date().toISOString()} ERROR Falha HTTP 500 simulada`);
  res.status(500).json({ error: 'Falha simulada' });
});

app.get('/slow', async (req, res) => {
  await new Promise(resolve => setTimeout(resolve, 1200));
  res.json({ message: 'Resposta lenta simulada' });
});

app.get('/metrics', async (req, res) => {
  res.setHeader('Content-Type', client.contentType);
  res.end(await client.register.metrics());
});

app.listen(3000, '0.0.0.0', () => {
  console.log('API pronta na porta 3000');
});
