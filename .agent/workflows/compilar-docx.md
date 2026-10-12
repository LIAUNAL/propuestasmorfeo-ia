# Workflow: compilar-docx

> Compila la propuesta activa a formato Word (DOCX) ejecutando build.sh --docx en redaccion/.


# /compilar-docx — Compilar propuesta a DOCX

Exporta el documento principal de la corrida activa a formato Word (`main.docx`)
vía pandoc a partir del PDF y las fuentes de `redaccion/`.

## Qué hacés vos (el asistente) al recibir este comando

1. **Resolvé la corrida activa:**
   Leé `proposals/.current-run`. Si el archivo no existe o está vacío, informá
   que no hay ninguna corrida activa y sugerí iniciar una con `/propuesta-init <idea>`.
   Si el usuario indicó un `<run-id>` como argumento, verificá si existe
   `proposals/<run-id>/` y usalo como objetivo.

2. **Ejecutá la compilación:**
   Corré el comando de exportación a Word:
   ```bash
   ./compilar-docx.sh $ARGUMENTS
   ```
   (o `./scripts/compilar-docx.sh $ARGUMENTS`).

3. **Verificá el resultado:**
   - Confirmá que `proposals/<run-id>/redaccion/main.docx` existe.
   - Informá el tamaño del archivo resultante.
   - Si se presentaron advertencias de conversión de tablas o diagramas, mencionalas brevemente.
   - Incluí el enlace markdown al archivo generado: `[main.docx](file:///.../redaccion/main.docx)`.
