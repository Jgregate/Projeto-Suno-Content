#!/usr/bin/env bash
# Sobe a demo a partir de um clone limpo.
#
#   scripts/demo.sh            instala, testa e sobe API (:8000) + frontend (:5173) sobre o cache em outputs/
#   scripts/demo.sh check      igual, mas só confirma que os dois respondem e encerra (para CI / teste de clone)
#
# No Windows (PowerShell): scripts\demo.ps1
#
# Modo demo: a API serve as execuções salvas em outputs/ sem chamar LLM.
set -euo pipefail

MODE="${1:-demo}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

step "Dependências Python (uv sync)"
uv sync --all-extras

step "Dependências do frontend (npm ci)"
(cd frontend && npm ci --no-fund --no-audit)
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env

step "Testes do backend"
uv run pytest

step "Testes, lint e build do frontend"
(cd frontend && npm run test && npm run lint && npm run build)

PIDS=()
kill_tree() {  # encerra o processo e todos os filhos (npm -> vite, uv -> uvicorn)
  local pid="$1"
  for child in $(pgrep -P "$pid" 2>/dev/null); do kill_tree "$child"; done
  kill "$pid" 2>/dev/null || true
}
cleanup() { for pid in "${PIDS[@]:-}"; do [ -n "$pid" ] && kill_tree "$pid"; done; }
trap cleanup EXIT INT TERM

if [ -z "$(ls outputs/*/*.json 2>/dev/null)" ]; then
  echo "Aviso: outputs/ não tem execuções salvas; a API vai chamar o LLM ao gerar (precisa do .env com chaves)."
fi
step "API em modo demo (cache em outputs/)"
uv run uvicorn backend.api.main:app --port 8000 &
PIDS+=($!)

step "Frontend"
(cd frontend && npm run dev -- --port 5173 --strictPort) &
PIDS+=($!)

wait_for() {
  for _ in $(seq 1 60); do curl -fsS "$1" >/dev/null 2>&1 && return 0; sleep 1; done
  echo "Não respondeu: $1" >&2
  return 1
}
wait_for http://127.0.0.1:8000/documents
wait_for http://localhost:5173/
wait_for http://localhost:5173/api/documents   # proxy do Vite -> API (caminho que o navegador usa)

DOCS="$(curl -fsS http://127.0.0.1:8000/documents)"
echo "Documentos servidos pela API: $DOCS" | cut -c1-300

if [ "$MODE" = "check" ]; then
  step "OK: API e frontend responderam"
  exit 0
fi

step "Pronto: abra http://localhost:5173 (Ctrl+C encerra)"
wait
