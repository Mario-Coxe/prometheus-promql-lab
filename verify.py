#!/usr/bin/env python3
import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    credentials = {}
    env_file = Path(__file__).resolve().parent / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, separator, value = line.strip().partition('=')
            if separator and not key.startswith('#'):
                credentials[key] = value.strip().strip("\"'")
    user = os.getenv('GRAFANA_ADMIN_USER', credentials.get('GRAFANA_ADMIN_USER', 'admin'))
    password = os.getenv('GRAFANA_ADMIN_PASSWORD', credentials.get('GRAFANA_ADMIN_PASSWORD', ''))
    if not password:
        raise ValueError('Executa ./lab.sh init ou define GRAFANA_ADMIN_PASSWORD.')
    auth = base64.b64encode(f'{user}:{password}'.encode()).decode()
    api = os.getenv('API_URL', 'http://127.0.0.1:3000').rstrip('/')
    prometheus = os.getenv('PROMETHEUS_URL', 'http://127.0.0.1:9090').rstrip('/')
    grafana = os.getenv('GRAFANA_URL', 'http://127.0.0.1:3001').rstrip('/')

    def get(url, expected=200):
        headers = {'Authorization': f'Basic {auth}'} if url.startswith(grafana + '/') else {}
        try:
            response = urlopen(Request(url, headers=headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read().decode()
            if response.code != expected:
                raise ValueError(f'{url}: esperado HTTP {expected}, recebido {response.code}.')
            return body

    def get_json(url):
        return json.loads(get(url))

    def query(expression):
        result = get_json(prometheus + '/api/v1/query?' + urlencode({'query': expression}))
        assert result['status'] == 'success', expression
        return result['data']['result']

    assert get_json(api + '/health')['status'] == 'ok', '/health não está OK.'
    get(api + '/ok')
    get(api + '/error', 500)
    started = time.monotonic()
    get(api + '/slow')
    assert time.monotonic() - started >= 1, '/slow não apresentou a latência esperada.'
    metrics = get(api + '/metrics')
    for name in ('demo_http_requests_total', 'demo_http_request_duration_seconds_bucket', 'process_resident_memory_bytes'):
        assert name in metrics, f'Métrica ausente: {name}'
    print('OK: rotas, HTTP 500, latência e métricas Node.js.')

    get(prometheus + '/-/ready')
    for _ in range(15):
        up = query('up{job="api"}')
        if up and all(float(sample['value'][1]) == 1 for sample in up):
            break
        time.sleep(1)
    else:
        raise ValueError('O target api não ficou UP; confirma /targets e recupera a API.')
    assert query('process_resident_memory_bytes{job="api"}'), 'Ainda não há métricas Node.js na TSDB.'
    print('OK: Prometheus pronto, target UP e métricas armazenadas.')

    assert get_json(grafana + '/api/health')['database'] == 'ok', 'BD Grafana indisponível.'
    datasource = get_json(grafana + '/api/datasources/uid/prometheus')
    assert datasource['url'] == 'http://prometheus:9090', 'URL incorreto no Data Source.'
    assert get_json(grafana + '/api/datasources/uid/prometheus/health')['status'] == 'OK', 'Falha na ligação Grafana → Prometheus.'
    dashboard = get_json(grafana + '/api/dashboards/uid/application-support-monitoring-lab')['dashboard']
    assert dashboard['title'] == 'Application Support — Monitoring Lab', 'Dashboard incorreto.'
    assert len(dashboard['panels']) == 7, 'Faltam painéis no dashboard.'
    for panel in dashboard['panels']:
        for target in panel.get('targets', []):
            query(target['expr'])
    print('OK: Grafana, ligação ao Prometheus e sete painéis provisionados; PromQL aceite pelo servidor.')

    rules = get_json(grafana + '/api/v1/provisioning/alert-rules')
    expected = {'lab-api-down': ('critical', '30s'), 'lab-high-http-500': ('warning', '1m')}
    for uid, (severity, pending) in expected.items():
        rule = next((rule for rule in rules if rule['uid'] == uid), None)
        assert rule, f'Alerta não provisionado: {uid}'
        assert rule['labels']['severity'] == severity and rule['for'] == pending, f'Configuração incorreta: {uid}'
        assert not rule.get('isPaused', False), f'Alerta pausado: {uid}'
        query(next(item['model']['expr'] for item in rule['data'] if item['refId'] == 'A'))
    titles = {rule['title'] for rule in rules if rule['uid'] in expected}
    for _ in range(8):
        groups = get_json(grafana + '/api/prometheus/grafana/api/v1/rules')['data']['groups']
        evaluated = {rule['name']: rule for group in groups for rule in group['rules'] if rule['name'] in titles}
        if titles == set(evaluated) and all(rule['health'] == 'ok' for rule in evaluated.values()):
            break
        time.sleep(2)
    else:
        raise ValueError('Os alertas ainda não têm avaliação saudável; consulta os erros em Alert rules.')
    policy = get_json(grafana + '/api/v1/provisioning/policies')
    assert policy['receiver'] == 'lab-disabled', 'Receiver inesperado.'
    assert policy['routes'][0]['mute_time_intervals'] == ['lab-notifications-disabled'], 'Notificações não estão silenciadas.'
    print('OK: dois alertas Grafana com avaliação saudável e notificações silenciadas.')
    print('As transições Normal → Pending → Firing devem ser testadas com ./lab.sh e observadas no Grafana.')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError, StopIteration) as error:
        sys.exit(f'FALHOU: {error}')
