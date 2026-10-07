# Anexos en formato editable y publicación en Drive

Corrida `2026-09-tept-depresion-ia-portable`. Los nueve anexos administrativos
viven en Markdown bajo `artefactos/anexos/` y hoy solo se derivan a PDF. El
encargo pide un formato editable, abrible en Google Docs, y subirlo a Drive sin
alterar ni el formato ni los logos.

## Dos hechos verificados que acotan el encargo

**No hay logos que preservar.** `pdfimages -list` sobre los PDF generados
devuelve cero imágenes: el único elemento de identidad visual es un encabezado de
texto en rojo —`BORRADOR — pendiente de firma`— compuesto en Latin Modern por
`fancyhdr`. El membrete institucional real existe solo como descripción en prosa
dentro de `artefactos/productos-avales-y-comunidad.md`, nunca como imagen
incrustada. Preservar el formato, entonces, significa conservar ese encabezado de
borrador y la geometría A4 a 11 pt; no hay logotipo en juego.

**Drive admite escritura, no lectura.** El montaje
`~/Library/CloudStorage/GoogleDrive-amalvarezme@unal.edu.co/` acepta archivos
nuevos, y de ahí el cliente los sincroniza. En cambio, leer los precedentes ya
alojados falla con `EDEADLK` (*Resource deadlock avoided*), porque son archivos en
streaming que el proceso no puede materializar. De modo que el membrete real de
`Docs_Aval_Hermes/` queda fuera de alcance por esta vía.

## Decisiones de diseño

Un `.docx` copiado al montaje llega a Drive **como `.docx`**, no como documento
nativo de Google Docs: la conversión nativa exige la API de Drive con OAuth, que
no está configurada. El archivo abre en Docs con un clic y se convierte desde
ahí, lo cual satisface el uso previsto sin inventar credenciales.

El encabezado de borrador se inyecta como encabezado real de Word mediante
cirugía OOXML con `zipfile` de la biblioteca estándar, ya que `pandoc` no traduce
el `fancyhdr` de LaTeX al generar `.docx`. Así la marca se repite en cada página,
igual que en el PDF, en lugar de degradarse a un párrafo suelto al inicio.

## Tareas

- [x] Escribir `artefactos/anexos/convertir_a_docx.sh`, hermano determinista de
      `convertir_a_pdf.sh`, con las mismas decisiones de formato
- [x] Generar los nueve `.docx` en `artefactos/anexos/docx/`
- [x] Verificar encabezado por página, geometría y ausencia de marcadores `⟨ ⟩`
- [x] Copiar la carpeta a Drive y confirmar la sincronización

## Verificación ejecutada

| Control | Resultado |
|---|---|
| Zip íntegro y XML bien formado en cada parte | 9/9 |
| Partes `header1.xml` y `footer1.xml` con su `Override` y su `rId` | 9/9 |
| `pgSz` A4 y `pgMar` de 1417 dxa | 9/9 |
| Tamaño base en 22 medios puntos | 9/9 |
| Apertura real en LibreOffice headless y export a PDF | 9/9 |
| A4 (595,3 × 841,9 pt) en el PDF renderizado | 9/9 |
| Encabezado de borrador en todas las páginas | 9/9 |
| Pie con número de página correlativo | verificado en los multipágina |
| Guillemets legibles, sin `⟨ ⟩` ni glifos ausentes | 9/9 |
| Fidelidad de texto contra el PDF original | sin pérdidas |

El diff de fidelidad arrojó una sola diferencia, y favorece al `.docx`: LaTeX
partía «Castellanos-Domínguez» al final de renglón y `pdftotext` lo leía como una
palabra sin guion. El editable conserva el apellido entero.

Un hueco que la primera pasada dejó y la verificación atrapó: el PDF lleva pie
con número de página (`\fancyfoot[C]{\thepage}`) y el `.docx` salía sin él. Se
agregó como campo PAGE, de modo que se renumere al editar.

## Publicado en Drive

`My Drive/Anexos_SIUN_Emergencias_2026/`, con `docx_editables/`,
`pdf_referencia/` y un `LEEME.md`. Los 19 objetos tienen `item-id` de Drive, que
es la señal de que el cliente los registró.

## Pendiente, fuera del alcance de esta tarea

El script vive en la corrida, bajo `proposals/`, que no se versiona. Si el
`.docx` editable va a ser parte del flujo habitual, conviene llevarlo al kit
versionado junto a `anexos_a_pdf.sh`.
