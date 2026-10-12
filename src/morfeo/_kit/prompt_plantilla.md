# Plantilla de prompt para `/propuesta`

Guía para estructurar el prompt de una corrida nueva. No es un formato rígido de
`$ARGUMENTS` (el dispatcher solo parsea el override de run-id, ver §1) — es un
orden recomendado para que el usuario no omita lo que el pipeline **sí**
necesita de él, y no reescriba lo que el pipeline **ya deriva solo**. Basado en
el análisis de `.claude/agents/insumos-observador.md`, `investigador.md`,
`redactor.md`, `presupuestador.md`, `.claude/commands/propuesta.md` y
`guiaProyectosIA_Agente.md` (ver `prompt_agentesIA.md` para un ejemplo real ya
corregido con esta misma estructura).

## Cómo usar esta plantilla

1. Completa las secciones marcadas `[REQUERIDO]`; usa las `[OPCIONAL]` si
   aportan contexto real, no por completitud.
2. Guarda el resultado como `info_data/prompt_<slug-corto>.md` — así
   Insumos-Observador lo clasifica como insumo `background` y lo cachea por
   hash (no se pierde si la conversación se comprime o el turno rota).
3. Invoca `/propuesta` con un texto corto que apunte al archivo, por ejemplo:
   `/propuesta <título tentativo> — detalle de equipo/enfoque/presupuesto en info_data/prompt_<slug>.md`.
   No hace falta pegar todo el contenido de esta plantilla en `$ARGUMENTS`;
   basta con que el archivo exista en `info_data/` antes de correr el comando.

## 1. Invocación mínima [REQUERIDO]

```
/propuesta <título tentativo o idea de una línea>
```

- El texto de `$ARGUMENTS` es la única entrada obligatoria: de ahí se deriva
  el `run-id` automático (`<YYYY-MM>-<slug>`, 2-4 palabras clave en
  kebab-case). El título final de §1 lo redacta el Redactor más adelante —
  este es solo un título de trabajo.
- **Override de run-id** `[OPCIONAL]`: antepón `run-id=<valor>` o
  `--run-id <valor>` (regex `[a-z0-9-]+`) antes del resto del texto si quieres
  fijar el identificador tú mismo en vez del slug auto-derivado.

## 2. Equipo de trabajo y alianza [REQUERIDO — alimenta §9]

Tabla con estas 4 columnas exactas (mismo formato que usa Redactor para
`tab:equipo`, así no hay que reinterpretar nada):

| Actor | Nombre | Sede/Ciudad | Dependencia/Facultad/Unidad |
|---|---|---|---|
| Investigador / Grupo de investigación / Aliado institucional | ... | ... | ... |

- Nombres, sede y dependencia deben venir de aquí — el Redactor nunca los
  inventa; si falta un dato lo marca `[inferido]`.
- Si el equipo cruza sedes/instituciones, agrega un párrafo breve explicando
  quién compone la alianza y por qué esa composición encaja con el alcance
  del proyecto (la guía §9 lo exige antes de la tabla).
- No hace falta escribir "Responsabilidades" por integrante: el Redactor las
  deriva de los objetivos específicos (§7), nunca al revés.

## 3. Insumos declarados en `info_data/` [OPCIONAL, recomendado]

Lista qué archivo es qué, para acelerar (no reemplazar) la clasificación
automática de Insumos-Observador:

- **TDR**: términos de referencia / convocatoria / bases — el archivo que trae
  la tabla de criterios ponderados y, si aplica, el marco presupuestal.
- **doc-secciones**: documento cuyo contenido es solo la lista de epígrafes
  exigidos por la convocatoria (sin prosa de propuesta).
- **draft-base**: una propuesta previa similar, no autoritativa — complementa,
  nunca reemplaza al TDR.
- **background**: todo lo demás (papers, anexos, datos, prompts guardados).

Si un archivo no calza claramente en TDR o draft-base, Insumos-Observador lo
marca ambiguo y el dispatcher te preguntará — nombrar los archivos de forma
reconocible reduce esas preguntas.

## 4. Enfoque temático y pedagógico [OPCIONAL, alto impacto en calidad]

Espacio libre para inclinar el estado del arte y la metodología: qué
perspectiva debe ser la más fuerte (técnica, pedagógica, de dominio), qué
mecanismos de aprendizaje/interacción se buscan, qué debe excluirse de qué
sección (p. ej. "aborda X solo en justificación, nunca en objetivos"). Esta
sección es la que más mueve la calidad de §2/§3/§4/§8 — el pipeline no puede
adivinar un énfasis que no esté escrito en algún lado.

## 5. Roles por sede/actor [OPCIONAL, recomendado en alianzas]

Narrativa corta de qué hace cada sede/actor en la práctica (población
objetivo, curso/asignatura, tipo de aporte). No es un campo estructurado que
el pipeline valide, pero le da al Redactor contexto real para §9/§10 en vez de
inferirlo del nombre de la dependencia.

## 6. Presupuesto [REQUERIDO SOLO SI el TDR no trae marco presupuestal]

Revisa primero `info_data/insumos.md` tras la Fase 0: si el TDR sí especifica
tope/cofinanciación/rubros/duración, Presupuestador los toma de ahí (MODE=tdr)
y esta sección sobra. Si el TDR no trae esos datos (sentinel `sin datos
presupuestales en TDR`, MODE=base), sin esto el Presupuestador solo puede
construir montos `[supuesto]` para que los ajustes en el gate interactivo:

- Tope total y moneda.
- Rubros y montos (o criterio de reparto) que ya tengas decididos.
- Contrapartida/cofinanciación institucional, si existe y en qué condición
  (por sede, por aliado, etc.).

## 7. Duración de ejecución [REQUERIDO SOLO SI el TDR no la fija — alimenta §14]

Meses de ejecución, si tienes un plazo objetivo distinto al que se infiera de
la guía ajustada al TDR.

## 8. Consideraciones éticas [REQUERIDO SOLO SI aplica — alimenta §12]

Si el proyecto involucra sujetos humanos, datos personales, o requiere aval de
comité de ética, decláralo explícitamente (qué, con quién, bajo qué
consentimiento). Si no aplica, decláralo también explícitamente — evita dejarlo
ambiguo para que §12 no quede como un supuesto del Redactor.

## 9. Lo que NO hace falta escribir (el pipeline lo deriva solo)

No dupliques esto en el prompt — ya está gobernado por
`guiaProyectosIA_Agente.md` y `AGENTS.md`, y reescribirlo solo agrega ruido:

- §1 Título, §3 Descripción del problema + subproblemas, §5 Hipótesis, §6
  Objetivo general, §7 Objetivos específicos, §8 Marco conceptual — Investigador
  los deriva de la idea + insumos + literatura.
- §2 Justificación, §4 Estado del arte, §16 Bibliografía — Redactor/
  Bibliografo-Propuesta, con literatura Q1/Q2.
- §10 Metodología, §11 Resultados esperados, §15 Productos esperados — se
  derivan de §7/§9 y de la cadena de valor por objetivo.
- TRL 6 o 7, formato APA autor-año, densidad de citas por párrafo — reglas
  globales fijas del framework (`AGENTS.md`), no requieren mención.
- Prioridad por sección (ALTA/media/no ponderada) — se calcula sola en Fase 0.5
  desde la tabla de criterios ponderados del TDR.

## Checklist antes de correr `/propuesta`

- [ ] Insumos copiados a `info_data/` (TDR, draft-base si existe, background)
- [ ] Este archivo guardado como `info_data/prompt_<slug>.md`
- [ ] Equipo con Actor/Nombre/Sede/Dependencia completos para cada fila (sin
      huecos que obliguen a `[inferido]`)
- [ ] Enfoque/exclusiones temáticas explícitas si el proyecto las necesita
- [ ] Presupuesto (§6) completado si el TDR no trae uno propio
- [ ] Duración (§7) completada si el TDR no la fija
- [ ] Consideraciones éticas (§8) declaradas — aplica o no aplica, no en blanco
