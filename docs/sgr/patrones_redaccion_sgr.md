# Patrones de redacción SGR por capítulo del Anexo 2 (evidencia del flujo `sgr`)

> **Framing note (EN).** Evidence base for the SGR writing layer of Morfeo: the `Redacción` part of each `### SGR` block in `guiaProyectosIA_Agente_Regalias.md`, the lexicon `scripts/sgr/lexico_sgr.json`, the checker `scripts/estilo_sgr.py`, the skill `estilo-sgr` and the agent `revisor-estilo-sgr`. All of it applies only when the run flow is `sgr`; the base research flow does not read this file. Rules are written in Spanish because they feed Spanish-writing agents; framing notes are in English.
>
> **Sources.** The finished Anexo 2 of a reference SGR project (Conv 54) and its content-control tables; a partial Conv 54 draft (used for its non-template prose and for the template guidance it carries); the official Anexo 2 templates of Conv 56 and of the Conv 55 macroprojects; the Conv 54 TdR (numerals 6, 13, 16); the rubrics in `scripts/rubricas_sgr/`; DNP Manual conceptual MGA 2015, Instructivo MGA 2023, modules 1, 3 and 4 of the SGR diploma and its anonymized DTS example; Morfeo's guides, `estilo-natural-es`, `depuracion-redundancias-es`, `grant-flow-auditor` and `scripts/check_run.py`.
>
> **Confidentiality.** No project, place, entity, person or amount is named. Examples are generic phrasing with placeholders (`<territorio>`, `<entidad>`, `N`).
>
> **Measurement method.** Reference text split by chapter; prose = normal paragraphs outside tables; counts are case-insensitive regex hits; rates are per 1,000 prose words. Bibliography (ch. 30) excluded from voice counts. The reference is a strong model but not flawless: where it breaks a DNP/MGA rule this file says so and the DNP rule wins.
>
> **Precedence (unchanged from Morfeo):** TdR of the call > Anexo 2 template text of that call > DNP/MGA (Manual 2015, Instructivo 2023) > reference projects > Morfeo base style.

---

## 1. Voz global SGR

### 1.1 Reglas de voz (para los agentes)

1. **Tercera persona sobre el proyecto.** El sujeto por defecto es «El proyecto…». Alternativas válidas: «La propuesta se enmarca en…» (identificación y alineación), «El presente proyecto…» (máximo una vez por capítulo), «La alianza…», «La entidad proponente…», «<Entidad> coordinará / aportará…», y la impersonal con *se* («Se realizarán campañas de muestreo…»).
2. **Cero primera persona.** Ni singular ni plural: *nosotros, nuestro(a)(s), hemos, proponemos, buscamos, esperamos, pretendemos, realizaremos, podemos decir, consideramos*. Tampoco imperativos de plural implícito en tablas («Ser muy rigurosos en…»).
3. **Registro institucional de inversión pública.** El documento es un proyecto de inversión formulado con la lógica de marco lógico de la MGA (Anexo 2, nota inicial: «La estructura de este documento guía atiende a la estructura de Marco Lógico implementado en la Metodología General Ajustada (MGA)»). El vocabulario rector es *problema, causas, efectos, alternativa, objetivo, producto, actividad, indicador, meta, línea base, población afectada/objetivo, cadena de valor, riesgo*; no *pregunta de investigación, hipótesis, paquete de trabajo, estado del arte* como ejes del texto.
4. **Compromiso, no intención.** Las actividades y los productos son compromisos verificables: futuro de indicativo («entregará», «se verificará») o presente descriptivo («El proyecto se desarrolla en N meses»). Se evitan *se pretende, intentará, tratará de, esperamos, ojalá*. «Se espera…» solo para impactos de mediano y largo plazo (cap. 17), nunca para productos.
5. **Afirmación con fuente.** Toda cifra de magnitud, población o línea base lleva entidad, documento y año (Directriz SGR 4 de Morfeo; Anexo 2 §5.3 «fuente de verificación oficial actualizada»).
6. **Nominal donde la MGA es nominal.** Títulos, nodos de los árboles, nombres de productos, riesgos y tareas son sintagmas nominales; no se «verbalizan» por estilo.

### 1.2 Frecuencias medidas en el proyecto de referencia 

Cuerpo sin bibliografía: 76.441 palabras (incluye tablas). Prosa de capítulos con más de 150 palabras: ver 1.3.

| Marcador | Ocurrencias | Por 1.000 palabras | Lectura |
|---|---:|---:|---|
| «el proyecto» | 149 | 1,95 | sujeto por defecto |
| «del proyecto» | 178 | 2,33 | complemento habitual |
| «este proyecto» | 13 | 0,17 | uso puntual |
| «el presente proyecto» | 2 | 0,03 | uso excepcional |
| «la propuesta» | 8 | 0,10 | identificación y alineación |
| «la presente propuesta» | 0 | 0 | no se usa |
| «la propuesta se enmarca» | 1 | — | cap. 1 (desafío y líneas) |
| *se* (todas las funciones) | 729 | 9,54 | impersonal y pasiva refleja dominantes |
| «se busca» / «busca» | 13 / 37 | 0,17 / 0,48 | aceptado, mejor con verbo concreto |
| «se pretende» / «pretende» | 1 / 1 | 0,01 | casi ausente |
| «se espera» | 1 | 0,01 | casi ausente |
| «permitirá(n)» / «contribuirá(n)» | 30 / 10 | 0,39 / 0,13 | futuro de compromiso |
| primera persona (*nuestro, hemos, podemos decir*) | 15 + 3 + 1 | 0,25 | solo en cap. 27 (texto institucional pegado) y un desliz en cap. 11 |
| «innovador(a)(es)» | 66 | 0,86 | casi todo en nombres oficiales (entidad aliada, «jóvenes investigadores e innovadores»); 6 usos promocionales («soluciones/tecnologías innovadoras») |
| «novedoso», «pionero», «revolucionario», «vanguardia», «disruptivo» | 0 | 0 | ausentes |
| «fortalec-» | 126 | 1,64 | léxico oficial de la convocatoria |
| «articul-» | 83–99 | 1,1–1,3 | jerga SGR, tiende a la saturación |
| «sostenible» | 221 | 2,89 | saturación (término del desafío) |
| «crucial» / «efectiv-» | 15 / 26 | 0,20 / 0,34 | relleno valorativo a podar |
| «falta de» / «ausencia de» | 15 / 4 | 0,25 | 7 de 15 en el cap. 5 (contra la MGA) |
| «asimismo/así mismo» / «de esta manera/forma» | 21 / 15 | 0,27 / 0,20 | conectores repetidos |
| «a continuación» / «entre otros» | 13 / 13 | — | metadiscurso y listas abiertas |
| «machine learning» | 11 | 0,14 | anglicismo con equivalente («aprendizaje automático») |
| oración media (prosa, sin caps. 27 y 30) | 933 oraciones | 32,0 palabras (DE 16,3) | 23 % supera 40 palabras |

### 1.3 Tiempo verbal y densidad por capítulo (medido)

Tasas por 1.000 palabras de prosa. «fut» = formas en *-rá/-rán*; «pres» = es/son/está/existe/presenta.

| Capítulo | Palabras prosa | «el/del/este proyecto» | *se* | fut | pres | 1.ª persona | Tiempo dominante |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 Identificación | 1.076 | 5,6 | 5,6 | 4,6 | 0 | 0 | presente + futuro («Se abordarán las sublíneas…») |
| 2 Resumen ejecutivo | 647 | 7,7 | 15,5 | 0 | 4,6 | 0 | presente descriptivo |
| 4 Alineación | 811 | 14,8 | 7,4 | 1,2 | 1,2 | 0 | presente («se articula», «responde», «contribuye») |
| 5 Problema | 5.011 | 0,8 | 12,8 | 0,6 | 6,0 | 0 | presente y pretérito; casi sin «el proyecto» |
| 6 Antecedentes | 3.598 | 6,1 | 11,4 | 0,8 | 1,9 | 0 | pretérito (iniciativas) + presente (pertinencia) |
| 7 Justificación | 2.240 | 11,2 | 19,2 | 8,5 | 4,5 | 0 | presente + futuro |
| 9 Marco conceptual | 5.385 | 0,4 | 13,7 | 0,4 | 11,0 | 0 | presente gnómico (definiciones) |
| 11 Población | 2.270 | 15,0 | 18,1 | 13,2 | 8,4 | 0,9 | presente (criterios) + futuro (medidas) |
| 12 Objetivos | 536 | 7,5 | 5,6 | 0 | 3,7 | 0 | infinitivo (enunciados) |
| 13 Alternativas | 1.140 | 7,0 | 14,9 | 0 | 5,3 | 0 | presente |
| 14 Metodología | 2.937 | 3,4 | 16,0 | 16,0 | 2,0 | 0 | futuro + *se* |
| 16 Sostenibilidad | 1.292 | 10,1 | 16,3 | 0 | 1,5 | 0 | presente («contribuye», «produce», «fortalece») |
| 17 Resultados | 440 | 18,2 | 11,4 | 2,3 | 9,1 | 0 | presente, oraciones cortas (media 18 palabras) |
| 18 Transferencia | 1.804 | 3,9 | 16,1 | 39,4 | 0,6 | 0 | futuro dominante |
| 19 ASC | 1.740 | 5,7 | 13,8 | 16,7 | 1,1 | 0 | futuro + presente |
| 26 Aspectos éticos | 298 | 10,1 | 13,4 | 10,1 | 0 | 0 | futuro normativo |
| 27 Idoneidad | 10.681 | 1,9 | 12,8 | 1,0 | 5,0 | 2,2 | presente y pretérito; aquí aparece la 1.ª persona |

**Regla derivada (tiempo por capítulo):** presente para diagnóstico, marco conceptual, alineación, alternativas, sostenibilidad y descripción del proyecto en el resumen; pretérito para antecedentes y evolución reciente del problema; futuro de indicativo para metodología, transferencia, ASC, medidas de población, ética y verificación del TRL; infinitivo solo en enunciados de objetivos, medios y nombres de actividades.

### 1.4 Diferencia con el flujo base de Morfeo

| Aspecto | Flujo base (investigación) | Flujo SGR (inversión pública) | Fuente |
|---|---|---|---|
| Marco del texto | propuesta de investigación: pregunta, hipótesis (§5), estado del arte (§4, ≥39 refs), novedad en IA | proyecto de inversión: problema, alternativa, cadena de valor, producto, indicador | Anexo 2 nota inicial; TdR 13.1 |
| Voz | tercera persona sobria «el proyecto plantea», «el grupo implementará»; admite el marco «la investigación», «el modelo propuesto» y argumentar la novedad técnica | tercera persona «el proyecto», impersonal *se*; la novedad se demuestra frente a alternativas del territorio, no se proclama | estilo-natural-es §4.3; rúbrica 1.2 «atributos diferenciadores frente a las alternativas ya disponibles en el territorio» |
| Autorreferencia | prohibida en §3 y §4 («esta propuesta», «el proyecto propone») | prohibida en el diagnóstico (5.1–5.4); permitida en cierres de cap. 6, en 5.2 «intervenciones realizadas diferentes a la que se proponen» y en el resto de capítulos | guía base §3; Anexo 2 §5.2 |
| Verbos de objetivo | menú IA: Desarrollar/Diseñar/Proponer; Implementar/Desplegar/Validar | espejo del árbol: Aumentar, Incrementar, Mejorar, Fortalecer, Reducir, Ampliar… | guía SGR §6; Manual MGA p. 28; Módulo 4 |

---

## 2. Patrones por capítulo del Anexo 2 (Conv 54, títulos textuales del TdR 13.1)

> Los títulos se conservan textualmente («deberá contener como mínimo los siguientes elementos, conservando textualmente sus títulos», TdR 13.1). Las subsecciones citadas son las de la plantilla Conv 54 (tal como aparecen en el borrador Conv 54 y en la referencia). Extensiones: palabras de prosa medidas en referencia.

### 1. IDENTIFICACIÓN DEL PROYECTO

- **Propósito.** Ficha: nombre, entidades y aspa, código SIGP, duración, localización (región, departamentos, municipios, centro poblado, resguardo), demandas territoriales, desafío y líneas temáticas, grupos de investigación.
- **Estructura.** Campos rotulados de la plantilla + dos tablas.
  - Demandas (referencia): `Demanda Territorial | Descripción | Reto`.
  - Grupos (plantilla): `Nombre del Grupo | Entidad a la que pertenece el grupo | Líneas de Investigación a las que se encuentra vinculado | # Investigadores vinculados al grupo y su nivel de formación | # Estudiantes que puede vincular el grupo de investigación | Contribución de las líneas al abordaje de las demandas territoriales y los alcances temáticos`.
- **Extensión.** 1.076 palabras de prosa (justificación del desafío, la línea y las sublíneas, 3–7 párrafos cortos de ~54 palabras) + 2.005 en tablas.
- **Nombre del proyecto.** Máximo 256 caracteres con espacios; estructura «Proceso + Objeto + Localización» (plantilla); en Morfeo es el objetivo general con el verbo nominalizado («Desarrollar…» → «Desarrollo de…»), regla `sgr-titulo-no-derivado`.
- **Aperturas favorecidas.**
  - «La propuesta se enmarca en el Desafío <n>, «<nombre>», porque busca contribuir a…»
  - «Se abordarán las sublíneas <x.y> <nombre> y <x.z> <nombre>, mediante…»
  - «<x.y> <nombre de la sublínea>: mediante la investigación y validación de…» (una entrada por sublínea)
  - «El proyecto atenderá una demanda territorial por cada uno de los <N> departamentos de ejecución.»
  - «La propuesta responde a problemáticas compartidas por <departamentos>, relacionadas con…»
- **Evitar.**
  - Adjetivos promocionales en el nombre («innovador», «integral», «sostenible» como adorno) y fines («…para mejorar la calidad de vida»): el nombre deriva del objetivo general, que no los admite (Manual MGA 2015, tabla 12, p. 80).
  - Una entidad con dos categorías de aspa: «Las entidades ostentarán sólo una de las categorías indicadas» (plantilla, campo Aspa).
  - Primera persona o lenguaje de portafolio institucional («nuestra universidad»).
  - Contribución del grupo redactada como trayectoria; la columna pide su «contribución … al abordaje de las demandas territoriales».
- **Fuente.** Anexo 2 Conv 54/56 cap. 1; Directriz SGR 6 de Morfeo.

### 2. RESUMEN EJECUTIVO

- **Propósito (plantilla).** «Información mínima necesaria para comunicar de manera precisa los contenidos y alcances del proyecto… debe incluir el propósito del proyecto y su descripción (desarrollo metodológico), así como los resultados esperados».
- **Estructura.** Prosa, sin tablas. Referencia: 3 párrafos (problema y emergencia → propósito; duración, territorio, alianza y desarrollo metodológico por objetivo; resultados con cifras, población objetivo y aporte).
- **Extensión.** 647 palabras (párrafos de ~216). Recomendación: 450–650 palabras, 3–4 párrafos.
- **Aperturas y expresiones favorecidas.**
  - «<Recurso o sector> es <condición> para <territorio> y se encuentra <estado negativo con cifra y fuente>.»
  - «En respuesta, el proyecto tiene como propósito <objetivo general en infinitivo, literal>.»
  - «El proyecto se desarrolla en N meses, en N municipios de N departamentos, con una alianza liderada por <entidad> que reúne a N entidades…»
  - «Su desarrollo metodológico articula los cuatro componentes de la convocatoria alrededor de N objetivos específicos. El primero <verbo del OE1 en presente> …: se identifican…, se realizan…, se evalúa…»
  - «Entre los resultados esperados están <N productos con unidad>…»
  - «La población objetivo es de N personas, que participan en…»
  - «Con ello, el proyecto aporta a <efecto directo> y, en el largo plazo, a <fin>.»
- **Evitar.**
  - Oraciones de más de 45 palabras: en la referencia la media es 49,8 y el 69 % supera 40; es la sección con peor cadencia del documento.
  - Definiciones conceptuales («Al hablar de riesgo, el proyecto adopta la definición…»): van en el cap. 9. Se observaron dos párrafos de definiciones en un borrador.
  - El marco de hipótesis («El proyecto parte de la hipótesis de que…»): el Anexo 2 no tiene hipótesis.
  - Énfasis emotivo y servil: «es necesario y urgente», «De hecho, el proyecto está concebido para…», «el proyecto busca cumplir con la premisa de la convocatoria».
  - «paquetes de trabajo (PT)» en lugar de objetivos, productos y actividades.
- **Fuente.** Anexo 2 cap. 2; estilo-natural-es patrones 15, 24 y 29.

### 3. PALABRAS CLAVE

- **Regla.** «Incluir máximo seis (6) palabras clave que describan el objeto del proyecto» (plantilla). Referencia: 6, separadas por punto y coma (13 palabras).
- **Favorecido.** Términos del objeto, la variable del problema y la línea temática, en español.
- **Evitar.** Términos genéricos («proyecto», «innovación», «CTeI»), anglicismos con equivalente, repetir el título palabra por palabra, más de seis.
- **Fuente.** Anexo 2 cap. 3.

### 4. ALINEACIÓN CON LA POLÍTICA PÚBLICA

- **Propósito.** Mostrar el anclaje en PND (estrategia transversal, transformación, pilar, catalizador, programa), planes departamentales y municipales (estrategia, programa), planes étnicos si aplican, política de CTeI y líneas de la convocatoria.
- **Estructura.** Subsecciones de la referencia: 4.1 Plan Nacional de Desarrollo; 4.2 Política nacional de CTeI y compromisos internacionales; 4.3 Plan departamental de desarrollo; 4.4 Plan municipal de desarrollo; 4.5 Planeación ambiental regional (si aplica); 4.6 Articulación con las líneas de la convocatoria. Tablas:
  - `Transformación | Pilar | Catalizador | Componente | Relación con el proyecto`
  - `Departamento | Plan de desarrollo | Estrategia del plan | Programas del plan | Relación con el proyecto`
  - `Departamento | Municipio | Plan | Estrategia del plan | Programas del plan`
- **Extensión.** 811 palabras de prosa + 855 en tablas; párrafos de ~81 palabras.
- **Aperturas favorecidas.**
  - «El proyecto se articula con los instrumentos nacionales, departamentales, municipales y regionales de…»
  - «El proyecto responde a la Convocatoria N del Sistema General de Regalías (SGR), regulada por…»
  - «Se inscribe en el desafío <n> «<nombre>» y en la línea temática <n> «<nombre>» (principal)…»
  - «<Nombre oficial de la política> [cita]. El proyecto contribuye a…»
  - «El proyecto contribuye al ODS <n> (<nombre>) como principal, …»
  - «Programa de inversión: 3906 «Fomento a vocaciones y formación, generación, uso y apropiación social del conocimiento de la ciencia, tecnología e innovación».»
- **Evitar.**
  - Enumerar pilares o programas sin la columna «Relación con el proyecto»: el par pregunta «¿La alineación con los planes nombra programa y meta de cada plan?» (`_guia_comun`, familia demandas_territoriales); guía SGR §2.
  - Pegar párrafos enteros del texto del PND (visto en un borrador): se cita el nombre oficial entre comillas latinas y se explica el aporte.
  - «se alinea perfectamente», «en total consonancia», «contribuye de manera significativa» sin meta ni indicador.
  - Repetir esta alineación en los caps. 7 y 16 (ver sección 4, R3).
- **Fuente.** Anexo 2 cap. 4; Módulo 3 («Importancia del PND en la etapa de identificación»); Módulo 4; guía SGR §2 y A19.

### 5. IDENTIFICACIÓN Y DESCRIPCIÓN DEL PROBLEMA

Extensión total: 5.011 palabras de prosa (32 párrafos de ~154 palabras). Recomendación: 2.000–3.500.

#### 5.1. Problema central
- **Regla.** Una sola oración: el tronco del árbol, literal, sin preámbulo. Fórmula: calificativo negativo + variable medible + población o territorio (+ evento breve si hay emergencia). Patrón de la referencia y de un borrador: «Insuficientes <variable> <complemento> en <territorio>».
- **Evitar.**
  - Ausencia de solución: «falta de…», «ausencia de…», «carencia de…», «no existe(n)…», «inexistencia de…», «necesidad de…», «se requiere…» («Un problema no es la ausencia de su solución, sino un estado existente negativo», Instructivo MGA 2023, glosario; Manual MGA 2015 p. 16; Módulo 3: «Jamás formular el problema central como la falta de una solución»). Regex existente `ABSENCE_RE`.
  - Abrir con infinitivo (la solución) o con un verbo cualquiera.
  - Preámbulos agramaticales como «El problema central abordará el proyecto es: …» (visto en un borrador).
  - **Precaución (juicio, no regex):** que tras el calificativo venga un sustantivo-solución («Insuficientes prototipos…», «Escasas plataformas…», «Limitados sistemas de información…»). Es la ausencia de solución disfrazada; la variable debe ser un estado de la población o del territorio (capacidad, cobertura, aprovechamiento, calidad, oportunidad). «Insuficientes capacidades…» y «Insuficientes mecanismos de CTeI…» aparecen en proyectos SGR reales y la convocatoria habla de capacidades, por lo que se aceptan, pero el revisor debe preferir la variable de estado cuando exista.

#### 5.2. Descripción del problema y la situación existente
- **Contenido (plantilla).** «Características de la zona de estudio. Análisis de cada uno de los factores que hacen parte del problema y de las relaciones que se establecen entre ellos. Evolución reciente de la situación negativa identificada. Intervenciones realizadas diferentes a la que se proponen.»
- **Estructura recomendada (referencia + guía SGR §3).** Contexto y zona → presiones y evolución reciente → evento o emergencia con cifras oficiales → un párrafo por causa directa, en el orden del árbol → intervenciones previas → cierre con los efectos.
- **Aperturas favorecidas.**
  - «<Recurso/sector> es <rol> de <región>…» (contexto, presente).
  - «Sin embargo, estas dinámicas productivas generan diferentes presiones sobre…»
  - «A las presiones derivadas de <x> se suma <y>. De acuerdo con <fuente, año>…»
  - «A esta situación se suma la emergencia derivada de <evento> ocurrido el <fecha>… Con base en <reporte oficial>, …»
  - «Esta emergencia agudiza la problemática descrita sobre…»
  - «Una de las causas directas relacionadas con el problema central es <causa directa literal>.»
  - «Otra causa directa del problema son <causa directa literal>…»
  - «<Causa directa literal> representan la tercera causa directa del problema.»
  - «Esto se debe a <causas indirectas>…» (cada indirecta como estado del territorio).
  - «Esta situación afecta directamente a <población>, que…»
  - «Frente a <problemática>, se han promovido diferentes espacios… / Como parte de las iniciativas orientadas a <x>, se destaca <iniciativa>, que…» (intervenciones previas).
- **Evitar.**
  - «falta de», «ausencia de», «carencia de», «la inexistencia de» también en la narración causal: la referencia lo usa 7 veces en este capítulo («la falta de capacidad técnica…, la falta de recursos financieros»). Reformular como estado: «baja capacidad técnica», «escasa financiación», «cobertura de monitoreo de N estaciones».
  - Hablar de la solución dentro del diagnóstico: «En este contexto, resulta necesario desarrollar soluciones…», «Con el proyecto se busca…» (presentes en la referencia). La descripción de la situación existente describe lo que pasa hoy (Manual MGA 2015 p. 17); la respuesta va en 7, 12 y 13. La guía base de Morfeo ya prohíbe la autorreferencia en §3.
  - Condicionales especulativos en cadena («lo que puede llevar a…», «podrían mejorar…»): afirmar con dato y fuente.
  - Valorativos sin criterio: «crucial», «efectivas», «adecuado», «soluciones innovadoras» (3 usos en este capítulo de la referencia).
  - Registro periodístico con nombres de personas («el profesor X llamó la atención…», «el entonces ministro…»): citar la institución y el documento con año.
  - Atribuciones vagas: «diversos estudios», «se ha evidenciado» sin cita.
  - Repetir en cada causa los calificadores del tronco (territorio, poblaciones, evento): guía SGR §3 «Causas directas sin preámbulo».

#### 5.3. Magnitud actual del problema indicadores de referencia
- **Regla (plantilla).** «registrar un indicador de línea base o de referencia (expresión cuantitativa)… registrar una fuente de verificación oficial actualizada».
- **Estructura.** Tabla `Descripción | Número de unidades | Fuente` (referencia); Morfeo: tabla `Indicador | Causa | Valor | Fuente | Año` con la línea base en negrita.
- **Fórmula de cierre favorecida.** «Por lo anterior, se define como indicador de referencia del problema: <indicador, valor, unidad, fuente, año>.»
- **Evitar.** Línea base que cuenta la solución inexistente («Cero (0) prototipos basados en CTeI…», presente en la referencia): es la ausencia de solución expresada como cifra. La magnitud mide el estado negativo (ejemplo DNP: «tasa de aprovechamiento de tan solo el 1 %», Manual MGA 2015 p. 17). Evitar también cifras sin año o con fuentes no oficiales cuando existe una oficial.

#### 5.4. Árbol de problemas
- **Estructura (plantilla).** Tabla `Efectos indirectos | Efectos directos | Problema central | Causas directas | Causas indirectas`.
- **Redacción de nodos.** Sintagma nominal con calificativo negativo inicial (referencia: «Insuficiente…», «Limitado(a)s…», «Escaso…», «Poco interés…»). Sin infinitivos, sin «falta de», sin metas.
- **Fuente del capítulo.** Anexo 2 cap. 5; Manual MGA 2015 pp. 16–19; Instructivo MGA 2023 pp. 22–23; Módulo 3; códigos `arbol-ausencia-de-solucion`, `arbol-solucion-en-problema`, `arbol-problema-sin-calificativo-negativo`, `sgr-problema-estructura`.

### 6. ANTECEDENTES

- **Propósito (plantilla).** «antecedentes identificados por la(s) entidad(es) en relación con la problemática… presentar el desarrollo previo de iniciativas a nivel internacional, nacional, departamental o municipal… así como los resultados de éstas, que ilustran la pertinencia… En lo posible relacione la información anterior con el contexto regional y departamental.»
- **Estructura.** Prosa organizada por escala con rótulos: «Internacional», «Nacional», «Departamental» (referencia). Un párrafo por iniciativa: qué fue, quién y cuándo, qué hizo, qué resultado dejó, qué aprende de ella el proyecto. Cierre de síntesis.
- **Extensión.** 3.598 palabras, 22 párrafos de ~156. Recomendación: 1.500–3.000.
- **Tiempo.** Pretérito para las iniciativas («ejecutó», «generó», «buscó»); presente para la pertinencia.
- **Aperturas favorecidas.**
  - «A nivel internacional, las investigaciones sobre <tema> han integrado…»
  - «Entre las primeras experiencias se encuentra el proyecto <nombre>, que, financiado por <fuente>, …»
  - «En una experiencia posterior, el proyecto <nombre> buscó…»
  - «En Colombia, la articulación entre <a> y <b> se encuentra en…»
  - «En el ámbito departamental, la experiencia de <x> permite vincular…»
  - «Las experiencias revisadas muestran avances en <x>. … A partir de estos antecedentes, el proyecto articula…» (cierre; aquí sí se nombra el proyecto).
- **Evitar.**
  - Lista de nombres de entidades (visto en un borrador): la capacidad de la alianza va en el cap. 27.
  - Revisión de literatura al estilo del estado del arte del flujo base: el capítulo pide iniciativas y sus resultados.
  - «pionero», «primer proyecto del país», «exitoso» sin evidencia; la novedad se puntúa «frente a las alternativas ya disponibles en el territorio» (rúbrica 1.2).
  - Primera persona en antecedentes propios («hemos desarrollado»): «El grupo <nombre> ejecutó…».
- **Fuente.** Anexo 2 cap. 6; rúbrica Conv 54, 1.2 (novedad).

### 7. JUSTIFICACIÓN

- **Propósito (plantilla).** «describir la(s) necesidad(es) particular(es) para adelantar el proyecto y las consideraciones que lo justifican… dar cuenta de la viabilidad y pertinencia del proyecto para el territorio a un corto, mediano y largo plazo».
- **Estructura.** Prosa + tabla `Factor | Elemento | Corto plazo | Mediano plazo | Largo plazo` (referencia).
- **Extensión.** 2.240 palabras, 17 párrafos de ~130 + 621 en tabla.
- **Aperturas favorecidas.**
  - «El presente proyecto … se encuentra centrado en…» (una vez).
  - «La necesidad de esta intervención se relaciona con…»
  - «La pertinencia científica y tecnológica radica en…»
  - «La ejecución conjunta en estos N departamentos se justifica, además, por…»
  - «La viabilidad se apoya en las capacidades de <grupos>, la infraestructura <x> y la experiencia <y>…»
  - Antes de la tabla: «La Tabla N presenta la viabilidad y pertinencia del proyecto a corto, mediano y largo plazo.»
- **Evitar.**
  - Volver a describir el problema (41 6-gramas compartidos con el cap. 5 en la referencia).
  - Volver a enumerar ODS y PND: «Por otra parte, este proyecto se justifica por su alineación con los ODS…» (13 menciones de ODS en el cap. 7 de la referencia frente a 6 en el cap. 4). La alineación vive en el cap. 4.
  - «es de vital importancia», «es fundamental», «urgente», «sin precedentes», «se hace necesario».
  - El esquema base de seis párrafos (OCDE, Banco Mundial, auge de la IA, ≥13 referencias Q1/Q2): no lo pide el Anexo 2.
- **Fuente.** Anexo 2 cap. 7; estilo-natural-es patrones 1 y 15.

### 8. ARTICULACIÓN DEL PROYECTO CON LAS DEMANDAS TERRITORIALES ATENDIDAS EN CADA DEPARTAMENTO DE EJECUCIÓN

Incluye 8.1. CONFIGURACIÓN REGIONAL: JUSTIFICACIÓN DE LOS DEPARTAMENTOS, MUNICIPIOS Y ACTORES, Y DE SU PERTINENCIA PARA LOS OBJETIVOS DEL PROYECTO.

- **Propósito (plantilla Conv 54).** «cómo el proyecto… responde a los retos estratégicos y demandas territoriales… (Anexo 4)… describir la forma en que la alianza comprende el o los retos… y por qué considera que su atención es importante y se atiende con la ejecución del proyecto».
- **Estructura.** Tablas. `Demanda Territorial | Descripción | Articulación y contribución del proyecto`; 8.1: `Actores departamentos, municipios y participantes de la alianza | Pertinencia frente a los objetivos, demandas territoriales y objetivos con los que se relaciona`.
- **Extensión.** Prosa mínima (15 palabras); 4.696 palabras en tablas.
- **Patrones de celda.** La demanda se cita literal entre comillas latinas, con su departamento. La contribución empieza por el objetivo o el producto: «El OE<n> aporta <producto con unidad> a <actor>, con <indicador>…», «Mediante la actividad <n.n.n>, el proyecto entrega…».
- **Evitar.**
  - Contribución general sin indicador: señal de alerta «La contribución por departamento se describe en términos generales, sin indicador» (`_guia_comun`); la rúbrica 2.1 da 3 de 7 puntos a la contribución «parcial o general».
  - El mismo texto de contribución copiado para cada departamento.
  - Duplicar la tabla de demandas del cap. 1 (323 6-gramas compartidos en la referencia).
  - «contribuirá significativamente», «impactará positivamente».
- **Fuente.** Anexo 2 Conv 54 cap. 8; TdR numeral 4; rúbrica 2.1.

### 9. MARCO CONCEPTUAL

- **Propósito (plantilla).** «Describir de manera breve los aspectos conceptuales y teóricos que enmarcan el problema… Asimismo, describa el Marco de Política Pública, Marco Normativo, según aplique.»
- **Estructura.** Subsecciones numeradas por concepto; bloque «Conceptos fundamentales» con definiciones; marco de política pública; marco normativo en tabla `Normatividad <sector> - Colombia | Descripción`.
- **Extensión.** 5.385 palabras + 1.002 en tablas (la plantilla dice «breve»). Recomendación: 1.500–3.000.
- **Tiempo y voz.** Presente gnómico; casi sin «el proyecto» (0,4 por mil).
- **Aperturas favorecidas.** «Los/Las <concepto> son…», «<Concepto>: se refiere a…», «Es un enfoque… que se emplea para…», «<Concepto> se puede definir como…», «Según <autor> (<año>), …».
- **Evitar.**
  - Aperturas cósmicas: «Los <recursos> desempeñan un papel crucial en el desarrollo…» (patrón 1 de estilo-natural-es).
  - «extremadamente importantes», «de gran relevancia».
  - Títulos en inglés cuando hay término español («Análisis de datos Machine learning (ML)» → «aprendizaje automático»).
  - Viñetas con rótulo en negrita para cada instrumento si una tabla o un párrafo lo resuelve.
  - Repetir la tabla normativa en el cap. 28 (449 6-gramas compartidos en la referencia, el mayor duplicado del documento).
- **Fuente.** Anexo 2 cap. 9.

### 10. ANÁLISIS DE PARTICIPANTES

Incluye 10.1. MATRIZ DE RESPONSABILIDADES DE LAS ENTIDADES PARTICIPANTES QUE CONFORMAN LA ALIANZA.

- **Estructura.** Tablas, prosa mínima (16 palabras en la referencia).
  - Plantilla: `Datos de la entidad | Posición | Contribución o Gestión`. Referencia: `Datos de la entidad | Posición | Interés del proyecto | Poder/ / influencia | Ubicación en la matriz de influencia | Contribución o Gestión`.
  - 10.1 (plantilla): `Nombre de la Entidad | Tipo de Aliado | Posición | Rol en la Alianza | Responsabilidades /Obligaciones | Aportes`; referencia: `Aportes (dinero / especie)`.
- **Vocabulario fijo.** Posiciones: Beneficiario, Cooperante, Oponente, Perjudicado. Cuadrantes de la matriz poder-interés: «Gestionar atentamente», «Mantener satisfecho», «Mantener informado», «Monitorear» (Módulo 3).
- **Patrones de celda.** «Actor: <nivel> / Entidad: <nombre> / Posición: <posición> / Intereses o Expectativas: <sintagma nominal>»; contribuciones como viñetas en infinitivo: «- Formular y ejecutar el proyecto.», «- Supervisar y realizar el seguimiento técnico y financiero del proyecto.»
- **Evitar.**
  - Una entidad que es a la vez cooperante y beneficiaria («Por restricciones de la Metodología General Ajustada, una misma entidad no podrá ostentar al mismo tiempo la calidad de Proponente /Aliado (Cooperante) y Beneficiario», plantilla).
  - Omitir oponentes o perjudicados sin decir por qué; su estrategia de manejo se costea (guía SGR A20, §13).
  - Responsabilidades genéricas («apoyar», «acompañar») que no correspondan a actividades del cronograma.
- **Fuente.** Anexo 2 cap. 10; Instructivo MGA 2023 p. 32; Módulo 3.

### 11. POBLACIÓN

Subsecciones: 11.1. Población afectada; 11.2. Población objetivo; 11.3. Características demográficas de la población objetivo.

- **Propósito (plantilla).** Definir la población afectada y la objetivo, «presentar como se determinó esta población (criterios de selección claramente definidos) y soportarla con una fuente que permita su validación (fuentes estadísticas oficiales…)»; caracterizar el enfoque diferencial.
- **Estructura.** Prosa + tablas (`Región | Departamento | Municipio` con cifras DANE; enfoque diferencial: `GRUPO POBLACIONAL / (ACTORES DIFERENCIALES) | ACTIVIDAD EN LA CADENA DE VALOR | VALOR DE LA ACTIVIDAD | DESCRIPCIÓN DE LA PARTICIPACIÓN DE LOS ACTORES DIFERENCIALES PARA EL CAMBIO`).
- **Extensión.** 2.270 palabras + 1.293 en tablas; párrafos de ~72.
- **Aperturas favorecidas.**
  - «La población afectada por esta problemática incluye a…»
  - «Por esta razón, se seleccionó como población afectada a…»
  - «La selección de la población objetivo considera <criterios>…»
  - «Para caracterizar demográficamente a <grupo> según <variable>, se recurrió a <fuente oficial, año>.»
  - «El proyecto vinculará / priorizará la vinculación de…» (medidas, en futuro).
- **Evitar.**
  - Primera persona («Según los valores de la tabla anterior podemos decir que…», desliz real de la referencia) → «Según la Tabla N, el 9 % de la población afectada…».
  - Promesas vacías («Se garantizará que…», «El proyecto garantiza…»): cada medida diferencial lleva actividad, indicador, meta y evidencia (rúbrica 4.4; `_guia_comun` enfoque_diferencial).
  - Cuantificadores vagos donde se exige porcentaje («una parte significativa del talento humano»).
  - Población expresada como entidades o hogares sin personas: «Siempre son personas, con cifra mayor que cero, fuente y localización» (guía SGR A21).
  - «beneficiará a toda la región».
- **Fuente.** Anexo 2 cap. 11; Instructivo MGA 2023 pp. 36–38; Módulo 3.

### 12. OBJETIVOS

Subsecciones: 12.1. Objetivo General; 12.2. Objetivos específicos; 12.3. Árbol de objetivos; 12.4. DESCRIPCIÓN DE PERFILES, ACTIVIDADES Y PLAN DE TRABAJO DEL TALENTO HUMANO A VINCULAR.

- **Plantilla.** «Los objetivos son una proyección de la situación deseable, se construyen a partir del árbol de problemas, formulando todas las condiciones negativas del mismo, en forma de condiciones positivas…». OG: «se inicia con un verbo en modo infinitivo, es medible, alcanzable y conlleva a una meta»; su indicador «debe corresponder a un indicador(es) de impacto o de resultado». OE: «No debe confundirse con las actividades… ni con el alcance de los productos».
- **Estructura.** OG en una oración + tabla de indicador (`Indicador Objetivo | Medido a través de | Línea base | Meta | Tipo de Fuente | Fuente de Verificación`, referencia). OE con el rótulo literal «Objetivo específico 1 (OE1): …». Árbol: `Fines indirectos | Fines directos | Objetivo general | Objetivos específicos | Medios`. 12.4: `Perfil | Entidad que lo vincula | Formación y experiencia | Actividades y meses | Producto final`.
- **Extensión.** 536 palabras + 1.041 en tablas.
- **Verbos favorecidos (espejo del árbol).** Aumentar, Incrementar, Mejorar, Fortalecer, Reducir, Disminuir, Ampliar; Implementar y Desarrollar cuando la causa lo pide (referencia: Desarrollar / Incrementar / Implementar). Módulo 4: «se formula como un verbo en infinitivo (ej. mejorar, fortalecer, aumentar)».
- **Evitar (Manual MGA 2015, tabla 12, p. 80; guía SGR §6).**
  - El medio: «mediante…», «a través de…», «por intermedio de…» (regex `MEANS_RE`).
  - Los fines: «…para mejorar la calidad de vida» (regex `ENDS_RE`).
  - El producto: «Construcción de…»; la acción parcial: «Adquirir equipos…».
  - Metas dentro del enunciado (regex `TARGET_RE`).
  - Objetivos demasiado amplios («Ampliar la cobertura en educación»).
  - Verbos vagos sin variable («Plasmar una visión de futuro…», «Generar conocimiento…» cuando la causa no es de conocimiento; vistos en un borrador).
  - El menú de verbos rectores de IA del flujo base.
  - Indicador del OG que es un producto («Sistema de información… / Meta: 1»): debe medir el cambio en la población (criterios CREMA, Instructivo MGA 2023 pp. 40–41).
- **Fuente.** Anexo 2 cap. 12; Manual MGA 2015 pp. 27–29 y 80; Instructivo MGA 2023 pp. 39–42; Módulos 3 y 4; códigos `sgr-objetivo-general-distinto`, `objetivo-general-con-medio`, `objetivo-general-con-fin`, `objetivo-general-con-meta`.

### 13. ANÁLISIS DE LAS ALTERNATIVAS

Subsección: 13.1. Análisis técnico de la alternativa seleccionada.

- **Plantilla.** «Incluya las alternativas identificadas (al menos 2)…»; 13.1: «características técnicas, financieras o de otra índole… sus ventajas… las razones por las cuales se descarta… tener presente que la disponibilidad de recursos financieros no es una razón suficiente para justificar el descarte».
- **Estructura.** Tabla `Nombre de la alternativa | Descripción de la evaluación: Rentabilidad/Costo-Eficiencia/ Costo Mínimo. | Breve justificación de la Alternativa seleccionada`; la referencia añade `Factor | Descripción | Alt. 1 | Alt. 2 | Alt. 3` con puntuación 0–10. Prosa en párrafos rotulados: «Características técnicas.», «Objetivos y productos.», «Metodología y duración.», «Resultados e impacto.», «Características financieras.».
- **Extensión.** 1.140 palabras + 752 en tablas.
- **Aperturas favorecidas.** «La alternativa 1 parte de <activo o capacidad existente>…», «De las tres alternativas presentadas en la Tabla N, en mayor o menor medida todas están orientadas al…», «La alternativa seleccionada contempla…», «La alternativa <n> se descarta porque <razón técnica>».
- **Evitar.**
  - Descartar solo por costo.
  - Alternativa de paja sin evaluación (visto en un borrador: «TRADICIONAL… (Incluya la justificación…)» sin desarrollo).
  - «Rentabilidad: Sí» sin explicar el tipo de evaluación (CTeI: costo-eficiencia o multicriterio, guía SGR A22).
  - «la única alternativa viable», y re-resumir todo el proyecto (124 6-gramas compartidos con el resumen ejecutivo en la referencia).
- **Fuente.** Anexo 2 cap. 13; Módulo 3 p. 50; Instructivo MGA 2023 p. 44.

### 14. METODOLOGÍA PARA DESARROLLAR LA ALTERNATIVA SELECCIONADA

Subsecciones Conv 54: 14.1. Estado de desarrollo y madurez tecnológica de la solución; 14.2. PLAN DE VERIFICACIÓN DEL TRL DE SALIDA, CONFORME CON LA TIPOLOGÍA DECLARADA Y, CUANDO APLIQUE, TRATAMIENTO Y PROTECCIÓN DE DATOS PERSONALES.

- **Plantilla.** «definición lógica y sistemática de las actividades conducentes al cumplimiento de los objetivos…»; por actividad: «Responsable:», «Tareas:», «Resultados de la actividad:», «Medio de verificación:»; incluir «Administración y apoyo a la supervisión»; actividades idénticas a cadena de valor y cronograma.
- **Estructura (referencia).** Por objetivo, el rótulo «Objetivo Específico <n>: <texto literal>» y tablas:
  - `No. | Actividad | Responsable | Tareas | Resultados | Medio de verificación`
  - `No. | Actividad | Mes inicio | Mes fin | ¿En qué consiste?`
  - TRL: `Tipología declarada | TRL actual (Entrada) | Justificación | TRL esperado al finalizar el proyecto | Hito y evidencia de cierre`; ruta: `Etapa y periodo | Actividades e hito verificable | Responsables propuestos`; verificación: `Aspecto por verificar | Criterio de aceptación | Evidencias de cumplimiento`.
- **Extensión.** 2.937 palabras de prosa + 3.422 en tablas; párrafos de ~71; oración media 28.
- **Tiempo y voz.** Futuro (16 por mil) e impersonal *se* (16 por mil); el actor queda en la columna «Responsable» o en el sujeto («<Entidad> coordinará…»).
- **Nombres de actividad.** «Actividad <n>: <infinitivo> + objeto + localización». Verbos de la referencia: Identificar, Definir, Ejecutar, Realizar, Cuantificar, Evaluar. Ejemplos de forma (Módulo 4): «Diseñar material pedagógico», «Ejecutar jornadas de capacitación».
- **Aperturas favorecidas.**
  - «Esta actividad consiste en…» / «Esta actividad tiene como objetivo / finalidad…» (celda «¿En qué consiste?»).
  - «Las primeras campañas de <x> aportarán la información necesaria para…»
  - «La verificación del TRL N se sustentará en…»
  - «La demostración se realizará en un entorno pertinente, mediante…»
  - «Se efectuarán corridas independientes y controles sin tratamiento para…»
  - «Los criterios de aceptación se establecerán a partir de…»
  - «<Entidad> coordinará la ejecución y documentación de…»
  - «Se conformará un expediente documental técnico que reúna…»
  - «El punto de partida tecnológico corresponde a <activo>, …» (14.1).
- **Evitar.**
  - Verbos que la MGA prohíbe para actividades: apropiar, asegurar, colaborar, consolidar, desarrollar, fomentar, fortalecer, garantizar, implementar, impulsar, mejorar, movilizar, proponer, promover (Manual MGA 2015 p. 81; guía SGR A23). Vistos en un borrador: «Implementar sistema de información», «Socializar visión».
  - Tareas o insumos como actividades: «Comprar resmas de papel, adquirir computadores y proyectores, viáticos, contratar personal» (Manual MGA 2015 p. 81); «Contratar a un arquitecto…» es tarea (Módulo 1).
  - «paquetes de trabajo (PT)» o «work packages»: el Anexo 2 organiza por objetivo, producto y actividad. («paquete tecnológico» sí es término oficial de transferencia.)
  - TRL declarado sin evidencia: «No será suficiente la sola declaración del nivel de madurez» (plantilla Conv 56, 13.2); rúbrica 1.3.
  - «se determinará durante la ejecución» sin criterio de decisión.
  - «de manera integral», «robusto» como relleno.
- **Fuente.** Anexo 2 cap. 14; TdR numeral 6 y criterios 1.1–1.3; Manual MGA 2015 p. 81; Módulos 1 y 4.

### 15. CADENA DE VALOR

- **Plantilla.** «Es una relación secuencial entre los objetivos específicos y los productos necesarios para materializarlos a través de un conjunto de actividades.»
- **Estructura.** Solo tabla: `Objetivo específico | Producto | Medido a través del cual se verifica | Cantidad / Meta | Actividades asociadas al producto`. Celda de producto (referencia): «Código: 3906xxx / <nombre del catálogo> / $ <valor>»; celda de actividad: «n.n.n Actividad n: <nombre> / Ruta crítica».
- **Reglas.** Productos del catálogo DNP, sector 39, programa 3906; dos o más actividades por producto; ruta crítica marcada; actividades con el mismo nombre y costo que en caps. 14 y 22 y en el Anexo 3; administración incluida.
- **Evitar.** «elaborado», «implementado», «entregado» dentro del nombre del producto (Manual MGA 2015 p. 81; guía SGR §15), salvo que formen parte del nombre oficial del catálogo (p. ej. «Infraestructura para la I+D+i dotada»); productos que son población, actividad o insumo (Instructivo MGA 2023 p. 64); un producto con una sola actividad; renombrar actividades entre capítulos (la referencia advierte de inconsistencias al imprimir la MGA).
- **Fuente.** Anexo 2 cap. 15; Instructivo MGA 2023; Módulo 4 (cadena de valor en 6 pasos).

### 16. SOSTENIBILIDAD SOCIAL Y AMBIENTAL DEL PROYECTO

- **Plantilla.** «Describa la contribución del proyecto al logro de los objetivos de desarrollo sostenible, su alineación con las bases del nuevo Plan Nacional de Desarrollo y con estrategias para mejorar la capacidad de generación de conocimiento… De igual forma, describa las estrategias de sostenibilidad del proyecto sus actividades, funciones, apuestas, compromisos y articulación de actores».
- **Estructura.** Prosa + tablas `ODS | Contribución del proyecto | Productos y resultados que la respaldan` y `Actores | Funciones en el proyecto | Compromiso con la sostenibilidad`. Párrafos rotulados de una o dos oraciones («Capacidad instalada y talento humano: …», «Mecanismos de continuidad: …», «Administración de los recursos: …», «Gestión de riesgos ambientales: …»).
- **Extensión.** 1.292 palabras + 545 en tablas; párrafos de ~49.
- **Tiempo.** Presente (0 futuros en la referencia).
- **Aperturas favorecidas.** «El proyecto contribuye de manera directa a los ODS <n>…», «El proyecto produce <información/metodologías> replicables…», «El proyecto fortalece N grupos de investigación…», «La sostenibilidad se plantea desde la formulación y se apoya en…», «La Tabla N sintetiza las funciones y los compromisos de cada grupo de actores…».
- **Evitar.**
  - Copiar la alineación del cap. 4 (76 6-gramas compartidos en la referencia): aquí va la contribución con su respaldo en productos.
  - «garantiza la sostenibilidad» sin responsable ni fuente de recursos (rúbrica 4.2).
  - Afirmaciones absolutas («no genera impactos negativos sobre…») sin análisis.
  - ODS sin número ni meta.
- **Fuente.** Anexo 2 cap. 16; rúbrica 4.2.

### 17. RESULTADOS E IMPACTOS PARA LA REGIÓN Y LOS DEPARTAMENTOS OBJETO DEL PROYECTO

Subsección: 17.1. USO Y OPERACIÓN POSTERIOR DE LOS RESULTADOS.

- **Plantilla.** «resultados medibles y cuantificables…»; «el impacto… a corto, mediano y largo plazo en la región y en cada uno de los departamentos»; «una reflexión responsable sobre los efectos positivos o negativos, sobre el medio ambiente y la salud humana». 17.1: «entidad responsable de la operación y el mantenimiento… y la fuente de recursos»; «compromiso de adopción o uso asumido por el actor usuario».
- **Estructura (referencia).** Tablas: `RESULTADO | META | IMPACTO`; `Tipo de Impacto | Impacto Esperado | Plazo (años) después de finalizado el proyecto: corto (1-4), mediano (5-9), largo (10 o más) | Indicador Verificable`; `EFECTOS EN EL MEDIO NATURAL Y LA SALUD HUMANA`; 17.1: `Entidad responsable | Bienes adquiridos con SGR | Valor SGR | Operación y mantenimiento posterior`, `Resultado | Entidad responsable | Operación y mantenimiento posterior | Fuente de recursos`, `Actor | Resultado que adoptará | Condiciones de adopción`.
- **Extensión.** 440 palabras de prosa (oración media 18) + 2.967 en tablas.
- **Aperturas favorecidas.** «El impacto de la implementación del proyecto a corto, mediano y largo plazo en la región…», «A continuación, se presenta una reflexión responsable sobre los efectos positivos o negativos…», «El proyecto no destina recursos SGR a la operación posterior de los bienes.», «Cada bien queda a cargo de <entidad>, que…».
- **Evitar.** Impactos sin indicador ni plazo; productos presentados como impactos; «transformará la región», «beneficiará a miles de personas»; omitir los efectos negativos; financiar operación permanente con SGR («nunca gastos permanentes de funcionamiento», Módulo 1).
- **Fuente.** Anexo 2 cap. 17; rúbrica 4.2; Módulo 1.

### 18. COMPONENTE TRANSVERSAL DE TRANSFERENCIA, ADOPCIÓN Y VALORACIÓN TECNOLÓGICA DEL CONOCIMIENTO

Subsecciones: 18.1. PLAN DE TRANSFERENCIA, ADOPCIÓN Y VALORACIÓN TECNOLÓGICA DEL CONOCIMIENTO; 18.2. RESULTADOS, USUARIOS Y OPORTUNIDADES DE TRANSFERENCIA; 18.3. ESTRATEGIA O RUTA DE TRANSFERENCIA, ADOPCIÓN Y VALORACIÓN TECNOLÓGICA; 18.4. ACTIVIDADES, PRODUCTOS, INDICADORES Y PRESUPUESTO; 18.5. CONTINUIDAD DEL PROCESO.

- **Plantilla.** Alcance: «el proceso mediante el cual los usuarios, empresas, comunidades e investigadores receptores adoptan, aplican y sostienen el uso de la tecnología… No se limita a la divulgación de resultados ni a la producción de publicaciones: se verifica mediante evidencia de uso, adopción y valor generado». Mínimo 1 % del valor solicitado al SGR.
- **Tablas (encabezados textuales de la plantilla).**
  - 18.2: `Resultado / conocimiento / tecnología | Potencial de uso o aplicación | Usuario, beneficiario o receptor potencial | Oportunidad de aprovechamiento / transferencia | Activo de propiedad intelectual (si aplica)`
  - 18.3: filas `Ruta o estrategia propuesta` y `Principales barreras o retos`
  - 18.4: `Actividad | Resultado asociado | Producto / evidencia | Indicador | Responsable | Periodo | Presupuesto`
- **Extensión.** 1.804 palabras + 3.695 en tablas; párrafos de ~60; futuro dominante (39 por mil).
- **Aperturas favorecidas.**
  - «El componente transversal de transferencia establecerá las condiciones para que los conocimientos, tecnologías y metodologías generados por el proyecto puedan ser utilizados por <usuarios>.»
  - «Su finalidad es vincular los resultados científicos y tecnológicos con necesidades concretas de…»
  - «El componente partirá de los resultados, usuarios y oportunidades identificados en el numeral 18.2…»
  - «El alcance será proporcional al estado de desarrollo de cada solución.»
  - «Se priorizarán los resultados que respondan a una necesidad identificada, cuenten con un usuario potencial y…»
  - «Cada resultado priorizado contará con una ficha de transferencia que identifique…»
  - «Se destinará como mínimo el uno por ciento (1 %) del valor solicitado al SGR a…»
  - «Una vez finalizado el proyecto, se dará continuidad al proceso de transferencia mediante…»
- **Evitar.** Equiparar transferencia con divulgación, talleres o artículos («no constituirán por sí solas evidencia de transferencia», plantilla); receptores genéricos («la comunidad en general»); prometer comercialización con TRL bajo; anglicismos no oficiales («partners», «stakeholders», «pipeline»). «spin-off», «start-up», «know-how» y «software» son términos de la propia plantilla y se admiten.
- **Fuente.** Anexo 2 cap. 18; TdR numeral 9; rúbrica 2.3.

### 19. COMPONENTE TRANSVERSAL DE APROPIACIÓN SOCIAL DEL CONOCIMIENTO (ASC)

Subsección: 19.1 ESTRATEGIA DE APROPIACIÓN SOCIAL DEL CONOCIMIENTO.

- **Plantilla (mínimos).** «Análisis y reconocimiento del contexto; Identificación y caracterización de actores; Identificación de saberes, conocimientos y capacidades; Mecanismos de participación; Enfoque de colaboración y co-creación; Articulación con el ciclo de ejecución del proyecto; Sistematización». TdR 6.1: «demostrar quiénes participan, cómo participan, en qué momentos tienen incidencia, qué aportan, qué decisiones construyen o validan conjuntamente y qué resultados se derivan».
- **Estructura (referencia).** Prosa por elemento + tablas `Grupo y actores | Relación con la problemática | Saberes y capacidades | Rol y momento de participación | Incidencia`; `Fase | Meses | Qué se hace con los actores | Momento del ciclo | Actividades`; `Producto | Descripción`.
- **Extensión.** 1.740 palabras + 880 en tablas; párrafos de ~48.
- **Aperturas favorecidas.**
  - «La estrategia de Apropiación Social del Conocimiento (ASC) del proyecto se concibe como un proceso transversal de participación, diálogo de saberes, colaboración y co-creación entre…»
  - «La estrategia se desarrollará mediante el reconocimiento de los contextos territoriales, …»
  - «Se busca que los actores sean participantes activos en la identificación de problemáticas, la definición de alternativas, la validación de resultados…»
  - «El reconocimiento del contexto parte de comprender que…»
  - «Los actores locales contribuirán a identificar y contextualizar…»
- **Léxico favorecido (TdR 6.1).** participación, colaboración, diálogo de saberes, co-creación, incidencia, validación conjunta, mesas de trabajo, talleres participativos, grupos focales, laboratorios de co-creación, comunidades de práctica, seguimiento participativo, sistematización.
- **Evitar.** Como núcleo de la estrategia: «socializar los resultados», «capacitar a la comunidad», «divulgar», «sensibilizar», «llevar el conocimiento a las comunidades» (comunicación unidireccional; TdR: «no se puede plantear sólo como actividades de divulgación o socialización»; rúbrica 2.4); «empoderar» sin mecanismo; ASC concentrada al final del cronograma.
- **Fuente.** Anexo 2 cap. 19; TdR 6.1 A–E; rúbrica 2.4; Anexo 10 (citado por la plantilla, no leído).

### 20. VINCULACIÓN DE TALENTO HUMANO

- **Estructura.** Tabla de plantilla `CARGO / ESPECIFICO | JUSTIFICACION | CANTIDAD` con filas «Jóvenes Investigadores e Innovadores | | 6 (Mínimo)», «Estudiantes de Maestría | | 2 (Mínimo)», «Doctor en Estancia posdoctoral | | 1 (Mínimo)»; referencia añade `Categoría | Cantidad | Entidad que vincula | Duración | Valor mensual (Tabla 9, numeral 15.6) | Producto final`.
- **Extensión.** 467 palabras + 507 en tablas.
- **Aperturas favorecidas.** «El equipo de formación del proyecto integra la cadena de formación del numeral 10 de los términos de referencia…», «Todos se vinculan como sujetos activos de la investigación, con actividades, meses y productos definidos en el numeral 12.4…».
- **Evitar.** Duplicar 12.4 (161 6-gramas compartidos); renombrar las categorías oficiales («jóvenes talentos», «semilleristas»). «innovador» en «Jóvenes Investigadores e Innovadores» es nombre oficial y queda exento de la regla de adjetivos promocionales.
- **Fuente.** Anexo 2 Conv 54 cap. 20; TdR numeral 10.

### 21. PRODUCTOS ESPERADOS

Subsección Conv 54: 21.1. MEDIDAS DIFERENCIALES.

- **Estructura.** Tabla `Programa | Producto | Medido a través de | Indicador de producto | Unidad de medida` (plantilla; la referencia añade `Descripción`). Nombres y códigos del catálogo (p. ej. «3906012 Documentos de investigación», indicador «Documentos de investigación elaborados»). En el indicador el participio es oficial; en el nombre del producto no se agrega.
- **21.1.** Barrera → medida → actividad → indicador → meta → evidencia; si no hay barreras, justificar la conclusión (rúbrica 4.4).
- **Evitar.** Productos repetidos o de más de un programa («Se debe seleccionar solamente un programa… y no se puede repetir productos por restricciones propias de la MGA», plantilla); nombres inventados; medidas diferenciales sin indicador.
- **Fuente.** Anexo 2 cap. 21; TdR 6.2; Instructivo MGA 2023 p. 108.

### 22. CRONOGRAMA

- **Estructura.** Tabla `Objetivo específico | Producto | Actividad | Mes` con columnas 1…n; prosa solo para una frase de entrada.
- **Reglas.** Actividades idénticas a caps. 14 y 15; meses, no trimestres; etapas (preinversión, inversión, operación) y ruta crítica (guía SGR §14).
- **Evitar.** Capacitaciones antes de que exista el equipo o la plataforma; primeros resultados útiles solo al final (`_guia_comun`, familia oportunidad).

### 23. ANÁLISIS DE RIESGOS

- **Estructura.** Tabla `Tipo de riesgo | Descripción del riesgo | Probabilidad | Impacto | Medidas de mitigación` (plantilla); la referencia añade `Efectos`. Escalas de plantilla: «Raro/ improbable / probable» y «Mayor / moderado / menor»; MGA: 1–5. Al menos un riesgo por nivel (propósito, productos, actividades de ruta crítica).
- **Redacción.** Descripción nominal («Retrasos en la contratación de personal…», «Defectos en los equipos o software adquiridos»); medida en infinitivo, con responsable y costo.
- **Evitar.** Medidas genéricas («hacer seguimiento», «mantener una actitud preventiva más que reactiva», «ser muy rigurosos en el proceso de selección», vistas en un borrador); riesgos sin valoración; omitir el riesgo de desastres y climático (Instructivo MGA 2023).
- **Fuente.** Anexo 2 cap. 23; Módulo 4 pp. 38–40; rúbrica 1.5.

### 24. INDICADORES DE GESTIÓN

- **Estructura.** Tabla `Indicador | Medida / meta | Fecha de entrega de acuerdo a cronograma` (plantilla); referencia: `Indicador | Medida/Meta | Código | Fórmula | Tipo de fuente | Fecha de entrega de acuerdo a cronograma`. Fila base: «Informes de supervisión del proyecto | Número / <n> | Periodicidad trimestral».
- **Regla.** «Deben presentarse informes de gestión trimestrales, es decir al menos cuatro informes por cada periodo estimado en la MGA» (plantilla Conv 56).

### 25. INDICADORES DE PRODUCTO

- **Estado.** Sin texto guía en las plantillas y vacío en la referencia (0 palabras). Recomendación: tabla de indicadores del catálogo coherente con el cap. 21 (indicador, unidad, meta, fuente de verificación), sin prosa.

### 26. ASPECTOS ÉTICOS

- **Plantilla.** «Incluya aspectos éticos y bioéticos relevantes del proyecto en caso de aplicar.»
- **Extensión.** 298 palabras (4 párrafos).
- **Aperturas favorecidas.** «La investigación tendrá en cuenta los principios éticos establecidos en <norma>…», «Para este proyecto, se tendrán las siguientes consideraciones:», «El tratamiento de datos personales se regirá por la Ley 1581 de 2012…».
- **Evitar.** Fórmulas genéricas sin relación con las actividades («evitando malas prácticas como el plagio y el fraude»); «no aplica» sin justificar; dar por obtenido un aval que no existe.

### 27. IDONEIDAD Y TRAYECTORIA DE LA ENTIDAD PROPONENTE Y DEMÁS PARTICIPANTES

- **Plantilla.** «Describa los aportes de los integrantes de la alianza… financieros, técnicos /tecnológicos y de talento humano de alto nivel… total coherencia con la información suministrada en la Carta aval… y en el presupuesto».
- **Extensión.** 10.681 palabras, el capítulo más largo de la referencia (129 párrafos).
- **Estructura recomendada por entidad.** Nombre y aspa → aporte al proyecto (rol, actividades, contrapartida) → trayectoria pertinente (proyectos SGR con BPIN, listados de elegibles) → capacidades (grupos con categoría, infraestructura).
- **Aperturas favorecidas.** «<Entidad> aporta al proyecto <aporte> en las actividades <n.n.n>…», «El grupo <nombre>, categoría <A1> en la convocatoria <n>, …», «Desde <año>, <entidad> ha ejecutado N proyectos financiados por el SGR, entre ellos…».
- **Evitar.** Texto institucional pegado en primera persona (aquí se concentran *nuestro* ×7 y *hemos* ×2 de la referencia): reescribir en tercera persona; lenguaje de folleto («nuestro compromiso», «líder», «referente nacional», «puede ser una solución integral»); historias institucionales sin relación con las actividades; el mismo proyecto acreditado por dos integrantes (rúbrica 3.1).
- **Fuente.** Anexo 2 cap. 27; rúbricas 3.1–3.4.

### 28. ANÁLISIS DE LICENCIAS Y PERMISOS

- **Plantilla.** «Enuncie las licencias, estudios, permisos y demás requerimientos que se consideren necesarios previo o durante la ejecución del proyecto…» (lista i–vii: licencias ambientales, acceso a recursos genéticos, recolección de especímenes, colecciones biológicas, consentimiento informado, consulta previa…).
- **Extensión.** 232 palabras + tabla normativa (duplicada del cap. 9).
- **Aperturas favorecidas.** «La entidad proponente y las demás entidades aliadas se comprometen a que, durante la ejecución del proyecto, se cumpla con…», «Por la naturaleza del objetivo general y los objetivos específicos, el proyecto no requiere <licencia>; sin embargo, si durante la ejecución…».
- **Recomendación.** Tabla `Licencia o permiso | Norma | ¿Aplica? | Justificación | Responsable | Momento del trámite`.
- **Evitar.** Copiar la tabla normativa del cap. 9; omitir la verificación de consulta previa en territorios con comunidades étnicas (guía SGR §17).

### 29. RESUMEN DE FUENTES DE FINANCIACIÓN

- **Estructura.** Tabla `Entidad | Fuente de recursos | Valor` + tres líneas literales: «Valor total de recursos solicitados a la Asignación de CTeI/ Asignación de CTeI Ambiental del SGR – Sistema General de Regalías:», «Valor total contrapartida (en efectivo y en especie):», «Valor total del proyecto:», cada una «en letras y números». Sin prosa adicional.
- **Regla.** Coherencia con el Anexo 3 y la carta unificada (plantilla, nota).

### 30. BIBLIOGRAFÍA

- **Regla.** «Se debe hacer referencia únicamente a aquellas fuentes empleadas… No se incluirán referencias que no se citen» (plantilla). El TdR no fija formato (la referencia usa numeración [n]; un borrador pidió APA). Fuera del alcance del revisor de estilo.

### 31. ANEXOS

- **Título textual de la plantilla:** «ANEXOS REQUISITOS SECTORIALES QUE LE SEAN APLICABLES.» Lista, sin prosa.

---

## 3. Léxico consolidado

Columna **Regex**: `sí` = verificable de forma determinista (patrón propuesto); `parcial` = regex como alerta y juicio del revisor; `no` = solo juicio. Ámbito por capítulo del Anexo 2. Todos los patrones se aplican sobre prosa y celdas de tabla de texto, excluyendo citas literales entre comillas («…», "…") y nombres propios de planes, programas y entidades.

### 3.1 Prohibidas o desaconsejadas

| # | Expresión | Ámbito | Razón | Fuente | Regex |
|---|---|---|---|---|---|
| L1 | Primera persona: *nosotros(as), nuestro(a)(s), hemos, proponemos, buscamos, esperamos, pretendemos, consideramos, creemos, podemos (decir)*, futuro 1.ª plural | global | voz de tercera persona sobre el proyecto; solo aparece en la referencia como texto pegado o desliz | práctica de la referencia; estilo-natural-es §4.3 | sí: `\b(nosotr[oa]s|nuestr[oa]s?|hemos|proponemos|buscamos|esperamos|pretendemos|consideramos|creemos|podemos)\b|\b\w+(aremos|eremos|iremos)\b` (excluir texto entre comillas: «<plan cuyo nombre contiene «Podemos»>») |
| L2 | *se pretende, pretende, intentar(á), tratará de, quizá(s), tal vez, ojalá* | global, sobre todo 12, 14, 17, 18 | intención en vez de compromiso verificable | Anexo 2 (actividades con medio de verificación) | sí: `\b(se\s+)?pretende(n)?\b|\bintentar[áa]n?\b|\btratar[áa]n?\s+de\b|\bquiz[áa]s?\b|\btal\s+vez\b|\bojal[áa]\b` |
| L3 | *se espera que* aplicado a productos o actividades | 14, 15, 21 | los productos son compromisos; «se espera» solo para impactos de largo plazo | Manual MGA 2015 (producto = bien o servicio entregado) | parcial |
| L4 | Ausencia de solución: *falta de, ausencia de, carencia de, inexistencia de, no existe(n), no hay, se requiere, necesidad de* | 5.1, 5.2, 5.3, 5.4 (error en nodos; alerta en prosa) | «Un problema no es la ausencia de su solución» | Instructivo MGA 2023; Manual MGA 2015 p. 16; Módulo 3 | sí: `ABSENCE_RE` de `check_run.py` |
| L5 | Línea base como conteo de la solución: *cero (0) <prototipos/plataformas/sistemas>* | 5.3, 12.1 | ausencia de solución disfrazada de magnitud | Manual MGA 2015 p. 17 | parcial: `\b(cero|0)\s*(\(0\)\s*)?(prototipos?|plataformas?|sistemas?|herramientas?|modelos?|mecanismos?)\b` |
| L6 | Sustantivo-solución tras el calificativo del tronco (*insuficientes prototipos/plataformas/sistemas/herramientas/laboratorios*) | 5.1, 5.4 | la variable debe ser un estado de la población | Manual MGA 2015 p. 16 («restringiendo la solución») | parcial: `^\w+\s+(prototipos?|plataformas?|sistemas?|herramientas?|software|laboratorios?|centros?|equipos?)\b` sobre el tronco |
| L7 | Infinitivo al inicio de nodos del árbol de problemas | 5.4 | el infinitivo es la solución | Instructivo MGA 2023 | sí: `starts_with_infinitive` |
| L8 | Solución dentro del diagnóstico: *con el proyecto se busca, el proyecto propone, resulta necesario desarrollar, se propone* | 5.1–5.3 | la descripción de la situación existente describe el presente | Manual MGA 2015 p. 17; guía base §3 | sí (alerta): `\b(con\s+el\s+proyecto|el\s+proyecto\s+(busca|propone|pretende)|la\s+propuesta|resulta\s+necesario\s+desarrollar|se\s+propone)\b` |
| L9 | Medio en el objetivo general: *mediante, a través de, por medio de, por intermedio de* | 12.1 | incluye la alternativa | Manual MGA 2015 tabla 12 | sí: `MEANS_RE` |
| L10 | Fin en el objetivo general: *para mejorar…, con el fin de, con el propósito de* | 12.1 | incluye el efecto | Manual MGA 2015 tabla 12 | sí: `ENDS_RE` |
| L11 | Meta en el objetivo: porcentajes o cifras | 12.1, 12.2 | «Incluir la(s) meta(s) del proyecto dentro de su objetivo general» es error | Manual MGA 2015 tabla 12 | sí: `TARGET_RE` |
| L12 | OG como producto o acción parcial: *construcción de, adquirir, dotar* | 12.1 | error frecuente | Manual MGA 2015 tabla 12 | parcial: `^(construcci[óo]n|adquisici[óo]n|adquirir|dotar|comprar)\b` |
| L13 | Verbos MGA prohibidos al inicio del nombre de una actividad: *apropiar, asegurar, colaborar, consolidar, desarrollar, fomentar, fortalecer, garantizar, implementar, impulsar, mejorar, movilizar, proponer, promover* | 14, 15, 22, 18.4 (nombres de actividad) | «verbos demasiado generales que no permiten determinar claramente de que se trata la acción» | Manual MGA 2015 p. 81 | sí: `^(Actividad\s*\d+[:.]\s*)?(apropiar|asegurar|colaborar|consolidar|desarrollar|fomentar|fortalecer|garantizar|implementar|impulsar|mejorar|movilizar|proponer|promover)\b` (no aplicar a objetivos) |
| L14 | Insumos o tareas como actividad: *comprar, adquirir, contratar, viáticos, enviar, llamar* | 14, 15, 22 | son insumos o tareas, no actividades MGA | Manual MGA 2015 p. 81; Módulos 1 y 4 | sí (alerta): `^(Actividad\s*\d+[:.]\s*)?(comprar|adquirir|contratar|pagar|enviar|llamar)\b|\bvi[áa]ticos\b` |
| L15 | Participio en el nombre del producto: *elaborado, implementado, entregado* | 15, 21 | el producto no incluye su condición | Manual MGA 2015 p. 81; guía SGR §15 | sí: `\b(elaborad|implementad|entregad)[oa]s?\b` en la columna Producto (no en Indicador; exentos nombres del catálogo) |
| L16 | Adjetivos promocionales: *innovador(a)(es), novedoso, revolucionario, disruptivo, pionero, único en, de vanguardia, de punta, de clase mundial, sin precedentes, primero del país, líder, referente* | global; crítico en 1, 2, 6, 13, 27 | la novedad se demuestra «frente a las alternativas ya disponibles en el territorio» con referencias | rúbrica 1.2; estilo-natural-es patrón 4; grant-flow-auditor Pass 3 | sí: `\b(innovador[ae]?s?|novedos[oa]s?|revolucionari[oa]s?|disruptiv[oa]s?|pioner[oa]s?|[úu]nic[oa]s?\s+en|de\s+vanguardia|de\s+punta|de\s+clase\s+mundial|sin\s+precedentes|primer[oa]?\s+(proyecto\s+)?(en|del)\s+(el\s+)?pa[íi]s|l[íi]der(es)?|referente)\b`; exentos: «Jóvenes Investigadores e Innovadores», «joven investigador e innovador», nombres de entidades y centros, «innovación» (sustantivo) |
| L17 | Inflación valorativa: *crucial, vital, de vital importancia, fundamental, clave (adjetivo), robusto, extremadamente, juega un papel, se erige como* | global | relleno sin evidencia | estilo-natural-es patrones 1 y 7 | sí: `\b(crucial(es)?|vital(es)?|de\s+vital\s+importancia|fundamental(es)?|robust[oa]s?|extremadamente|juega\s+un\s+papel|se\s+erige)\b` (alerta; «clave» requiere juicio) |
| L18 | Énfasis emotivo: *urgente, necesario y urgente, apremiante, alarmante* | 2, 5, 7 | registro de opinión | estilo-natural-es patrón 1 | sí: `\b(urgentes?|apremiantes?|alarmantes?)\b` |
| L19 | Cuantificadores vagos: *varios, diversos, numerosos, muchos, gran cantidad/número/parte, una parte significativa, significativamente, considerablemente, miles de, cientos de* | 5, 11, 16, 17 | la MGA exige cifra, unidad y fuente | Anexo 2 §5.3 y §11; Directriz SGR 4 | sí (alerta): `\b(vari[oa]s|divers[oa]s|numeros[oa]s|much[oa]s|gran\s+(cantidad|n[úu]mero|parte)|parte\s+significativa|significativamente|considerablemente|miles\s+de|cientos\s+de)\b` |
| L20 | Atribuciones vagas: *diversos estudios, la literatura señala, se ha evidenciado, expertos coinciden* sin cita | 5, 6, 7, 9 | comadreo | estilo-natural-es patrón 2 | parcial: patrón sin `\[\d+\]|\\cite` en la misma oración |
| L21 | Promesas sin mecanismo: *se garantizará, garantiza, asegurará* | 11, 16, 17 | la rúbrica pide actividad, indicador, meta y evidencia | rúbricas 4.2 y 4.4 | parcial: `\b(se\s+)?garantizar[áa]n?\b|\bgarantiza(n)?\b|\basegurar[áa]n?\b` |
| L22 | ASC unidireccional como núcleo: *socializar, socialización de resultados, capacitar a la comunidad, divulgar, sensibilizar, llevar el conocimiento a* | 19 | «no se puede plantear sólo como actividades de divulgación o socialización» | TdR 6.1; rúbrica 2.4 | parcial: `\b(socializ\w+|sensibiliz\w+|capacitar\s+a\s+la\s+comunidad|llevar\s+el\s+conocimiento)\b` (alerta si domina el capítulo) |
| L23 | Transferencia reducida a publicaciones o eventos | 18 | «no constituirán por sí solas evidencia de transferencia» | plantilla cap. 18 | no |
| L24 | Marco de investigación como eje: *pregunta de investigación, hipótesis, paquete(s) de trabajo, work package, estado del arte* | 2, 5, 7, 13, 14 | el Anexo 2 no tiene esos capítulos | Anexo 2; TdR 13.1 | sí (alerta): `\b(pregunta\s+de\s+investigaci[óo]n|hip[óo]tesis|paquetes?\s+de\s+trabajo|work\s+packages?)\b` («paquete tecnológico» exento) |
| L25 | Anglicismos con equivalente: *machine learning, deep learning, big data, dataset, stakeholders, partners, pipeline, framework, workshop, feedback, input(s), output(s), engagement, benchmark* | global | norma culta y lectores territoriales | estilo-natural-es patrones 14 y 35 | sí: `\b(machine\s+learning|deep\s+learning|big\s+data|datasets?|stakeholders?|partners?|pipelines?|frameworks?|workshops?|feedback|inputs?|outputs?|engagement|benchmarks?)\b` (exentos los términos de plantilla: software, hardware, spin-off, start-up, know-how) |
| L26 | Metadiscurso: *en esta sección, en el presente documento, a continuación se presenta(n)*, *cabe destacar/resaltar/mencionar/señalar, es importante (destacar/mencionar)* | global | throat-clearing | estilo-natural-es patrones 15 y 29 | sí: `\b(en\s+esta\s+secci[óo]n|en\s+el\s+presente\s+documento|cabe\s+(destacar|resaltar|mencionar|se[ñn]alar)|es\s+importante\s+(destacar|mencionar|resaltar|se[ñn]alar))\b`; «a continuación se presenta» se tolera una vez como entrada a tabla |
| L27 | Listas abiertas: *entre otros, etc.* | global | vaguedad en compromisos | Directriz SGR 4 | sí (alerta): `\bentre\s+otr[oa]s\b|\betc\.` |
| L28 | Servilismo o premisa de la convocatoria: *cumplir con la premisa de la convocatoria, en total consonancia con los términos* | 2, 7 | tono complaciente | estilo-natural-es patrón 24 | parcial |
| L29 | Nombres de personas como fuente en el diagnóstico (*el profesor X señaló*) | 5, 6 | registro periodístico; citar institución y documento | Directriz SGR 4 | no |
| L30 | Rayas y doble guion en prosa | global | regla de Morfeo | `check_run.py` (`raya-en-prosa`, `doble-guion-en-prosa`) | sí (existente) |

### 3.2 Favorecidas

| Expresión | Ámbito | Razón | Fuente |
|---|---|---|---|
| «El proyecto…» (sujeto por defecto) + *se articula con, responde a, se inscribe en, contribuye a, aporta, atiende, aborda, integra, incorpora* | 1, 2, 4, 7, 13, 16, 17 | verbos más frecuentes tras «el proyecto» en la referencia (busca 7, contribuye 5, articula 4, aporta 3, responde 2, aborda 2) | referencia |
| «La propuesta se enmarca en el Desafío <n> / la línea <n>…» | 1, 4 | fórmula de encuadre | referencia; un borrador («el proyecto se enmarca en la línea temática 9») |
| «El presente proyecto…» (máximo una vez por capítulo) | 7 | apertura de justificación | referencia |
| «En respuesta, el proyecto tiene como propósito <OG literal>.» | 2 | ancla el resumen al OG | referencia |
| «Una de las causas directas relacionadas con el problema central es…», «Otra causa directa del problema son…», «…representan la tercera causa directa del problema», «Esto se debe a…» | 5.2 | estructura causal explícita en el orden del árbol | referencia; guía SGR §3 |
| «A esta situación se suma…», «Esta emergencia agudiza…» | 5.2 | evento como agravante con fuente | referencia; criterio de emergencia (Conv 56) |
| «Por lo anterior, se define como indicador de referencia del problema: …» | 5.3 | cierre de magnitud | referencia |
| «De acuerdo con <entidad> (<año>)…», «Según <documento oficial>…» | 5, 11 | dato con fuente | Directriz SGR 4 |
| «Objetivo específico <n> (OE<n>): <infinitivo…>» | 12, 14, 15 | rótulo literal de plantilla | Anexo 2 cap. 12 |
| «Esta actividad consiste en…», «Esta actividad tiene como finalidad…» | 14 | descripción de actividad | referencia (tablas de control) |
| Futuro de compromiso: *realizará, entregará, verificará, coordinará, se conformará, se priorizarán, contará con, se dará continuidad* | 14, 18, 19, 26 | compromiso verificable | referencia (fut 16–39 por mil en esos capítulos) |
| «El cumplimiento se verificará mediante…», «La verificación del TRL N se sustentará en…», «Los criterios de aceptación…» | 14.1–14.2, 18 | lenguaje de evidencia | referencia; rúbrica 1.3 |
| «El alcance será proporcional al estado de desarrollo de cada solución» | 18 | eco de la plantilla («proporcionales a la naturaleza y grado de madurez») | plantilla cap. 18 |
| Léxico ASC del TdR (participación, diálogo de saberes, co-creación, incidencia, validación conjunta, mesas de trabajo, grupos focales, comunidades de práctica, sistematización) | 19 | coincide con la rúbrica 2.4 | TdR 6.1 |
| Párrafos rotulados de plantilla («Responsable:», «Tareas:», «Resultados de la actividad:», «Medio de verificación:»; «Características técnicas.», «Características financieras.») | 13, 14, 16 | estructura esperada por el evaluador | Anexo 2; referencia |
| Nombres oficiales literales (planes entre «…», productos del catálogo con código, demandas del Anexo 4) | 1, 4, 8, 15, 21 | trazabilidad | rúbrica 1.1; `_guia_comun` coherencia |
| Conectores institucionales variados: *no obstante, por ende, en tal sentido, de ahí que, a su vez, en concreto, por consiguiente* | global | evitar saturación de «asimismo» (21) y «de esta manera» (15) | estilo-natural-es §4.2 |

---

## 4. Patrones de redundancia típicos de documentos SGR

Medición: 6-gramas de palabras compartidos entre capítulos de referencia y conteo de repeticiones de textos clave.

**Lista blanca de repetición obligatoria (no se depura).** Título, problema central, objetivo general, objetivos específicos, nombres de actividades, nombres y códigos de productos, textos de las demandas, nombres de planes y programas, cifras de la línea base. Su repetición literal es exigida por la trazabilidad (rúbrica 1.1; `_guia_comun`: «¿El título del proyecto es idéntico en la MGA, el documento técnico, las cartas y el presupuesto?»; códigos `sgr-objetivo-general-distinto`, `sgr-objetivos-especificos-distintos`). El revisor de redundancia nunca parafrasea ni sustituye por sinónimos estos textos.

| # | Patrón | Evidencia medida | Regla |
|---|---|---|---|
| R1 | El problema central se repite fuera de su lugar | texto del tronco/OG en caps. 1, 2, 5 (×2), 7, 12, 13 y 27 | Literal solo en 5.1, 5.4 y, en positivo, 12.1–12.3 y el título. En el resto, una referencia breve con la variable («la baja cobertura de monitoreo descrita en el capítulo 5»). |
| R2 | Los objetivos específicos se reescriben en cada capítulo | OE1 en caps. 1, 2, 5, 12, 13, 14; OE3 en 2, 5, 7, 12, 13, 14, 19 | Literal en 12.2, 12.3, rótulos del cap. 14 y tablas 15 y 22. En los demás, «el OE<n>» o el verbo y la variable, sin copiar la oración. |
| R3 | ODS y PND en tres capítulos | menciones de ODS: cap. 4 = 6, cap. 7 = 13, cap. 16 = 10; 6-gramas: 4↔7 = 64, 4↔16 = 76, 7↔16 = 82 | Cap. 4 = alineación (programa y meta). Cap. 7 = necesidad y viabilidad; remite al cap. 4 en una oración. Cap. 16 = contribución con productos que la respaldan, sin repetir pilares. |
| R4 | Tabla de demandas duplicada | caps. 1↔8 = 323 6-gramas | Cap. 1: nombre y código de cada demanda. Cap. 8: descripción y contribución con indicador. |
| R5 | Tabla normativa duplicada | caps. 9↔28 = 449 6-gramas (mayor duplicado) | Cap. 9: normas que enmarcan el problema. Cap. 28: solo licencias y permisos aplicables, con justificación. |
| R6 | Talento humano en dos lugares | 12.4↔20 = 161 | 12.4: perfiles, actividades y meses. 20: justificación, cantidad, entidad y costo; remite a 12.4. |
| R7 | Alternativas que re-resumen el proyecto | 2↔13 = 124; 13↔14 = 79 | Cap. 13 compara alternativas por factores; no repite el resumen ni la metodología. |
| R8 | Copia entre transferencia y ASC | 18↔19 = 33 (la referencia los mantiene separados: modelo a seguir) | Transferencia = uso, adopción y valoración por receptores identificados con mecanismo y evidencia. ASC = participación y co-creación. Una actividad compartida se nombra una vez y la otra sección remite a ella con su propósito distinto. |
| R9 | Continuidad descrita tres veces | 16↔17 = 24; mecanismos de continuidad en 16, 17.1 y 18.5 | 16: estrategia y actores. 17.1: responsable de operación y fuente de recursos. 18.5: continuidad de la transferencia. |
| R10 | Diagnóstico repetido en la justificación | 5↔7 = 41 | La justificación no re-describe el problema; parte de él en una oración. |
| R11 | Saturación de un término de la línea dentro de un capítulo | «<término del desafío>» 15 veces en el cap. 5 y 12 en el cap. 19; «sostenible» 221 en el documento | Fuera de la lista blanca, máximo dos repeticiones del mismo término comodín en cinco líneas (depuración, paso 3.4); se sustituye por la variable concreta o un pronombre. |
| R12 | Causas que repiten los calificadores del tronco | patrón en el cap. 5 («…en <territorio> y su área de influencia en <N departamentos>» en cada causa) | Guía SGR §3 «Causas directas sin preámbulo». |
| R13 | Prosa que repite la tabla contigua | población, resultados y riesgos | La prosa explica criterio y lógica; la cifra queda en la tabla (depuración tipo 4). |
| R14 | Conectores en serie | «asimismo» 21, «de esta manera/forma» 15, «adicionalmente» 7, «a continuación» 13 | Ningún conector repetido en arranques consecutivos (estilo-natural-es §4.2). |

---

## 5. Reglas SGR que contradicen o tensionan las reglas actuales del flujo base de Morfeo

> **Framing note (EN).** Each row must be gated on `flujo == "sgr"`. "Base" = `guiaProyectosIA_Agente.md`, `estilo-natural-es`, `depuracion-redundancias-es`, `grant-flow-auditor`. Some items are already handled by the SGR guide; they are listed so the new reviewer does not undo them.

| # | Regla base vigente | Regla SGR | Estado actual | Acción sugerida |
|---|---|---|---|---|
| C1 | Marco de investigación: pregunta de investigación, hipótesis §5, estado del arte §4 con ≥39 refs, novedad en IA | Marco de inversión pública; el Anexo 2 no tiene hipótesis ni pregunta; la referencia no las usa (0 «pregunta de investigación», 2 «hipótesis») | guía SGR §3 aún pide cerrar §3 con la pregunta de investigación | Revisar si el cierre con pregunta de investigación debe quedar fuera del documento SGR. |
| C2 | §3/§4 prohíben «esta propuesta», «el proyecto propone» | Prohibido en 5.1–5.4; permitido en 5.2 (intervenciones diferentes a la que se proponen), cierre del cap. 6 (6,1 por mil en la referencia) y resto de capítulos | parcial | El revisor SGR aplica la prohibición solo al diagnóstico. |
| C3 | Menú de verbos rectores IA en §6–§7 | Verbos espejo del árbol | resuelto en guía SGR §6 | Mantener. |
| C4 | Sin prohibición de verbos para actividades; los objetivos base usan «Desarrollar», «Implementar» | La MGA prohíbe *desarrollar, implementar, fortalecer, mejorar, promover…* como verbo de actividad, pero los admite en objetivos | guía SGR A23 lo dice, sin regex | Regex L13 solo en nombres de actividad SGR. |
| C5 | Título de 12–15 palabras con novedad y herramientas de IA | Título = OG nominalizado, ≤256 caracteres, «Proceso + Objeto + Localización» | resuelto (`sgr-titulo-no-derivado`) | Mantener; añadir alerta de 256 caracteres. |
| C6 | §2 de seis párrafos con OCDE, Banco Mundial, auge de la IA y ≥13 refs Q1/Q2 (3–4 por párrafo); estilo-natural-es «los 6 párrafos reglamentarios de §2» | Cap. 7: necesidad, viabilidad y pertinencia a corto, mediano y largo plazo con tabla; la alineación va en el cap. 4 | no resuelto en las skills | Las skills de estilo no deben exigir seis párrafos ni densidad de citas en SGR. |
| C7 | Resumen ejecutivo de exactamente 5 párrafos con TRL | Mínimo informativo: propósito, desarrollo metodológico, resultados (referencia: 3 párrafos) | no resuelto | Sin conteo fijo en SGR. |
| C8 | Palabras clave: 5, minúscula, separadas por comas | Máximo 6 (plantilla) | no resuelto | Tope de 6 en SGR. |
| C9 | grant-flow-auditor Pass 1: «Convert passive voice into active voice. Eliminate nominalizations»; Pass 3: «we will», «our architecture achieves» | Impersonal *se* es la norma (9,5 por mil; 16 en metodología); nominalización obligatoria en títulos, nodos, productos, riesgos; primera persona prohibida | contradicción directa | En SGR: alternar *se* con sujetos institucionales, no eliminarlo; no tocar nominalizaciones de la lista blanca; reemplazar «we will» por futuro en tercera persona. |
| C10 | estilo-natural-es patrón 8 (evitar «cuenta con», «constituye») | «La alianza cuenta con…», «el grupo cuenta con…» son fórmulas normales en caps. 1, 20 y 27 | tensión | Relajar el patrón 8 en SGR. |
| C11 | estilo-natural-es patrón 11 (variación elegante) y depuración paso 3.4 (no repetir la palabra clave más de dos veces en cinco líneas; usar sinónimos o elipsis) | Repetición literal obligatoria de la lista blanca | contradicción | Exentar la lista blanca del límite y de la sustitución por sinónimos. |
| C12 | estilo-natural-es patrón 18 (listas con encabezado en línea → prosa) | Campos rotulados de plantilla y párrafos rotulados de la referencia | contradicción | Conservar rótulos de plantilla en SGR. |
| C13 | grant-flow-auditor parte oraciones de más de 35 palabras; estilo-natural-es fija el techo en 45 | Referencia: media 32, 23 % sobre 40 | tensión | En SGR usar el techo de 45 de estilo-natural-es (alerta, no división automática). |
| C14 | Pisos bibliográficos (65 total, 39 en estado del arte, 13 en justificación) y densidad por párrafo | El Anexo 2 no fija pisos; marco conceptual «breve»; lo obligatorio son fuentes oficiales de cifras | parcial (la guía SGR delega en la base) | Revisar qué pisos rigen en SGR. |
| C15 | grant-flow-auditor pide «bolded key terms» en el borrador final | estilo-natural-es patrón 17 lo desaconseja; las plantillas SGR no usan negrita en prosa | contradicción interna de Morfeo | Sin negrita en prosa SGR, salvo la línea base en la tabla de magnitud. |
| C16 | Calificativo negativo del tronco (base y SGR aceptan «insuficiente») | Igual en ambos flujos; la precaución de L6 es adicional | sin contradicción | La percepción de que «Insuficientes capacidades…» solo vale en SGR no se confirma: `NEGATIVE_QUALIFIERS` ya lo acepta en los dos flujos. |
| C17 | Base §3: estructura de 6 párrafos | SGR: 5.1–5.4 | resuelto (`sgr-problema-estructura`) | Mantener. |
| C18 | Sin tope de adjetivos oficiales | «innovador» es oficial en «Jóvenes Investigadores e Innovadores» y en nombres de entidades | — | La regex L16 necesita la lista de exentos. |

---

## 6. Implementación en Morfeo (EN, brief)

- **Lexicon.** `scripts/sgr/lexico_sgr.json` (schema `morfeo.lexico-sgr/v1`) holds the voice rules (section 1.1), global and per-section entries keyed by Morfeo section stem, the exemptions, the verbatim whitelist (section 4), the chapter map (Anexo 2 chapter → Morfeo stem) and the chapters with no Morfeo file yet. Entries with a regex are deterministic; entries with `null` guide the reviewer agent.
- **Checker.** `scripts/estilo_sgr.py RUN_ROOT [--section KEY] [--json]` reports L1, L2, L4, L5, L8–L11, L13, L14, L16–L22, L24–L28 where checkable, the «El presente proyecto» limit, R14 (connectors in series) and R1–R10 as copied spans of 12 or more words between sections. Severity: `prohibida` → advertencia, `desaconsejada` → info. L30 stays in `check_run.py`.
- **Chapter scope.** L8 only in the problem section, L13 and L14 only on activity names (tables of methodology, schedule and value chain, and `artefactos/sgr/cadena_valor.json`), L22 only in the ASC section.
- **Exemptions.** Quoted text, official names («Jóvenes Investigadores e Innovadores»), catalog product names and the whitelist texts (title, central problem, objectives, products, activities) are masked before matching.
- **Reference weaknesses flagged on purpose:** «Cero (0) prototipos…» baseline, «falta de» in the causal narrative, solution talk in 5.2, the 650-word résumé with 50-word sentences, first person in ch. 27, and the duplicated normative and demand tables.
