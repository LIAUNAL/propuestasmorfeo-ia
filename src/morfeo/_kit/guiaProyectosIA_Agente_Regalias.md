# Complemento SGR de la guía de formulación (flujo `sgr`)

Este archivo **no reemplaza** a `guiaProyectosIA_Agente.md`: la complementa para
los proyectos creados con `morfeo init --sgr` (`"flujo": "sgr"` en
`.morfeo/config.json`). Condensa la metodología general ajustada (MGA) del DNP
para proyectos de inversión financiados por el Sistema General de Regalías (SGR),
según el material de `sgrguia`: Instructivo MGA 2023, Manual conceptual MGA 2015
y los módulos de Identificación y Preparación del diplomado SGR.

**Orden de precedencia.** TDR de la convocatoria > este complemento > guía base.
Lo que este archivo no toca (el TRL fuera del bloque A31, ética, densidad de
citas, pisos bibliográficos, convenciones de LaTeX, estilo) sigue rigiéndose por
la guía base o por la guía ajustada al TDR. La MGA no cubre los términos de
referencia de Minciencias: el TRL, los productos de CTeI y los criterios de
evaluación de una convocatoria salen siempre de su TDR.

**Cómo lo usa el dispatcher.** Con el flujo `sgr`, el dispatcher lee la guía
aplicable (base o ajustada) y además este archivo, una sola vez por corrida. Cada
vez que arma un `## FRAGMENTO DE GUÍA` con la sección `N`, agrega al final el
bloque `### SGR §N` de este archivo, si existe. Los bloques `### SGR A19` a
`### SGR A25` se inyectan en la Fase 6.47 (anexos MGA); `### SGR A30` acompaña
a §13 en la Fase 6.4 y en la fase de anexos; `### SGR A31` a `### SGR A35` y
`### SGR §18` acompañan la unidad «TRL y componentes transversales»
(`fase5_5_sgr`), donde se escriben los textos de `componentes.json`. Con el
flujo base este archivo no se lee.

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
7. **Voz y léxico.** La prosa habla del proyecto en tercera persona: «El
   proyecto…», «Este proyecto busca…», «La presente propuesta se enmarca
   en…», «La alianza…» o la impersonal con «se». Nunca en primera persona
   (nosotros, nuestro, hemos, proponemos). Presente para el diagnóstico,
   pretérito para los antecedentes y futuro para actividades y resultados.
   Cada bloque `### SGR` trae su parte «Redacción»; las expresiones
   prohibidas, desaconsejadas y favorecidas por sección están en
   `scripts/sgr/lexico_sgr.json` y las verifica `scripts/estilo_sgr.py`. En
   este flujo, `revisor-estilo-sgr` (skill `estilo-sgr`) audita y pule cada
   sección antes del `revisor`, en el lugar de `grant-flow-auditor`. Donde el
   proyecto de referencia y la MGA difieren, manda la MGA.

---

### SGR §2

La justificación resume la alineación con el Plan Nacional de Desarrollo, el
plan departamental y el municipal, y con los planes étnicos cuando apliquen
(Plan de Etnodesarrollo, Plan de Vida, Plan Integral Rrom). Nombra el programa y
la meta de cada plan con la que contribuye. La tabla completa va en el anexo
`19_alineacion_planes.tex`.

**Redacción.** (Anexo 2, cap. 7 «Justificación».)

* Apertura: «El presente proyecto se centra en…» (una sola vez) o «La necesidad
  de esta intervención se relaciona con…».
* Favorecer: «La pertinencia científica y tecnológica radica en…», «La
  viabilidad se apoya en las capacidades de <grupos>…» y, antes de la tabla,
  «La Tabla N presenta la viabilidad y pertinencia del proyecto a corto,
  mediano y largo plazo».
* Evitar: volver a describir el problema, porque la justificación parte de él
  en una oración; repetir ODS y PND, que viven en el anexo 19 y aquí se
  remiten en una oración; «es de vital importancia», «es fundamental», «se
  hace necesario» o «urgente», que son énfasis sin evidencia; el esquema base
  de seis párrafos (OCDE, Banco Mundial, auge de la IA) como estructura, que el
  Anexo 2 no pide (el piso de referencias de la guía base sigue vigente).
* Tiempo: presente para la necesidad y la pertinencia; futuro para lo que el
  proyecto entregará.
* Extensión: la referencia mide unas 2.240 palabras en párrafos de unas 130,
  más la tabla.
* Tabla: `Factor | Elemento | Corto plazo | Mediano plazo | Largo plazo`.

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

  La sección cierra con la cita a la figura del árbol de problemas. En el flujo
  SGR, §3 no cierra con la pregunta de investigación: ni la plantilla del
  Anexo 2 ni el proyecto de referencia la usan, porque el documento es un
  proyecto de inversión (problema, alternativa, cadena de valor) y no una
  propuesta de investigación; el objetivo general responde al problema
  central. Las cifras, las causas y la variable son las mismas de
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
  del árbol de problemas.

**Redacción.** (Anexo 2, cap. 5.)

* Apertura: el problema central es el tronco literal, sin preámbulo («El
  problema central que abordará el proyecto es…» sobra).
* Favorecer: «<Recurso o sector> es <rol> de <territorio>…» para el contexto;
  «A esta situación se suma…» y «Esta emergencia agudiza…» para el evento;
  «Una de las causas directas relacionadas con el problema central es <causa
  literal>», «Otra causa directa del problema son…» y «Esto se debe a…» para
  las causas; «Por lo anterior, se define como indicador de referencia del
  problema: <indicador, valor, unidad, fuente, año>» para cerrar la magnitud.
* Evitar: «falta de», «ausencia de», «carencia de» o «no existe», también en
  la narración causal, porque un problema no es la ausencia de su solución
  (reformular como estado: «baja capacidad técnica»); hablar de la solución en
  el diagnóstico («con el proyecto se busca», «resulta necesario
  desarrollar»), que va en objetivos y alternativas; una línea base que cuenta
  la solución inexistente («Cero (0) prototipos»); condicionales en cadena
  («lo que puede llevar a…»); valorativos sin criterio («crucial», «soluciones
  innovadoras»); nombres de personas como fuente.
* Tiempo: presente para la situación existente y la magnitud; pretérito para
  la evolución reciente y las intervenciones previas.
* Extensión: de 2.000 a 3.500 palabras.
* Tabla: `Indicador | Causa | Valor | Fuente | Año`, con la línea base en
  negrita.

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

**Redacción.** (Anexo 2, 12.1.)

* Apertura: el enunciado es el tronco del árbol de objetivos, literal y en una
  sola oración: verbo en infinitivo, objeto y población o territorio.
* Favorecer: los verbos espejo del árbol (Aumentar, Incrementar, Mejorar,
  Fortalecer, Reducir, Disminuir, Ampliar).
* Evitar: «mediante» o «a través de» (el medio), «para mejorar…» (el fin),
  cifras o porcentajes (la meta) y «construcción de…» (el producto); la prosa
  que acompañe el enunciado no lo parafrasea, porque el título y §6 lo
  repiten literal.
* Tiempo: infinitivo en el enunciado; presente en la prosa que lo acompaña.
* Extensión: una oración de hasta 460 caracteres; el indicador de resultado va
  en §11.

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

**Redacción.** (Anexo 2, 12.2.)

* Apertura: «Objetivo específico <n> (OE<n>): <texto literal del árbol>».
* Favorecer: verbo, objeto y el elemento mínimo que distingue cada objetivo.
* Evitar: confundir el objetivo con actividades o productos; metas en el
  enunciado; repetir los calificadores del objetivo general; parafrasear, ya
  que el texto se repite literal en la metodología, la cadena de valor y el
  cronograma.
* Tiempo: infinitivo.
* Extensión: tres enunciados de una oración.

### SGR §10

La metodología se organiza como cadena de valor: insumos → actividades →
productos → resultados → impactos (Instructivo MGA 2023, p. 62). Cada producto
responde a un objetivo específico y cada fase nombra sus actividades por etapa
(preinversión, inversión, operación). El detalle tabular va en
`23_cadena_valor.tex`.

**Redacción.** (Anexo 2, cap. 14.)

* Apertura: por objetivo, «Objetivo específico <n>: <texto literal>»; por
  actividad, «Actividad <n.n.n>: <infinitivo + objeto + localización>» con los
  campos «Responsable:», «Tareas:», «Resultados de la actividad:» y «Medio de
  verificación:».
* Favorecer: «Esta actividad consiste en…», «<Entidad> coordinará…», «Se
  conformará un expediente documental técnico que reúna…», «La verificación
  del TRL N se sustentará en…», «Los criterios de aceptación se establecerán a
  partir de…».
* Evitar: en el nombre de una actividad, los verbos que la MGA prohíbe para
  ellas (apropiar, asegurar, colaborar, consolidar, desarrollar, fomentar,
  fortalecer, garantizar, implementar, impulsar, mejorar, movilizar, proponer,
  promover; Manual MGA 2015, p. 81), que en los objetivos sí valen; tareas o
  insumos como actividad («Comprar…», «Contratar…», «viáticos»); «paquetes de
  trabajo», porque el Anexo 2 organiza por objetivo, producto y actividad
  («paquete tecnológico» sí es término oficial); un TRL declarado sin
  evidencia; «se determinará durante la ejecución» sin criterio; «de manera
  integral» o «robusto» como relleno.
* Tiempo: futuro de indicativo e impersonal con «se»; infinitivo solo en los
  nombres de actividad.
* Extensión: la referencia mide unas 2.940 palabras de prosa en párrafos de
  unas 70, más las tablas.
* Tablas: `No. | Actividad | Responsable | Tareas | Resultados | Medio de
  verificación`; `No. | Actividad | Mes inicio | Mes fin | ¿En qué consiste?`;
  TRL: `Tipología declarada | TRL actual (Entrada) | Justificación | TRL
  esperado al finalizar el proyecto | Hito y evidencia de cierre`.

### SGR §11

Los resultados esperados incluyen el **indicador de resultado** del objetivo
general, que nace de la magnitud del problema central y cumple los criterios
CREMA (claro, relevante, económico, medible, adecuado): nombre, unidad de medida,
meta numérica, tipo de fuente y fuente de verificación (Instructivo MGA 2023,
pp. 40-41). Ejemplo de forma: «Residuos sólidos aprovechados / residuos sólidos
generados; unidad: porcentaje; meta: 20 %». La regla de no fijar metas
porcentuales rige para §5, §6 y §7; aquí la meta es obligatoria.

**Redacción.** (Anexo 2, cap. 17.)

* Apertura: «El impacto de la implementación del proyecto a corto, mediano y
  largo plazo en la región…».
* Favorecer: resultados con meta, plazo e indicador; «Cada bien queda a cargo
  de <entidad>, que…»; «El proyecto no destina recursos SGR a la operación
  posterior de los bienes».
* Evitar: impactos sin indicador ni plazo; productos presentados como
  impactos; «transformará la región» o «beneficiará a miles de personas»; «se
  garantizará» sin mecanismo; omitir los efectos negativos sobre el ambiente y
  la salud humana.
* Tiempo: presente, en oraciones cortas; «se espera» solo para impactos de
  mediano y largo plazo.
* Extensión: prosa breve (la referencia mide unas 440 palabras con oraciones
  de unas 18); el peso está en las tablas.
* Tablas: `Resultado | Meta | Impacto`; `Tipo de impacto | Impacto esperado |
  Plazo | Indicador verificable`; `Resultado | Entidad responsable | Operación
  y mantenimiento posterior | Fuente de recursos`.

### SGR §13

En el flujo SGR §13 no se redacta a mano: el presupuestador escribe
`artefactos/sgr/presupuesto.json` (esquema `morfeo.presupuesto-sgr/v1`) en la
Fase 6.4 y `python3 scripts/presupuesto_sgr.py render <RUN_ROOT>` genera
`13_presupuesto.tex` con la cabecera `% GENERADO`; las cifras se corrigen en
el JSON, nunca en el `.tex`. Cada ítem tiene dos vistas del mismo dinero:

* **Rubro de Minciencias** (TdR Conv 54 §13.2): talento humano, equipos y
  software, capacitación y eventos, servicios tecnológicos y pruebas,
  materiales, insumos y documentación, protección del conocimiento y
  divulgación, gastos de viaje, infraestructura, administrativos, seguimiento
  y otros. Cada rubro se justifica frente a los objetivos y coincide con el
  SIGP y los Anexos 1, 2 y 3.
* **Insumo de la MGA** (Instructivo MGA 2023, p. 68): 1 mano de obra
  calificada, 2 mano de obra no calificada, 3 materiales, 4 servicios
  domiciliarios, 5 terrenos, 6 edificios, 7 maquinaria y equipo, 8
  transporte, 9 alojamiento y comidas, 10 servicios a empresas y a la
  producción, 11 servicios comunitarios.

Cada ítem declara la entidad (de `alianza.json`) y la fuente (SGR, especie o
efectivo), las actividades de la cadena de valor que financia y sus
cotizaciones. Su valor se reparte por igual entre esas actividades (regla del
Anexo 3) y `presupuesto_sgr.py sync-cadena` escribe el `costo` de cada
actividad en `cadena_valor.json`; la proyección financiera anual sale de esos
costos y de los meses del cronograma. El script verifica: el total SGR no
supera el tope; el rubro Seguimiento con recursos SGR existe; los equipos y
servicios tecnológicos tienen al menos dos cotizaciones; los gastos de viaje
SGR no pasan del 2 % del total SGR; el componente de transferencia llega al
1 %; la contrapartida en especie y en efectivo de cada entidad es la de
`alianza.json`.

* Solo gasto de inversión. Se costean la mitigación de cada riesgo del anexo
  `24_riesgos.tex` y las estrategias de manejo de participantes oponentes o
  perjudicados.
* La cofinanciación entre fuentes se declara por fuente y por año. Si hay
  vigencias futuras: al menos 15 % apropiado en el bienio vigente, máximo cuatro
  bienios y no más del 50 % del plan de recursos.
* El talento humano de contrapartida se calcula con horas por semana × valor
  hora × meses × semanas por mes × factor prestacional (campo `talento` del
  ítem).

**Redacción.** (Presupuesto MGA, Anexo 3 y Anexo 2 cap. 29.)

* Apertura: la oración de entrada a las tablas la escribe el script; la única
  prosa del agente es la `justificacion` de cada ítem, que empieza por la
  actividad que financia: «Financia la actividad <n.n.n>, <nombre>, con…».
* Favorecer: el código de actividad en cada justificación; la razonabilidad
  probada con cotizaciones; los nombres de entidad idénticos a `alianza.json`;
  las cifras en pesos, sin decimales.
* Evitar: rubros o ítems sin actividad; gastos permanentes de funcionamiento;
  cifras distintas de las de la carta unificada y el Anexo 3; «entre otros» o
  «etc.» en la lista de insumos; «costos razonables» o «precios de mercado»
  sin cotización; editar `13_presupuesto.tex` a mano.
* Tiempo: presente.
* Extensión: sin prosa fuera de la justificación por ítem.
* Tablas (generadas): `Rubro | SGR | Especie | Efectivo | Total` con el
  desglose por entidad; `Entidad | SGR | Especie | Efectivo | Total`; `Insumo
  de la MGA | SGR | Especie | Efectivo | Total`; `Rubro | Descripción y
  justificación | Entidad | Actividades | Valor | Cotizaciones`; `Año | Valor |
  Porcentaje`.

### SGR §14

El cronograma se genera desde la cadena de valor (`artefactos/sgr/cadena_valor.json`,
con `mes_inicio`, `mes_fin`, `ruta_critica` y la `etapa` opcional de cada
actividad) y desde `artefactos/sgr/hitos.json` (esquema `morfeo.hitos-sgr/v1`),
que escribe el investigador en la Fase 6.45. `python3 scripts/cronograma_sgr.py
render <RUN_ROOT>` escribe `14_cronograma_actividades.tex` con la cabecera
`% GENERADO`, agrupado por objetivo específico y producto, en meses, con la
etapa (preinversión, inversión, operación; inversión por defecto) y la marca de
ruta crítica. Cada producto lleva dos o más actividades y al menos una en la
ruta crítica; las tareas no se cronograman. Después del mes 3 no pasan más de
tres meses seguidos sin un hito verificable.

**Redacción.** (Anexo 2, cap. 22.)

* Apertura: una frase de entrada a la tabla, que pone el script.
* Favorecer: las actividades con el mismo nombre y código de la metodología y
  la cadena de valor, en meses, con etapa y ruta crítica; cada hito de
  `hitos.json` con un nombre nominal («Prototipo validado en laboratorio»), el
  mes, las actividades que lo producen y su medio de verificación.
* Evitar: trimestres en lugar de meses; renombrar actividades; capacitaciones
  antes de que exista el equipo o la plataforma; dejar los primeros
  resultados útiles para el final; hitos sin medio de verificación.
* Tiempo: presente en la frase de entrada; nominal en los hitos.
* Extensión: una oración más la tabla.
* Tabla (generada): `Objetivo específico | Producto | Actividad | Mes 1 … Mes n`.

### SGR §15

En el flujo SGR, §15 (`15_productos_esperados.tex`, Anexo 2 cap. 21) no se
redacta a mano cuando existe `artefactos/sgr/productos.json`: lo genera
`python3 scripts/productos_sgr.py render <RUN_ROOT>` con la cabecera
`% GENERADO`. Los productos por objetivo salen de la cadena de valor: cada
producto se toma del catálogo de productos del DNP, con su código
(`^39\d{5}$`), su indicador de producto, unidad y meta (Instructivo MGA 2023, p.
108); `check` avisa cuando a un producto le falta alguno de ellos. El nombre del
producto no incluye «elaborado», «implementado» ni «entregado», y no se confunde
con la población, las actividades ni los insumos (Instructivo MGA 2023, p. 64).
Siguen los productos de CTeI del bloque `productos_ctei` (tipo, subtipo,
categoría, cantidad, producto de la cadena y si es adicional al mínimo de la
convocatoria) y la estrategia de divulgación pública de la ciencia del bloque
`divulgacion` (públicos, medios, productos, responsable, cronograma y si está
costeada). `check` exige el mínimo de productos de CTeI que fija la rúbrica
(`minimo_productos`, por integrante del talento) y calcula la vista previa del
criterio 2.5 de la Convocatoria 54: los productos del mínimo no suman; los
adicionales sí (tres o más con dos TOP o A, 3 puntos; dos con uno TOP o A, 2;
uno, 1), y la divulgación completa y costeada vale 2 (incompleta, 1).
`investigador` escribe los productos de CTeI y la estrategia de divulgación;
`redactor`, su `introduccion`. Una corrida SGR anterior sin `productos.json`
conserva su §15 escrito a mano. En el flujo base §15 sigue la guía base.

**Redacción.** (Anexo 2, cap. 21; rúbrica 2.5.) Rige la `introduccion` de la
divulgación y los textos de los productos de CTeI.

* Apertura: «El proyecto entregará…» con el nombre del catálogo; para la
  divulgación, «La estrategia de divulgación pública de la ciencia acercará
  <resultado> a <público>, mediante <medio>…».
* Favorecer: el nombre y el código del catálogo, literales («3906012
  Documentos de investigación»), con su indicador («Documentos de
  investigación elaborados»): en el indicador el participio es oficial; cada
  producto de CTeI con su tipo, categoría y producto de la cadena; públicos y
  medios con nombre propio.
* Evitar: «elaborado», «implementado» o «entregado» en el nombre del
  producto; productos inventados, repetidos o de más de un programa; contar
  como adicionales los productos del mínimo de la convocatoria; «público en
  general» como destinatario de la divulgación; «se espera» para productos.
* Tiempo: futuro de compromiso en la prosa («El proyecto entregará…»).
* Extensión: introducción de la divulgación de 60 a 150 palabras; el resto va
  en las tablas.
* Tablas (generadas): `Programa | Producto | Medido a través de | Indicador de
  producto | Unidad de medida | Descripción`, agrupada por objetivo
  específico; `Tipo | Subtipo | Categoría | Cantidad | Producto de la cadena |
  Compromiso | Descripción`; `Públicos | Medios | Productos | Responsable |
  Costeada`; `Mes | Acción`.

### SGR §17

Las comunidades se presentan con su rol en la matriz de participantes del anexo
`20_participantes.tex`. Cuando el territorio tiene comunidades étnicas, se
verifica si el proyecto requiere consulta previa y se deja constancia del
certificado correspondiente.

**Redacción.** (Anexo 2 Conv 54, cap. 8.)

* Apertura de celda: la demanda citada literal entre comillas latinas, con su
  departamento; la contribución empieza por el objetivo o el producto: «El
  OE<n> aporta <producto con unidad> a <actor>, con <indicador>…» o «Mediante
  la actividad <n.n.n>, el proyecto entrega…».
* Favorecer: el rol de cada comunidad tal como figura en la matriz de
  participantes.
* Evitar: una contribución general sin indicador; el mismo texto copiado para
  cada departamento; duplicar la tabla de demandas; «contribuirá
  significativamente» o «impactará positivamente».
* Tiempo: futuro para la contribución; presente para la pertinencia.
* Extensión: prosa mínima; el contenido va en las tablas.
* Tablas: `Demanda territorial | Descripción | Articulación y contribución del
  proyecto`; `Actores | Pertinencia frente a los objetivos y las demandas
  territoriales`.

### SGR §18

En el flujo SGR, §18 (`18_apropiacion_social.tex`, Anexo 2 cap. 19) no se
redacta a mano: lo genera `python3 scripts/componentes_sgr.py render <RUN_ROOT>`
desde el bloque `asc` de `artefactos/sgr/componentes.json`, con la cabecera
`% GENERADO`. La ruta cubre los siete elementos del TdR 6.1 (identificación del
problema, vinculación de actores, diseño, planeación, ejecución, seguimiento y
resultados y sostenibilidad), cada uno con sus meses, lo que se hace con los
actores y las actividades de la cadena de valor; la estrategia no se limita a
la divulgación o la socialización de resultados. `redactor` escribe la
`introduccion` y los textos de los actores, de la ruta y de los productos;
`check` exige los siete elementos y al menos un producto con medio de
verificación y mes. En el flujo base §18 sigue la guía base.

**Redacción.** (Anexo 2, cap. 19; TdR 6.1; rúbrica 2.4.)

* Apertura: «La estrategia de Apropiación Social del Conocimiento (ASC) del
  proyecto se concibe como un proceso transversal de participación, diálogo
  de saberes, colaboración y co-creación entre…» o «La estrategia se
  desarrollará mediante el reconocimiento de los contextos territoriales…».
* Favorecer: quiénes participan, cómo participan, en qué momentos inciden, qué
  aportan y qué deciden o validan juntos; el léxico del TdR (participación,
  diálogo de saberes, co-creación, incidencia, validación conjunta, mesas de
  trabajo, grupos focales, comunidades de práctica, seguimiento participativo,
  sistematización).
* Evitar: reducir la ASC a «socialización» o «divulgación» de resultados,
  «capacitar a la comunidad», «sensibilizar» o «llevar el conocimiento a»
  (comunicación unidireccional); «empoderar» sin mecanismo; concentrar la ASC
  al final del cronograma; productos sin medio de verificación ni mes.
* Tiempo: futuro para la estrategia y los productos; presente para el
  reconocimiento del contexto.
* Extensión: introducción de 150 a 300 palabras; el detalle va en las tablas.
* Tablas (generadas): `Grupo y actores | Relación con la problemática |
  Saberes y capacidades | Rol y momento de participación | Incidencia`;
  `Elemento | Meses | Qué se hace con los actores | Actividades`;
  `Producto | Descripción | Medio de verificación | Mes | Actividad`.

---

## Anexos MGA (Fase 6.47, solo flujo SGR)

Cada anexo es un archivo de `redaccion/sections/` que `main.tex` incluye después
de §18 y antes de la bibliografía. Los redacta `redactor`, salvo los que se
generan desde datos: A23 (`cadena_valor.json`), A26 a A28 (`alianza.json` y
`territorio.json`), A30 (`presupuesto.json`, con §13), A31 a A35
(`componentes.json`, con §18), A36 y A37 (`productos.json`, con §15) y A38 y
A39 (`requisitos.json`).
Las tablas usan `xltabular`; la prosa sigue `estilo-natural-es` con los
ajustes de la skill `estilo-sgr`.

### SGR A19

`19_alineacion_planes.tex`, «Alineación con los planes de desarrollo». Tabla:
plan (PND, departamental, municipal, étnico si aplica, agenda o plan regional de
CTeI) | programa | meta o indicador del plan | contribución del proyecto. Nombra
el actor del SNCTeI que participa.

**Redacción.** (Anexo 2, cap. 4.)

* Apertura: «El proyecto se articula con los instrumentos nacionales,
  departamentales, municipales y regionales de…» o «La presente propuesta se
  enmarca en el Desafío <n>, «<nombre>»…».
* Favorecer: el nombre oficial del plan o del programa entre comillas latinas
  y, en la columna de contribución, el aporte a esa meta; «Se inscribe en el
  desafío <n>…»; «El proyecto contribuye al ODS <n> (<nombre>)…».
* Evitar: pilares o programas sin la relación con el proyecto; pegar
  párrafos del PND; «se alinea perfectamente», «en total consonancia» o
  «contribuye de manera significativa» sin meta.
* Tiempo: presente («se articula», «responde», «contribuye»).
* Extensión: la referencia mide unas 810 palabras de prosa en párrafos de
  unas 80, más las tablas.
* Tabla: `Plan | Programa | Meta o indicador del plan | Contribución del
  proyecto`.

### SGR A20

`20_participantes.tex`, «Análisis de participantes». Matriz con actor, nivel
(nacional, departamental, municipal, otro), entidad, posición (beneficiario,
cooperante, oponente, perjudicado), intereses o expectativas y contribución o
gestión (Instructivo MGA 2023, p. 32). El análisis es obligatorio con dos o más
actores. Para oponentes y perjudicados se describe la estrategia de manejo, que
se costea en §13.

**Redacción.** (Anexo 2, cap. 10.)

* Apertura: una frase de entrada; las celdas son sintagmas nominales.
* Favorecer: el vocabulario fijo de la MGA: posiciones Beneficiario,
  Cooperante, Oponente y Perjudicado; cuadrantes «Gestionar atentamente»,
  «Mantener satisfecho», «Mantener informado» y «Monitorear»; contribuciones
  en infinitivo («Formular y ejecutar el proyecto»).
* Evitar: una entidad cooperante y beneficiaria a la vez; omitir oponentes o
  perjudicados sin decir por qué; responsabilidades genéricas («apoyar»,
  «acompañar») que no correspondan a actividades del cronograma.
* Tiempo: presente; infinitivo en las contribuciones.
* Extensión: prosa mínima.
* Tablas: `Actor | Entidad | Posición | Intereses o expectativas |
  Contribución o gestión`; `Nombre de la entidad | Tipo de aliado | Posición |
  Rol en la alianza | Responsabilidades u obligaciones | Aportes (dinero /
  especie)`.

### SGR A21

`21_poblacion.tex`, «Población afectada y objetivo». La población afectada es el
conjunto de personas que padecen la situación negativa en el área de estudio; la
población objetivo, la parte priorizada que el proyecto atiende (Instructivo MGA
2023, pp. 36-38). Siempre son personas, con cifra mayor que cero, fuente y
localización hasta vereda o resguardo cuando aplique, y caracterización por grupo
de edad, etnia, género, condición de víctima y discapacidad.

**Redacción.** (Anexo 2, cap. 11.)

* Apertura: «La población afectada por esta problemática incluye a…» y «La
  selección de la población objetivo considera <criterios>…».
* Favorecer: «Para caracterizar demográficamente a <grupo> según <variable>,
  se recurrió a <fuente oficial, año>»; «Según la Tabla N, el <x> % de la
  población afectada…»; las medidas en futuro («El proyecto vinculará…»).
* Evitar: la primera persona («podemos decir que…»); «se garantizará» sin
  actividad, indicador y meta; cuantificadores vagos («una parte
  significativa»); entidades u hogares en lugar de personas; «beneficiará a
  toda la región».
* Tiempo: presente para los criterios; futuro para las medidas.
* Extensión: la referencia mide unas 2.270 palabras de prosa en párrafos de
  unas 70, más las tablas.
* Tablas: `Región | Departamento | Municipio | Población`, con cifras del
  DANE; `Grupo poblacional | Actividad en la cadena de valor | Valor de la
  actividad | Descripción de la participación`.

### SGR A22

`22_alternativas.tex`, «Alternativas de solución». Al menos dos alternativas, una
de ellas puede ser el escenario sin proyecto o la situación base optimizada
(Módulo 3, p. 50; Instructivo MGA 2023, p. 44). Clasifica las acciones en
complementarias o excluyentes, justifica las descartadas y declara el tipo de
evaluación (costo-eficiencia o multicriterio para CTeI, donde el desarrollo de la
ciencia, la tecnología y la innovación es un criterio).

**Redacción.** (Anexo 2, cap. 13.)

* Apertura: «La alternativa 1 parte de <activo o capacidad existente>…».
* Favorecer: párrafos rotulados («Características técnicas.», «Objetivos y
  productos.», «Metodología y duración.», «Resultados e impacto.»,
  «Características financieras.»); «La alternativa seleccionada contempla…»;
  «La alternativa <n> se descarta porque <razón técnica>».
* Evitar: descartar solo por costo; una alternativa de paja sin evaluación;
  «Rentabilidad: Sí» sin el tipo de evaluación; «la única alternativa viable»;
  volver a resumir el proyecto.
* Tiempo: presente.
* Extensión: la referencia mide unas 1.140 palabras, más las tablas.
* Tablas: `Nombre de la alternativa | Descripción de la evaluación |
  Justificación de la alternativa seleccionada`; `Factor | Descripción |
  Alt. 1 | Alt. 2 | Alt. 3`.

### SGR A23

`23_cadena_valor.tex`, «Cadena de valor». Tabla: objetivo específico | producto
(catálogo DNP, indicador, unidad, meta) | actividades (etapa, ruta crítica) |
costo por insumo MGA. Cada producto tiene dos o más actividades. Las actividades
no usan los verbos que la MGA prohíbe para ellas (Manual MGA 2015, p. 81):
apropiar, asegurar, colaborar, consolidar, desarrollar, fomentar, fortalecer,
garantizar, implementar, impulsar, mejorar, movilizar, proponer, promover.
Los costos salen de §13 (ya aprobado en la Fase 6.4) y su suma coincide con el
total del presupuesto; la compuerta de anexos lo verifica.

**Redacción.** (Anexo 2, cap. 15.)

* Apertura: una frase de entrada; el anexo es una tabla. Cuando la cadena de
  valor existe como datos (`artefactos/sgr/cadena_valor.json`), la tabla la
  escribe un script y los nombres se corrigen en ese archivo, no en el `.tex`.
* Favorecer: celda de producto «Código: 3906xxx / <nombre del catálogo> /
  <valor>»; celda de actividad «<n.n.n> Actividad <n>: <nombre> / Ruta
  crítica».
* Evitar: un verbo prohibido por la MGA al inicio del nombre de una
  actividad; «elaborado», «implementado» o «entregado» en el nombre del
  producto, salvo en el nombre del catálogo; un producto con una sola
  actividad; renombrar actividades entre capítulos.
* Tiempo: infinitivo en los nombres de actividad; sintagma nominal en los
  productos.
* Extensión: solo la tabla.
* Tabla: `Objetivo específico | Producto | Medido a través del cual se verifica
  | Cantidad / Meta | Actividades asociadas al producto`.

### SGR A24

`24_riesgos.tex`, «Análisis de riesgos». Al menos un riesgo por nivel
(propósito, productos, actividades), con tipo, descripción, probabilidad (1-5),
impacto (1-5), efectos y medida de mitigación costeada (Módulo 4, pp. 38-40;
Instructivo MGA 2023, pp. 72-74). Incluye el riesgo de desastres y climático del
territorio.

**Redacción.** (Anexo 2, cap. 23.)

* Apertura: una frase de entrada a la tabla.
* Favorecer: la descripción nominal del riesgo («Retrasos en la contratación
  de personal…»); la medida en infinitivo, con responsable y costo; la escala
  declarada (1 a 5).
* Evitar: medidas genéricas («hacer seguimiento», «mantener una actitud
  preventiva», «ser muy rigurosos»); riesgos sin valoración; omitir el riesgo
  de desastres y climático.
* Tiempo: nominal en la descripción; infinitivo en la medida.
* Extensión: solo la tabla.
* Tabla: `Tipo de riesgo | Descripción del riesgo | Probabilidad | Impacto |
  Efectos | Medidas de mitigación`.

### SGR A25

`25_marco_logico.tex`, «Matriz de marco lógico». Matriz 4×4: filas fin (objetivo
del plan de desarrollo), propósito (objetivo general), productos y actividades;
columnas descripción, indicadores, fuentes de verificación y supuestos. Los
riesgos del anexo A24 pasan a ser supuestos (Manual MGA 2015, pp. 79-82). La
fila del propósito usa el indicador de resultado de §11.

**Redacción.** (Matriz de marco lógico de la MGA.)

* Apertura: una frase de entrada a la matriz.
* Favorecer: en fin, propósito, productos y actividades, los textos literales
  del plan, del objetivo general, del catálogo y de la cadena de valor; los
  supuestos como condiciones externas en positivo («Las entidades
  territoriales mantienen…»).
* Evitar: parafrasear los textos que vienen del árbol y de la cadena;
  supuestos que el proyecto controla; indicadores sin fuente de verificación.
* Tiempo: nominal en las filas; presente en los supuestos.
* Extensión: solo la matriz.
* Tabla: `Nivel | Descripción | Indicadores | Fuentes de verificación |
  Supuestos`.

### SGR A26

`26_identificacion.tex`, «Identificación del proyecto» (Anexo 2, cap. 1). Ficha
de la alianza y del territorio: entidades con su tipo y su rol, departamentos y
municipios de ejecución, demandas territoriales con su código y grupos de
investigación. Fuente: `artefactos/sgr/alianza.json` y
`artefactos/sgr/territorio.json` (unidad `fase1b_sgr`, compuerta
`GTerritorio`). La sección la escribe
`python3 scripts/alianza_territorio_sgr.py render <RUN_ROOT>` y lleva la
cabecera `% GENERADO`; los datos se corrigen en los JSON, nunca en el `.tex`.
El título del proyecto sigue en `redaccion/datos_proyecto.tex`
(`sgr-titulo-no-derivado`). Con `artefactos/estructura_tdr.json`, la sección
abre el capítulo cuyo título textual es «IDENTIFICACIÓN DEL PROYECTO».

**Redacción.** (Anexo 2, cap. 1.)

* Apertura: la justificación del desafío y de las sublíneas, cuando el TdR la
  pide, va fuera de las tablas: «La propuesta se enmarca en el Desafío <n>,
  «<nombre>», porque…», «Se abordarán las sublíneas <x.y> <nombre>…» o «El
  proyecto atenderá una demanda territorial por cada uno de los <N>
  departamentos de ejecución».
* Favorecer: el nombre oficial de cada entidad y de cada grupo, idéntico en la
  matriz, la idoneidad y las cartas (lista blanca); un solo tipo por entidad;
  en la tabla de grupos, la contribución de las líneas a las demandas.
* Evitar: adjetivos de adorno o fines en el nombre («integral», «para mejorar
  la calidad de vida»), porque el nombre deriva del objetivo general (Manual
  MGA 2015, tabla 12, p. 80); una entidad con dos tipos, porque la plantilla
  admite una sola categoría; la primera persona o el lenguaje de portafolio
  («nuestra universidad»); la contribución del grupo redactada como
  trayectoria, que va en el capítulo 27.
* Tiempo: presente en la ficha; futuro para lo que el proyecto atenderá.
* Extensión: tablas generadas; la prosa del desafío, en párrafos cortos de
  unas 50 palabras.
* Tablas: `Entidad | NIT | Tipo de entidad y rol en la alianza |
  Departamento`; `Departamento | Municipios`; `Código | Demanda territorial |
  Departamento`; `Nombre del grupo | Entidad a la que pertenece | Código
  GrupLAC y clasificación | Líneas de investigación`.

### SGR A27

`27_demandas_territoriales.tex`, «Articulación del proyecto con las demandas
territoriales» y «Configuración regional» (Anexo 2 Conv 54, caps. 8 y 8.1).
Fuente: `demandas` y `configuracion_regional` de
`artefactos/sgr/territorio.json`. `insumos-observador` copia el texto de cada
demanda literal del TdR (Anexo 4) con su código, departamento y fuente;
`investigador` la vincula con causas del árbol de problemas y objetivos
específicos, y con actividades y productos cuando existe la cadena de valor
(`fase4_sgr`), y redacta en el campo `articulacion` la contribución del
proyecto. La tabla la escribe `scripts/alianza_territorio_sgr.py render`; la
prosa vive dentro del JSON y se corrige allí.

**Redacción.** (Anexo 2 Conv 54, cap. 8.)

* Apertura de celda: la demanda va literal entre comillas latinas, con su
  código y su departamento; la articulación empieza por el objetivo o el
  producto: «El OE<n> aporta <producto con unidad> a <actor>, con
  <indicador>…» o «Mediante la actividad <n.n.n>, el proyecto entrega…».
* Favorecer: un texto de articulación propio por demanda, con el indicador del
  producto; en 8.1, la pertinencia de cada actor frente a un objetivo o una
  demanda concreta.
* Evitar: parafrasear la demanda, porque la rúbrica 2.1 coteja el texto del
  TdR; una contribución general sin indicador («contribuirá
  significativamente», «impactará positivamente»), porque la rúbrica le da 3
  de 7 puntos; el mismo texto copiado para cada departamento; declarar la
  pertinencia («es pertinente», «de gran importancia») en vez de mostrarla.
* Tiempo: futuro para la contribución; presente para la pertinencia.
* Extensión: prosa mínima; cada articulación, de una a tres oraciones.
* Tablas: `Demanda territorial | Descripción | Articulación y contribución del
  proyecto`; `Departamento | Actor | Pertinencia frente a los objetivos y las
  demandas territoriales`.

### SGR A28

`28_matriz_responsabilidades.tex`, «Matriz de responsabilidades de las
entidades participantes que conforman la alianza» (Anexo 2, cap. 10.1) y el
modelo de gobernanza del Anexo 1. Fuente: `entidades` y `gobernanza` de
`artefactos/sgr/alianza.json`. La escribe
`scripts/alianza_territorio_sgr.py render`; con
`artefactos/estructura_tdr.json` entra como subsección del capítulo «ANÁLISIS
DE PARTICIPANTES», después de `20_participantes`, que conserva la matriz de
posición, interés e influencia.

**Redacción.** (Anexo 2, cap. 10.1; Anexo 1.)

* Apertura: ninguna; la matriz y la tabla de gobernanza son el contenido.
* Favorecer: las posiciones de la MGA (Cooperante, Beneficiario, Oponente,
  Perjudicado); responsabilidades en infinitivo («Formular y ejecutar el
  proyecto») con los códigos de actividad de la cadena de valor; aportes en
  especie y en efectivo iguales a los del Anexo 3; una gobernanza con
  instancia, periodicidad y responsable.
* Evitar: responsabilidades genéricas («apoyar», «acompañar») sin actividad
  del cronograma; una entidad cooperante y beneficiaria a la vez, que la
  plantilla prohíbe; una gobernanza «de manera articulada» o «trabajo
  conjunto» sin decir quién decide ni cada cuánto, porque la rúbrica 4.1 lo
  pide.
* Tiempo: infinitivo en las responsabilidades; presente en la gobernanza.
* Extensión: solo las tablas.
* Tablas: `Entidad | Tipo de aliado | Posición | Rol | Responsabilidades u
  obligaciones | Aportes (especie / efectivo)`; `Componente | Descripción`
  (toma de decisiones, instancias, propiedad intelectual y seguimiento).

### SGR A29

`29_idoneidad_trayectoria.tex`, «Idoneidad y trayectoria de la entidad
proponente y demás participantes» (Anexo 2, cap. 27). La redacta `redactor` en
la fase de anexos SGR a partir de `artefactos/sgr/alianza.json` (rol,
actividades, aportes, grupos y `trayectoria`) y de las cartas aval; no la
genera un script. Cada proyecto de trayectoria se acredita una sola vez,
aunque lo liste más de una entidad (rúbrica 3.1, nota ii); los conteos los da
`python3 scripts/alianza_territorio_sgr.py datos <RUN_ROOT>`.

**Redacción.** (Anexo 2, cap. 27.)

* Apertura: un bloque por entidad, en tercera persona: «<Entidad> aporta al
  proyecto <aporte> en las actividades <n.n.n>…».
* Favorecer: el orden nombre y tipo, aporte (rol, actividades,
  contrapartida), trayectoria pertinente con código o BPIN, y capacidades con
  evidencia: «El grupo <nombre>, categoría <A1> en la convocatoria <n>, …»,
  «Desde <año>, <entidad> ha ejecutado N proyectos financiados por el SGR,
  entre ellos…».
* Evitar: el texto institucional pegado en primera persona («nuestra
  universidad», «hemos ejecutado»), que en la referencia concentra casi toda
  la primera persona del documento; el lenguaje de folleto («líder»,
  «referente nacional», «de talla mundial», «reconocido» sin la entidad que
  reconoce ni la categoría), porque la idoneidad se prueba con proyectos y
  categorías; historias institucionales sin relación con las actividades; el
  mismo proyecto acreditado por dos integrantes.
* Tiempo: presente para las capacidades; pretérito para la trayectoria;
  futuro para el aporte al proyecto.
* Extensión: de 300 a 600 palabras por entidad; la referencia mide 10.681
  palabras en total, el capítulo más largo, y conviene no imitarla.

### SGR A30

`30_fuentes_financiacion.tex`, «Resumen de fuentes de financiación» (Anexo 2,
cap. 29). Fuente: `artefactos/sgr/presupuesto.json` y los nombres de
`artefactos/sgr/alianza.json`. Lo genera
`python3 scripts/presupuesto_sgr.py render <RUN_ROOT>` junto con §13, con la
cabecera `% GENERADO`; en la fase de anexos SGR se vuelve a generar si el
presupuesto cambió. Con `artefactos/estructura_tdr.json` entra en el capítulo
cuyo título textual es «RESUMEN DE FUENTES DE FINANCIACIÓN».

**Redacción.** (Anexo 2, cap. 29.)

* Apertura: ninguna; el capítulo es la tabla y las tres líneas literales.
* Favorecer: las tres líneas de la plantilla, cada una en letras y números
  («MIL CIENTO VEINTE MILLONES DE PESOS M/CTE ($ 1.120.000.000)»): «Valor
  total de recursos solicitados a la Asignación de CTeI/ Asignación de CTeI
  Ambiental del SGR – Sistema General de Regalías:», «Valor total
  contrapartida (en efectivo y en especie):» y «Valor total del proyecto:»;
  los nombres de entidad idénticos a la matriz de responsabilidades.
* Evitar: prosa adicional o justificación del gasto, que va en §13; cifras
  aproximadas («cerca de», «alrededor de»); un total solo en números; montos
  distintos de la carta unificada, el Anexo 3 y la matriz de
  responsabilidades.
* Tiempo: no aplica; líneas nominales.
* Extensión: solo la tabla y las tres líneas.
* Tabla (generada): `Entidad | Fuente de recursos | Valor`.

### SGR A31

`31_trl.tex`, «Estado de desarrollo y madurez tecnológica de la solución» y
«Plan de verificación del TRL de salida» (Anexo 2 Conv 54, caps. 14.1 y 14.2).
Fuente: el bloque `trl` de `artefactos/sgr/componentes.json` (tipología A o B,
TRL de entrada con su evidencia, ruta de maduración con hitos, meses, TRL y
actividades, y el plan de verificación con escenario, responsables, criterios
de aceptación, evidencias y actor usuario). Lo genera
`python3 scripts/componentes_sgr.py render <RUN_ROOT>` con la cabecera
`% GENERADO`; con `artefactos/estructura_tdr.json` entra como subsección del
capítulo «METODOLOGÍA PARA DESARROLLAR LA ALTERNATIVA SELECCIONADA». `check`
verifica que la salida supere la entrada, que los hitos lleguen al TRL de
salida dentro de la duración y el rango de la convocatoria (Conv 54: tipología
A hasta TRL 6 con evidencia de entrada; tipología B desde TRL 4 y salida entre
7 y 9; Conv 56: una salida menor que 7 vale 0 en el criterio 3.1).

**Redacción.** (Anexo 2, caps. 14.1 y 14.2; rúbrica 1.3.) Rige la
`introduccion` del bloque `trl`.

* Apertura: «El punto de partida tecnológico corresponde a <activo>, …»; «La
  verificación del TRL <n> se sustentará en…»; «La demostración se realizará
  en un entorno pertinente, mediante…».
* Favorecer: la evidencia concreta del TRL de entrada (informe, línea base,
  resultados previos con fecha); el entorno de verificación de la tipología
  (laboratorio o entorno relevante en A; entorno operativo real con el actor
  usuario en B); «<Entidad> coordinará la ejecución y documentación de…».
* Evitar: el TRL declarado sin evidencia («No será suficiente la sola
  declaración del nivel de madurez»); «se determinará durante la ejecución»
  sin criterio de decisión; prometer un TRL de salida fuera del rango de la
  tipología; «de manera integral» o «robusto» como relleno; nombrar el TRL en
  los objetivos.
* Tiempo: presente para el punto de partida; futuro para la ruta y la
  verificación.
* Extensión: introducción de 120 a 250 palabras.
* Tablas (generadas): `Tipología declarada | TRL de entrada | Evidencia del
  punto de partida | TRL de salida comprometido`; `Hito | Mes | TRL |
  Actividades | Evidencia`; `Escenario | Responsables | Criterios de
  aceptación | Evidencias`.

### SGR A32

`32_sostenibilidad.tex`, «Sostenibilidad social y ambiental del proyecto»
(Anexo 2, cap. 16). Fuente: el bloque `sostenibilidad` de
`artefactos/sgr/componentes.json` (ODS con su contribución y los productos
que la respaldan, actores con funciones y compromiso, efectos ambientales por
actividad con su manejo). Lo genera
`python3 scripts/componentes_sgr.py render <RUN_ROOT>`; con la estructura del
TdR abre el capítulo «SOSTENIBILIDAD SOCIAL Y AMBIENTAL DEL PROYECTO».

**Redacción.** (Anexo 2, cap. 16; rúbrica 4.2.) Rige la `introduccion` del
bloque `sostenibilidad`.

* Apertura: «El proyecto contribuye de manera directa a los ODS <n>…»; «La
  sostenibilidad se plantea desde la formulación y se apoya en…».
* Favorecer: párrafos rotulados de una o dos oraciones («Capacidad instalada y
  talento humano: …», «Mecanismos de continuidad: …», «Gestión de riesgos
  ambientales: …»); cada ODS con número y meta; cada compromiso con su actor y
  su fuente de recursos.
* Evitar: «garantiza la sostenibilidad» sin responsable ni fuente de
  recursos; copiar la alineación del cap. 4 (R3); afirmaciones absolutas
  («no genera impactos negativos») sin análisis; ODS sin número.
* Tiempo: presente.
* Extensión: introducción de 120 a 250 palabras.
* Tablas (generadas): `ODS | Contribución del proyecto | Productos y
  resultados que la respaldan`; `Actores | Funciones en el proyecto |
  Compromiso con la sostenibilidad`; `Actividad | Medio | Efecto | Manejo`.

### SGR A33

`33_uso_posterior.tex`, «Uso y operación posterior de los resultados» (Anexo
2, cap. 17.1). Fuente: el bloque `uso_posterior` de
`artefactos/sgr/componentes.json` (bienes con valor SGR, entidad que los
opera, fuente de recursos y mantenimiento; compromisos de adopción de los
actores usuarios de la alianza). Lo genera
`python3 scripts/componentes_sgr.py render <RUN_ROOT>`; con la estructura del
TdR entra como subsección del capítulo «RESULTADOS E IMPACTOS…». Todo bien con
valor SGR necesita operador y fuente de recursos.

**Redacción.** (Anexo 2, cap. 17.1; rúbrica 4.2.) Rige la `introduccion` del
bloque `uso_posterior`.

* Apertura: «Cada bien queda a cargo de <entidad>, que…»; «El proyecto no
  destina recursos SGR a la operación posterior de los bienes.».
* Favorecer: la entidad responsable de la operación y el mantenimiento con su
  fuente de recursos; el compromiso del actor usuario con las condiciones de
  adopción.
* Evitar: financiar con el SGR la operación permanente o gastos de
  funcionamiento; «transformará la región» o «beneficiará a miles de
  personas» sin indicador ni actor; un bien sin operador.
* Tiempo: futuro de compromiso.
* Extensión: introducción de 80 a 180 palabras.
* Tablas (generadas): `Bienes adquiridos con SGR | Valor SGR | Entidad
  responsable | Operación y mantenimiento posterior | Fuente de recursos`;
  `Actor | Resultado que adoptará | Condiciones de adopción`.

### SGR A34

`34_transferencia.tex`, «Componente transversal de transferencia, adopción y
valoración tecnológica del conocimiento» (Anexo 2, cap. 18, numerales 18.1 a
18.5). Fuente: el bloque `transferencia` de `artefactos/sgr/componentes.json`
(resultados con usuarios y protección de PI, ruta con etapas, mecanismos,
barreras y acciones, actividades y continuidad), los nombres, productos y meses
de la cadena de valor, los responsables de la alianza y la parte de
presupuesto de cada actividad. Lo genera
`python3 scripts/componentes_sgr.py render <RUN_ROOT>`; con la estructura del
TdR abre el capítulo del componente de transferencia. `check` avisa cuando el
componente no llega al 1 % del total SGR o cuando sus actividades no coinciden
con los ítems de `presupuesto.json` con componente «transferencia».

**Redacción.** (Anexo 2, cap. 18; TdR numeral 9; rúbrica 2.3.) Rige la
`introduccion` (numeral 18.1) y la `continuidad` (numeral 18.5).

* Apertura: «El componente transversal de transferencia establecerá las
  condiciones para que los conocimientos, tecnologías y metodologías generados
  por el proyecto puedan ser utilizados por <usuarios>.»; «El alcance será
  proporcional al estado de desarrollo de cada solución.»; para 18.5: «Una vez
  finalizado el proyecto, se dará continuidad al proceso de transferencia
  mediante…».
* Favorecer: el usuario, beneficiario o receptor de cada resultado; la
  evidencia de uso, adopción y valor generado; «Se destinará como mínimo el
  uno por ciento (1 %) del valor solicitado al SGR a…».
* Evitar: reducir la transferencia a publicaciones, artículos, talleres o
  eventos («no constituirán por sí solas evidencia de transferencia»);
  receptores genéricos («la comunidad en general»); prometer
  comercialización con un TRL bajo; anglicismos no oficiales («partners»,
  «stakeholders»).
* Tiempo: futuro.
* Extensión: introducción de 150 a 300 palabras; continuidad de 60 a 150.
* Tablas (generadas): `Resultado | Usuarios | Protección de PI`; `Etapa |
  Mecanismo | Barreras | Acciones`; `Actividad | Resultado | Producto |
  Indicador | Responsable | Periodo | Presupuesto`.

### SGR A35

`35_medidas_diferenciales.tex`, «Medidas diferenciales» (Anexo 2 Conv 54, cap.
21.1). Fuente: el bloque `diferencial` de `artefactos/sgr/componentes.json`
(barreras con población, medida, actividades, indicador, meta y evidencia, o
la justificación de que no hay barreras). Lo genera
`python3 scripts/componentes_sgr.py render <RUN_ROOT>`; con la estructura del
TdR entra como subsección del capítulo «PRODUCTOS ESPERADOS».

**Redacción.** (Anexo 2, cap. 21.1; TdR 6.2; rúbrica 4.4.) Rige la
`introduccion` y, sin barreras, la `justificacion_sin_barreras`.

* Apertura: la barrera concreta que enfrenta la población («La población
  rural de <municipios> accede con conectividad limitada…»), seguida de la
  medida y su actividad.
* Favorecer: la secuencia barrera, medida, actividad, indicador, meta y
  evidencia; si no hay barreras, la razón verificable de esa conclusión.
* Evitar: «población vulnerable» sin nombrar la barrera; medidas sin
  indicador ni meta; «enfoque incluyente» o «de manera inclusiva» sin
  medida.
* Tiempo: presente para la barrera; futuro para la medida.
* Extensión: introducción de 60 a 150 palabras.
* Tabla (generada): `Barrera | Población | Medida | Actividades | Indicador |
  Meta | Evidencia`.

### SGR A36

`36_talento_humano.tex`, «Vinculación de talento humano» (Anexo 2 Conv 54, cap.
20) con la «Descripción de perfiles, actividades y plan de trabajo del talento
humano a vincular» (cap. 12.4). Fuente: el bloque `talento` de
`artefactos/sgr/productos.json` (categoría, cantidad, entidad que vincula,
perfil, formación y experiencia, actividades de la cadena de valor, duración,
valor mensual y producto final). Lo genera
`python3 scripts/productos_sgr.py render <RUN_ROOT>` con la cabecera
`% GENERADO`; con `artefactos/estructura_tdr.json` abre el capítulo
«VINCULACIÓN DE TALENTO HUMANO» (o entra como subsección cuando otro archivo lo
abre). `check` exige los mínimos de la convocatoria que copia la rúbrica
(`minimos_talento`; Conv 54 y Conv 56: «Un (1) doctor para la realización de
una estancia posdoctoral», «Dos (2) estudiantes de maestría en modalidad de
investigación», «Seis (6) jóvenes investigadores e innovadores») y avisa cuando
el talento con valor y duración no coincide con un ítem de talento humano de la
misma entidad en `presupuesto.json` (Fase 6.4). Debajo de la tabla, una línea
compara lo vinculado con cada mínimo.

**Redacción.** (Anexo 2, caps. 12.4 y 20; TdR numeral 10.) `redactor` escribe
los perfiles: `perfil`, `formacion` y `producto_final` de cada integrante.

* Apertura: «El equipo de formación del proyecto integra la cadena de
  formación de los términos de referencia…»; «Todos se vinculan como sujetos
  activos de la investigación, con actividades, meses y productos
  definidos…».
* Favorecer: las categorías oficiales del TdR («Jóvenes Investigadores e
  Innovadores», «Estudiantes de maestría», «Doctor en estancia
  posdoctoral»); el producto final que el TdR fija para cada categoría; las
  actividades con su código, tal como figuran en la cadena de valor.
* Evitar: renombrar las categorías («jóvenes talentos», «semilleristas»);
  perfiles sin actividades, meses ni producto final; copiar en prosa la tabla
  de perfiles (R6); vincular al doctor de la estancia posdoctoral con una
  entidad de la alianza de la que sea empleado.
* Tiempo: presente para los perfiles; futuro para las actividades.
* Extensión: sin prosa propia; los textos van en las celdas.
* Tablas (generadas): `Categoría | Cantidad | Entidad que vincula | Duración |
  Valor mensual | Producto final`; `Perfil | Entidad que lo vincula |
  Formación y experiencia | Actividades y meses | Producto final`.

### SGR A37

`37_indicadores.tex`, «Indicadores de gestión» e «Indicadores de producto»
(Anexo 2 Conv 54, caps. 24 y 25). Fuente: el bloque `indicadores_gestion` de
`artefactos/sgr/productos.json` (indicador, código, meta, unidad, fórmula, tipo
de fuente y periodicidad) y, para los indicadores de producto, la cadena de
valor (código DNP, indicador, unidad y meta de cada producto), que no se
duplica. Lo genera `python3 scripts/productos_sgr.py render <RUN_ROOT>`; con la
estructura del TdR abre «INDICADORES DE GESTIÓN» y, cuando el capítulo
«INDICADORES DE PRODUCTO» le sigue sin archivo propio, también lo abre. `check`
avisa cuando faltan los informes de supervisión o los informes técnicos y
financieros con su periodicidad.

**Redacción.** (Anexo 2, caps. 24 y 25; plantilla Conv 56.) `investigador`
escribe los indicadores de gestión.

* Apertura: sin prosa; la fila base es «Informes de supervisión del proyecto
  | Número / <n> | Trimestral».
* Favorecer: la periodicidad trimestral de la plantilla («al menos cuatro
  informes por cada periodo estimado en la MGA»); fórmulas verificables
  («Informes entregados / informes programados»); el tipo de fuente con su
  documento.
* Evitar: «periódicamente», «cuando se requiera» o «según se requiera» en
  lugar de la periodicidad; indicadores de producto distintos de los de la
  cadena de valor; metas sin unidad.
* Tiempo: nominal en las celdas.
* Extensión: sin prosa; solo las tablas.
* Tablas (generadas): `Indicador | Medida/Meta | Código | Fórmula | Tipo de
  fuente | Periodicidad`; `Producto | Código DNP | Indicador de producto |
  Unidad de medida | Meta`.

### SGR A38

`38_licencias_permisos.tex`, «Análisis de licencias y permisos» (Anexo 2 Conv
54, cap. 28). Fuente: el bloque `licencias` de `artefactos/sgr/requisitos.json`
(introducción y, por cada licencia o permiso, norma, si aplica, justificación,
entidad responsable y momento del trámite: previo o durante la ejecución). Lo
genera `python3 scripts/requisitos_sgr.py render <RUN_ROOT>` con la cabecera
`% GENERADO`; con `artefactos/estructura_tdr.json` abre el capítulo «ANÁLISIS
DE LICENCIAS Y PERMISOS». `check` exige norma, responsable y momento a cada
licencia que aplica y justificación a la que no aplica, y avisa cuando falta el
bloque. La plantilla pide: «Enuncie las licencias, estudios, permisos y demás
requerimientos que se consideren necesarios previo o durante la ejecución del
proyecto» (licencias ambientales, acceso a recursos genéticos, recolección de
especímenes, colecciones biológicas, consentimiento informado, consulta
previa).

**Redacción.** (Anexo 2, cap. 28; TdR Conv 54 numeral 21.) `investigador`
escribe la tabla de licencias; `redactor` escribe la introducción, que revisa
`revisor-estilo-sgr`.

* Apertura: «La entidad proponente y las demás entidades aliadas se
  comprometen a que, durante la ejecución del proyecto, se cumpla con…»; «Por
  la naturaleza del objetivo general y los objetivos específicos, el proyecto
  no requiere <licencia>; sin embargo, si durante la ejecución…».
* Favorecer: el nombre oficial de cada licencia o permiso con su norma; la
  autoridad competente, la actividad que lo hace exigible y el momento del
  trámite; la consulta previa evaluada cuando el proyecto interviene
  territorios con comunidades étnicas; tercera persona sobre el proyecto.
* Evitar: «los permisos necesarios», «las licencias pertinentes» o «a que haya
  lugar» sin nombrarlos; copiar la tabla normativa del marco conceptual (R5);
  «no aplica» sin justificación; dar por obtenido un permiso que está en
  trámite.
* Tiempo: presente para el compromiso; futuro para los trámites.
* Extensión: introducción de 80 a 200 palabras.
* Tabla (generada): `Licencia o permiso | Norma | ¿Aplica? | Justificación |
  Responsable | Momento del trámite`.

### SGR A39

`39_anexos.tex`, «ANEXOS REQUISITOS SECTORIALES QUE LE SEAN APLICABLES.»
(Anexo 2 Conv 54, cap. 31; título textual de la plantilla, que se usa cuando
la estructura del TdR no fija otro: Conv 54 TdR 13.1 «ANEXOS»). Fuente: los
requisitos habilitantes de la rúbrica (`requisitos`, copiados textuales del TdR:
Conv 54 numeral 11, Conv 56 numeral 10) y su estado en
`artefactos/sgr/requisitos.json`. Lo genera
`python3 scripts/requisitos_sgr.py render <RUN_ROOT>`: una lista, sin prosa,
de los documentos de los requisitos que aplican (los condicionales marcados
«no_aplica» con justificación y los que la alianza o el presupuesto descartan
no entran). El TdR advierte que «se tendrá por no cumplida toda condición que
no haya sido soportada documentalmente»; `check --final` (Fase 7) exige
`listo`, con su archivo en `insumos/requisitos/`, a cada requisito que aplica,
y `check` coteja las cifras declaradas del SIGP, el Anexo 1, el Anexo 3 y la
MGA Web con `presupuesto.json` y `alianza.json` (criterio 1.4 de la Conv 54,
«Coherencia de las cifras entre el SIGP, el Anexo 1 … el Anexo 2 … y el Anexo
3»). Cuando la entidad proponente es la Universidad Nacional de Colombia y la
convocatoria es la 54 o la 55, también registra los documentos del aval
institucional que pide la Vicerrectoría de Investigación en Hermes.

**Redacción.** (Anexo 2, cap. 31.) Nadie redacta este capítulo: la lista sale
de los datos.

* Apertura: sin prosa; cada ítem es «<documento> (requisito <n.n>: <nombre
  del requisito en el TdR>)».
* Favorecer: los nombres de los documentos y de los requisitos tal como los
  escribe el TdR («Anexo 1», «MGA WEB Tipología D – PIIP», «Carta de
  intención»).
* Evitar: párrafos de presentación o comentario; listar documentos de
  requisitos que no aplican; renombrar los anexos oficiales.
* Tiempo: nominal.
* Extensión: sin prosa; solo la lista.

---

## Juez SGR (asesor, Fase 7 y `/propuesta-juez`)

El agente `juez-sgr` estima el puntaje que la propuesta obtendría en la
evaluación por pares de la convocatoria. Califica cada subcriterio de la
rúbrica oficial (`scripts/rubricas_sgr/<convocatoria>.json`, con los niveles
textuales del TdR) y se apoya en la capa guía `scripts/rubricas_sgr/_guia_comun.json`,
que reúne por familia de criterio las preguntas de un par exigente, las señales
de alerta y la evidencia mínima. La capa guía orienta; los puntos salen solo de
los niveles oficiales, y sin evidencia en el documento no hay puntos.

Cada ronda deja en `artefactos/juez/` los datos extraídos con su fuente
(`datos_sgr.json`), la calificación del agente (`evaluacion_ronda_<N>.json`) y
el consolidado que escribe `scripts/juez_sgr.py calificar`: `evaluacion.json`
(total, subtotales, elegibilidad, alertas, acciones e historial de rondas) y
`evaluacion.md`, el formulario legible.

En el flujo SGR el agente copia también en `datos_sgr.json` la salida de
`python3 scripts/requisitos_sgr.py datos <RUN_ROOT> --json` (claves
`requisitos`, `cifras_coherentes` y `cifras_diferencias`); `calificar` levanta
una alerta por cada requisito habilitante aplicable que no esté listo y una
por cada cifra declarada que no coincide con el presupuesto o la alianza.

Para iterar se aplican las acciones, cada una dirigida a un agente o al
usuario: desde la pestaña «Juez final» del tablero o con
`/propuesta-juez AC1 AC3`. Las secciones de prosa pasan después por
`revisor-estilo-sgr`, y una nueva ronda de `/propuesta-juez` muestra si el
total sube. El juez nunca cambia el veredicto PASS/FAIL del `revisor`; la
auditoría final de la Fase 7 sí lee sus alertas `error` abiertas.
