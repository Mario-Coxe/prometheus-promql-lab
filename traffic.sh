#!/bin/sh
set -eu
for i in $(seq 1 25); do
  curl -fsS -o /dev/null http://localhost:3000/ok
  curl -sS -o /dev/null http://localhost:3000/error
  if [ "$((i % 5))" -eq 0 ]; then
    curl -fsS -o /dev/null http://localhost:3000/slow
  fi
  sleep 1
done
echo "25 respostas OK, 25 erros HTTP 500 e 5 respostas lentas simulados."
