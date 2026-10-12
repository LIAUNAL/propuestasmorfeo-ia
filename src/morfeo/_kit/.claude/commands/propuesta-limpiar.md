---
description: Cierra la corrida activa de /propuesta marcándola como archivada, sin copiar ni borrar su contenido, y deja el repo listo para una corrida nueva.
---

# /propuesta-limpiar — Cerrar la corrida activa

Deja el repo listo para arrancar una corrida nueva, sin tener que lanzar
`/propuesta` primero. **No copia ni borra contenido**: la carpeta de la corrida
(`proposals/<run-id>/`) ya es su archivo permanente, con su `main.pdf`,
`main.docx` y todos sus artefactos dentro. Cerrar una corrida es marcarla como
terminada.

## Qué hacés vos (el asistente primario) al recibir este comando

1. **Resolvé la corrida activa.** Leé `proposals/.current-run`. Si no existe, no
   hay nada que cerrar: respondé "No hay ninguna corrida activa; podés arrancar
   una nueva con `/propuesta-init <idea>`" y DETENÉTE sin tocar ningún archivo.
   Si existe, leé `proposals/<run-id>/_run.md` y confirmá que su `estado` es
   `activa`.

2. **Mostrale al usuario, antes de tocar nada**: `run_id`, fecha de creación,
   qué compuertas están cerradas vs. pendientes (leé
   `proposals/<run-id>/artefactos/estado_propuesta.md`), cuántas secciones hay
   en `proposals/<run-id>/redaccion/sections/*.tex`, y si existe
   `redaccion/main.pdf`. Preguntá explícitamente: "Esto va a cerrar la corrida
   `<run_id>` como `archivada`. Su carpeta `proposals/<run_id>/` queda intacta
   con todo su contenido. ¿Confirmás? (sí/no)". NO continúes sin un "sí"
   explícito.

3. **Tras la confirmación**, ejecutá exactamente estos cuatro pasos (los mismos
   de "CIERRE DE LA CORRIDA PREVIA" en `propuesta.md`, Fase 0 — ese bloque es la
   fuente de verdad):
   1. En `proposals/<run-id>/_run.md`: `estado: archivada` y
      `cerrada: <YYYY-MM-DD>`. Agregá al manifiesto el conteo final de
      artefactos (secciones, referencias, papers del corpus, notas del vault) y
      el SHA-256 corto de los entregables, para que el archivo sea auditable sin
      abrirlo.
   2. En el registro local `proposals/registry.md`: misma fila a `archivada`, con `cerrada` y
      `archivo` (ruta local `proposals/<run-id>/`, nunca una URL de GitHub). Si
      hubiera más de una fila con ese run-id (corridas previas canceladas que
      reusaron el slug), actualizá **solo** la que corresponde a esta carpeta y
      dejalo anotado en el manifiesto.
   3. `delete_project("<run-id>-papers")` y `delete_project("<run-id>-vault")`
      para no dejar índices de `codebase-memory` huérfanos. Si la corrida nunca
      llegó a indexar, es un no-op: seguí sin error.
   4. No hay commit: `proposals/` entero está gitignored, registro incluido,
      así que cerrar una corrida no produce ningún cambio versionado. Sin
      `git add -f` de nada bajo `proposals/`.

4. **Borrá el puntero** `proposals/.current-run` (ya no hay corrida activa).

5. **Confirmá**: la corrida quedó archivada en `proposals/<run_id>/` (intacta,
   solo en disco local), el hash del commit del registro, y que el siguiente
   paso es `/propuesta-init <idea>` para la corrida nueva.

## Qué nunca hace este comando

- Nunca borra ni vacía `proposals/<run_id>/` — es el archivo permanente, y vive
  solo en disco local (nunca en GitHub: `proposals/*/` está gitignored a
  propósito). Tampoco toca las corridas ya archivadas.
- Nunca hace `git add -f`/force-add de contenido de la propuesta (activa o
  archivada) para meterlo en git — nada bajo `proposals/` se versiona, tampoco
  el registro local.
- Nunca toca el esqueleto del framework (`plantilla/`), la guía
  (`guiaProyectosIA_Agente.md`), ni ningún archivo fuera de la corrida que está
  cerrando y su fila en el registro local.
- Nunca hace `git commit` ni `git push`: no hay nada versionado que cambiar al
  cerrar una corrida.
- Nunca se ejecuta sin la confirmación explícita del paso 2.
