# Complemento SGR de la guía de formulación (flujo `sgr`)

Este archivo **no reemplaza** a `guiaProyectosIA_Agente.md`: la complementa para
los proyectos creados con `morfeo init --sgr` (`"flujo": "sgr"` en
`.morfeo/config.json`). Condensa la metodología general ajustada (MGA) del DNP
para proyectos de inversión financiados por el Sistema General de Regalías (SGR),
según el material de `sgrguia`: Instructivo MGA 2023, Manual conceptual MGA 2015
y los módulos de Identificación y Preparación del diplomado SGR.

**Orden de precedencia.** TDR de la convocatoria > este complemento > guía base.
Lo que este archivo no toca (ética, densidad de citas, convenciones de LaTeX)
sigue rigiéndose por la guía base o por la guía ajustada al TDR. Los pisos
bibliográficos, el número de objetivos específicos y el TRL los fija cada
convocatoria en `artefactos/convocatoria.json` (ver «Reglas de la convocatoria»).
La MGA no cubre los términos de referencia de Minciencias: el
TRL, los productos de CTeI y los criterios de evaluación de una convocatoria
salen siempre de su TDR.

**Cómo lo usa el dispatcher.** Con el flujo `sgr`, el dispatcher lee la guía
aplicable (base o ajustada) y además este archivo, una sola vez por corrida. Cada
vez que arma un `## FRAGMENTO DE GUÍA` con la sección `N`, agrega al final el
bloque `### SGR §N` de este archivo, si existe. Los bloques `### SGR A20`,
`A21`, `A22` y `A24` se inyectan en la Fase 6.3, antes del presupuesto, y `A19`,
`A23` y `A25` en la Fase 6.47. El bloque «Estilo de redacción SGR» acompaña toda
redacción del flujo. Con el flujo base este archivo no se lee.

---

**Directrices Generales SGR:**

1. **Proyecto de inversión pública.** La propuesta se formula como un proyecto
   de inversión en la MGA-Web, que avanza por cuatro módulos en orden y «no
   permite avanzar de un módulo a otro mientras no se haya concluido el
   anterior» (Manual MGA 2015, p. 80): Identificación (plan de desarrollo,
   problemática, participantes, población, objetivos, alternativas),
   Preparación (necesidades, localización, cadena de valor, riesgos, ingresos y
   beneficios), Evaluación y Programación (indicadores, regionalización,
   focalización y matriz de marco lógico).
2. **Solo gasto de inversión.** Ningún rubro financia gastos permanentes de
   funcionamiento de la entidad.
3. **Fuente de CTeI.** Los recursos de ciencia, tecnología e innovación (10 % del
   SGR) se asignan por convocatorias públicas de Minciencias. Se exige la
   participación de al menos un actor del SNCTeI y que el proyecto esté
   priorizado en los planes, agendas o estrategias regionales de CTeI.
4. **Datos locales.** Toda cifra de magnitud, población o línea base lleva su
   fuente verificable (entidad, documento y año) y su localización.
5. **Árboles.** Las reglas MGA de los dos árboles están en la guía base (§3,
   «Árbol de problemas y árbol de objetivos según la MGA») y aplican en ambos
   flujos. Lo propio del flujo SGR es que §6 y §7 copian literalmente el árbol
   de objetivos.
6. **Título derivado del objetivo general.** El título del proyecto
   (`\TituloProyecto` en `redaccion/datos_proyecto.tex`) es el objetivo
   general cambiando solo la primera palabra: el verbo en infinitivo pasa a su
   sustantivo, seguido de «de» («Fortalecer las capacidades de infraestructura
   en la Universidad Nacional» → «Fortalecimiento de las capacidades de
   infraestructura en la Universidad Nacional»; «Incrementar el
   aprovechamiento…» → «Incremento del aprovechamiento…»). El resto queda
   idéntico. En el flujo SGR no aplica la extensión de 12 a 15 palabras de la
   guía base; `scripts/check_run.py` verifica la derivación
   (`sgr-titulo-no-derivado`).

---

## Estilo de redacción SGR

Este bloque recoge el estilo de los documentos técnicos de referencia del flujo.
Se suma a `estilo-natural-es` y no cambia ninguna regla de la MGA.

* **Voz.** Tercera persona impersonal, sin primera persona del plural ni
  adjetivos promocionales: «El proyecto levanta la línea base en tres
  municipios». La oración media de esos documentos ronda las 24 palabras; es una
  referencia de ritmo, no una meta.
* **Tareas.** Infinitivo, objeto y propósito, en ese orden: «Investigar,
  recopilar y estructurar la información de las fuentes oficiales, que soporte
  la evaluación de las alternativas». Las actividades de la cadena de valor
  respetan además los verbos que A23 prohíbe.
* **Productos.** Una línea con la forma «Nombre: definición», donde la definición
  dice qué es el entregable y qué contiene. El medio de verificación va aparte, en
  su propia columna o línea, y nombra el documento que prueba la entrega.
* **Método.** Cada tarea lleva uno o dos párrafos de método: qué se hace, con qué
  datos o instrumentos y cuándo se da por terminada.
* **Reglas de decisión.** Un criterio de aceptación declara su umbral y lo que
  ocurre si no se alcanza: «Regla de decisión: una clase que no supere
  `<umbral>` en `<métrica>` no se publica». El umbral sale del protocolo del
  proyecto o del TDR, y estas reglas van en la metodología, nunca en §5, §6 ni §7.
* **Compuertas.** Los hitos de avance van en una tabla cuya última columna dice
  qué pasa si fallan:

  | Compuerta | Criterio | Si no se cumple |
  |---|---|---|
  | `<hito>` | `<condición verificable>` | `<acción concreta y responsable>` |

* **Plan B.** Cada interfaz de la que depende el proyecto (un dato de un tercero,
  un aliado, un sistema externo) declara su plan B en una frase.
* **Proyecciones.** Las cifras futuras se presentan como escenarios condicionados
  a sus supuestos, no como predicciones.

## Reglas de la convocatoria (`artefactos/convocatoria.json`)

Cada convocatoria de regalías fija sus propias reglas, y por eso viven en un
archivo de la corrida y no en el código. El dispatcher lo llena a partir del TDR
al cerrar la guía ajustada. Todas las claves son opcionales; si el TDR no
menciona algo, la clave se omite.

```json
{
  "nombre": "Convocatoria de ejemplo",
  "pisos_referencias": {"justificacion": 10, "estado_arte": 25, "total": 40},
  "objetivos_especificos": 4,
  "trl": {"tipologia": "Desarrollo tecnológico", "entrada": 3, "salida": 6},
  "rubrica": [
    {"id": "1.1", "criterio": "Calidad de la propuesta", "puntos": 60,
     "capitulos": [3, 4], "evidencia": "Árbol de problemas y objetivos coherentes"},
    {"id": "2.1", "criterio": "Pertinencia territorial", "puntos": 40,
     "capitulos": [5], "evidencia": "Vínculo del problema con el territorio"}
  ]
}
```

`scripts/check_run.py` lo aplica así en el flujo SGR:

| Clave | Declarada | Sin declarar |
|---|---|---|
| `pisos_referencias` | Error por debajo del piso (`piso-referencias`) | Aviso con los números de la guía base |
| `objetivos_especificos` | Error si §7 enumera otro número (`objetivos-no-son-3`) | Aviso con menos de tres |
| `trl` | §2 y §11 nombran `trl.salida` (`trl-ausente`); `salida` menor que `entrada` es error | §2 y §11 nombran algún TRL |
| `rubrica` | Revisa capítulos y puntos | Sin revisión |

El TRL nunca se nombra en §6 ni en §7, con o sin declaración. Un archivo que no se
puede leer da un solo error (`convocatoria-invalida`) y se trata como si no
existiera.

**Número de objetivos y de capítulos.** Los dos salen de la convocatoria. Tres
objetivos específicos es el valor por defecto de la plantilla, no una regla de la
MGA: si la convocatoria fija otro número, ese es el de subproblemas, causas
directas y objetivos específicos, y el mapeo 1:1 entre ellos se conserva. Cuando
el TDR fija sus capítulos, `artefactos/estructura_tdr.json` manda sobre las
secciones canónicas y los anexos: con `--final` se exigen sus archivos (las
figuras `diag_*` son opcionales), un capítulo sin contenido es error
(`tdr-capitulo-vacio`) y los archivos `tdr*.tex` pasan por los chequeos de prosa y
citas. Si la guía ajustada trae la tabla de capítulos y falta la estructura,
`--final` da `tdr-estructura-faltante`; se crea con
`python3 scripts/ensamblar_main.py <RUN_ROOT> --from-guide`.

**Cómo usar la rúbrica.** La tabla de criterios de evaluación del TDR se transcribe
con una entrada por criterio: `id` y `criterio` textuales, `puntos`, los
`capitulos` donde el evaluador lo buscará (el `numero` de cada capítulo de
`estructura_tdr.json`) y la `evidencia` que debe encontrar allí. Antes de redactar
un capítulo se leen los criterios que apuntan a él, y la evidencia de cada uno se
vuelve un requisito de ese capítulo. `check_run.py` da error si un criterio apunta
a un capítulo inexistente (`rubrica-capitulo-inexistente`) y avisa si los puntos no
suman 100 (`rubrica-puntos`).

**Marcas de trabajo.** Mientras se redacta, un dato sin resolver se deja con
`[PENDIENTE`, `[VERIFICAR`, `[CONFIRMAR` o `[PROPUESTA`. Cada marca es un aviso con
archivo y línea, y con `--final` es error (`sgr-marca-trabajo`).

## Bloques por sección

### SGR §2

La justificación resume la alineación con el Plan Nacional de Desarrollo, el
plan departamental y el municipal, y con los planes étnicos cuando apliquen
(Plan de Etnodesarrollo, Plan de Vida, Plan Integral Rrom). Nombra el programa y
la meta de cada plan con la que contribuye. La tabla completa va en el anexo
`19_alineacion_planes.tex`.

### SGR §3

Además de las reglas de la guía base:

* **Estructura de §3.** En el flujo SGR, el planteamiento del problema sigue
  la estructura de `artefactos/mga_resumido.md` y reemplaza los seis párrafos
  de la guía base. Lleva tres subsecciones con estos títulos textuales:
  1. `\subsection{Problema central}`: un párrafo con el tronco del árbol de
     problemas, copiado literal, con su población o territorio y el evento
     cuando lo hay.
  2. `\subsection{Descripción de la situación existente}`: un párrafo de
     contexto (antecedentes, sector, zona de estudio, evolución reciente e
     intervenciones previas) que cierra enunciando las tres causas directas,
     y luego un párrafo por causa directa, C1 a C3, en el orden del árbol.
     Cada uno desarrolla su causa directa y sus causas indirectas como
     estados negativos del territorio; esas causas son los subproblemas SP1 a
     SP3.
  3. `\subsection{Magnitud del problema}`: dos o tres párrafos con las cifras
     del tronco, de cada causa directa y de los efectos directos, cada una con
     su fuente, y la tabla de indicadores (Indicador, Causa, Valor, Fuente,
     Año) con la línea base del proyecto en negrita.

  La sección cierra con la pregunta de investigación y la cita a la figura del
  árbol de problemas. Las cifras, las causas y la variable son las mismas de
  `mga_resumido.md`; si el TDR fija el capítulo «Planteamiento del problema»,
  su título manda sobre el de la sección. Si falta una de las tres
  subsecciones, `scripts/check_run.py` lo advierte como
  `sgr-problema-estructura`.
* **Descripción de la situación actual.** Cubre las características de la zona
  de estudio, el análisis de cada factor del árbol y de sus relaciones, los
  antecedentes, la evolución reciente del problema y las intervenciones previas
  distintas de la que se propone (Instructivo MGA 2023, pp. 28-29). Responde
  cómo, dónde, a quién afecta y desde cuándo, con datos y evidencias locales.
* **Magnitud obligatoria.** El tronco de la spec lleva `trunk.magnitude` con
  indicador, valor y fuente; en el flujo SGR también la llevan las causas
  directas y los efectos directos (Manual MGA 2015, p. 18: «1. Problema central…
  2. Causas… 3. Efectos…», cada uno con su fuente).
* **Localización.** El problema central nombra la población o el territorio
  (departamento, municipio, zona urbana o rural).
* **Subproblemas = causas directas.** En el flujo SGR los subproblemas SP1 a
  SP3 son las causas directas del árbol, y se redactan en lenguaje MGA: un
  calificativo negativo, la variable afectada y la población o el territorio
  («Tardía identificación del riesgo psicosocial en estudiantes de Caldas»). No
  describen una limitación técnica de IA. Esa limitación baja un nivel, como
  causa indirecta, y desde ahí conecta con el estado del arte (§4) y con la
  metodología (§10). Cada causa directa pasa la prueba «si existe esta causa,
  ¿sucede el problema?» y lleva su magnitud.
* **Una sola variable en el problema central.** El tronco nombra una variable
  medible y no la acompaña de términos genéricos que se solapen con ella. Si el
  proyecto trata el estrés postraumático, el tronco dice «estrés postraumático»
  y no suma «y estrés»: el constructo clínico tiene instrumento de tamizaje,
  mientras el estrés fisiológico es una señal que usa la metodología, no un
  trastorno del tronco.
* **El evento, breve, en el tronco.** Cuando el proyecto responde a una
  emergencia, el tronco la nombra en pocas palabras («afectados por el sismo de
  2026»). No la omite: si el vínculo con la emergencia descansa solo en la
  localización, el criterio de pertinencia pierde puntos (en la Convocatoria 56,
  el criterio 2.1 asigna 5 de 17 puntos cuando el vínculo se apoya en la
  localización). La fecha exacta, los decretos y el argumento de que el problema
  fue «producido o agravado» por el evento van en §3 y en la justificación del
  criterio 2.1, no en el tronco.
* **Contexto local en cada nodo.** Las causas indirectas describen la situación
  actual en el territorio y en las instituciones del proyecto («Escaso registro
  de casos en las secretarías de salud de Caldas»), no vacíos de la literatura.
  Un vacío de investigación se argumenta en §4 Estado del arte y en §2; en el
  árbol aparece, si acaso, como la condición local que ese vacío produce. Ningún
  nodo de los dos árboles promete un alcance mayor que el del proyecto: si la
  validación ocurre en tres departamentos de Colombia, no se habla de
  «población latinoamericana».
* **Causas directas sin preámbulo.** Las causas directas no repiten los
  calificadores de contexto que el tronco ya fija (la lista de poblaciones entre
  paréntesis, el territorio, el evento). Cada una lleva el calificativo
  negativo, la variable y solo el elemento que la distingue de las otras dos.
* **Un indicador por variable.** La magnitud de una causa directa mide la
  variable de esa causa, no la del problema central ni la de un efecto: una
  causa de información se mide con la cobertura o la oportunidad de la
  información, no con el estado de salud. Un mismo indicador nunca mide a la vez
  una causa y un efecto (`scripts/check_run.py` lo advierte como
  `sgr-magnitud-repetida`).
* **Compuerta GCausas.** Después de G1a, el operador elige entre dos modos.
  En el modo plantilla de IA aplicada, las tres causas directas son las causas
  tipo de un proyecto SGR de IA aplicada: C1 levantamiento y gestión de datos,
  C2 plataforma y modelos de IA y C3 apropiación social e institucional. Cada
  subproblema de G1a queda bajo la causa tipo que le corresponde. En el modo
  exploratorio, el investigador propone tres causas raíz propias a partir de la
  idea y de los subproblemas del estado del arte. Las tres causas aprobadas
  quedan en `artefactos/arboles/causas_directas.md` y son las causas directas
  del árbol de problemas. Tres es el número por defecto de la plantilla: si
  `artefactos/convocatoria.json` declara otro en `objetivos_especificos`, la
  compuerta aprueba ese número de causas, y lo que este bloque dice de tres
  causas, de C1 a C3 y de SP1 a SP3 se lee con ese número.

### SGR §6

El objetivo general es literalmente el tronco del árbol de objetivos: verbo en
infinitivo + objeto + elementos descriptivos, la misma variable del problema
central en positivo (Manual MGA 2015, p. 28). En el flujo SGR no aplica el menú
de verbos rectores de IA de la guía base; siguen aplicando la oración única, el
verbo rector único, el límite de 460 caracteres y la prohibición de nombrar el
TRL o la duración. Formas prohibidas (Manual MGA 2015, p. 80, tabla 12):

* incluir la solución: «mediante…», «por intermedio de…», «a través de…»;
* incluir los fines: «…para mejorar la calidad de vida»;
* enunciarlo como el producto: «construcción de…»;
* enunciar una acción parcial: «adquirir bienes…», «construir infraestructura»;
* hacerlo demasiado amplio: «ampliar la cobertura en educación»;
* incluir las metas.

Conserva la población, el territorio y el evento del tronco tal como están, sin
ampliar el alcance más allá de lo que el proyecto valida.

### SGR §7

Cada objetivo específico es literalmente la conversión en positivo de una causa
directa del árbol, en el mismo orden. Solo las causas directas pasan a ser
objetivos específicos y entran a la cadena de valor; las indirectas son medios
(Instructivo MGA 2023, pp. 41-42). No todas las causas tienen que atenderse,
pero toda causa que no se atienda se justifica en el anexo de alternativas.

La redacción del objetivo específico va limpia: verbo en infinitivo, objeto y el
elemento mínimo que lo distingue de los demás. No lleva preámbulo ni repite los
calificadores de contexto que el objetivo general ya fija (poblaciones entre
paréntesis, territorio, evento). En `artefactos/arboles/arbol_objetivos.json`,
`groups[].title` es el rótulo `OE<n>` y `groups[].objective` guarda solo el
objetivo; el texto de la causa directa nunca se copia en el título.

### SGR §10

La metodología se organiza como cadena de valor: insumos → actividades →
productos → resultados → impactos (Instructivo MGA 2023, p. 62). Cada producto
responde a un objetivo específico y cada fase nombra sus actividades por etapa
(preinversión, inversión, operación). El detalle tabular va en
`23_cadena_valor.tex`.

### SGR §11

Los resultados esperados incluyen el **indicador de resultado** del objetivo
general, que nace de la magnitud del problema central y cumple los criterios
CREMA (claro, relevante, económico, medible, adecuado): nombre, unidad de medida,
meta numérica, tipo de fuente y fuente de verificación (Instructivo MGA 2023,
pp. 40-41). Ejemplo de forma: «Residuos sólidos aprovechados / residuos sólidos
generados; unidad: porcentaje; meta: 20 %». La regla de no fijar metas
porcentuales rige para §5, §6 y §7; aquí la meta es obligatoria.

**Indicadores de gestión y de producto.** Además del indicador de resultado, el
seguimiento de la etapa de inversión usa dos más, que miden el comportamiento
físico del proyecto (Instructivo MGA 2023, p. 119). El indicador de producto
cuantifica los bienes y servicios producidos; el indicador de gestión identifica
los recursos físicos, humanos y financieros utilizados y mide las acciones,
procesos y operaciones realizadas (Instructivo MGA 2023, p. 120). Cada meta declara
si es acumulable o no entre periodos y su fuente de verificación: documentos
oficiales, informes, evaluaciones, encuestas o registros contables (Instructivo MGA
2023, p. 110).

### SGR §12

**Licencias y permisos.** Sea cual sea la fase de formulación, el proyecto analiza
en detalle sus obligaciones legales en materia de permisos, autorizaciones,
licencias o cualquier otro requisito previo a la ejecución (Instructivo MGA 2023,
pp. 48-49). Cada requisito se nombra con la actividad que condiciona, y su trámite
entra al cronograma. Si la demora de un permiso puede frenar el proyecto, va como
riesgo en el anexo `24_riesgos.tex` con su medida, por ejemplo la solicitud
anticipada y el seguimiento al trámite (Módulo 4, p. 41).

### SGR §13

* Los costos se clasifican en las 11 categorías de insumos de la MGA
  (Instructivo MGA 2023, p. 68): 1 mano de obra calificada, 2 mano de obra no
  calificada, 3 materiales, 4 servicios domiciliarios, 5 terrenos, 6 edificios,
  7 maquinaria y equipo, 8 transporte, 9 alojamiento y comidas, 10 servicios a
  empresas y a la producción, 11 servicios comunitarios.
* Solo gasto de inversión. Se costean la mitigación de cada riesgo del anexo
  `24_riesgos.tex` y las estrategias de manejo de participantes oponentes o
  perjudicados.
* La cofinanciación entre fuentes se declara por fuente y por año. Si hay
  vigencias futuras: al menos 15 % apropiado en el bienio vigente, máximo cuatro
  bienios y no más del 50 % del plan de recursos.
* **Resumen de fuentes de financiación.** Una tabla cierra la sección con la
  etapa, la entidad a la que se solicita el aporte, el tipo y el monto de los
  recursos y el periodo en que se requieren (Manual MGA 2015, p. 89). Sus totales
  coinciden con los costos del proyecto, porque la maduración del proyecto busca su
  cierre financiero (Instructivo MGA 2023, p. 106).

### SGR §14

El cronograma agrupa las actividades por etapa (preinversión, inversión,
operación) y marca las que están en la ruta crítica. Cada producto lleva dos o
más actividades; las tareas no se cronograman.

### SGR §15

Cada producto se toma del catálogo de productos del DNP, con su indicador de
producto, unidad y meta (Instructivo MGA 2023, p. 108). El nombre del producto no
incluye «elaborado», «implementado» ni «entregado», y no se confunde con la
población, las actividades ni los insumos (Instructivo MGA 2023, p. 64). Los
productos de CTeI que exija el TDR se listan además con su tipología.

### SGR §17

Las comunidades se presentan con su rol en la matriz de participantes del anexo
`20_participantes.tex`. Cuando el territorio tiene comunidades étnicas, se
verifica si el proyecto requiere consulta previa y se deja constancia del
certificado correspondiente.

### SGR §18

**Sostenibilidad social y ambiental.** La sección explica cómo siguen funcionando
los productos cuando termina la financiación. Para la etapa de operación nombra los
recursos que aseguran la puesta en marcha, la operación y el mantenimiento, que
debieron identificarse desde la planeación (Instructivo MGA 2023, p. 18), y la
organización responsable, con los acuerdos institucionales que surgieron del
análisis de participantes (Instructivo MGA 2023, p. 49). En lo social se apoya en
la aceptación de la comunidad y en lo ambiental en la sostenibilidad de la
alternativa, dos criterios de preselección de las soluciones (Módulo 3, p. 50).
Cuando se requiere una evaluación de impacto ambiental, las medidas para prevenir,
mitigar, corregir o compensar los daños se valoran e incluyen en el presupuesto
(Instructivo MGA 2023, p. 49).

---

## Anexos MGA (Fases 6.3 y 6.47, solo flujo SGR)

Cada anexo es un archivo de `redaccion/sections/` que `main.tex` incluye después
de §18 y antes de la bibliografía. Los redacta `redactor`. A20, A21, A22 y A24 van
en la Fase 6.3, antes del presupuesto, porque §13 costea participantes y riesgos;
A19, A23 y A25 van en la Fase 6.47.
Las tablas usan `xltabular`; la prosa sigue `estilo-natural-es`.

### SGR A19

`19_alineacion_planes.tex`, «Alineación con los planes de desarrollo». Tabla:
plan (PND, departamental, municipal, étnico si aplica, agenda o plan regional de
CTeI) | programa | meta o indicador del plan | contribución del proyecto. Nombra
el actor del SNCTeI que participa.

### SGR A20

`20_participantes.tex`, «Análisis de participantes». Matriz con actor, nivel
(nacional, departamental, municipal, otro), entidad, posición (beneficiario,
cooperante, oponente, perjudicado), intereses o expectativas y contribución o
gestión (Instructivo MGA 2023, p. 32). El análisis es obligatorio con dos o más
actores. Para oponentes y perjudicados se describe la estrategia de manejo, que
se costea en §13.

**Matriz Poder-Interés.** Antes de asignar la posición, cada actor se ubica en una
matriz de 2×2, con el poder o la influencia en el eje vertical y el interés en el
horizontal (Módulo 3, pp. 32-35). Con alto poder y alto interés se gestiona
atentamente; con alto poder y bajo interés se mantiene satisfecho; con bajo poder y
alto interés se mantiene informado, y con bajo poder y bajo interés se monitorea.
El cuadrante orienta la estrategia de cada actor y no reemplaza su posición MGA.

### SGR A21

`21_poblacion.tex`, «Población afectada y objetivo». La población afectada es el
conjunto de personas que padecen la situación negativa en el área de estudio; la
población objetivo, la parte priorizada que el proyecto atiende (Instructivo MGA
2023, pp. 36-38). Siempre son personas, con cifra mayor que cero, fuente y
localización hasta vereda o resguardo cuando aplique, y caracterización por grupo
de edad, etnia, género, condición de víctima y discapacidad.

### SGR A22

`22_alternativas.tex`, «Alternativas de solución». Al menos dos alternativas, una
de ellas puede ser el escenario sin proyecto o la situación base optimizada
(Módulo 3, p. 50; Instructivo MGA 2023, p. 44). Clasifica las acciones en
complementarias o excluyentes, justifica las descartadas y declara el tipo de
evaluación (costo-eficiencia o multicriterio para CTeI, donde el desarrollo de la
ciencia, la tecnología y la innovación es un criterio). El cálculo de esa
evaluación va en A23, cuando ya existen los costos de §13.

### SGR A23

`23_cadena_valor.tex`, «Cadena de valor». Tabla: objetivo específico | producto
(catálogo DNP, indicador, unidad, meta) | actividades (etapa, ruta crítica) |
costo por insumo MGA. Cada producto tiene dos o más actividades. Las actividades
no usan los verbos que la MGA prohíbe para ellas (Manual MGA 2015, p. 81):
apropiar, asegurar, colaborar, consolidar, desarrollar, fomentar, fortalecer,
garantizar, implementar, impulsar, mejorar, movilizar, proponer, promover.
Los costos salen de §13 (ya aprobado en la Fase 6.4) y su suma coincide con el
total del presupuesto; la compuerta de anexos lo verifica.

**Evaluación MGA.** El anexo cierra con la evaluación del tipo que declaró A22:

* **Precios económicos.** Los precios de mercado se convierten con las razones
  precio cuenta (RPC): una RPC de 1 no altera el valor y una menor a 1 lo reduce
  (Instructivo MGA 2023, pp. 91-92). A manera de ejemplo, mano de obra calificada
  1; no calificada 0,6; materiales 0,79; maquinaria y equipo 0,77; otros servicios
  0,71; otros gastos generales 0,8 (Manual MGA 2015, p. 67). Los valores de cada
  insumo salen del aplicativo, que contempla 349 (Instructivo MGA 2023, p. 92).
* **Tasa social de descuento (TSD).** Es del 9 % y actualiza el 12 % del Manual
  2015 (Instructivo MGA 2023, p. 95).
* **Costo beneficio.** Con beneficios monetizables, el flujo económico descontado da
  el VPNE, la RBCE y la TIRE. La alternativa es conveniente con VPNE mayor que cero,
  RBCE mayor que 1 o TIRE mayor que la TSD; es indiferente en el punto de igualdad, y
  por debajo no conviene, salvo que los beneficios de difícil valoración compensen
  la pérdida social (Instructivo MGA 2023, p. 102). La TIRE no sirve como indicador
  cuando hay más de una o no se puede calcular (Instructivo MGA 2023, p. 101).
* **Costo eficiencia.** Con beneficios que no se pueden monetizar, compara dos o más
  alternativas y elige el menor costo presente por unidad del efecto positivo. Sus
  indicadores son el costo por capacidad y el costo por beneficiario; el valor
  presente de los costos sirve con igual vida útil y el costo anual equivalente con
  vidas útiles distintas. No determina si conviene ejecutar una alternativa
  (Instructivo MGA 2023, pp. 97, 103-104).
* **Multicriterio.** Complementa a las anteriores: pondera información cuantitativa y
  cualitativa con criterios estratégicos e importancia relativa definida por los
  actores (Instructivo MGA 2023, p. 105).

### SGR A24

`24_riesgos.tex`, «Análisis de riesgos». Al menos un riesgo por nivel
(propósito, productos, actividades), con tipo, descripción, probabilidad (1-5),
impacto (1-5), efectos y medida de mitigación costeada (Módulo 4, pp. 38-40;
Instructivo MGA 2023, pp. 72-74). Incluye el riesgo de desastres y climático del
territorio. El anexo nombra cada medida antes del presupuesto, y §13 la costea.

### SGR A25

`25_marco_logico.tex`, «Matriz de marco lógico». Matriz 4×4: filas fin (objetivo
del plan de desarrollo), propósito (objetivo general), productos y actividades;
columnas descripción, indicadores, fuentes de verificación y supuestos. Los
riesgos del anexo A24 pasan a ser supuestos (Manual MGA 2015, pp. 79-82). La
fila del propósito usa el indicador de resultado de §11.
