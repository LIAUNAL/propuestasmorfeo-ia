---
name: estilo-natural-es
description: Pulir y humanizar la prosa académica y científica en español (norma académica culta de Colombia) para propuestas de investigación. Erradica los 35 patrones de escritura de IA (fórmulas mecánicas, aperturas cósmicas, gerundios de cierre, inflación de trascendencia, falsos rangos, regla de tres, monotonía de ritmo), introduce burstiness y perplejidad académica controlada y preserva estrictamente la fidelidad factual (cifras, fechas, citas BibTeX, comandos LaTeX, estructura de párrafos y prohibición de rayas anglosajonas o dobles guiones).
---

# Estilo Natural en Español Académico (Colombia) para Propuestas de Investigación

## 1. Naturaleza y propósito de la skill

Esta skill eleva la calidad literaria, la fluidez argumentativa y la cadencia rítmica de la prosa académica y científica en español, bajo la norma culta institucional de Colombia (MinCiencias, Sistema General de Regalías, Universidad Nacional de Colombia y universidades aliadas como la UTP). Su propósito es erradicar la textura mecánica, predecible y uniforme que delata la generación por inteligencia artificial, transformándola en la prosa sobria, precisa y contundente de un investigador senior.

Es el resultado de acoplar la metodología de estilo académico natural del marco con el catálogo exhaustivo de patrones de detección de `humanizer-mit` (adaptación al español de la guía *Signs of AI writing* de Wikipedia y WikiProject AI Cleanup), calibrado específicamente para el género de propuestas de subvención y formulación de proyectos en Colombia.

### Líneas rojas inviolables (lo que esta skill NO hace):
1. **Cero evasión tramposa:** No emplea caracteres invisibles, espacios de ancho cero, homóglifos cirílicos ni trucos de codificación Unicode. No introduce errores tipográficos intencionales ni falsas imperfecciones ortográficas.
2. **Cero coloquialismo o degradación de registro:** No confunde naturalidad con informalidad. Jamás inserta modismos callejeros (*chévere*, *vaina*, *de una*), tuteo/voseo en la narrativa técnica, ni frases de falsa confidencia conversacional (*la verdad es que*, *mira*, *seamos honestos*). El registro se mantiene estrictamente formal, académico y riguroso.
3. **Fidelidad factual sagrada:** La skill modifica exclusivamente el *estilo* y la *cadencia sintáctica*; el *contenido* es inamovible. Números, porcentajes, fechas, presupuestos, cohortes (`EST-MZ-xxx`, `EST-PE-xxx`), niveles TRL (6 o 7), ecuaciones, fórmulas matemáticas y afirmaciones científicas permanecen idénticos byte a byte.
4. **Seguridad en LaTeX y citaciones:** Preserva intactos todos los comandos, entornos, etiquetas (`\label`, `\ref`, `\cref`), archivos incluidos (`\input`) y claves de citación en formato natbib APA autor-año (`\citep{...}`, `\citet{...}`). Jamás inventa citas ni altera claves de citación existentes.
5. **Prohibición absoluta de rayas anglosajonas (` — `) y doble guion (`--`):** En español académico formal no se utiliza la raya con espacios a los lados ni el doble guion para incisos en prosa narrativa; se emplean comas, punto y coma o paréntesis.
6. **Estructura intacta:** Respeta escrupulosamente la cantidad de párrafos y la progresión argumentativa exigida por la guía (por ejemplo, los 6 párrafos reglamentarios de §2 Justificación y pertinencia, o el mapeo 1:1 de los 3 subproblemas con los 3 objetivos específicos). Las listas reglamentarias (objetivos, rubros, productos) no se disuelven.

---

## 2. Ámbito de aplicación

### Aplica a:
- Toda la prosa narrativa en español de la propuesta: Secciones 2 a 12, 14, 15, 17, 18 y el Front-matter (Resumen, Resumen ejecutivo, Palabras clave).
- La revisión de estilo obligatoria ejecutada por `grant-flow-auditor` antes de cada compuerta de validación (`revisor`).
- Toda documentación, guías, reportes y notas en español redactadas por el asistente primario.

### No aplica a:
- Entradas BibTeX (`refs.bib`), tablas de LaTeX, tabla de presupuesto (§13), código del cronograma Gantt (§14) ni código TikZ de figuras.
- Listados reglamentarios estructurados que la guía exige mantener como viñetas o listas numeradas (objetivos específicos, rubros presupuestales, productos esperados de la Tabla 4).
- Textos o fragmentos en inglés.

---

## 3. Catálogo de los 35 patrones de IA a erradicar (Contexto Académico Colombia)

### A. Patrones de contenido y retórica
1. **Inflación de trascendencia y clichés de grandeza:** Expresiones como *se erige como*, *juega un papel fundamental/crucial*, *marca un antes y un después*, *un punto de inflexión*, *sentando las bases para*, *en el corazón de*.  
   *Corrección:* Usar verbos directos, funcionales y sobrios (*permite*, *resuelve*, *aporta*, *constituye*, *facilita*).
2. **Atribuciones vagas y comadreo (weasel words):** Afirmaciones como *diversos expertos coinciden*, *estudios recientes señalan*, *la literatura sugiere* sin respaldo bibliográfico inmediato.  
   *Corrección:* Citar la fuente concreta (`\citep{...}`) o declarar el hecho técnico de forma directa.
3. **Análisis superficiales con gerundios de cierre:** Oraciones que rematan con gerundios decorativos (*destacando su pertinencia...*, *subrayando el compromiso...*, *reflejando la estrecha articulación...*, *garantizando un impacto...*).  
   *Corrección:* Reemplazar por oraciones coordinadas o subordinadas con verbo conjugado, o cerrar la frase con el aserto principal.
4. **Lenguaje publicitario o promocional:** Adjetivos inflados como *vibrante*, *revolucionario*, *impresionante*, *de vanguardia*, *rico patrimonio*, *profundo impacto*.  
   *Corrección:* Describir el alcance técnico exacto con evidencia cuantitativa o metodológica.
5. **Cierres y conclusiones optimistas genéricas:** Frases de clausura vacías como *abriendo un horizonte prometedor para la región* o *sin duda, un avance en la dirección correcta*.  
   *Corrección:* Concluir con el entregable tangible, el hito verificable o el nivel TRL alcanzado.
6. **Secciones formularías prefabricadas:** Párrafos de transición genéricos tipo *a pesar de los retos planteados, las oportunidades continúan siendo prometedoras*.  
   *Corrección:* Abordar los riesgos operacionales o limitaciones metodológicas de manera técnica y contextualizada.

### B. Patrones de lenguaje, léxico y gramática
7. **Vocabulario comodín de alta frecuencia en IA:** Uso reiterado y simultáneo de *robusto*, *crucial*, *fundamental*, *clave* (como adjetivo comodín), *ecosistema* (en sentido figurado abstracto), *tapiz*, *entramado*, *un abanico de*, *en última instancia*, *de la mano de*.  
   *Corrección:* Aplicar la regla 70/30 (70% de términos técnicos fijos y estables, 30% de variación en verbos y adjetivos descriptivos precisos).
8. **Evitación rebuscada de la cópula:** Reemplazar innecesariamente *es*, *son* o *tiene* por perífrasis como *se posiciona como*, *constituye*, *alberga*, *cuenta con*.  
   *Corrección:* Usar la cópula directa o el verbo propio de posesión o pertenencia.
9. **Paralelismos negativos forzados y negaciones de cola:** Construcciones repetitivas como *no solo busca X, sino también consolidar Y*, *no se trata de un simple modelo, sino de una arquitectura*, y coletillas recortadas al final (*sin esfuerzo*, *sin adivinar*).  
   *Corrección:* Afirmar directamente lo que el sistema hace, de manera asimétrica y contundente.
10. **Abuso de la regla de tres:** Forzar sistemáticamente la enumeración de tres adjetivos, tres sustantivos o tres beneficios en una sola frase (*innovación, rigor y pertinencia*; *captura, procesa y evalúa*).  
    *Corrección:* Coordinar dos elementos con fuerza o integrar los conceptos en cláusulas jerarquizadas.
11. **Variación elegante artificial:** Rotar sinónimos forzados para referirse al mismo concepto técnico dentro del mismo párrafo (*el modelo... el algoritmo... la red... la herramienta predictiva*).  
    *Corrección:* Mantener el término técnico unificado para no generar ambigüedad en el evaluador.
12. **Falsos rangos:** Construcciones *desde X hasta Y* donde los extremos no pertenecen a una misma escala medible (*desde la captura de señales electroencefalográficas hasta la inclusión territorial*).  
    *Corrección:* Enumerar las dimensiones técnicas en planos diferenciados.
13. **Voz pasiva refleja que oculta la agencia técnica:** Abuso de *se realiza el procesamiento* o *se efectúa la recolección* cuando el texto debe dejar claro qué componente o actor ejecuta la acción.  
    *Corrección:* Alternar con voz activa (*el módulo de extracción procesa...*, *el equipo de campo recolecta...*).
14. **Calcos del inglés y falsos amigos:**  
    - *hacer sentido* → *tener sentido*.  
    - *eventualmente* (por *eventually*) → *con el tiempo*, *al final*, *a largo plazo*.  
    - *remover* (por *remove*) → *eliminar*, *retirar*, *suprimir*.  
    - *consistente con* (por *consistent with*) → *coherente con*, *acorde con*.  
    - *aplicar a una convocatoria* (por *apply to*) → *postularse a*, *presentarse a*.  
    - *en orden de / para* (por *in order to*) → *a fin de*, *con el propósito de*, *para*.  
    - *billón* (por *billion*) → *mil millones*.  
    - *dramático / dramáticamente* (por *dramatic*) → *drástico*, *notable*, *significativo*.  
    - *actualmente* (cuando se traduce erróneamente de *actually*) → *en realidad*, *en efecto*.
15. **Muletillas de apertura y conectores ceremoniosos:** *En el mundo actual*, *En la era digital*, *Hoy en día*, *Cabe destacar que*, *Es importante mencionar que*, *Es fundamental comprender que*.  
    *Corrección:* Suprimir el preámbulo y arrancar con el sujeto o la afirmación sustantiva.

### C. Patrones de estilo, puntuación y tipografía
16. **Prohibición de rayas anglosajonas (` — `) y doble guion (`--`):**  
    - Queda **terminantemente prohibido** el uso del guion largo con espacios (` — `) o el doble guion (`--`) como paréntesis o aparte en medio de la prosa en español.  
    - *Corrección:* Utilizar la coma de inciso, el punto y coma (`;`), los dos puntos (`:`) o los paréntesis rectos/curvos según corresponda a la sintaxis española.
17. **Abuso de negrita mecánica:** Evitar resaltar frases completas o términos obvios con negrita dentro de párrafos continuos.
18. **Listas con encabezado en línea en lugar de prosa:** Transformar esquemas mecánicos (`- **Dimensión:** explicación`) en párrafos cohesivos y fluidos, salvo donde el TDR o la guía exija explícitamente una tabla o lista.
19. **Mayúsculas estilo inglés en títulos:** En español solo se escribe con mayúscula la letra inicial del título y los nombres propios (`\section{Justificación y pertinencia}`, nunca `\section{Justificación Y Pertinencia}`).
20. **Emojis o decoraciones gráficas:** Incompatibles con el rigor del documento científico.
21. **Comillas y signos de apertura:** Emplear comillas dobles rectas (`"..."`) o latinas (`«...»`), y garantizar el uso obligatorio de los signos de apertura `¿` e `¡` cuando existan oraciones interrogativas o exclamativas.

### D. Patrones de comunicación, meta-discurso y estructura
22. **Restos de conversación de chatbot:** Frases como *¡Por supuesto!*, *Espero que esta sección cumpla con los requisitos*, *A continuación presento...*. Erradicar todo metadiscurso.
23. **Relleno especulativo por corte de conocimiento:** Párrafos que discuten la ausencia de información en lugar de limitarse a los datos disponibles.
24. **Tono servil o complaciente:** Adulaciones a la convocatoria o al evaluador.
25. **Perífrasis y rodeos innecesarios:**  
    - *Con el fin de lograr este propósito* → *Para lograrlo*.  
    - *Debido al hecho de que* → *Dado que*, *Puesto que*, *Porque*.  
    - *Tiene la capacidad de ejecutar* → *Puede ejecutar*, *Ejecuta*.
26. **Exceso de matización e hiper-cautela:** Acumular condicionales como *podría potencialmente quizás argumentarse que tal vez influya*. Afirmar con precisión epistémica calibrada.
27. **Abuso de compuestos de moda:** Saturar con *en tiempo real*, *orientado a datos*, *de extremo a extremo*, *multidisciplinario*.
28. **Fórmulas de autoridad impostada:** *La verdadera pregunta es*, *En el fondo*, *Lo que de verdad importa*.
29. **Anuncios y señalización («throat-clearing»):** *En esta sección procederemos a describir detalladamente...* Entrar directamente en materia.
30. **Encabezados fragmentados:** Títulos seguidos de oraciones huecas de un renglón que repiten el título antes de iniciar el contenido real.
31. **Escritura anclada al cambio (estilo changelog/diff):** Redactar como si se narrara una modificación (*esta sección se corrigió para...*) en vez de exponer la propuesta como un documento definitivo.
32. **Remates en staccato melodramático:** Apilar cuatro o cinco frases telegráficas consecutivas para fabricar falso dramatismo.
33. **Fórmulas de aforismo pretencioso:** *La tecnología es el espejo de la sociedad*, *El dato es la moneda del siglo XXI*.
34. **Aperturas de falsa confidencia:** *La verdad es que*, *Siendo honestos*, *A decir verdad*.
35. **«Español de ninguna parte» (mezcla de variantes):** Mezclar modismos peninsulares (*ordenador*, *coche*, *móvil*, *vosotros*) con términos de otros países. Se exige la norma culta académica colombiana.

---

## 4. Contexto de Redacción: Norma Académica e Institucional de Colombia

La redacción de la propuesta debe reflejar los estándares de los comités científicos y evaluadores de MinCiencias y las universidades públicas colombianas (Universidad Nacional de Colombia, Universidad Tecnológica de Pereira):

1. **Léxico institucional colombiano:**
   - Emplear la terminología propia del sistema de ciencia y tecnología de Colombia: *proyecto de investigación y desarrollo (I+D)*, *transferencia tecnológica*, *apropiación social del conocimiento (ASC)*, *grupos de investigación categorizados por MinCiencias*, *contrapartida en especie y en efectivo*, *formación de talento humano*, *articulación territorial*, *semillero de investigación*, *jóvenes investigadores*.
   - Preferencias léxicas estándar: *computador* o *equipo de cómputo* (nunca *ordenador*), *vehículo* (nunca *coche*), *dispositivo móvil* o *celular* (nunca *móvil*), *validar/verificar* (nunca *checar*), *postularse / presentarse* (nunca *aplicar* a convocatorias), *cohorte institucional* (en Manizales y Pereira).
2. **Conectores lógicos del español formal de Colombia:**
   - Conectores preferidos para transiciones argumentativas fluidas: *no obstante*, *por ende*, *en tal sentido*, *de ahí que*, *con todo*, *ahora bien*, *en concreto*, *a su vez*, *en contraposición*, *así las cosas*, *en efecto*, *por consiguiente*.
   - Evitar la saturación monótona de *asimismo* y *adicionalmente* en arranques consecutivos.
3. **Tratamiento y voz gramatical:**
   - Narrativa en tercera persona sobria (*el proyecto plantea*, *el grupo de investigación implementará*) combinada equilibradamente con la pasiva refleja institucional (*se seleccionó una muestra*, *se realizarán pruebas de validación*).
   - Queda totalmente excluido el tuteo y el voseo en la redacción técnica.

---

## 5. Burstiness y dinamismo sintáctico (Variación de cadencia)

La escritura humana experta se distingue por la variabilidad en la longitud y complejidad de sus frases (*burstiness*). La IA tiende a aplanar el texto en oraciones medianas de 20 a 25 palabras, todas con la misma estructura gramatical.

Para romper este patrón:
1. **Alternancia de longitud oracional:**
   - Combinar oraciones breves y contundentes (8 a 15 palabras), que fijen asertos y principios irrefutables, con oraciones compuestas y ramificadas (25 a 40 palabras), que desarrollen la argumentación causal o técnica.
   - Evitar oraciones monstruosas de más de 45 palabras que fatiguen al lector, así como ristras de frases cortadas en staccato.
2. **Asimetría de arranques:**
   - Nunca iniciar tres oraciones consecutivas con el esquema básico [Sujeto + Verbo].
   - Alternar arranques utilizando:
     - Complementos circunstanciales de lugar, tiempo o instrumento (*En los campus de Manizales y Pereira,...*, *Durante la fase de validación de campo,...*).
     - Proposiciones condicionales o causales (*Dado que la latencia en borde constituye una restricción crítica,...*).
     - Cifras o métricas sustantivas al inicio (*Un 42 % de la población evaluada registró...*).
     - Conectores contraargumentativos o ilativos (*No obstante, la convergencia algorítmica exige...*).
3. **Puntuación viva y variada:**
   - Salir del binomio elemental [coma - punto seguido].
   - Emplear punto y coma (`;`) para separar proposiciones yuxtapuestas con estrecha vinculación lógica.
   - Emplear dos puntos (`:`) para introducir explicaciones causales directas o deducciones inmediatas.
   - Emplear paréntesis para precisiones metodológicas, siglas o rangos numéricos.

---

## 6. Procedimiento de auditoría y pulido (Paso a paso)

Al revisar o refactorizar una sección en `redaccion/sections/`:

```
Paso 1: Mapeo y Detección ──> Paso 2: Poda y Desmecanización ──> Paso 3: Reescritura Holística (Cadencia) ──> Paso 4: Verificación de Invariantes
```

1. **Paso 1: Mapeo:** Identificar la presencia de cualquiera de los 35 patrones de IA, prestando especial atención a muletillas de apertura, gerundios de cierre, paralelismos negativos, dobles guiones (`--`) o rayas anglosajonas (` — `).
2. **Paso 2: Poda:** Eliminar preámbulos vacíos, conectores redundantes y adjetivos inflados.
3. **Paso 3: Reescritura holística en un solo pase:** Reformular la prosa integrando la cadencia sintáctica colombiana, variando la longitud oracional y enriqueciendo el léxico sin alterar términos técnicos ni significados.
4. **Paso 4: Verificación estricta de invariantes:**
   - [ ] ¿Se mantuvieron exactamente todas las cifras, fechas, porcentajes y presupuestos?
   - [ ] ¿Permanecieron intactas todas las claves BibTeX (`\citep`, `\citet`) y comandos LaTeX?
   - [ ] ¿Se eliminaron todos los dobles guiones (`--`) y rayas anglosajonas (` — `)?
   - [ ] ¿Se respetó el número exacto de párrafos exigido por la sección?
   - [ ] ¿El registro es estrictamente formal y acorde a la norma académica de Colombia?

---

## 7. Contrato de salida (Reporte de auditoría)

La edición se realiza **directamente sobre el archivo `.tex` correspondiente**. El reporte se presenta en la respuesta del agente con la siguiente estructura:

1. **Patrones detectados:** Listado puntual de vicios de IA encontrados en el borrador original.
2. **Tabla de transformaciones clave:**
   | Patrón corregido | Fragmento original | Fragmento reescrito (Estilo Natural Colombia) |
   | :--- | :--- | :--- |
   | *[Ej. Gerundio de cierre]* | *"...mejorando el rendimiento de la red."* | *"...lo cual incrementa la tasa de acierto del modelo."* |
3. **Verificación de invariantes:** Confirmación explícita de preservación de cifras, citas, comandos LaTeX, ausencia de `--` y conteo de párrafos.
4. **Índice de Naturalidad y Fidelidad (0 a 100):**
   - Variación de longitud oracional (Burstiness): 25 pts.
   - Variedad de conectores académicos colombianos: 20 pts.
   - Variación léxica y ausencia de comodines de IA (Regla 70/30): 20 pts.
   - Supresión de fórmulas mecánicas y rayas anglosajonas: 15 pts.
   - Fidelidad estricta factual y seguridad LaTeX: 20 pts.
