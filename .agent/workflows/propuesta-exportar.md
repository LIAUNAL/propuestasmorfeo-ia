# Workflow: propuesta-exportar

> Empaqueta y exporta la propuesta activa con todos sus artefactos, insumos, grafos y redacción a un archivo comprimido (.tar.gz o .zip) para compartir y continuar en otro computador.


# /propuesta-exportar — Exportar propuesta y artefactos para compartir

Empaqueta de forma autocontenida la propuesta activa (o todas las corridas) junto con sus insumos, artefactos generados, reportes de grafos, fuentes LaTeX, marcas editoriales y documentos PDF/DOCX compilados, generando un archivo transferible listo para usar en otro computador.

## Qué hacés vos (el asistente) al recibir este comando

1. **Resolvé la corrida activa:**
   Leé `proposals/.current-run`. Si el archivo no existe o está vacío, informá que no hay ninguna corrida activa y sugerí iniciar una con `/propuesta-init <idea>`.
   Si existe, leé `proposals/<run-id>/_run.md` y presentá un resumen previo:
   - Título de la propuesta
   - ID de la corrida activa
   - Fases completadas y compuertas cerradas

2. **Ejecutá la exportación:**
   Corré el comando CLI:
   ```bash
   morfeo export $ARGUMENTS
   ```
   (o `python3 -m morfeo.cli export $ARGUMENTS`).

3. **Verificá el archivo generado:**
   - Confirmá la existencia del archivo de salida (`.tar.gz` o `.zip`) y su tamaño.
   - Presentá al usuario el resumen del empaquetado y las instrucciones exactas para que el destinatario lo use en otro computador:
     1. Cómo transferirlo (Drive, correo, Slack).
     2. Cómo importarlo en destino con `morfeo import <archivo>` o descomprimirlo con `tar -xzf <archivo>`.
     3. Cómo abrir el tablero con `morfeo ui` y continuar con `/propuesta-continuar`.
