#!/bin/sh
set -eu
api_url=${API_URL:-http://127.0.0.1:3000}
for i in $(seq 1 25); do
  curl -fsS -o /dev/null "$api_url/ok"
  curl -sS -o /dev/null "$api_url/error"
  if [ "$((i % 5))" -eq 0 ]; then
    curl -fsS -o /dev/null "$api_url/slow"
  fi
  sleep 1
done
echo "25 respostas OK, 25 erros HTTP 500 e 5 respostas lentas simulados."
