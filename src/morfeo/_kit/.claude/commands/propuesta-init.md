---
description: Crea la carpeta de proyecto de una corrida nueva de /propuesta (proposals/<run-id>/ con docs, artefactos, grafos y redaccion) y la deja activa.
argument-hint: "[idea breve de la propuesta] | run-id=<valor> [idea breve]"
---

# /propuesta-init — Crear la carpeta de proyecto de una corrida

Crea **una sola carpeta de proyecto por corrida** —`proposals/<run-id>/`— con
sus artefactos repartidos en exactamente cuatro subcarpetas. Nada de la corrida
queda suelto fuera de ahí, y archivarla deja de ser una copia: la carpeta ya
**es** el archivo.

Entrada del usuario:

$ARGUMENTS

## Qué hacés vos (el asistente primario) al recibir este comando

0. **Validá el runtime y confirmá la tabla de modelos con el usuario** (antes
   de crear nada). Este marco despacha subagentes, y cada subagente tiene
   asignado un modelo concreto. Si esa asignación no existe, no es alcanzable en
   el runtime actual, o el proveedor no está autenticado, el pipeline falla a
   mitad de una fase — y el síntoma es un subagente que devuelve *sin reporte*
   tras varios minutos, no un error claro. Verificá antes de empezar:

   1. **Qué agente de código está corriendo esta sesión** y qué runtime es
      (el marco soporta varios; cada uno tiene su propio directorio de agentes y
      su propio mecanismo de asignación de modelos).
   2. **Qué modelos hay realmente disponibles** en ese runtime. Nunca asumas que
      una lista de modelos recordada o declarada en un archivo de configuración
      sigue siendo alcanzable: consultá la lista del runtime.
   3. **Contrastá la tabla vigente del marco con el perfil activo del usuario.**
      El marco guarda su tabla de modelos por agente en un único archivo
      versionado (la *fuente de verdad de modelos*); el usuario, además, tiene
      un *perfil activo* de modelos que gobierna el resto de su entorno.
      Compará ambos y reportá cualquier divergencia: un agente del marco que
      apunte a un modelo ausente del perfil activo, o a un proveedor distinto
      del que el perfil usa, es una divergencia a resolver ahora y no en la
      Fase 4.
   4. **Mostrá la tabla al usuario y pedí confirmación explícita**, una fila por
      agente (agente · modelo · nivel de razonamiento · por qué ese nivel). No
      avances con la creación de la corrida hasta tener la confirmación: la
      tabla es una decisión del operador, no un valor por defecto silencioso.
   5. **Escribí la tabla confirmada en la fuente de verdad de modelos** y
      regenerá los puertos si el runtime los genera. Si el usuario no cambia
      nada, no reescribas el archivo: reportá "sin cambios".

   Si el runtime no expone forma de listar modelos o de asignar modelos por
   subagente, decilo explícitamente en el reporte en vez de inventar un valor:
   el paso se marca como `no verificable en este runtime` y el resto de
   `/propuesta-init` continúa. Nunca bloquees la creación de la corrida por
   esto; sí es obligatorio dejar constancia de que la verificación no se hizo.

1. **Resolvé el run-id.** Esquema `<YYYY-MM>-<slug>` (p. ej.
   `2026-09-siun-alianzas`): `<YYYY-MM>` de la fecha del sistema, `<slug>` =
   2-4 palabras clave en kebab-case, minúsculas, ASCII-folded (sin tildes ni
   ñ), derivadas de la idea en `$ARGUMENTS` descartando stopwords. Override:
   si `$ARGUMENTS` empieza con `run-id=<valor>` o `--run-id <valor>`, validá
   `<valor>` contra `[a-z0-9-]+` y usalo tal cual (el resto es la idea).
   Es el mismo esquema que la "RESOLUCIÓN DE RUN-ID" de `propuesta.md`, Fase 0.

2. **Guardia de corrida activa.** Leé `proposals/.current-run` (si existe) y
   el `_run.md` de esa corrida. Si hay una corrida con `estado: activa`
   distinta de la que se va a crear, **DETENETE** y preguntá explícitamente:
   "Existe la corrida activa `<run-id-activo>` (última compuerta `<Gx>`).
   ¿Cerrarla como `archivada` y activar `<run-id-nuevo>`? (sí/no)". Solo "sí"
   continúa; con "no", ofrecé reanudar la corrida existente. Cerrarla es
   únicamente editar su `_run.md` (`estado: archivada`, `cerrada:
   <YYYY-MM-DD>`) y su fila en `proposals/registry.md` — **nunca** se copia ni
   se borra contenido: la carpeta de esa corrida ya lo conserva todo.

3. **Creá la carpeta con el script determinista** (no lo hagas a mano, no
   reimplementes el scaffolding):

   ```bash
   scripts/init-run.sh <run-id> "<idea breve>"
   ```

   El script es idempotente: sobre una carpeta existente crea solo lo que
   falta y nunca trunca un archivo ya escrito. Crea:

   ```
   proposals/<run-id>/
     _run.md                      # único archivo en la raíz: manifiesto de la corrida
     insumos/                        # INSUMOS DEL USUARIO: TDR, papers, propuestas base
     artefactos/                  # todo lo generado que no es fuente LaTeX
       estado_propuesta.md        #   estado del pipeline y de cada compuerta
       insumos.md                 #   insumos estructurados por insumos-observador
       pipeline/                  #   log de fases/compuertas (+ _estado.md)
       scoping/papers/            #   corpus de papers del scoping (G1a/G1b)
       vault/                     #   espejo Obsidian: secciones/, insumos/, .cbmignore
     grafos/                      # reportes de codebase-memory (papers y vault)
     redaccion/                   # el proyecto LaTeX
       sections/  refs.bib        #   fuentes de la propuesta
       build.sh  scripts/  logos/  templates/   # copiados del esqueleto del framework
   ```

   `main.tex`, `main.pdf` y `main.docx` aparecen en `redaccion/` cuando el
   pipeline los genera (Fase 7 y cada compilación de compuerta).

   El script además activa la corrida escribiendo el run-id en
   `proposals/.current-run` (el puntero que el dispatcher lee para resolver
   `RUN_ROOT`) y agrega una fila al registro LOCAL `proposals/registry.md`,
   creándolo con su encabezado si falta (nada de `proposals/` se versiona).

4. **Llevá los insumos a `insumos/`.** Si el usuario mencionó archivos en el
   mensaje o los tiene en otra ruta, preguntá si los copiás (`cp`, no `mv`,
   salvo que pida moverlos) a `proposals/<run-id>/insumos/`. Los insumos de una
   corrida viven dentro de su corrida; `insumos/` es la única subcarpeta que
   llena el usuario. Si una corrida archivada tiene insumos reutilizables
   (`proposals/<otro-run-id>/insumos/`), copiarlos desde ahí es válido.

5. **No commitees nada.** `proposals/` entero está en `.gitignore` —corridas,
   registro local y puntero incluidos—, así que crear una corrida no produce
   ningún cambio versionado. Nunca uses `git add -f` sobre nada bajo
   `proposals/`.

6. **Cerrá informando**: run-id, `RUN_ROOT`, las cuatro subcarpetas, los dos
   nombres de índice de `codebase-memory` que usará la corrida
   (`<run-id>-papers` sobre `artefactos/scoping/papers`, `<run-id>-vault`
   sobre `artefactos/vault`), la tabla de modelos confirmada en el paso 0 (o su
   marca de `no verificable`) y el siguiente paso literal: dejar los insumos en
   `proposals/<run-id>/insumos/` y correr `/propuesta <idea>`.

## Qué NO hace este comando

- No despacha ningún subagente ni arranca el pipeline. Eso es `/propuesta`.
- No borra ni copia contenido de corridas anteriores. Archivar es un cambio de
  estado en `_run.md` + el registro local.
- No crea índices de `codebase-memory`. Los crea el dispatcher en las Fases
  1a/1b, con `repo_path` absoluto al corpus (ver "Cómo usar `codebase-memory`"
  en `propuesta.md`).
