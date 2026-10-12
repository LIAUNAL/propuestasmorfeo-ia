#!/usr/bin/env bash
# anexos_a_pdf.sh — Convierte los anexos Markdown de una corrida a PDF de radicacion.
#
# Forma parte del framework: los anexos administrativos de una convocatoria son un
# paso recurrente de la fase de cierre, y `marco init` instala este script en
# `plantilla/scripts/` para que cada corrida lo tenga sin depender de que alguien
# recuerde el comando de pandoc. Es el mismo tipo de utilidad que
# `plantilla/scripts/prep_docx.py`, que convierte la propuesta a .docx.
#
# Por qué existe: el §8.6 del TDR exige radicar cada anexo en **PDF, máximo
# 2 MB**. Los anexos se redactan en Markdown (versionables, diffeables) y de ahí
# se derivan los PDF; este script es el paso determinista entre ambos, así que el
# proceso vive en el proyecto y no en la cabeza de quien lo corrió.
#
# Requisitos: pandoc y un motor LaTeX con xelatex (ambos ya presentes en la
# máquina de referencia). Si faltan, el script falla con un mensaje claro.
#
# Uso (desde la carpeta que contiene los anexos, o pasando su ruta):
#   <RUN_ROOT>/redaccion/scripts/anexos_a_pdf.sh [DIR]
#   <RUN_ROOT>/redaccion/scripts/anexos_a_pdf.sh DIR 01 03
#
# `DIR` es la carpeta con los `NN_*.md`; por defecto, el cwd. Los PDF quedan en
# `DIR/pdf/`.
#
# Decisiones de formato, todas deliberadas:
#
#   * **Guillemets en lugar de ⟨ ⟩.** Los borradores marcan los datos por
#     completar con U+27E8/U+27E9 (⟨completar: nombre⟩). Ese carácter no está en
#     ninguna de las fuentes instaladas, así que en el PDF se ve como un cuadro
#     vacío. Se reemplaza por «…», que existe en toda fuente y es idiomático en
#     español. El Markdown NO se modifica: la sustitución ocurre solo en la copia
#     temporal que consume pandoc.
#   * **Marca de borrador en cada página.** Ninguno de estos documentos está
#     firmado y todos llevan datos por completar; un PDF sin esa marca puede
#     confundirse con el documento radicable. El membrete dice exactamente eso.
#   * **A4, 11 pt, márgenes de 2.5 cm.** Formato de radicación institucional.
#   * **Saltos de línea duros.** El Markdown de estas cartas no envuelve la prosa
#     (cada párrafo es una línea larga), pero usa un salto por línea para la
#     fecha, el destinatario y las líneas de firma. Sin `hard_line_breaks` pandoc
#     une ese bloque en un párrafo corrido y la carta deja de parecer una carta.
set -euo pipefail

DIR="${1:-$PWD}"
if [ $# -gt 0 ] && [ -d "$1" ]; then shift; fi
HERE="$(cd "$DIR" && pwd)"
OUT="$HERE/pdf"

command -v pandoc >/dev/null 2>&1 || {
  printf 'error: falta pandoc (brew install pandoc)\n' >&2; exit 1; }
command -v xelatex >/dev/null 2>&1 || {
  printf 'error: falta xelatex (TeX Live con xelatex)\n' >&2; exit 1; }

mkdir -p "$OUT"

# Prefijos a convertir: los argumentos, o todos los NN_*.md si no hay ninguno.
if [ $# -gt 0 ]; then
  files=()
  for prefix in "$@"; do
    while IFS= read -r f; do files+=("$f"); done < <(find "$HERE" -maxdepth 1 -name "${prefix}_*.md" | sort)
  done
else
  files=()
  while IFS= read -r f; do files+=("$f"); done < <(find "$HERE" -maxdepth 1 -name '[0-9][0-9]_*.md' | sort)
fi

[ ${#files[@]} -gt 0 ] || { printf 'error: no hay anexos que convertir\n' >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cat > "$tmp/cabecera.tex" <<'EOF'
\usepackage{fancyhdr}
\usepackage{xcolor}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\fancyhead[L]{\footnotesize\color{red!70!black}\textbf{BORRADOR — pendiente de firma}}
\fancyhead[R]{\footnotesize\color{gray}SIUN Emergencias 2026 · UNAL Manizales}
\fancyfoot[C]{\footnotesize\thepage}
\setlength{\headheight}{14pt}
EOF

for src in "${files[@]}"; do
  base="$(basename "$src" .md)"
  # Copia temporal con los placeholders sustituidos (el .md no se toca).
  sed -e 's/⟨/«/g' -e 's/⟩/»/g' "$src" > "$tmp/$base.md"
  # `hard_line_breaks`: el Markdown de estas cartas NO envuelve la prosa (cada
  # párrafo es una línea larga) pero sí usa un salto por línea para el bloque de
  # fecha, destinatario y líneas de firma. Sin esta extensión pandoc une ese
  # bloque en un solo párrafo corrido y la carta deja de parecer una carta.
  pandoc "$tmp/$base.md" \
    -f markdown+hard_line_breaks \
    -o "$OUT/$base.pdf" \
    --pdf-engine=xelatex \
    -V geometry:a4paper \
    -V geometry:margin=2.5cm \
    -V fontsize=11pt \
    -V lang=es \
    -V colorlinks=true \
    -V linkcolor=blue!60!black \
    -H "$tmp/cabecera.tex" \
    2> "$tmp/$base.err" || {
      printf 'error: pandoc falló en %s:\n' "$base" >&2
      tail -5 "$tmp/$base.err" >&2
      exit 1
    }
  rm -f "$base.tex"   # pandoc deja el .tex intermedio en el cwd si no se le dice lo contrario
  size=$(wc -c < "$OUT/$base.pdf")
  if [ "$size" -gt 2097152 ]; then
    printf '  [AVISO] %s.pdf pesa %s bytes: el TDR exige máximo 2 MB\n' "$base" "$size" >&2
  fi
  printf '  %-62s %6s B\n' "$OUT/$base.pdf" "$size"
done

printf 'Listo: %d PDF en %s\n' "${#files[@]}" "$OUT"
