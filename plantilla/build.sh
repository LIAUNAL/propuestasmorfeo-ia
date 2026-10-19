#!/usr/bin/env bash
#
# build.sh — Compila la propuesta de investigación (LaTeX + natbib/apalike, BibTeX).
#
# Uso:
#   ./build.sh              Compilación normal (latexmk)
#   ./build.sh --clean      Limpia artefactos auxiliares y recompila desde cero
#   ./build.sh --clean-only Solo limpia artefactos (no compila)
#   ./build.sh --manual     Usa la secuencia manual pdflatex→bibtex→pdflatex×2
#   ./build.sh --watch      Recompila automáticamente al detectar cambios
#   ./build.sh --docx       Exporta a Word (main.docx, junto a main.tex) vía pandoc (acepta opcionalmente --csl <archivo.csl>)
#   ./build.sh --help       Muestra esta ayuda
#
# Requisitos: pdflatex, bibtex, latexmk; opcional: doi2bib3
#   (instalable con 'pipx install git+https://github.com/CarlosAndres12/doi2bib3.git');
#   para --docx: pandoc, pdftoppm (todos en PATH).
#
set -euo pipefail

# --- Configuración -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="main.tex"
PDF="main.pdf"
ENGINE="pdflatex"
# La guía (guiaProyectosIA_Agente.md > "Convenciones técnicas de LaTeX") exige
# natbib + apalike (citas autor-año), no biblatex/biber: apalike es un .bst
# clásico procesado por bibtex, no genera el .bcf que biber requiere.
BIBENGINE="bibtex"
# doi2bib3 repara/normaliza refs.bib antes de bibtex (ver repair_bib).
BIB_FILE="refs.bib"
DOIREPAIR_BIN="doi2bib3"

# Colores (si la terminal los soporta)
if [[ -t 1 ]]; then
  C_RED='\033[0;31m'; C_GRN='\033[0;32m'; C_YLW='\033[1;33m'
  C_BLU='\033[0;34m'; C_RST='\033[0m'
else
  C_RED=''; C_GRN=''; C_YLW=''; C_BLU=''; C_RST=''
fi

log()  { printf "${C_BLU}[build]${C_RST} %s\n" "$*"; }
ok()   { printf "${C_GRN}[ OK ]${C_RST} %s\n" "$*"; }
warn() { printf "${C_YLW}[WARN]${C_RST} %s\n" "$*"; }
err()  { printf "${C_RED}[FAIL]${C_RST} %s\n" "$*" >&2; }

# --- Artefactos auxiliares a limpiar -----------------------------------------
AUX_EXT=(
  aux bcf bbl blg fdb_latexmk fls log out run.xml toc lof lot
  nav snm vrb idx ilg ind xdv synctex.gz
)

clean_artifacts() {
  log "Limpiando artefactos auxiliares..."
  for ext in "${AUX_EXT[@]}"; do
    rm -f "${SCRIPT_DIR}"/*.${ext} 2>/dev/null || true
  done
  # latexmk también deja _minted-* y auto-* en subdirectorios
  find "${SCRIPT_DIR}" -maxdepth 2 -type f \( -name "*.aux" -o -name "*.bbl" \
    -o -name "*.bcf" -o -name "*.log" -o -name "*.out" -o -name "*.fls" \
    -o -name "*.fdb_latexmk" -o -name "*.run.xml" -o -name "*.synctex.gz" \) \
    -delete 2>/dev/null || true
  # refs.bib.bak lo escribe doi2bib3 --overwrite_backup; no usar *.bak (no clobberearía operador)
  rm -f "${SCRIPT_DIR}/refs.bib.bak" 2>/dev/null || true
  ok "Artefactos eliminados."
}

# --- Reparación de refs.bib (doi2bib3) ---------------------------------------
repair_bib() {
  if [[ "${SKIP_DOI_REPAIR:-0}" == "1" ]]; then
    log "SKIP_DOI_REPAIR=1 activo: salteando reparación DOI para compilación rápida."
    return 0
  fi
  local bib="${SCRIPT_DIR}/${BIB_FILE}"
  if [[ ! -f "${bib}" ]]; then
    warn "${BIB_FILE} ausente — salteando reparación DOI (se crea en Fase 2 del pipeline)."
    return 0
  fi
  if ! command -v "${DOIREPAIR_BIN}" >/dev/null 2>&1; then
    warn "${DOIREPAIR_BIN} no está en PATH. Instalalo con:"
    warn "  pipx install git+https://github.com/CarlosAndres12/doi2bib3.git"
    if [[ -t 0 ]]; then
      # Sesión interactiva: parar y preguntar
      printf "${C_YLW}[WARN]${C_RST} ¿Continuar compilando SIN reparar refs.bib? [y/N] "
      local answer=""
      read -r answer
      case "${answer}" in
        [yY]|[yY][eE][sS]|[sS]|[sS][iI]) warn "Continuando SIN reparación DOI." ; return 0 ;;
        *) err "Abortando por decisión del operador. Instalá doi2bib3 y re-ejecutá." ; exit 1 ;;
      esac
    else
      # No-TTY (CI/pipe): no colgar; continuar sin reparar
      warn "stdin no es TTY — continuando SIN reparación DOI."
      return 0
    fi
  fi
  log "Reparando ${BIB_FILE} con ${DOIREPAIR_BIN} (--normalize --overwrite_backup)..."
  ( cd "${SCRIPT_DIR}" && "${DOIREPAIR_BIN}" repair "${BIB_FILE}" --normalize --overwrite_backup ) \
    | sed 's/^/  /' || { warn "${DOIREPAIR_BIN} reportó errores; continuando igual." ; return 0 ; }
  ok "refs.bib reparado."
}

# --- Verificación de dependencias --------------------------------------------
check_deps() {
  local mode="${1:-latexmk}"
  local missing=()
  local tools=("${ENGINE}" "${BIBENGINE}")
  if [[ "${mode}" == "docx" ]]; then
    tools+=("pandoc" "pdftoppm")   # docx: conversión y rasterizado de diagramas
  fi
  for tool in "${tools[@]}"; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
      missing+=("${tool}")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    err "Faltan dependencias: ${missing[*]}"
    err "Instala TeX Live (pdflatex, bibtex) o MiKTeX; para --docx: 'brew install pandoc' (pdftoppm viene con poppler)."
    exit 1
  fi
  if [[ ! -f "${SCRIPT_DIR}/${MAIN}" ]]; then
    err "No existe ${SCRIPT_DIR}/${MAIN}."
    err "init-run.sh siembra main.tex desde plantilla/main.tex al crear la corrida."
    err "Copialo a mano desde la plantilla del marco o vuelve a correr /propuesta-init."
    exit 1
  fi
}

# --- Compilación con latexmk (por defecto) -----------------------------------
build_latexmk() {
  log "Compilando con latexmk (${ENGINE} + ${BIBENGINE})..."
  cd "${SCRIPT_DIR}"
  latexmk \
    -f \
    -pdf \
    -pdflatex="${ENGINE} -interaction=nonstopmode -synctex=1 %O %S" \
    -bibtex \
    -shell-escape \
    "${MAIN}" 2>&1 | sed 's/^/  /' || true
  # latexmk devuelve non-zero si hay errores de LaTeX, pero el PDF puede
  # haberse generado correctamente. Verificamos el PDF, no el exit code.
  # latexmk devuelve 0 incluso con warnings; verificar que el PDF existe
  if [[ -f "${PDF}" ]]; then
    local pages
    pages=$(pdfinfo "${PDF}" 2>/dev/null | awk '/^Pages:/{print $2}' || echo "?")
    local size
    size=$(du -h "${PDF}" | cut -f1)
    ok "Compilación exitosa: ${PDF} (${pages} páginas, ${size})"
    # Reportar errores y warnings de LaTeX aunque el PDF se generara
    # Nota: grep -c imprime 0 y sale con código 1 cuando no hay coincidencias;
    # el fallback || echo 0 concatenaría otro "0\n0" y rompería la aritmética.
    local errs warns
    errs=$(grep -c '^!' "${SCRIPT_DIR}/main.log" 2>/dev/null; true)
    errs="${errs:-0}"
    warns=$(grep -c 'Warning' "${SCRIPT_DIR}/main.log" 2>/dev/null; true)
    warns="${warns:-0}"
    if [[ "${errs}" -gt 0 ]]; then
      err "LaTeX reportó ${errs} error(es) real(es) — revisa ${SCRIPT_DIR}/main.log; el PDF puede estar incompleto o mal formado"
      exit 1
    fi
    if [[ "${warns}" -gt 0 ]]; then
      warn "LaTeX emitió ${warns} advertencia(s) — revisa main.log"
    fi
  else
    err "No se generó ${PDF}. Revisa los errores arriba."
    exit 1
  fi
}

# --- Compilación manual (pdflatex → bibtex → pdflatex × 2) -------------------
build_manual() {
  log "Compilación manual: pdflatex → ${BIBENGINE} → pdflatex × 2"
  cd "${SCRIPT_DIR}"

  log "Paso 1/4: pdflatex (pass 1 — genera .aux con las citas)..."
  if ! ${ENGINE} -interaction=nonstopmode -synctex=1 "${MAIN}" 2>&1 | sed 's/^/  /'; then
    warn "pdflatex (pass 1) reportó errores. Continuando (nonstopmode)..."
  fi

  log "Paso 2/4: ${BIBENGINE} (procesa bibliografía apalike)..."
  if ! ${BIBENGINE} "$(basename "${MAIN}" .tex)" 2>&1 | sed 's/^/  /'; then
    warn "${BIBENGINE} reportó advertencias. Continuando..."
  fi

  log "Paso 3/4: pdflatex (pass 2 — incorpora bibliografía)..."
  if ! ${ENGINE} -interaction=nonstopmode -synctex=1 "${MAIN}" 2>&1 | sed 's/^/  /'; then
    warn "pdflatex (pass 2) reportó errores. Continuando (nonstopmode)..."
  fi

  log "Paso 4/4: pdflatex (pass 3 — resuelve referencias cruzadas)..."
  if ! ${ENGINE} -interaction=nonstopmode -synctex=1 "${MAIN}" 2>&1 | sed 's/^/  /'; then
    warn "pdflatex (pass 3) reportó errores. Continuando (nonstopmode)..."
  fi

  if [[ -f "${PDF}" ]]; then
    local pages
    pages=$(pdfinfo "${PDF}" 2>/dev/null | awk '/^Pages:/{print $2}' || echo "?")
    local size
    size=$(du -h "${PDF}" | cut -f1)
    ok "Compilación exitosa: ${PDF} (${pages} páginas, ${size})"
  else
    err "No se generó ${PDF}. Revisa los errores arriba."
    exit 1
  fi
}

# --- Modo watch --------------------------------------------------------------
build_watch() {
  log "Modo watch activo (latexmk -pvc). Ctrl+C para salir."
  cd "${SCRIPT_DIR}"
  latexmk \
    -pdf \
    -pdflatex="${ENGINE} -interaction=nonstopmode -synctex=1 %O %S" \
    -bibtex \
    -shell-escape \
    -pvc \
    "${MAIN}"
}

# --- Exportación a Word (.docx vía pandoc) -----------------------------------
build_docx() {
  local custom_csl="${1:-}"
  cd "${SCRIPT_DIR}"

  # The .docx is derived from the already-compiled PDF: require main.pdf first.
  if [[ ! -f "${PDF}" ]]; then
    err "No existe ${PDF}. Compila primero (./build.sh) antes de --docx."
    exit 1
  fi

  local csl_path=""
  if [[ -n "${custom_csl}" ]]; then
    csl_path="$(realpath "${custom_csl}" 2>/dev/null || echo "${custom_csl}")"
    if [[ ! -f "${csl_path}" ]]; then
      err "No existe el archivo CSL especificado: ${custom_csl}"
      exit 1
    fi
  else
    if [[ -f "${SCRIPT_DIR}/scripts/apa.csl" ]]; then
      csl_path="${SCRIPT_DIR}/scripts/apa.csl"
    elif [[ -f "${SCRIPT_DIR}/../scripts/apa.csl" ]]; then
      csl_path="${SCRIPT_DIR}/../scripts/apa.csl"
    else
      warn "No se encontró apa.csl por defecto; pandoc usará el estilo CSL integrado por defecto."
    fi
  fi

  local docx_abs="${SCRIPT_DIR}/main.docx"
  local ref_abs="${SCRIPT_DIR}/templates/reference.docx"
  local stage
  stage="$(mktemp -d)"

  # 1) Rasterize TikZ/pgfgantt diagrams to PNG and stage a docx-safe tex tree
  #    (pandoc's LaTeX reader cannot render raw TikZ/ganttchart).
  log "Preparando árbol docx (rasterizando diagramas TikZ/pgfgantt → PNG)..."
  if ! python3 scripts/prep_docx.py --stage "${stage}"; then
    err "Falló la preparación docx (rasterizado/sustitución). Revisa prep_docx.py."
    rm -rf "${stage}"
    exit 1
  fi

  # 2) Institutional-branding reference template (--reference-doc).
  if [[ ! -f "${ref_abs}" ]]; then
    warn "No existe ${ref_abs}. Generando plantilla por defecto (SIN logos)."
    mkdir -p "${SCRIPT_DIR}/templates"
    if ! pandoc --print-default-data-file reference.docx > "${ref_abs}"; then
      err "No se pudo generar la plantilla por defecto."
      rm -rf "${stage}"; exit 1
    fi
    warn "Edita ${ref_abs} UNA sola vez en Word/LibreOffice e inserta los 3 logos"
    warn "(UNAL cabecera-der, GCPDS pie-izq, LabIA pie-der) para igualar el PDF."
  fi

  # 3) LaTeX -> docx conversion. Surface the known cosmetic limitations at build time.
  log "Convirtiendo a Word con pandoc..."
  warn "El sombreado de filas (xcolor[table]) de §13 NO se preserva en .docx;"
  warn "la tabla conserva estructura, datos y totales. El Gantt de §14 va como imagen."

  local pandoc_args=(
    "main.tex"
    --from=latex
    --reference-doc="${ref_abs}"
    --citeproc
    --bibliography="refs.bib"
  )

  if [[ -n "${csl_path}" ]]; then
    log "Usando estilo de citas CSL: ${csl_path}"
    pandoc_args+=(--csl="${csl_path}")
  fi

  pandoc_args+=(-o "${docx_abs}")

  if (cd "${stage}" && pandoc "${pandoc_args[@]}"); then
    local size; size=$(du -h "${docx_abs}" | cut -f1)
    ok "Exportación exitosa: main.docx (${size})"
  else
    err "pandoc falló al generar main.docx."
    rm -rf "${stage}"; exit 1
  fi
  rm -rf "${stage}"
}

# --- Ayuda -------------------------------------------------------------------
show_help() {
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
}

# --- Main --------------------------------------------------------------------
main() {
  local mode="latexmk"
  local do_clean=false
  local csl_file=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --clean)        do_clean=true ;;
      --clean-only)   clean_artifacts; exit 0 ;;
      --manual)       mode="manual" ;;
      --watch)        mode="watch" ;;
      --docx)         mode="docx" ;;
      --csl)
        shift
        if [[ $# -eq 0 ]]; then
          err "Falta la ruta del archivo CSL para --csl."
          exit 1
        fi
        csl_file="$1"
        ;;
      --csl=*)        csl_file="${1#*=}" ;;
      --help|-h)      show_help; exit 0 ;;
      *) err "Opción desconocida: $1"; show_help; exit 1 ;;
    esac
    shift
  done

  check_deps "${mode}"

  if [[ "${do_clean}" == true ]]; then
    clean_artifacts
  fi

  repair_bib   # normaliza refs.bib antes de cualquier pase bibtex/citeproc

  case "${mode}" in
    latexmk) build_latexmk ;;
    manual)  build_manual ;;
    watch)   build_watch ;;
    docx)    build_docx "${csl_file}" ;;
  esac
}

main "$@"
