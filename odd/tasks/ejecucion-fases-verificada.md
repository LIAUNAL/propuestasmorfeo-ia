# Ejecución de fases visible y verificada en el tablero

Objetivo: al pulsar «Ejecutar» en «Fases del Pipeline Metodológico de Redacción», el tablero muestra el proceso en curso, verifica que la etapa se cumplió, habilita e ilumina las siguientes y refresca sus artefactos.
Rama: `feat/ejecucion-fases-verificada` · Entrega: merge local a `main` (como las features previas) · Tests: `npm test`, `uv run python -m unittest discover tests -p "test_*.py"`.

## Specs

- **S1** «al dar ejecutar, genera un visualizacion del proceso que se va ejecutando». El tablero muestra un seguidor de la ejecución: comando enviado a la terminal, unidad en curso (agentes, skill, nota de avance, artefacto esperado, tiempo transcurrido), verificación y resultado. El estado en curso sale del latido `artefactos/pipeline/_en_curso.json`, que los comandos `/propuesta-analizar` y `/propuesta-continuar` escriben al abrir la unidad, actualizan (`nota`) en cada despacho y borran al cerrar.
- **S2** «asegurate de poder asegurar que la etapa si se cumplio». Una unidad cuenta como cumplida solo si se cumplen tres cosas: su compuerta está en PASS, o, en las unidades sin compuerta, existe su evento `artefactos/pipeline/NN-<id>.md`; el control de ejecución ya avanzó más allá de ella; y existen sus artefactos y secciones esperados. El tablero lista cada comprobación con su estado. Si una unidad tiene PASS pero le falta algo, no se ilumina y se ve como incompleta, con lo que falta.
- **S3** «que se habiliten las etapas posterioes, y se iluminen». Cuando una unidad queda verificada, se ilumina y la siguiente (`next_step`) queda lista para ejecutar sin recargar la página. Un cambio de `en_curso`, de `control` o de los artefactos vuelve a pintar el panel. Un latido obsoleto (de una unidad ya cumplida, o con más de 6 h) no bloquea el pipeline y se señala como tal.
- **S4** «se actualicen los artefactos respectivos». Cada unidad declara los artefactos que produce. El seguidor y el modal los muestran con su estado (existe o falta) y marcan los que cambiaron desde que se lanzó la ejecución. La pestaña Artefactos se refresca con cada cambio.

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|----|-------|------|--------|-----------|
| T1 | S2, S3, S4 | inline | pendiente | — |
| T2 | S1 | inline | pendiente | — |
| T3 | S1–S4 | inline | pendiente | — |

- T1: servidor. Manifiesto `artifacts` por unidad, `unit_progress` en `/api/status`, latido obsoleto y `mtime` en los artefactos.
- T2: prompts. El latido explícito en `propuesta-continuar.md` y `propuesta-analizar.md` y la `nota` de avance en `_propuesta-steps.md`, más los ports y el kit.
- T3: tablero. La firma de re-render, la iluminación por verificación, el seguidor de ejecución, la lista de comprobaciones en el modal y el sondeo rápido mientras algo corre.

Ruta: inline, porque no se dispara el Writer trigger (las unidades comparten el contrato del sobre).

## Log

- L1 (2026-10-20): «revisa las etapas de la pestaña Fases del Pipeline Metodológico de Redacción, al dar ejecutar, genera un visualizacion del proceso que se va ejecutando, al dar ejecutar, y asegurate de poder asegurar que la etapa si se cumplio, y que se habiliten las etapas posterioes, y se iluminen y se actualicen los artefactos respectivos»
- L2: Mapa. El comando va como pulsaciones a un PTY (`/ws/terminal`) y el servidor no registra la salida. El estado en curso solo puede venir del latido. La firma de re-render de `loadStatus` excluye `en_curso`, `control` y los artefactos. Ningún prompt de comando escribe el latido; solo lo especifica `_propuesta-steps.md`. No existe un manifiesto de artefactos por unidad.
