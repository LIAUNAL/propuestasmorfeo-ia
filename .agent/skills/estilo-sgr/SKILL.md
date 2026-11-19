---
name: estilo-sgr
description: Voz, patrones por capítulo del Anexo 2, léxico y redundancia de los proyectos de inversión del Sistema General de Regalías (flujo sgr de Morfeo). Ajusta estilo-natural-es y depuracion-redundancias-es a las directrices del DNP (MGA), a las plantillas de Minciencias y a las rúbricas, con el léxico de scripts/sgr/lexico_sgr.json y el verificador scripts/estilo_sgr.py. Solo rige cuando el flujo de la corrida es sgr.
---

# Estilo SGR: voz, léxico y redundancia del Anexo 2

## 1. Cuándo aplica

Solo cuando el proyecto tiene `"flujo": "sgr"` en `.morfeo/config.json`. En el
flujo base esta skill no se carga y rigen `estilo-natural-es` y
`depuracion-redundancias-es` tal como están.

Un documento SGR es un **proyecto de inversión pública** formulado con el marco
lógico de la MGA, no una propuesta de investigación. Su vocabulario rector es
problema, causas, efectos, alternativa, objetivo, producto, actividad,
indicador, meta, línea base, población, cadena de valor y riesgo; la pregunta de
investigación, la hipótesis y el paquete de trabajo no son ejes del texto.

**Precedencia.** TdR de la convocatoria > plantilla del Anexo 2 de esa
convocatoria > DNP/MGA (Manual conceptual 2015, Instructivo 2023) > proyectos
de referencia > estilo base de Morfeo. Donde el proyecto de referencia y la MGA
difieren, **manda la MGA**: la referencia también comete errores («Cero (0)
prototipos» como línea base, «falta de» en la narración causal, primera persona
en el texto institucional pegado) y la regla no los copia.

Fuentes en el repositorio: la evidencia completa en
`docs/sgr/patrones_redaccion_sgr.md`; la parte «Redacción» de cada bloque
`### SGR` de `guiaProyectosIA_Agente_Regalias.md`; el léxico
`scripts/sgr/lexico_sgr.json`.

## 2. Voz

1. **Tercera persona sobre el proyecto.** Sujeto por defecto: «El proyecto…».
   Aperturas válidas: «Este proyecto busca…», «La presente propuesta se enmarca
   en…», «La propuesta se enmarca en el Desafío <n>…», «El presente
   proyecto…» (una vez por sección como máximo), «La alianza…», «La entidad
   proponente…», «<Entidad> coordinará…» y la impersonal con «se» («Se
   realizarán campañas de muestreo…»).
2. **Cero primera persona**, singular o plural, también en tablas y en el texto
   institucional pegado: nada de nosotros, nuestro, hemos, proponemos,
   buscamos, realizaremos.
3. **Compromiso, no intención.** Actividades y productos en futuro de
   indicativo («entregará», «se verificará»). Fuera «se pretende», «intentará»,
   «tratará de». «Se espera» solo para impactos de mediano y largo plazo.
4. **Afirmación con fuente.** Toda cifra de magnitud, población o línea base
   lleva entidad, documento y año.
5. **Nominal donde la MGA es nominal.** Títulos, nodos de los árboles,
   productos, riesgos y tareas son sintagmas nominales y no se verbalizan.
6. **Tiempo.** Presente para el diagnóstico, las definiciones, la alineación y
   las alternativas; pretérito para antecedentes y evolución reciente; futuro
   para metodología, resultados, transferencia, ASC, medidas de población y
   ética; infinitivo solo en objetivos, medios y nombres de actividad.

## 3. Patrones por capítulo (resumen)

| Capítulo del Anexo 2 | Archivo de Morfeo | Patrón clave |
|---|---|---|
| 2 Resumen ejecutivo | `00_frontmatter` | Propósito («En respuesta, el proyecto tiene como propósito <OG literal>»), desarrollo metodológico y resultados con cifras; 450 a 650 palabras, oraciones de menos de 45 palabras, sin hipótesis ni definiciones |
| 4 Alineación | `19_alineacion_planes` | Nombre oficial entre comillas latinas y la contribución a la meta del plan; presente |
| 5 Problema | `03_descripcion_problema` | Tronco literal; un párrafo por causa directa en el orden del árbol; magnitud con fuente; sin ausencia de solución ni solución en el diagnóstico; sin pregunta de investigación al cierre |
| 6 Antecedentes | `04_estado_arte` | Un párrafo por iniciativa en pretérito (qué, quién, cuándo, resultado, aprendizaje); cierre que nombra el proyecto |
| 7 Justificación | `02_justificacion` | Necesidad, pertinencia y viabilidad a corto, mediano y largo plazo; remite al problema y a la alineación en una oración |
| 8 Demandas | `17_articulacion_comunidades` | Demanda literal; contribución que empieza por el OE o el producto, con indicador |
| 9 Marco conceptual | `08_marco_conceptual` | Definiciones breves en presente gnómico |
| 10 Participantes | `20_participantes` | Vocabulario fijo MGA (Beneficiario, Cooperante, Oponente, Perjudicado) |
| 11 Población | `21_poblacion` | Personas con cifra, fuente y localización; medidas en futuro |
| 12 Objetivos | `06_objetivo_general`, `07_objetivos_especificos` | Textos literales del árbol; sin medio, fin, meta ni producto |
| 13 Alternativas | `22_alternativas` | Párrafos rotulados por factor; descarte por razón técnica |
| 14 Metodología | `10_metodologia` | «Actividad <n.n.n>: <infinitivo + objeto>» con Responsable, Tareas, Resultados y Medio de verificación; futuro e impersonal |
| 15 Cadena de valor | `23_cadena_valor` | Tabla; productos del catálogo DNP; dos o más actividades por producto |
| 17 Resultados | `11_resultados_esperados` | Meta, plazo e indicador; oraciones cortas |
| 19 ASC | `18_apropiacion_social` | Participación, diálogo de saberes, co-creación, incidencia; no solo socializar |
| 21 Productos | `15_productos_esperados` | Nombre del catálogo sin participio; el participio va en el indicador |
| 22 Cronograma | `14_cronograma_actividades` | Meses, etapa y ruta crítica; mismos nombres de actividad |
| 23 Riesgos | `24_riesgos` | Descripción nominal; medida en infinitivo con responsable y costo |
| 26 Ética | `12_consideraciones_eticas` | Futuro normativo atado a las actividades |
| 1 Identificación | `26_identificacion` (generada) | Tablas desde `alianza.json` y `territorio.json`; demandas textuales con su código |
| 8 y 8.1 Demandas territoriales | `27_demandas_territoriales` (generada) | Demanda textual + articulación en presente y futuro, en tercera persona |
| 10.1 Matriz de responsabilidades | `28_matriz_responsabilidades` (generada) | Responsabilidades con códigos de actividad; gobernanza |
| 27 Idoneidad y trayectoria | `29_idoneidad_trayectoria` | Una subsección por entidad, tercera persona, sin texto institucional en primera persona |

Los capítulos 16, 18, 24, 25, 28 y 31 aún no tienen archivo en Morfeo;
el léxico los lista en `capitulos_sin_archivo` con su nota de redacción.

## 4. Ajustes a `estilo-natural-es` y `depuracion-redundancias-es` en SGR

Estas dos skills siguen rigiendo; en el flujo SGR se suspenden o ajustan estas
reglas (conflictos C1 a C18 de la evidencia):

| # | Regla base | En SGR | Por qué |
|---|---|---|---|
| C1 | Pregunta de investigación, hipótesis y estado del arte como ejes | Marco de inversión: problema, alternativa, cadena de valor | El Anexo 2 no tiene esos capítulos y la referencia no los usa |
| C2 | Prohibida la autorreferencia en §3 y §4 | Prohibida solo en el diagnóstico; permitida en el cierre de antecedentes y en el resto | Plantilla 5.2 y práctica de la referencia |
| C4 | Sin veto de verbos para actividades | Veto MGA en nombres de actividad, no en objetivos | Manual MGA 2015, p. 81 |
| C6, C7, C8 | Seis párrafos de §2, cinco del resumen, cinco palabras clave | Sin conteo fijo de párrafos; hasta seis palabras clave | La plantilla no los fija |
| C9 | Pasar la pasiva a activa y eliminar nominalizaciones; «we will» | Conservar la impersonal con «se» y alternarla con sujetos institucionales; conservar las nominalizaciones de la lista blanca; futuro en tercera persona | La impersonal es la norma del género (9,5 por mil palabras) |
| C10 | Patrón 8: evitar «cuenta con», «constituye» | Se relaja: «La alianza cuenta con…» es fórmula normal | Uso en los capítulos de equipo e idoneidad |
| C11 | Patrón 11 y paso 3.4: no repetir la palabra clave, rotar sinónimos | La lista blanca se repite literal y nunca se parafrasea | Trazabilidad exigida por la rúbrica 1.1 |
| C12 | Patrón 18: listas con rótulo a prosa | Se conservan los campos y párrafos rotulados de la plantilla | El evaluador espera esa estructura |
| C13 | Partir oraciones de más de 35 palabras | Techo de 45 palabras como alerta, sin división automática | Media de la referencia: 32 palabras |
| C14 | Pisos bibliográficos y densidad por párrafo | Lo obligatorio son las fuentes oficiales de las cifras; los pisos de la guía base siguen mientras `check_run.py` los exija | El Anexo 2 no fija pisos |
| C15 | Negrita en términos clave | Sin negrita en prosa, salvo la línea base en la tabla de magnitud | Las plantillas no usan negrita |
| C18 | Adjetivos promocionales sin excepción | Exentos los nombres oficiales («Jóvenes Investigadores e Innovadores», nombres de entidades) | Son nombres, no adjetivos |

C3, C5, C16 y C17 ya están resueltos en la guía SGR y en `check_run.py`; no se
deshacen.

**Lista blanca de repetición obligatoria.** Título, problema central, objetivo
general, objetivos específicos, nombres de actividades, nombres y códigos de
productos, textos de las demandas, nombres de planes y programas y cifras de la
línea base. Se copian literal; el revisor de redundancia no los parafrasea ni
los sustituye por sinónimos.

## 5. Redundancia SGR (R1 a R14)

- R1 y R2: el problema central y los objetivos específicos van literales solo
  donde la plantilla los pide; en el resto, «el OE<n>» o una referencia breve
  con la variable.
- R3: ODS y PND en el anexo de alineación; la justificación remite en una
  oración; la sostenibilidad muestra la contribución con productos.
- R4 a R9: demandas, normativa, talento humano, alternativas, transferencia y
  ASC, y continuidad tienen cada uno su lugar; la otra sección remite.
- R10: la justificación no re-describe el problema.
- R11: fuera de la lista blanca, máximo dos repeticiones del mismo término
  comodín en cinco líneas.
- R12: las causas no repiten los calificadores del tronco.
- R13: la prosa explica criterio y lógica; la cifra queda en la tabla.
- R14: ningún conector repetido en arranques consecutivos.

## 6. Léxico y verificador

- `scripts/sgr/lexico_sgr.json` (esquema `morfeo.lexico-sgr/v1`): reglas de voz,
  entradas globales y por sección (stem de Morfeo) con tipo `prohibida`,
  `desaconsejada` o `favorecida`, expresión, regex o `null`, motivo, fuente y
  ámbito (`prosa`, `tabla`, `nombres_actividad`); exenciones; lista blanca;
  mapa de capítulos.
- `python3 scripts/estilo_sgr.py <RUN_ROOT> --section <stem> --json` reporta
  las coincidencias deterministas: primera persona, léxico por sección, verbos
  MGA en nombres de actividad, «El presente proyecto» repetido, conectores en
  serie y fragmentos de 12 o más palabras copiados entre secciones. `prohibida`
  sale como `advertencia`; `desaconsejada`, la redundancia y los límites, como
  `info`. Las entradas con regex `null` las juzga el agente.
- Un hallazgo no es una orden de borrar: dentro de una cita literal, de un
  nombre oficial o de un texto de la lista blanca, el texto se queda como está.

## 7. Invariantes

Las de `estilo-natural-es` sin cambio: cifras, fechas, claves de cita, comandos
LaTeX y tablas generadas desde datos quedan byte a byte; sin rayas ni dobles
guiones en prosa; registro formal de la norma académica colombiana.
