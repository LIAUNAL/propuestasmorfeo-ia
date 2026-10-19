#!/usr/bin/env bash
#
# compilar-pdf.sh — Compila la propuesta activa a PDF usando build.sh en redaccion/
#
# Uso:
#   ./compilar-pdf.sh              Compila la corrida activa (proposals/.current-run)
#   ./compilar-pdf.sh [run-id]     Compila una corrida específica
#   ./compilar-pdf.sh --clean      Limpia auxiliares y recompila
#   ./compilar-pdf.sh -y           Omite confirmaciones interactivas (ej. doi2bib3)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/scripts/init-run.sh" ]]; then
  PROJECT_ROOT="${SCRIPT_DIR}"
elif [[ -f "${SCRIPT_DIR}/../scripts/init-run.sh" ]] || [[ -d "${SCRIPT_DIR}/../proposals" ]]; then
  PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  PROJECT_ROOT="${SCRIPT_DIR}"
fi

PROPOSALS_DIR="${PROJECT_ROOT}/proposals"
POINTER="${PROPOSALS_DIR}/.current-run"

RUN_ID=""
BUILD_ARGS=()
AUTO_YES=0

for arg in "$@"; do
  if [[ "${arg}" == "-y" ]] || [[ "${arg}" == "--yes" ]]; then
    AUTO_YES=1
  elif [[ -z "${RUN_ID}" ]] && [[ ! "${arg}" =~ ^- ]] && [[ -d "${PROPOSALS_DIR}/${arg}" ]]; then
    RUN_ID="${arg}"
  else
    BUILD_ARGS+=("${arg}")
  fi
done

if [[ -z "${RUN_ID}" ]]; then
  if [[ -f "${POINTER}" ]]; then
    RUN_ID="$(tr -d '[:space:]' < "${POINTER}")"
  fi
fi

if [[ -z "${RUN_ID}" ]]; then
  printf "\033[0;31m[FAIL]\033[0m No hay ninguna corrida activa en '%s' ni se especificó un <run-id> válido.\n" "${POINTER}" >&2
  printf "Uso: %s [run-id] [opciones de build.sh]\n" "$0" >&2
  printf "Corridas disponibles en %s:\n" "${PROPOSALS_DIR}" >&2
  if [[ -d "${PROPOSALS_DIR}" ]]; then
    ls -1 "${PROPOSALS_DIR}" 2>/dev/null | grep -v '^\.' || printf "  (ninguna)\n"
  fi
  exit 1
fi

RUN_ROOT="${PROPOSALS_DIR}/${RUN_ID}"
REDACCION_DIR="${RUN_ROOT}/redaccion"
BUILD_SCRIPT="${REDACCION_DIR}/build.sh"

if [[ ! -f "${BUILD_SCRIPT}" ]]; then
  printf "\033[0;31m[FAIL]\033[0m No se encontró el script de compilación en '%s'.\n" "${BUILD_SCRIPT}" >&2
  exit 1
fi

printf "\033[0;34m[compilar-pdf]\033[0m Compilando PDF para la corrida: \033[1;33m%s\033[0m\n" "${RUN_ID}"

(
  cd "${REDACCION_DIR}"
  if [[ "${AUTO_YES}" -eq 1 ]]; then
    if [[ ${#BUILD_ARGS[@]} -gt 0 ]]; then
      echo "y" | ./build.sh "${BUILD_ARGS[@]}"
    else
      echo "y" | ./build.sh
    fi
  elif [[ ${#BUILD_ARGS[@]} -gt 0 ]]; then
    ./build.sh "${BUILD_ARGS[@]}"
  else
    ./build.sh
  fi
)

PDF_FILE="${REDACCION_DIR}/main.pdf"
if [[ -f "${PDF_FILE}" ]]; then
  PDF_SIZE="$(du -h "${PDF_FILE}" | cut -f1)"
  printf "\033[0;32m[ OK ]\033[0m PDF generado exitosamente: %s (%s)\n" "${PDF_FILE}" "${PDF_SIZE}"
else
  printf "\033[0;31m[FAIL]\033[0m El archivo PDF no fue generado.\n" >&2
  exit 1
fi
