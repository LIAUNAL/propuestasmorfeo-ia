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

---

# Segunda ronda: datos de David, monetización del aporte y avales concretos

## Datos que entró el operador

David Augusto Cárdenas Peña, cédula 1.053.779.322, valor hora \$149.958 M/CTE.
La cédula vino en el mismo mensaje, así que la búsqueda en correo quedó sin
objeto; además esta sesión no tiene herramienta de correo.

## Convención de horas, y por qué importa

Dos horas semanales durante doce meses admiten dos lecturas. Con cuatro semanas
por mes son 48 semanas, 96 horas y \$14.395.968; con el año calendario de 52
semanas son 104 horas y \$15.595.632. Se adoptó la primera y la segunda queda
anotada en los anexos 05 y 07, porque la diferencia —un millón doscientos mil
pesos— no es despreciable y la decisión la toma la UTP, no el marco.

## Lo que resolvió el aval HIDROIA de Downloads

`Aval_Horas_Departamento_Mz.FIAR.1.190-136-26_AMAlvarez_HIDROIA.pdf` no era solo
un modelo de redacción: traía datos que estaban como marcadores. La UAB es el
Departamento de Ingeniería Eléctrica, Electrónica y Computación; la firma Dahiana
López García como Directora UAB; Álvarez Meza es c.c. 1.088.257.232; el
destinatario de un aval de horas es la Dirección de Investigación y Extensión de
Sede, no la Vicerrectoría. El texto del PDF no se extraía con `pdftotext` —solo
salía el pie—, de modo que hubo que rasterizar la página y leerla.

Siguen sin resolverse las cédulas de Castellanos Domínguez y de Montes Monsalve.
No se infieren ni se completan por analogía.

## Cambios

- [x] Anexos 05 y 07: nombre completo, cédula, valor hora y aporte en especie
- [x] §13: el aporte UTP pasa de mención genérica a cifra, solo en prosa
- [x] Anexo 08 (Anexo 3): tabla de recursos con el aporte concreto
- [x] Avales 01, 03 y 04 reescritos con la estructura del aval radicado
- [x] Anexos 02, 05, 06, 07 y 08: fuera el bloque de «documento de trabajo» y la
      sección interna de datos por completar
- [x] `equipo.md`, §9 y los espejos del vault alineados
- [x] Borrados los PDF de `artefactos/anexos/` por decisión del operador; los
      `.md` se conservan como fuente

## Dos defectos de render que la verificación visual atrapó

Una línea de tres o más guiones bajos es un *thematic break* en Markdown, así que
la línea de firma salía como regla horizontal de ancho completo. Se escaparon los
guiones. Y la fecha con el radicado en la misma línea quedaban pegados, porque
Markdown no tiene tabulador derecho; el radicado pasó a su propia línea.

Ninguno de los dos aparece en la auditoría estructural del `.docx`: los dos
exigían mirar la página renderizada.

## El membrete de borrador se retiró

Mientras los anexos tenían marcadores por todas partes, estampar «BORRADOR —
pendiente de firma» en cada página era honesto. Con los datos institucionales ya
puestos y solo la firma pendiente, esa marca engaña en sentido contrario. El pie
con número de página se conserva.

## Un dato encontrado que nadie pidió

`~/Downloads/20261007CesarCastellanos.pdf` certifica el valor hora docente de
César Germán Castellanos Domínguez en \$751.441, para el trimestre julio–septiembre
de 2026. No se usó: §13 monetiza el aporte **externo**, que es el único que cuenta
para el criterio de fuentes adicionales, y las horas de los docentes UNAL son
aporte institucional propio. Queda anotado por si la intención es valorizarlas.

### Anexo 09: carta de intención de la Dirección de Pregrados

El operador pidió una carta de intención de apoyo que firme la Dirección de
Pregrados, concreta y breve, sobre apoyo logístico y divulgativo con la comunidad
estudiantil afectada por el sismo en la Sede Manizales.

La carta compromete dos frentes y nada más. En lo **logístico**, la coordinación
con las direcciones de los programas curriculares para disponer espacios,
horarios y canales de contacto sin interferir con la actividad académica. En lo
**divulgativo**, la difusión de la convocatoria de participación por los medios
institucionales de la Sede, con atención particular a los estudiantes afectados.

Tres acotaciones deliberadas, porque una carta que promete de más se vuelve un
problema cuando alguien la firma. La vinculación de cada estudiante queda
voluntaria y sujeta al aval del comité de ética, coherente con §12, que fija ese
aval como condición previa a toda captura. El respaldo se declara de naturaleza
logística y divulgativa, sin recursos financieros a cargo de la Dirección. Y se
excluye explícitamente la prestación de servicios de atención clínica, que el
proyecto no ofrece: su unidad de intervención es el tamizaje, no el tratamiento.

Quedan dos marcadores por completar: el nombre del director o directora y la
**denominación oficial exacta de la dependencia**. Lo segundo no es un detalle de
forma. El TDR no nombra esa oficina y el catálogo de dependencias de Hermes
tampoco la expone en la lista de la Sede Manizales, de modo que el rótulo que va
en una carta firmada conviene tomarlo de la propia dependencia.

El `.docx` quedó verificado con el mismo estándar que los demás: ZIP válido, una
página, A4 de 595,3 × 841,9 pt, abre en LibreOffice, el guion bajo de la firma no
se degrada a regla horizontal y los `⟨…⟩` salen como guillemets.

### Los nueve anexos anteriores llevan el título viejo

Al redactar el anexo 09 salió a la luz algo que afecta a todos los demás. El
título vigente del proyecto es **«Aplicativo móvil basado en inteligencia
artificial para apoyar el tamizaje de depresión posdesastre en estudiantes
universitarios»**, que es el que está en Hermes y en el documento técnico. Los
nueve anexos del 00 al 08 siguen nombrando el título anterior, «Sistema de
inteligencia artificial portable para la identificación de patrones de depresión
asociados a estrés postraumático en estudiantes universitarios».

El anexo 09 se escribió con el título vigente. Los otros nueve no se tocaron:
corregirlos obliga a regenerar sus `.docx` y a reemplazar los de Drive, y es una
decisión del operador. Mientras no se haga, hay nueve documentos firmables que
nombran un proyecto distinto del que se radica.
