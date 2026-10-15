# Proyecto guía descargable para el release del marco

Corrida `2026-09-tept-depresion-ia-portable`. El repositorio público necesita un
ejemplo terminado que cualquiera pueda leer sin ejecutar el pipeline desde cero,
y el paquete exportado de la corrida tiene que viajar con la documentación que
explica cómo recorrerlo.

## Specs

S1. Pedido del operador, textual:

> sincroniza el zip con la propuesta ejemplo de salud mental, y en el readme
> escribe en una seccion como pueden usar el ejemplo para guiarse y ver los
> artefactos, tablero, etc de ese proyecto guia. comit, mergea push y release.

S2. Decisión del operador sobre el contenido del activo, elegida entre tres
opciones después de advertirle que el repositorio es público: **«Zip completo,
tal cual»**. El activo publica la exportación íntegra de la corrida, con los
datos personales del equipo (nombres, cédulas, correos) y los PDF de la
convocatoria que sirvieron de insumo.

S3. El release se publica como `v0.5.2`. `.github/workflows/publish.yml` dispara
la publicación en PyPI al publicar un release, de modo que la versión sube de
forma coordinada en `src/morfeo/__init__.py`, en `scripts/kit-manifest.json` y
en las dos aserciones de `tests/test_morfeo_cli.py`.

S4. El paquete se regenera **después** de editar el README, para que el
`README.md` que viaja dentro del zip ya incluya la sección nueva.

S5. `proposals/` sigue fuera de git. El paquete se publica como activo de
release, no como archivo versionado, y su patrón se ignora en `.gitignore`.

## Tareas

- [x] T1 `README.md`: sección «Proyecto guía descargable» con el recorrido por
      artefactos, grafos y tablero (S1, S4)
- [x] T2 `.gitignore`: ignorar los paquetes de `morfeo export` (S5)
- [x] T3 versión `0.5.2` y sus dos aserciones de prueba (S3)
- [x] T4 regenerar el paquete exportado de la corrida (S1, S4)
- [ ] T5 commit, merge a `main` y push (S1)
- [ ] T6 release `v0.5.2` con el zip y el tar.gz como activos (S1, S2)

## Log

L1 (2026-10-15, pedido original): sincroniza el zip con la propuesta ejemplo de
salud mental, y en el readme escribe en una seccion como pueden usar el ejemplo
para guiarse y ver los artefactos, tablero, etc de ese proyecto guia. comit,
mergea push y release.

L2 (2026-10-15, decisión): ante la advertencia de que el zip contiene cédulas,
correos y anexos firmables, y de que el repositorio es público, el operador
eligió «Zip completo, tal cual».

L3 (2026-10-15, evidencia): el zip existente se exportó el 2026-10-14 a las
16:59 y ningún archivo de la corrida tiene fecha posterior, así que el contenido
estaba al día; solo faltaba el README nuevo.

L4 (2026-10-15, evidencia): el árbol traía trabajo completo y probado sin
commitear del puerto Pi (`scripts/gen-pi.py`, `.pi/mcp.json`, sus pruebas) y del
arreglo de versión de `morfeo status`. Entra en el mismo release con commits
propios.

L5 (2026-10-15, verificación independiente): el verificador recorrió las 27
rutas del rango `main..HEAD` y dio PASS en el ancla del README, las 16 rutas que
nombra, la coherencia de la versión y las reglas nuevas de `.gitignore`. Encontró
un desajuste real: el README declaraba 691 archivos y `unzip -l` cuenta 692,
porque el manifiesto de exportación viaja dentro del paquete y no se cuenta a sí
mismo en `files_count`. La fila ahora dice «sin el manifiesto».

L6 (2026-10-15, hallazgo de integración): el `sync` que pidió el evaluador nativo
también reescribió los diez `.pi/agents/*.md` del proyecto, y le agregó a cada uno
un bloque gestionado `<!-- gentle-ai:pi-codegraph-guidance -->`. Eso deja
`scripts/gen-pi.py --check` en rojo, porque esos archivos son salida de nuestro
generador y este los reescribe sin el bloque. Se revirtieron los diez archivos
para conservar el invariante; el activo gestionado global sí quedó sincronizado.
Queda pendiente decidir si `gen-pi.py` debe preservar ese bloque gestionado.
