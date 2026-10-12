---
name: depuracion-redundancias-es
description: Audita y depura redundancias conceptuales, léxicas y estructurales dentro de una misma sección de una propuesta en español, articulando y garantizando la aplicación estricta de la skill estilo-natural-es (humanización, cadencia, fluidez y eliminación de fórmulas mecánicas).
---

# Depuración de Redundancias y Estilo Natural en Español

## Propósito y alcance

Esta skill proporciona una metodología sistemática para auditar, depurar y condensar la redacción de propuestas académicas en español. Su objetivo es erradicar la repetición innecesaria de conceptos, justificaciones o giros lingüísticos dentro de una misma sección, asegurando al mismo tiempo la aplicación integral de la metodología de humanización y estilo académico natural establecida en `estilo-natural-es`.

Una propuesta con redundancias fatiga al evaluador, dispersa el argumento central y aparenta texto de relleno generado mecánicamente. La depuración exige que cada párrafo y cada oración aporten una función argumentativa diferenciada y progresiva, manteniendo la máxima densidad conceptual sin sacrificar claridad ni rigor.

## Principios irrenunciables (Líneas rojas)

1. **Fidelidad estricta al contenido:** La depuración elimina la redundancia de la forma y la repetición viciosa, pero jamás suprime hechos, datos, cifras presupuestales, plazos, claves de cita (`\citep`, `\citet`) ni compromisos técnicos.
2. **Preservación del registro formal:** No se confunde "naturalidad" con informalidad o coloquialismo. La prosa debe mantener el tono formal, académico y riguroso propio de una propuesta científica de alto nivel.
3. **Cero invención:** Nunca se introducen supuestos o datos adicionales para rellenar un espacio condensado. Si algo no está explícito en los insumos, no se inventa.
4. **Articulación obligatoria con `estilo-natural-es`:** Todo fragmento intervenido para eliminar redundancias debe pasar de forma simultánea por los criterios de cadencia, ritmo, variación de longitud oracional y desmecanización de conectores.

---

## Tipología de redundancias a detectar y corregir

### 1. Redundancia conceptual y de premisa
* **Defecto:** Repetir la misma justificación, alcance o premisa en varios párrafos de la misma sección con ligeras variaciones de redacción (por ejemplo, reiterar tres veces en la misma sección que el sistema no hace diagnóstico clínico o que se articuló con una dependencia particular).
* **Corrección:** Fijar la declaración de forma contundente y detallada en el punto metodológico o normativo donde corresponde de manera natural, y en las menciones subsecuentes referenciarla brevemente o prescindir de la reiteración si no aporta nueva evidencia o decisión.

### 2. Redundancia léxica y de muletillas conectivas
* **Defecto:** Saturación de conectores formulaicos ("asimismo", "por consiguiente", "en este sentido", "cabe destacar que", "de igual manera") al inicio de oraciones consecutivas o dentro del mismo párrafo.
* **Corrección:** Eliminar el conector prescindible y dejar que la conexión semántica fluya por yuxtaposición o puntuación; alternar conectores variados y naturales propios del español académico.

### 3. Redundancia de preámbulo y metadiscurso («throat-clearing»)
* **Defecto:** Oraciones introductorias vacías que anuncian lo que se va a decir en lugar de entrar directamente a la materia (ejemplo: *"A continuación se procede a describir de manera detallada los aspectos correspondientes a..."* o *"Es fundamental señalar que para el desarrollo de esta actividad se requiere..."*).
* **Corrección:** Suprimir el preámbulo y comenzar directamente con la afirmación sustantiva, el sujeto o la acción técnica.

### 4. Redundancia estructural o de espejo
* **Defecto:** Decir en la prosa lo que una tabla o un listado contiguo ya expresa de forma idéntica, o repetir la justificación de un rubro en tres niveles diferentes de detalle sin agregar contexto operativo.
* **Corrección:** La prosa debe explicar la lógica de articulación, el criterio de decisión y el impacto sistémico, dejando los datos específicos tabulados en la tabla o lista correspondiente sin duplicar texto idéntico.

---

## Flujo de trabajo integrado (Auditoría + Humanización)

Al revisar o refactorizar cualquier sección de la propuesta, sigue estos cuatro pasos secuenciales:

```
Paso 1: Mapeo de densidad ──> Paso 2: Poda y fusión ──> Paso 3: Humanización (estilo-natural-es) ──> Paso 4: Verificación
```

### Paso 1: Mapeo de densidad de ideas
1. Lee la sección completa e identifica el propósito de cada párrafo.
2. Subraya o lista las afirmaciones sustantivas.
3. Marca aquellas oraciones que repiten una idea ya establecida en un párrafo previo de la misma sección.

### Paso 2: Poda y fusión de redundancias
1. Si dos oraciones de párrafos distintos dicen sustancialmente lo mismo, unifica la mejor formulación en el párrafo principal y elimina la duplicación secundaria.
2. Si un párrafo contiene dos o tres oraciones que giran en círculos sobre el mismo concepto, fúndelas en una sola oración robusta y precisa.
3. Elimina las frases de metadiscurso y aperturas mecánicas.

### Paso 3: Aplicación de la técnica de humanización (`estilo-natural-es`)
Sobre el texto podado y conciso, aplica de inmediato las directrices de `estilo-natural-es`:
1. **Regla 70/30 de longitud:** Alterna oraciones directas y breves (10–18 palabras) con oraciones compuestas y subordinadas (25–38 palabras). Rompe la monotonía rítmica de oraciones uniformes de 20 palabras.
2. **Desmecanización de aperturas:** Erradica listas formulaicas ("En primer lugar... En segundo lugar...", "Por una parte... Por otra parte...").
3. **Voz activa y naturalidad:** Prefiere verbos de acción directa y construcciones sintácticas propias de la prosa hispanohablante sobre estructuras pasivas anglicadas o perífrasis innecesarias.
4. **Variedad léxica:** Sustituye sinónimos gastados y evita repetir la misma palabra clave más de dos veces en un intervalo de cinco líneas, empleando pronombres demostrativos o elipsis cuando el referente sea inequívoco.

### Paso 4: Verificación de consistencia y cierre
1. Confirma que no se eliminó ninguna clave de citación BibTeX (`\citep{...}`, `\citet{...}`).
2. Revisa que todas las cifras monetarias, plazos, porcentajes o cantidades métricas coincidan exactamente con la versión original.
3. Asegura que la sección conserve su extensión adecuada y resulte ágil, persuasiva y contundente para el evaluador.
