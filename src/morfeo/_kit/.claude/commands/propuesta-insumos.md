---
description: Crea zonas de depósito bajo insumos/ (TDR, borrador, background, doc-secciones, ideas) sin iniciar una corrida del pipeline.
argument-hint: "[slug opcional o ruta bajo insumos/]"
---

# /propuesta-insumos — Zonas de depósito de insumos

Prepara carpetas etiquetadas donde el operador deja TDR, propuesta previa,
papers, lista de secciones e **ideas de investigación** para adaptar a la
convocatoria. **No** inicia el pipeline, **no** asigna run-id, **no** despacha
agentes, **no** toca `redaccion/sections/`.

Entrada:

$ARGUMENTS

## Qué hacés vos (asistente primario)

### 0. Modo portable (proyecto `marco init`)

Si el directorio actual contiene `.marco/version`, el proyecto fue creado con
`marco init` y `/propuesta-insumos` opera en **modo portable**:

- Solo asegura que existan las zonas de depósito dentro del `insumos/` de la corrida activa (pasos 1–5).
- **No** toca: `.marco/`, **ningún directorio de runtime de agentes** (el de
  cada runtime soportado), `AGENTS.md`, `guiaProyectosIA_Agente.md`,
  `DECISIONS.md`, `journal/`, `plantilla/**` ni el `redaccion/` de una corrida.
- **No** asigna run-id, **no** despacha `insumos-observador`, **no** modifica
  `redaccion/sections/`.
- La verificación "fuera del repositorio `marco-propuestas-ia`" del paso 1
  **no aplica**; la raíz del proyecto portable **es** el directorio de trabajo.
- El resto de las instrucciones (pasos 1–5) aplican igual.

### 1. Resolver el directorio objetivo

- Si `$ARGUMENTS` está vacío → objetivo = `insumos/` (raíz del repo marco).
- Si `$ARGUMENTS` es un **slug** (solo `[a-zA-Z0-9_-]+`, sin `/`) → objetivo =
  `insumos/<slug>/`.
- Si `$ARGUMENTS` es una ruta relativa que empieza por `insumos/` (o es
  exactamente un subpath bajo `insumos/`) → usala tal cual, normalizada al
  repo.
- Si la ruta apunta **fuera** del repositorio `marco-propuestas-ia` o **fuera**
  de `insumos/` → **rechazá** con un mensaje claro y DETENETE. No crees
  árboles de proyecto externos como raíz de ingestión.

### 2. Crear drop zones (idempotente)

```bash
mkdir -p "<objetivo>/tdr" \
         "<objetivo>/draft" \
         "<objetivo>/background" \
         "<objetivo>/doc-secciones" \
         "<objetivo>/ideas"
# opcional: touch .gitkeep en cada subcarpeta vacía
```

### 3. Sembrar `ideas/idea.md` solo si falta

Si **no** existe `<objetivo>/ideas/idea.md`, crealo con este template en
español (placeholders; el operador los reemplaza). Si el archivo **ya
existe**, **NO lo sobrescribas**.

```markdown
# Idea de investigación / concepto para la convocatoria

> Completá las secciones. Podés dejar vacías las que no apliquen.
> Con TDR en `tdr/`, el pipeline **adapta** esta idea a la convocatoria
> (no la pega ignorando topes, secciones ni criterios).

## Problema o necesidad

(¿Qué problema técnico o de transferencia resolvés?)

## Enfoque o solución propuesta

(¿Qué producto/servicio de IA y con qué enfoque?)

## Beneficiarios e impacto

(¿Quiénes se benefician? ¿TRL objetivo 6 o 7?)

## Restricciones o alineación a la convocatoria

(Duración, tope, socios, temas prioritarios si ya los conocés)

## Preguntas abiertas

(Lo que todavía no sabés y querés que el pipeline explore)
```

### 4. Escribir o refrescar README de operador

Escribí (o sobrescribí) `<objetivo>/README.md` en español, corto, con:

| Carpeta | Qué poner |
|---------|-----------|
| `tdr/` | Términos de referencia / bases / convocatoria (PDF/DOCX) |
| `draft/` | Propuesta previa o en curso (PDF/DOCX) — semilla, no resume LaTeX |
| `background/` | Papers, datos, notas de apoyo |
| `doc-secciones/` | Lista de secciones obligatorias si el TDR no las enumera |
| `ideas/` | Notas de idea/concepto (`idea.md` u otros `.md`) para **adaptar al grant** |

**Idea + TDR:** las notas en `ideas/` son la semilla científica/de producto;
el TDR manda en estructura, criterios, presupuesto y duración. No reemplazan
un `draft/` (propuesta completa previa).

**Siguiente flujo recomendado:**

1. Copiá TDR / borrador / papers a las carpetas de arriba.
2. Completá `ideas/idea.md` (o pasá la idea en la línea de comando).
3. `/propuesta-analizar` — con o sin `<idea>` en args; si args vacíos, usa
   `ideas/idea.md` si tiene contenido real (no solo el template vacío).
4. `/propuesta-continuar` — una unidad del pipeline por invocación.
5. Alternativa en una sola sesión: `/propuesta` (o `/propuesta`).

También podés dejar archivos **planos** en `insumos/` (sin subcarpetas); el
clasificador sigue funcionando.

### 5. Confirmar al usuario

Mostrá la ruta del objetivo, listá las **cinco** carpetas, indicá si se creó
o se conservó `ideas/idea.md`, y recordá que **no** se inició ninguna corrida.
Sugerí completar ideas + TDR y luego `/propuesta-analizar`.

Cerrá siempre el reporte de respuesta con la sección estandarizada:

```markdown
## 🎯 NEXT STEPS
- **Fase Completada**: /propuesta-init (Zonas de depósito preparadas)
- **Archivos/Carpetas**: `insumos/{tdr,draft,background,doc-secciones,ideas}/`
- **Acción requerida**: Colocar insumos y/o editar `insumos/ideas/idea.md`
- **Próximo comando**: `/propuesta-analizar`
```

## Qué nunca hace este comando

- No escribe `artefactos/estado_propuesta.md` ni run-id.
- No despacha `insumos-observador` ni ningún otro subagente.
- No modifica `redaccion/`, `artefactos/`, `grafos/`, ni ninguna otra corrida.
- No borra archivos que el usuario ya haya puesto en las drop zones (solo
  crea directorios, siembra `idea.md` si falta, y refresca el README).
- **Nunca** sobrescribe un `ideas/idea.md` existente.
