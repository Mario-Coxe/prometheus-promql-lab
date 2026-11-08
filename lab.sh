#!/bin/sh
set -eu
cd "$(dirname "$0")"

mode=${1:-status}
api_url=${API_URL:-http://127.0.0.1:3000}

case "$mode" in
  init)
    if [ -e .env ]; then
      echo '.env já existe; credenciais mantidas.'
      exit 0
    fi
    (
      umask 077
      password=$(openssl rand -hex 24)
      printf 'GRAFANA_ADMIN_USER=admin\nGRAFANA_ADMIN_PASSWORD=%s\n' "$password" > .env
    )
    echo 'Credenciais criadas em .env. Consulta o ficheiro para iniciar sessão.'
    ;;
  status)
    curl --max-time 5 -fsS "$api_url/health"
    printf '\n'
    ;;
  normal|errors|slow)
    duration=${2:-90}
    case "$duration" in
      ''|*[!0-9]*|0*) echo 'A duração deve ser um inteiro positivo, sem zeros iniciais.' >&2; exit 1 ;;
    esac
    end=$(( $(date +%s) + duration ))
    echo "Cenário $mode durante ${duration}s. Ctrl+C termina o tráfego."
    while [ "$(date +%s)" -lt "$end" ]; do
      case "$mode" in
        normal) curl --max-time 5 -fsS -o /dev/null "$api_url/ok" ;;
        errors)
          curl --max-time 5 -fsS -o /dev/null "$api_url/ok"
          code=$(curl --max-time 5 -sS -o /dev/null -w '%{http_code}' "$api_url/error")
          [ "$code" = 500 ] || { echo "Esperado HTTP 500; recebido $code." >&2; exit 1; }
          ;;
        slow) curl --max-time 5 -fsS -o /dev/null "$api_url/slow" ;;
      esac
      sleep 0.2
    done
    ;;
  down) docker compose stop api ;;
  recover) docker compose start api ;;
  *) echo "Uso: $0 {init|status|normal|errors|slow|down|recover} [segundos]" >&2; exit 1 ;;
esac
