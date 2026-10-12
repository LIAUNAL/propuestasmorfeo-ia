# Workflow: compilar-pdf

> Compila la propuesta activa a PDF ejecutando build.sh en la carpeta redaccion/ de la corrida.


# /compilar-pdf — Compilar propuesta a PDF

Compila el documento LaTeX principal (`main.tex`) de la corrida activa a PDF
(`main.pdf`) usando el script de compilación de `redaccion/`.

## Qué hacés vos (el asistente) al recibir este comando

1. **Resolvé la corrida activa:**
   Leé `proposals/.current-run`. Si el archivo no existe o está vacío, informá
   que no hay ninguna corrida activa y sugerí iniciar una con `/propuesta-init <idea>`.
   Si el usuario indicó un `<run-id>` como argumento, verificá si existe
   `proposals/<run-id>/` y usalo como objetivo.

2. **Ejecutá la compilación:**
   Corré el comando de compilación:
   ```bash
   ./compilar-pdf.sh $ARGUMENTS
   ```
   (o `./scripts/compilar-pdf.sh $ARGUMENTS`).

3. **Verificá el resultado:**
   - Confirmá que `proposals/<run-id>/redaccion/main.pdf` existe.
   - Informá el número de páginas y tamaño del archivo resultante.
   - En caso de advertencias o errores de LaTeX, presentá un resumen conciso de los hallazgos.
   - Incluí el enlace markdown al archivo generado: `[main.pdf](file:///.../redaccion/main.pdf)`.
