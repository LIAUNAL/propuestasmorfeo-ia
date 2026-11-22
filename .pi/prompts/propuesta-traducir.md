---
description: Traduce el manuscrito de la corrida activa al otro idioma (español a inglés o inglés a español) como versión derivada, bloque por bloque, con la compuerta de fidelidad de scripts/traducir.py y las reglas de humanización y redundancia del idioma de destino; compila la versión traducida. Es asesor y nunca edita el manuscrito canónico.
argument-hint: "<en|es> [plan|status]"
---

# /propuesta-traducir: versión traducida del manuscrito

Traduce el manuscrito de la corrida activa al otro idioma y deja la versión
traducida, compilada, en `redaccion/traducciones/<lang>/main.pdf`. El
manuscrito en el idioma de redacción de la corrida sigue siendo la fuente
canónica: este comando nunca edita `redaccion/main.tex`, `redaccion/sections/`
ni `datos_proyecto.tex`. La traducción se guarda por bloques (párrafos, tablas,
listas) y fragmentos (títulos, captions, portada), cada uno atado al digest de
su texto fuente: cuando el original cambia, solo lo cambiado queda `stale` y
se vuelve a traducir.

Entrada:

$ARGUMENTS

## 1. Resolver la corrida y el idioma de destino

1. Leé `proposals/.current-run`. Si no existe o está vacío, decí que no hay
   corrida activa y sugerí `/propuesta-init <idea>`. Detenete.
2. `RUN_ROOT` es `proposals/<run-id>/`. El idioma de redacción es
   `python3 scripts/language.py run <RUN_ROOT>`.
3. El destino es la primera palabra de la entrada: `en` o `es`. Sin entrada,
   el destino es el otro idioma de la corrida y lo decís. Un destino igual al
   idioma de redacción lo rechaza el script con `TRANSLATION_SAME_LANGUAGE`:
   mostrá el mensaje y detenete.
4. La segunda palabra, si está, elige un modo corto:
   - `status`: corré `python3 scripts/traducir.py status <RUN_ROOT> --lang
     <lang>`, mostrá los conteos (`missing`, `current`, `stale`) de bloques y
     fragmentos, si la versión está construida y compilada y el resumen de la
     última auditoría. Detenete.
   - `plan`: corré el paso 2 y detenete después de mostrar el plan.

## 2. Planear

`python3 scripts/traducir.py plan <RUN_ROOT> --lang <lang>`. Mostrá cuántos
bloques y fragmentos están pendientes por archivo de sección y el glosario
(siglas, términos y nombres de instituciones). Si el operador pidió fijar una
equivalencia (por ejemplo `TEPT=PTSD`), volvé a planear con
`--term "TEPT=PTSD"`. Si no hay nada `missing` ni `stale`, saltá al paso 5.

## 3. Traducir

Por cada archivo de sección con pendientes (y uno más para los fragmentos de
`main.tex`, `datos_proyecto.tex` y los captions de diagramas), despachá con
`subagent_run` al agente `traductor`, con `RUN_ROOT` absoluto, `LANG_DESTINO=<lang>` y
el archivo en el prompt. Podés despachar varias secciones en paralelo: cada
una escribe solo sus propios bloques. El agente lee las skills del idioma de
destino, escribe cada borrador en `traducciones/<lang>/borradores/` y lo
guarda con `traducir.py store` o `store-fragment`, que lo rechaza si cambia un
hecho (`TRANSLATION_FIDELITY`), si no se lee en el idioma de destino
(`TRANSLATION_NOT_ENGLISH`, `TRANSLATION_NOT_SPANISH`) o si deja texto
provisional. Mostrá tal cual los rechazos que el agente no haya podido
resolver.

## 4. Auditar y revisar el estilo

1. `python3 scripts/traducir.py audit <RUN_ROOT> --lang <lang>`: corre el
   chequeo de estilo del idioma de destino (`scripts/estilo_en.py` o
   `scripts/estilo_es.py`) sobre los bloques guardados y la fidelidad de cada
   uno contra el original, y escribe `traducciones/<lang>/auditoria.json`.
2. Despachá con `subagent_run` a `revisor-traduccion`, con `RUN_ROOT` y
   `LANG_DESTINO=<lang>`. Si responde `AUDITORIA_DESACTUALIZADA`, repetí el
   paso 4.1 y volvé a despacharlo.
3. Si devolvió correcciones, despachá al `traductor` una sola vez por archivo
   con esas correcciones, repetí la auditoría y mostrá el índice antes y
   después. No hay una segunda ronda: lo que quede se informa.

## 5. Construir y compilar

1. `python3 scripts/traducir.py build <RUN_ROOT> --lang <lang>`. Mientras
   quede algo `missing` o `stale`, el script rechaza con
   `TRANSLATION_INCOMPLETE` y la lista de pendientes: mostrala y volvé al
   paso 3 para esos ids.
2. `python3 scripts/traducir.py compile <RUN_ROOT> --lang <lang>` compila
   `traducciones/<lang>/main.tex` (latexmk, como `redaccion/build.sh`) con la
   bibliografía, los logos y las figuras de `redaccion/`. Si falla
   (`TRANSLATION_COMPILE_FAILED`), mostrá la cola del log.

## 6. Informar

Mostrá el idioma de origen y el de destino, los conteos finales, el índice de
estilo de la auditoría, las fallas de fidelidad si quedaron y el enlace a
`redaccion/traducciones/<lang>/main.pdf`. Cerrá con cómo verla: el tablero
(`morfeo ui`) la muestra en el pliegue «Versión del documento» de
«Previsualización PDF», con «Ver original / Ver traducción», y desde ahí se
puede pedir esta misma traducción o compilarla de nuevo.

## Qué nunca hace este comando

- No edita el manuscrito canónico ni sus figuras: los textos de los nodos
  TikZ de `sections/diag_*.tex` se copian sin traducir.
- No cambia el idioma de redacción de la corrida ni el de proyecto.
- No aprueba compuertas, no toca `artefactos/estado_propuesta.md` ni el
  veredicto del `revisor`.
- No escribe a mano en `traducciones/<lang>/`: todo pasa por
  `scripts/traducir.py`.
