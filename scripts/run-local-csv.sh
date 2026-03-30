#!/usr/bin/env bash
set -euo pipefail

# Ejecuta la simulación OSeMOSYS desde un directorio de CSV ya procesados (sin Excel ni BD).
# Equivalente en Linux a invocar manualmente:
#   cd backend && ../.venv/bin/python scripts/run_osemosys_cli.py csv <dir> [opciones]
#
# Uso:
#   ./scripts/run-local-csv.sh /ruta/al/directorio_csv [--solver glpk|highs] [--output-dir DIR] [--lp] ...

usage() {
  cat >&2 <<'EOF'
Uso: run-local-csv.sh <directorio_csv> [opciones de run_osemosys_cli.py csv]

Requiere .venv en la raíz del repositorio (mismas dependencias que el backend).

Opciones típicas (ver python scripts/run_osemosys_cli.py csv -h):
  --solver glpk|highs
  --output-dir, -o DIR
  --lp              generar archivo .lp
  --overwrite       escribir en --output-dir sin subcarpeta con timestamp
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
CLI="${BACKEND_DIR}/scripts/run_osemosys_cli.py"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

CSV_DIR="$1"
shift

if [[ ! -d "$CSV_DIR" ]]; then
  echo "ERROR: No existe el directorio: ${CSV_DIR}" >&2
  exit 1
fi

if [[ ! -f "$VENV_PYTHON" ]]; then
  echo "ERROR: No se encontró ${VENV_PYTHON}. Crea el venv en la raíz del repo (p. ej. python -m venv .venv && pip install -r backend/requirements.txt)." >&2
  exit 1
fi

if [[ ! -f "$CLI" ]]; then
  echo "ERROR: No se encontró ${CLI}" >&2
  exit 1
fi

echo "==> Simulación desde CSV: ${CSV_DIR}" >&2
exec "${VENV_PYTHON}" "${CLI}" csv "${CSV_DIR}" "$@"
