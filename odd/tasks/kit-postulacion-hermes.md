# Kit de diligenciamiento Hermes — Invitación Nacional Focalizada «Respuesta a emergencias y desastres»

**Estado:** en curso
**Origen:** pedido del operador (2026-10-01) para postular la propuesta de la corrida
`2026-09-tept-depresion-ia-portable` en el Sistema de Información Hermes.
**Plazo real:** cierre del registro **5 de octubre de 2026**. Publicación preliminar
de propuestas que cumplen requisitos: **9 de octubre**.

## Qué se puede y qué no se puede hacer desde acá

**Establecido con evidencia, no supuesto:**

1. ~~**El dispatcher no alcanza la sesión del operador.**~~ **CORREGIDO el
   2026-10-02, con verificación directa.** El diagnóstico anterior era
   incompleto. Lo que se comprobó ahora:
   - El nombre correcto es **`http://www.hermes.unal.edu.co`**. Sin `www`, el DNS
     no resuelve (`net::ERR_NAME_NOT_RESOLVED`), y eso fue lo que produjo la
     lectura equivocada de «página pública».
   - El navegador del MCP **es una instancia propia con perfil persistente** en
     `~/.cache/chrome-devtools-mcp/chrome-profile` (sin `--headless`: es una
     ventana visible). Su historial muestra visitas del 2026-10-01 22:51–22:53 a
     Hermes, **hechas por una sesión anterior**.
   - Ese perfil conserva cookies de `autenticasia.unal.edu.co`,
     `sia.unal.edu.co`, `siaman.unal.edu.co` y `dninfoa.unal.edu.co`
     (`cookiesession1`, vigentes hasta 2027). El inicio de sesión **no** se
     hereda: `login.xhtml?p=I` devuelve el formulario de Usuario/Contraseña, sin
     redirección automática al SSO.
   - **Conclusión:** el navegador controlable sí llega a Hermes y su perfil
     persiste entre sesiones, pero **no está autenticado**. Basta con que el
     operador escriba la credencial una vez en esa ventana; el dispatcher nunca
     la ve ni la maneja.
   - El Chrome personal del operador (pid 654, abierto desde el 16 de septiembre)
     es un perfil distinto y **no** tiene puerto de depuración
     (`127.0.0.1:9222` no responde), así que no es conducibble sin reiniciarlo.
2. **El TDR de esta convocatoria no fija límites de caracteres.** Verificado sobre
   las 19 páginas. Las únicas reglas de extensión son: **Resumen ejecutivo mínimo
   300 palabras** y **palabras clave máximo 6**. Si el formulario impone límites por
   campo, viven dentro del formulario y son invisibles sin la sesión.
3. **No existe instructivo publicado de esta convocatoria.** El único «registro de
   propuestas» disponible es de **UNAL–DFG**, otra convocatoria (exige socios
   alemanes y presupuesto de $50M–$120M). Sirve de advertencia: si el formulario
   pide contrapartes alemanas, es el formulario equivocado.
4. **Un guardado automático cada 2 minutos no es ejecutable desde acá.** Hermes ya
   tiene el suyo: guarda por sección con «Guardar y continuar después».

**Decisión del operador:** preparar el kit campo por campo desde el documento.

## Advertencia sobre «(ver documento_tecnico.pdf)»

El operador pidió resumir los campos que no quepan y cerrarlos con la referencia
`(ver documento_tecnico.pdf)`. **No se aplica, y hay que decidirlo explícitamente:**

- Los adjuntos que el TDR admite son **cinco cartas** (§8.6) y **tres anexos**
  (§18). **Un `documento_tecnico.pdf` no está en ninguna de las dos listas.**
- El riesgo es concreto: si un campo remite a un archivo que no puede cargarse, el
  evaluador se queda con un campo vacío de contenido. El fallo se descubriría el
  **9 de octubre**, en la publicación preliminar de propuestas que cumplen
  requisitos, cuando ya no hay margen.
- **El kit no usa esa fórmula.** Cada campo lleva su texto propio, y donde el
  original es largo lleva además una versión condensada autosuficiente.

## Los 16 campos y su fuente en el documento

Los apartados del **§8.3 del TDR** son la lista de campos del formulario.

| # | Campo del §8.3 | Fuente | Estado |
|---|---|---|---|
| a | Identificación (título, línea temática, lugar, director) | §1 | por extraer |
| b | Resumen ejecutivo (**mínimo 300 palabras**) | front-matter | por extraer |
| c | Palabras clave (**máximo 6**) | front-matter | por extraer |
| d | Preguntas de investigación | §3 (cierre) | por extraer |
| e | Justificación | §2 | por extraer |
| f | Marco conceptual | §8 | por extraer |
| g | Estado del conocimiento | §4 | por extraer |
| h | Objetivo general | §6 | por extraer |
| i | Objetivos específicos | §7 | por extraer |
| j | Metodología (con roles y responsabilidades) | §10 + §9 | por extraer |
| k | Resultados esperados | §11 | por extraer |
| l | Productos académicos (composición 1 + 2 + 3) | §15 | por extraer |
| m | Cronograma (**actividades ↔ objetivos numerados**) | §14 | por extraer |
| n | Participantes (rol, responsabilidades, actividades) | §9 | por extraer |
| o | Articulación con comunidades y actores territoriales | §17 | por extraer |
| p | Acceso, mediación, divulgación y apropiación social | §18 | por extraer |

**El mapeo es completo:** los 16 campos tienen sección de origen. Ninguno queda sin
contenido, que es la primera cosa que un evaluador verifica.

## Tareas

1. [x] Convertidor determinista: `.tex` → texto plano pegable.
2. [x] Extraer los 16 campos con su conteo de caracteres.
3. [x] Componer el campo a) (título + línea temática + lugar + director).
4. [x] Ensamblar `kit-hermes-postulacion.md`.
5. [x] Versiones condensadas (integradas al kit como «Versión condensada» en los
   11 campos largos d, e, f, g, j, k, l, m, n, o, p). Evidencia: cada bloque del
   `.md` abre con la versión condensada en 4–5 k caracteres y pliega la completa
   en un `<details>`; `condensados.json` guarda las 11 cadenas. Ratios reales
   1,29x–2,31x; total 143.794 → 40.423 caracteres (28 %). Los cinco campos
   cortos (a, b, c, h, i) no se condensan: b) tiene mínimo de 300 palabras y
   c) tiene el tope duro de 6 palabras clave.
6. [x] Verificar: cero comandos LaTeX residuales, conteos por script.

## Herramientas nuevas del marco

- `plantilla/scripts/latex_a_texto.py` — convierte una fuente LaTeX en texto
  pegable: acentos, citas resueltas a autor-año contra `refs.bib`, `\cref`
  resueltos por `etiquetas.json`, tablas a texto, y fuera los entornos de figura.
- `plantilla/scripts/kit_formulario.py` — arma el kit desde el mapa de campos del
  §8.3, compone el campo a) y escribe el Markdown y el JSON.

Ambas agregadas a `scripts/kit-manifest.json` (60 → **62** `kit_paths`).

## Dos bugs reales encontrados y corregidos en el convertidor

1. **La cedilla se comía las palabras que empiezan por `c`.** La regla del acento
   `\c` sin llaves se aplicaba a cualquier comando: `\caption` salía como
   `a̧ption`. Habría corrompido texto en el formulario sin que se notara. Ahora los
   acentos cuyo comando es una letra exigen la forma con llaves (`\c{c}`), y solo
   los que son signo de puntuación (`\'a`, `\~n`) admiten la forma suelta.
2. **Los saltos de línea duros del LaTeX llegaban al campo.** Un área de texto no
   necesita los cortes de la fuente: ahora un párrafo del documento es un párrafo
   de la salida, y las listas se conservan como líneas separadas.

## El hallazgo que más importa

**§9 deja cinco datos de identidad sin completar**, marcados `⟨completar: …⟩`
porque no se completan por inferencia:

1. La UAB exacta de cada docente de la UNAL y el nombre de su director(a).
2. El nombre oficial del grupo de Automática de la UTP.
3. El segundo apellido de David Augusto Cárdenas, si aplica.
4. La unidad académica o facultad de la UTP a la que está adscrito, y su director(a).
5. Nombre y cargo del representante de la UTP que firma las cartas de alianza.

**Bloquean el campo n) Participantes y cuatro de las cinco cartas obligatorias del
§8.6.** Son el primer cuello de botella de la postulación, no el último.

## Verificación

- 16 campos extraídos, **143.794 caracteres** de texto pegable.
- **Cero comandos LaTeX residuales** en los 16 (verificado con script).
- Acentos, comillas angulares y `⟨completar⟩` sobreviven la conversión.
- Las citas se resuelven a autor-año contra `refs.bib` (`(Torous et al., 2025)`),
  no a claves desnudas.
- Los 74 tests del marco siguen verdes (`python3 -m unittest discover -s tests`).

## Estado de la postulación al 2026-10-02

**El kit está listo.** 16 campos, 143.794 caracteres, cero comandos LaTeX
residuales, 74 tests del marco verdes. Los 9 anexos existen redactados y con PDF
borrador en `artefactos/anexos/pdf/`.

**La ruta crítica no es el texto: son los datos de identidad y la sesión.**

| # | Bloqueo | Quién lo resuelve |
|---|---|---|
| 1 | Sesión de Hermes sin autenticar en el navegador controlable | el operador, una vez, en la ventana del MCP |
| 2 | Cinco datos de identidad del §9 (`⟨completar⟩`) | el operador / las oficinas |
| 3 | Datos de firmantes en las cartas 01, 02, 03, 04, 05, 07 y 08 | el operador / las oficinas |
| 4 | Estudiantes seleccionados en la carta 06 | el equipo |
| 5 | Código Hermes del proyecto (lo pide la plantilla del Anexo 2) | se obtiene al crear el registro |

Los bloqueos 2, 3 y 4 son la misma cosa: **personas y unidades que no se infieren**.
Mientras no lleguen, cuatro de las cinco cartas del §8.6 y el campo **n)** siguen
incompletos, y todo lo demás se puede pegar ya.

## Pendiente de decidir por el operador

- Si el formulario tiene límite por campo: usar la versión condensada, que ya
  viaja dentro de cada bloque del kit. **El kit completo es el camino por
  defecto**, porque el TDR no documenta ningún límite.
- Los cinco datos de identidad del §9.
- **Cómo se autentica la sesión de Hermes** (ver «Estado de la postulación»
  arriba): escribir la credencial en la ventana del navegador del MCP, o
  reiniciar el Chrome personal con puerto de depuración.

## Estado del diligenciamiento en Hermes (2026-10-02)

**Proyecto 69609**, creado por el operador con el título ajustado «Aplicativo
móvil basado en inteligencia artificial para apoyar el tamizaje de depresión
posdesastre en estudiantes universitarios». Registrado en el **registro único de
proyectos**, no todavía en la Invitación Nacional Focalizada: la inscripción a la
convocatoria quedó detenida en `tab_AceptarTerminosReferencia.xhtml`, sin pulsar
«Aceptar».

### El formulario sí limita caracteres

El análisis del TDR («no documenta límites») era correcto para el TDR y
**insuficiente para el formulario**. La ficha mínima impone topes con contador
visible:

| Campo del formulario | Tope |
|---|---:|
| `* Resumen` | 4000 |
| `* Descripción del Problema (hipótesis)` | 4000 |
| `* Objeto/Objetivo general` | 4000 |
| Objetivo específico (fila repetible) | 2000 |
| Medio de verificación del objetivo | 2000 |
| Resultado (fila repetible) | 2000 |
| Entregable del resultado | 2000 |

La red de seguridad de `condensados.json` cubría los campos del kit, no estos
topes. Los textos ajustados se compusieron aparte y quedaron en
`artefactos/kit/hermes-campos.json`, con los 21 conteos verificados contra su
límite.

### Cargado y guardado

Guardado parcial confirmado por Hermes: «Su proyecto ha sido registrado
correctamente con el código: 69609».

| Bloque | Estado |
|---|---|
| Resumen | cargado (2434/4000) |
| Descripción del problema e hipótesis | cargado (3921/4000) |
| Objeto/objetivo general | cargado (372/4000) |
| Tres objetivos específicos con sus medios de verificación | cargados como filas |
| Seis resultados con entregable y fecha | cargados como filas |
| Sede, facultad y dependencia | Manizales · Ingeniería y Arquitectura · Depto. de Ingeniería Eléctrica, Electrónica y Computación |
| Rol de la UNAL y tipo de financiación | Ejecutora con varios participantes · Financiación interna |
| Departamento de impacto | Caldas |
| Aviso de privacidad | aceptado |

Las fechas de los entregables se anclaron a los hitos de §14 (M6, M9, M10, M11
y M12, contados desde el 09/09/2026). Quedan sujetas a revisión del operador,
porque el cronograma reparte los tres manuscritos entre M9, M11 y M12 y la
asignación resultante no es la única lectura posible.

### Segundo guardado: clasificación y palabras clave

Vuelto a guardar y verificado tras el guardado: los nueve selectores de
clasificación persisten. La clasificación quedó así:

| Selector | Valor |
|---|---|
| ODS principal | Garantizar una vida sana y promover el bienestar (ODS 3) |
| ODS secundario | Construir infraestructuras resilientes (ODS 9) |
| Objetivo socioeconómico | Salud |
| Área OCDE · subárea | Ingeniería y tecnología · Ingenierías eléctrica, electrónica e informática |
| Área OCDE secundaria · subárea | Ciencias médicas y de la salud · Ciencias de la salud |
| Componente del Plan Global | Segundo desafío: la proyección nacional en diálogo con los territorios |
| Nodo · programa | 2. Integración académica · 2.2 Líneas integradas de trabajo académico |
| Tipo de financiación | Financiación interna |
| Región de impacto | Caldas · Manizales (fila agregada) |
| Palabras clave | las seis del front-matter, agregadas una por una |

`Documento de identidad` del director ya venía registrado por el formulario:
ANDRES ALVAREZ, C-1088257232, dedicación 4 h/semana durante 12 meses.

### Pendiente en el formulario

Falta la pestaña **Información general**, y **Clasificación**, **Palabras
clave**, **Equipo de trabajo**, **Aspectos generales** y **Costos**: los
selectores de ODS, área OCDE, objetivo socioeconómico, política y nodos del Plan
Global, la tabla de dependencias y el director del proyecto.

**Corregido:** de esa lista ya están la clasificación y las palabras clave. Lo
que sigue en pie son cuatro bloques:

1. ~~**Productos académicos**~~ — **hecho.** Seis filas con la cascada completa:
   D/1226/1360 Prototipo de productos nuevos (1); B/1212/1264 Tesis de maestría
   (1); B/1213/1273 Estudiante en formación pregrado (2); C/1219/1297 Ponencia en
   evento científico (1); C/1220/1314 Participación ciudadana o comunidades (1);
   C/1224/1390 Cursos, seminarios o talleres (1).
2. **Equipo de trabajo** — pendiente: `tipodoecv2_input`, `documentov2`,
   `horasCoinv3` y `funcionInvestigador` para cada coinvestigador.
3. ~~**Costos**~~ — **hecho.** Dependencia ejecutora: 4- FACULTAD DE INGENIERÍA Y
   ARQUITECTURA. Fuente de recursos internos: DIRECCIÓN DE INVESTIGACIÓN Y
   EXTENSIÓN SEDE MANIZALES. Conviene que el operador confirme la dependencia
   ejecutora: la lista financiera solo llega a nivel de facultad, no de
   departamento, y la Dirección de Investigación es la alternativa natural.
4. **Duración en meses** — controlado por el botón `btnduracion`; la fila del
   director ya registra 12 meses.

### Equipo de trabajo: lo que falta para cerrarlo

El bloque pide, por persona, cuatro cosas: tipo de documento (C/P/E/T…),
número, horas y función; el botón `buscarPer2` («Agregar») resuelve el nombre a
partir del documento. Es decir, **el nombre no se escribe: se busca por cédula**.
Por eso el bloque está detenido.

Datos que ya están confirmados:

| Persona | Documento |
|---|---|
| Andrés Marino Álvarez-Meza (IP, director) | C-1088257232, 4 h/semana, 12 meses — ya registrado por el formulario |
| Alejandro Patiño Bedoya | 1002566760 · alpatinob@unal.edu.co |
| Jeronimo Novoa Giraldo | 1054858413 · jenovoag@unal.edu.co |
| Sergio Alejandro Gil Rios | 1055753057 · segilr@unal.edu.co |

Faltan los documentos de **Germán Castellanos-Domínguez**, **Jorge Iván
Montes-Monsalve**, **David Augusto Cárdenas** (UTP), **Carlos Andrés Pérez** y
**Diego Armando Pérez**, más las horas semanales de todos salvo el IP.

**El bloqueo no se resuelve por inferencia.** Las dos vías fallaron: el MCP de
Drive (`google-drive`) pide inicio de sesión («requires sign-in. Run /mcp»), y el
montaje local de DriveFS no materializa los archivos — `cp` y `cat` devuelven
0 bytes y `pdftotext` falla con «Couldn't find trailer dictionary» sobre un PDF
de 517 KB. La carpeta de la convocatoria de referencia vive en un acceso directo
roto localmente (`Convocatoria Nacional aliazas interdisiplinarias unal
2019-2021` = enlace de 0 bytes sin destino).

**El formulario exige horas semanales.** Al pulsar «Agregar» con la cédula
1002566760 y sin horas, Hermes responde: «Por favor verifique la información de
las Horas semanales de dedicación (mayor a 0)». §9 declara la dedicación en
**períodos** (doctorado a dedicación completa 12 meses, maestría un año, pregrado
cuatro meses cada uno), no en horas por semana, así que las horas no se pueden
tomar de ahí sin agregar un dato nuevo.

**Discrepancia de composición por resolver.** §9 declara cuatro estudiantes (un
doctorado, una maestría, dos pregrado) y §11/§15 la misma composición. El
operador nombra cinco: Alejandro Patiño Bedoya, Jeronimo Novoa Giraldo, Sergio
Alejandro Gil Rios, más **dos** estudiantes de doctorado (Carlos Andrés Pérez y
Diego Armando Pérez). Si son dos doctorados, hay que revisar §9, §11, la fila B.2
ya cargada en Hermes (hoy dice «Estudiante en formación pregrado», cantidad 2) y
el rubro de $50.000.000 de contratación de estudiantes.


### Trampa de los códigos


El código `4106` significa «Depto. de Ingeniería Eléctrica, Electrónica y
Computación» en el selector de dependencias del proyecto y «SEDE TUMACO» en el de
dependencia ejecutora. **Los dos catálogos no comparten codificación.** Seleccionar
por código entre catálogos distintos asigna en silencio la unidad equivocada; en
ese selector hay que buscar por nombre. La selección errónea se detectó en la
misma sesión y quedó corregida antes de guardar.

### Herramientas y tropiezos

- `PrimeFaces` no expone `getWidgetById`. Los widgets viven en
  `window.widget_<id_con_guiones_bajos>`; `selectValue()` dispara el AJAX de las
  cascadas (sede → facultad → dependencia, departamento → ciudad).
- El navegador **bloquea** `fetch` desde el sitio público hacia `127.0.0.1`
  aunque el servidor responda `Access-Control-Allow-Private-Network: true`. La
  inyección de textos se hizo pasándolos por el script, no por HTTP local.
- Los contadores «caracteres restantes» no se refrescan al asignar `value` por
  script; son cosméticos y no afectan el envío.


---

## Sesión 2026-10-07: equipo de trabajo del 69609

La sesión del operador quedó autenticada en el navegador del MCP, así que el
diligenciamiento pudo retomarse donde lo había dejado la corrida anterior. El
proyecto 69609 sigue en el registro único, sin inscribir en la convocatoria.

### El bloque de equipo acepta los datos pero no agrega a nadie

Los seis campos del integrante se cargaron y el formulario los conserva entre
recargas: tipo de vinculación «Profesor o investigador externo», tipo documento
«Cédula de ciudadanía», documento 1053779322, dedicación 2 h/s, vinculación 12
meses y las actividades de David Augusto Cárdenas Peña. El botón «Agregar»
dispara su petición y el servidor responde 200, pero la tabla «Participantes de
los cuales se conocen los datos personales» sigue diciendo «No se han agregado
participantes».

Lo decisivo es que `form:messages` vuelve **vacío**: no hay validación fallida ni
mensaje de error. El fallo es silencioso.

Se descartó que la causa fuera la forma de escribir los campos. El primer intento
usó JavaScript; el segundo usó `fill_form` y `click` del MCP, es decir
interacción real, y el resultado fue idéntico. También se descartó que el AJAX no
se disparara: la petición 531 lleva
`javax.faces.source=form:panelUnoInfAcad:buscarPer2` y vuelve con 200.

La explicación que queda en pie es que **Hermes no encuentra ninguna persona con
esa cédula en su registro**. David es profesor de la UTP, externo a la
Universidad Nacional, y el formulario busca contra el padrón institucional.

### La salida que el propio formulario ofrece

El bloque abre con «¿Conoce los datos personales de los integrantes que
conformarán el proyecto?», hoy en **SI**, y mantiene dos tablas: la de
participantes con datos personales y otra de participantes **sin** ellos, que
pide solo tipo de participante, cantidad y actividades. Esa segunda tabla es la
vía prevista para quien no está en el padrón. El precio es que el integrante
queda registrado de forma agregada, sin nombre ni cédula.

### Qué sigue bloqueado

Las cédulas de Castellanos Domínguez y de Montes Monsalve. Los dos son docentes
de planta de la UNAL, así que sí deberían estar en el padrón de Hermes; sin el
número no hay forma de invocarlos. Las herramientas de Gmail están declaradas
pero piden inicio de sesión propio (`/mcp`), de modo que la búsqueda en el correo
tampoco se pudo hacer.

### Sin tocar, a la espera de visto bueno

El enlace «Agregar Proy. Convocatoria» inscribe el proyecto en la Invitación
Nacional Focalizada y lleva al «Aceptar» de los términos de referencia. No se
pulsó.

### Las cédulas llegaron y el bloque cerró a medias

El operador aportó los dos documentos que faltaban: César Germán Castellanos
Domínguez, c.c. 79.439.458, y Jorge Iván Montes Monsalve, c.c. 16.074.725. Ambos
entraron sin fricción como «Profesor carrera docente UN», con 2 h/s y 12 meses, y
el guardado parcial devolvió «Su proyecto ha sido registrado correctamente con el
código: 69609». Una recarga confirmó que persisten.

| Participante | UAB según Hermes | h/s | m | Valor dedicación |
|---|---|---:|---:|---:|
| CESAR CASTELLANOS C-79439458 | Ing. Eléctrica, Electrónica y Computación | 2.0 | 12.0 | $72.138.336 |
| JORGE MONTES C-16074725 | **Informática y Computación** | 2.0 | 12.0 | $10.991.136 |

Con eso el diagnóstico de David queda confirmado por comparación controlada: la
receta idéntica agrega a dos personas y no a la tercera, de modo que la variable
es la persona y no el método. David Augusto Cárdenas Peña pertenece a la UTP y no
está en el padrón de la Universidad Nacional.

### Dos cosas que el formulario corrigió del trabajo previo

**Jorge no es del mismo departamento.** El aval 04 lo daba por adscrito a
Ingeniería Eléctrica, Electrónica y Computación y lo hacía firmar por Dahiana
López García, por analogía con el aval de referencia. Hermes lo reporta en el
**Departamento de Informática y Computación**. El anexo se corrigió: membrete,
firmante y pie, y el nombre del director de esa UAB vuelve a quedar por
completar, porque no se infiere.

**La convención de 48 semanas era la correcta.** Hermes valoriza la dedicación de
Castellanos en $72.138.336 por 2 h/s durante 12 meses. Su valor hora certificado
es $751.441, y 751.441 × 96 = 72.138.336 exacto. Es decir, el propio sistema
liquida 96 horas, las mismas que se adoptaron para el aporte de la UTP en §13 y
en los anexos 05, 07 y 08. La alternativa de 104 horas queda descartada por
evidencia, no por preferencia.

### La UTP entra como entidad participante, no por el equipo

Decisión del operador: David no se vincula al equipo de trabajo. La contrapartida
de la UTP se declara en el bloque **Entidades participantes** de la información
financiera, con el valor en especie que generan sus horas.

El bloque está detrás de una casilla, «¿El proyecto tiene entidades
participantes?», que al marcarse habilita el catálogo de entidades —4766
opciones— y los campos de monto en efectivo y en especie. Se registró:

| Entidad | Monto efectivo | Monto especie |
|---|---:|---:|
| UNIVERSIDAD TECNOLÓGICA DE PEREIRA | $0 | $14.395.968 |

Guardado con «Su proyecto ha sido registrado correctamente con el código: 69609»
y verificado tras recargar. El costo total quedó así:

| Concepto | Valor |
|---|---:|
| Aporte entidades participantes | $14.395.968 |
| Valor personal docente | $134.697.216 |
| **Valor total del proyecto** | **$149.093.184** |

La solución resuelve de raíz el fallo del alta de David: el aporte queda
declarado y cuantificado sin depender de que exista en el padrón de personas de
la Universidad Nacional.

**Un duplicado del catálogo, anotado:** la Universidad Tecnológica de Pereira
aparece dos veces, con código 8415 sin tilde y 4369 con tilde. Se eligió 4369 por
la grafía correcta y por ser el registro más antiguo. Si la oficina usa el otro,
basta eliminar la fila y repetir con 8415.

### Los $100M faltaban como fuente de financiación

El operador detectó el hueco: el total mostraba $149.093.184, que es la suma de
las contrapartidas y nada más. La causa estaba a la vista en el bloque de costos,
«No se han agregado fuentes de financiación»: el dinero solicitado al fondo nunca
se había registrado.

Se agregó **Vicerrectoría de Investigación** como fuente interna pública —el TDR
nombra a la VRI como convocante— y se distribuyeron los $100.000.000 en la
columna *Efectivo* del catálogo presupuestal, con este desglose indicado por el
operador:

| Rubro del catálogo | Ruta en el árbol | Valor |
|---|---|---:|
| Servicios De Investigación Y Desarrollo | Gastos de comercialización › Adquisición de servicios | $50.000.000 |
| Maquinaria De Oficina, Contabilidad E Informática | Adquisición de bienes › Activos fijos | $30.000.000 |
| Otros Servicios De Fabricación; Edición, Impresión Y Reproducción | Gastos de comercialización › Adquisición de servicios | $10.000.000 |
| Servicios De Telecomunicaciones, Transmisión Y Suministro De Información | Gastos de comercialización › Adquisición de servicios | $10.000.000 |

Total del proyecto tras el ajuste, verificado después de recargar:

| Concepto | Valor |
|---|---:|
| Valor en efectivo (VRI) | $100.000.000 |
| Valor personal docente | $134.697.216 |
| Aporte entidades participantes (UTP, especie) | $14.395.968 |
| **Valor total del proyecto** | **$249.093.184** |

**Dos cosas del formulario que cuestan tiempo si no se saben.** Los servicios no
cuelgan de «Adquisición de bienes y servicios» sino de «Gastos de comercialización
y producción», contra lo que sugiere el nombre. Y cada valor que se escribe
dispara un AJAX que repliega el árbol entero, así que la ruta de expansión hay que
rehacerla rubro por rubro.

### El desglose ya no coincide con §13

| Rubro | §13 del documento | Hermes |
|---|---:|---:|
| Servicios de investigación | $50.000.000 | $50.000.000 |
| Servicios técnicos | $15.000.000 | — |
| Artículos científicos / impresión | $15.000.000 | $10.000.000 |
| Equipos | $20.000.000 | $30.000.000 |
| Licencias de IA | — | $10.000.000 |

Ambos suman $100.000.000, pero son distribuciones distintas. §13 justifica cada
rubro contra una actividad de la metodología, de modo que el cambio arrastra la
prosa de §13 y la coherencia con §10 y §14. Queda pendiente de decisión del
operador.

### Los productos pasan de seis a ocho

El cotejo contra el Anexo 1 mostró que la composición cumplía el mínimo del TDR
—un producto de tipo A o D, dos de B y tres de C— pero justo en el borde, y con
dos incoherencias que costaban puntos. No había producto de tipo A aunque el
presupuesto financiaba la publicación de tres manuscritos, y el doctorando
figuraba en el equipo y en el presupuesto sin aparecer entre los productos de
formación.

Composición nueva, en el documento y en Hermes:

| # | Producto | Subtipo | Entrega |
|---|---|---|---|
| 1 | Aplicativo móvil con inteligencia artificial | D.1 prototipo fabricable por el sector empresarial | M10, cierre documental M11 |
| 2 | Artículo sometido a revista indexada, en acceso abierto | A.1 | M12 |
| 3 | Tesis de maestría | B.1 | M11 |
| 4 | Vinculación de dos estudiantes de pregrado | B.2 | M2 |
| 5 | Vinculación de un estudiante de doctorado | B.3 | M2 |
| 6 | Ponencia en evento científico | C.2 | M9 |
| 7 | Participación de la comunidad universitaria | C.3 | M12 |
| 8 | Taller de apropiación | C.7 | M12 |

**El doctorado se compromete por la vinculación, nunca por la culminación.** Una
tesis doctoral no se termina en doce meses, de modo que prometerla habría sido
comprometer lo que el calendario no sostiene. §10 y §11 se ajustaron en el mismo
sentido.

**El rubro de publicación se acotó.** Antes costeaba acceso abierto, traducción y
corrección de estilo; ahora paga únicamente los cargos de procesamiento del
artículo, porque esas otras labores las asume el equipo.

En Hermes se eligió el subtipo 1232, «artículo científico o de investigación
sometido, aceptado o aprobado para publicación en revista indexada»: es el único
que nombra revista indexada y admite el artículo sometido, que es lo realista en
la ventana de ejecución.

### Una regresión que el revisor atrapó

El primer pase actualizó la tabla de §15 y olvidó la prosa, que seguía citando la
numeración vieja: el producto 3 anclado en M2, la ponencia como producto 4, la
tesis de maestría como producto 2. El `revisor` devolvió FAIL con cinco
correcciones bloqueantes, todas reales. Se aplicaron y la reverificación cerró en
PASS, con las dieciséis menciones de «producto N» apuntando al producto correcto.

La causa de fondo estaba en el comentario de cabecera del archivo, que documentaba
el mapeo viejo de seis productos y servía de referencia al editar. Se actualizó a
la composición de ocho y se le agregó una advertencia explícita: cualquier cambio
en la lista obliga a recorrer el archivo completo.

### Qué se actualizó en Hermes

Los ocho productos del catálogo, y los entregables de cuatro resultados, que
citaban la numeración y el subtipo anteriores. El editor de fila de la tabla de
resultados funciona con el icono de lápiz y confirma con el de chequeo; no hay
botón visible, así que parece de solo lectura hasta que se inspecciona el DOM.

### Los rubros de Hermes quedan en cinco, con equipos en $20M

El operador fijó dos valores: equipos en $20.000.000 y servicios técnicos en
$10.000.000. En Hermes la instrucción se balancea sola, porque los $10M que
salen de equipos financian exactamente la línea nueva.

| Rubro del catálogo UNAL | Valor |
|---|---:|
| Servicios de Investigación y Desarrollo | $50.000.000 |
| Maquinaria de Oficina, Contabilidad e Informática | $20.000.000 |
| Servicios Profesionales, Científicos y Técnicos | $10.000.000 |
| Otros Servicios de Fabricación; Edición, Impresión | $10.000.000 |
| Servicios de Telecomunicaciones, Transmisión y Suministro de Información | $10.000.000 |

El nodo elegido para servicios técnicos excluye en su propio rótulo los
servicios de investigación, que son el primer rubro, así que no hay solapamiento
entre los dos.

**Un error que conviene no repetir.** El primer intento localizó las filas del
árbol por el texto de la primera celda y escribió $10.000.000 en «Viviendas», un
rubro que nada tiene que ver. La causa es que el árbol se re-renderiza tras cada
escritura y la correspondencia entre fila y etiqueta deja de ser estable. Salió a
la luz al verificar: el total marcaba $110.000.000 y equipos seguía en $30M.

La forma que sí funciona apunta por el id exacto del input
(`listaFuentesFinan2:0:treetable:<nodo>:j_id_1gc`), afirma el valor previo antes
de escribir y aborta si no coincide. Con esa guarda, las tres escrituras
—limpiar «Viviendas», bajar equipos, crear servicios técnicos— pasaron a la
primera. Ids de esta corrida: `0_0_0` Viviendas, `0_0_7` equipos, `1_1_12`
investigación, `1_1_14` servicios técnicos, `1_1_15` telecomunicaciones,
`1_1_20` edición e impresión.

### Pendiente: el quinto rubro del documento

§13 tiene cuatro rubros y suma $100.000.000. Para cuadrar con Hermes necesita
cinco, y el quinto es la línea de $10M que en Hermes quedó bajo
telecomunicaciones.

Ahí hay un conflicto que no se resuelve con aritmética. Esa línea venía
etiquetada como licencias de IA, decisión tomada sin verificar, y §10 declara
cuatro veces que el proyecto no requiere ninguna licencia: descriptores abiertos,
modelos preentrenados de distribuciones abiertas y entornos de ejecución móvil de
código abierto (líneas 166, 289, 408 y 509). Escribir un rubro de licencias
contradiría la metodología en cuatro puntos y le quitaría el argumento de código
abierto.

La salida que la metodología sí respalda es **servicios de cómputo**: §10 pide el
servicio académico de la Sede en los tres objetivos, para las corridas largas y
la búsqueda de hiperparámetros, para los experimentos de compresión y calibración
y para las corridas de la prueba inversa. Queda a decisión del operador; el
documento no se tocó mientras tanto, porque cambiar un solo rubro dejaría la
tabla sumando $95.000.000.

### El presupuesto queda en cinco rubros, con la frontera de las licencias explícita

El operador resolvió el conflicto que bloqueaba el documento: las licencias de IA
por $10.000.000 **se necesitan para el desarrollo**, y el despliegue **debe
funcionar con modelos gratuitos**. Eso permitió cerrar §13 sin contradecir la
metodología.

| # | Rubro | Valor |
|---|---|---:|
| 1 | Contratación de servicios de investigación | $50.000.000 |
| 2 | Servicios técnicos | $10.000.000 |
| 3 | Artículos científicos | $10.000.000 |
| 4 | Equipos | $20.000.000 |
| 5 | Licencias de IA | $10.000.000 |

La distinción no es cosmética. Un evaluador que lea «licencias» puede concluir que
el producto entregado depende de un pago recurrente, y de ahí se sigue que la
capacidad no permanece en el territorio tras el cierre. Por eso la descripción del
rubro 5 dice que el sistema entregado corre sobre modelos y entornos abiertos, y
los tres bloques de «Recursos necesarios» de §10 repiten la frontera con una
formulación distinta cada uno, según el eslabón del que hablan.

Las dos frases de §10 que sí dicen que no se requiere licencia quedaron intactas,
porque hablan de otra cosa: el acceso a las tres bases de datos y el carácter
abierto de los descriptores eGeMAPS y de los modelos preentrenados. El argumento
de código abierto, que sostiene el TRL comprometido, no se debilitó.

Verificación: `presupuestador` reestructuró §13 y encontró dos menciones de
«cuatro rubros» que el encargo no listaba; `redactor` ajustó las tres frases de
§10; `revisor` cerró en PASS sobre nueve controles, sin correcciones bloqueantes.
El PDF compila en 60 páginas, sin errores ni desbordes.

### Hermes: el registro 69609 quedó en la sección equivocada

El operador detectó que el proyecto se venía diligenciando en una sección que no
corresponde, y va a crear la versión en la zona correcta. Todo trabajo sobre 69609
quedó detenido en ese punto.

Lo cargado en 69609 sirve de inventario para migrar, no de trabajo perdido: los
cinco rubros de arriba, los ocho productos, el equipo docente con sus cédulas y
dedicaciones, la UTP como entidad participante en especie por $14.395.968, la
Vicerrectoría de Investigación como fuente interna de los $100.000.000, y los seis
resultados con sus entregables y fechas. Nada de eso se inscribió ni se envió: el
operador saca el reporte PDF y hace la inscripción a mano.

### El registro correcto es el 69693, en la convocatoria focalizada

La diferencia entre los dos registros estaba en la convocatoria, no en el
contenido. El 69609 colgaba de «Registro único de proyectos», modalidad
«Proyecto o programa de investigación»; el 69693 cuelga de la **Invitación
Nacional Focalizada – Respuesta a Emergencias y Desastres**, modalidad única.
Esa es la zona correcta.

Antes de escribir nada se volcó el contenido del 69609 a
`artefactos/kit/hermes_69609_inventario.json`: título, resumen, descripción del
problema, objeto, los tres objetivos con sus medios de verificación, los seis
resultados con entregables y fechas, clasificación, palabras clave, productos,
rubros, fuente, entidad y equipo. La sesión de Hermes ya se había caído una vez,
y rederivar esos textos desde el LaTeX habría producido una versión distinta sin
ninguna ganancia.

**Lo cargado y verificado en el 69693**

| Sección | Estado |
|---|---|
| Tipología, título, duración | ya venían del registro |
| Dependencias responsables | Manizales › Ingeniería y Arquitectura › Depto. de Ing. Eléctrica, Electrónica y Computación |
| Resumen y objetivo general | 2 434 y 372 caracteres |
| Objetivos específicos | 3, con sus medios de verificación |
| Resultados esperados | 6, con entregable y fecha |
| Productos académicos | 8: 1 A + 3 B + 3 C + 1 D |
| Región que impacta | Caldas/Manizales y Risaralda/Pereira |
| Clasificación | ODS salud, sector salud, ingeniería y tecnología, eléctrica/electrónica/informática, segundo desafío, integración académica, línea 2.2 |
| Palabras clave | las 6 |
| Lugar de ejecución financiera | 4- Dirección de Investigación y Extensión |
| Fuente de financiación | la que trae la convocatoria, en $100.000.000 |
| Rubros | los cinco, suma exacta |
| Entidad participante | UTP, $0 efectivo y $14.395.968 en especie |

Se guardó parcialmente con «Guardar y continuar después» ocho veces, y cada
tramo quedó verificado tras recargar.

**Dos diferencias de forma frente al 69609.** Esta convocatoria no pide la
descripción del problema en la ficha mínima —la pediría en «Información
Específica»— y trae la fuente de financiación ya creada en $0, de modo que los
rubros se asignan sobre esa fila en lugar de agregar una nueva. Agregar otra
habría duplicado el aporte.

**El catálogo de productos no es el mismo.** La primera elección del artículo
cayó en «Artículo (se aceptan artículos que se encuentren sometidos y/o
aprobados para publicación)», que no es el del 69609. Se eliminó y se puso
«Artículo científico o de investigación sometido o, aceptado o aprobado para
publicación en revista indexada», que es el que nombra la revista indexada. La
lección es que en este formulario hay diez variantes de «Artículo» y un regex
laxo escoge la equivocada.

### Dos topes que no me corresponden

**El aviso de privacidad.** La sección de equipo de trabajo no expone sus campos
hasta aceptar una cláusula donde el docente declara que ha recibido autorización
expresa de todas las personas vinculadas a la propuesta. Es una declaración legal
sobre autorizaciones que el operador posee y yo no: la acepta él.

**Falta un estudiante.** Al intentar «Guardar y Avanzar», la validación responde
«Debe incluir al menos un estudiante de pregrado o posgrado». La convocatoria lo
exige, y el paso siguiente del asistente no se abre sin eso. El formulario ofrece
la opción «¿Conoce los datos personales de los integrantes?» en NO, que permite
vincular sin datos personales; así no hay que inventar ninguna identidad.

Ese intento fallido no perdió nada: devolvió «Su proyecto NO ha sido registrado»
pero los guardados parciales anteriores sostienen todo, y se confirmó tras
recargar.

Quedan sin abrir, porque dependen de ese paso: Información Específica,
Actividades y Bibliografía. «Adjuntar archivos y enviar» no se toca: el operador
saca el reporte PDF, revisa y envía a mano.

### Estudiantes para vincular (datos aportados por el operador)

| Nombre | Documento | Correo | Nivel |
|---|---|---|---|
| Sergio Alejandro Gil Ríos | 1.055.753.057 | segilr@unal.edu.co | pregrado |
| Jerónimo Novoa Giraldo | 1.054.858.413 | jenovoag@unal.edu.co | pregrado |
| Alejandro Patiño Bedoya | 1.002.566.760 | alpatinob@unal.edu.co | maestría |
| Carlos Andrés Pérez | 1.036.660.212 | — | doctorado |

Este cuadro satisface la validación que hoy bloquea el avance: la convocatoria
exige «al menos un estudiante de pregrado o posgrado».

### La búsqueda de Carlos Andrés Pérez en Drive no dio resultado

Se buscó, de forma acotada, en:

- **My Drive por nombre**: `*siun*` (solo aparece la carpeta
  `Anexos_SIUN_Emergencias_2026` que creamos), `*perez*`, `*carlos*`, `*andres*`.
- **My Drive por contenido**: 330 archivos `.xlsx` y `.docx` de hasta 3 MB,
  descomprimiendo y buscando `carlos andr*` y `andres p[eé]rez`. Cero
  coincidencias.
- **My Drive por fecha**: los 25 archivos modificados en las últimas dos
  semanas. Son los anexos de esta corrida y documentos de renta, nada de la
  convocatoria.
- **Unidades compartidas** (`Shared drives`) por nombre: `*siun*`,
  `*focalizada*`, `*emergenc*`, `*convocatoria*`. Solo aparecen convocatorias de
  otros proyectos (neonatos, redes de monitoreo, CHEC).
- **Other computers**, `~/Downloads`, `~/Desktop`, `~/Documents`.
- El anexo `Anexo-2-Carta-Compromiso-Estudiantes.docx` de los insumos es una
  **plantilla en blanco**: tiene los seis espacios de firma y ningún nombre.

Tampoco se pudo usar el MCP de Google Drive: responde «MCP server google-drive
requires sign-in», igual que el de Gmail. La búsqueda quedó limitada al montaje
local de Drive, que no expone el contenido de los archivos nativos de Google
(`.gdoc`, `.gsheet`), que viven solo en la nube.

**Vía mejor.** Cuando el aviso de privacidad esté aceptado, la sección de equipo
trae un buscador de personas de Hermes (`buscarPer2`). Buscar ahí a Carlos
Andrés Pérez es más confiable que buscarlo en Drive: el registro de personas de
la Universidad tiene el documento, y es justamente lo que el formulario necesita.

### La composición de estudiantes queda cerrada en cuatro

El operador entregó la cédula que faltaba, **1.036.660.212** para Carlos Andrés
Pérez, y con ella la lista de estudiantes queda completa:

| Nombre | Documento | Nivel |
|---|---|---|
| Sergio Alejandro Gil Ríos | 1.055.753.057 | pregrado |
| Jerónimo Novoa Giraldo | 1.054.858.413 | pregrado |
| Alejandro Patiño Bedoya | 1.002.566.760 | maestría |
| Carlos Andrés Pérez | 1.036.660.212 | doctorado |

Eso resuelve la discrepancia que una nota anterior dejó abierta. Entonces el
operador había nombrado cinco estudiantes, con **dos** doctorados —Carlos Andrés
Pérez y Diego Armando Pérez—, mientras §9, §11 y §15 declaraban cuatro con uno
solo. La instrucción de hoy nombra cuatro y un único doctorado, de modo que
coincide con el documento y no hay nada que corregir en §9, ni en la fila B.2 de
Hermes, ni en el rubro de contratación de estudiantes.

### Falta un dato que §9 no tiene: las horas semanales

Hermes rechaza el alta de un integrante sin horas de dedicación mayores a cero.
Ya lo hizo antes con la cédula 1002566760: «Por favor verifique la información de
las Horas semanales de dedicación (mayor a 0)».

El problema es que §9 expresa la dedicación en **períodos**, no en horas por
semana: dedicación completa durante los doce meses para el doctorado, un año para
la maestría y cuatro meses para cada pregrado. Convertir eso a horas semanales
agrega un dato nuevo, y no es inocuo: el rubro de contratación de estudiantes son
$50.000.000, así que las horas y los meses tienen que cerrar contra ese monto.
Por eso la conversión la decide el operador y no se infiere aquí.

Lo que sí queda fijo desde §9 es la duración de cada vinculación: 12 meses para
el doctorado y la maestría, 4 meses para cada pregrado.

### El equipo se abre y entran los dos coinvestigadores

El operador aceptó el aviso de privacidad —queda registrado «aceptado por ANDRES
MARINO ALVAREZ MEZA el 08/10/2026 10:46»— y con eso la sección expuso sus
campos: `conoceDatos_input`, `j_id_we_input` (vinculación), `tipodoecv2_input`
(tipo de documento), `documentov2`, `horasCoinv2` (horas por semana),
`horasCoinv3` (meses), `funcionInvestigador` y el botón `buscarPer2`.

| Integrante | Documento | Vinculación | h/s | meses | Valor |
|---|---|---|---:|---:|---:|
| César Germán Castellanos | 79439458 | Profesor carrera docente UN | 2 | 12 | $72.138.336 |
| Jorge Iván Montes | 16074725 | Profesor carrera docente UN | 2 | 12 | $10.991.136 |

Las valoraciones coinciden con las del registro anterior, y la unidad de Jorge
aparece correcta: Departamento de Informática y Computación.

Las funciones se tomaron de §9, no se redactaron de nuevo: Germán responde por el
componente de señal de OE1 y Jorge por el instrumental de OE2.

**Un descuido propio, corregido.** La primera carga de Germán escribió la función
sin tildes («componente de senal», «disena y valida»). Las tildes sí funcionan al
asignar el valor por JavaScript, de modo que el problema fue mío y no del
formulario. La tabla de participantes no tiene editor de fila, así que corregirlo
obligó a eliminarlo y volverlo a cargar; quedó con el mismo valor y el texto ya
acentuado. Conviene revisar la acentuación antes de pulsar «Agregar», porque ese
texto viaja al formulario que lee el evaluador.

### La vinculación de estudiantes no distingue nivel

El catálogo de `j_id_we_input` ofrece cuatro opciones: profesor de la UN fuera de
la carrera docente, profesor de carrera docente, **estudiante pregrado UN** y
**estudiante posgrado UN**. No hay una entrada aparte para doctorado, así que
Alejandro y Carlos Andrés entran como posgrado y el nivel queda declarado en los
productos —que ya distinguen «Estudiante en formación Doctorado» de la tesis de
maestría— y en el campo de función.

### Sigue faltando la dedicación semanal de los estudiantes

Hermes exige horas mayores a cero para dar de alta a cualquier integrante, y ni
§9 ni el TDR las fijan para estudiantes. El TDR habla de horas solo para la
jornada docente (líneas 535 y 548) y sobre estudiantes se limita a exigir «al
menos 1 estudiante de pregrado o posgrado de la Universidad» (línea 395) y a
declarar el apoyo incompatible con monitorías o becas (líneas 353-354).

§9 aporta las duraciones y nada más: doce meses para el doctorado y la maestría,
cuatro meses para cada pregrado. La conversión a horas semanales es un dato nuevo
con efecto presupuestal, porque horas y meses tienen que cerrar contra los
$50.000.000 del rubro de contratación de estudiantes. Por eso la decide el
operador.

### El equipo queda completo y el paso 1 valida

Los cuatro estudiantes entraron con 10 horas semanales, los pregrados por cuatro
meses y los de posgrado por doce, según decidió el operador.

| Integrante | Documento | Vinculación | h/s | meses | Valor |
|---|---|---|---:|---:|---:|
| César Germán Castellanos | 79439458 | Profesor carrera docente UN | 2 | 12 | $72.138.336 |
| Jorge Iván Montes | 16074725 | Profesor carrera docente UN | 2 | 12 | $10.991.136 |
| Carlos Andrés Pérez | 1036660212 | Estudiante posgrado UN | 10 | 12 | $0 |
| Alejandro Patiño Bedoya | 1002566760 | Estudiante posgrado UN | 10 | 12 | $0 |
| Sergio Alejandro Gil Ríos | 1055753057 | Estudiante pregrado UN | 10 | 4 | $0 |
| Jerónimo Novoa Giraldo | 1054858413 | Estudiante pregrado UN | 10 | 4 | $0 |

Los estudiantes valen $0 porque la contrapartida solo valoriza a docentes y
administrativos, tal como advierte la propia nota del formulario. Con el equipo
completo, «Guardar y Avanzar» pasó la validación que antes exigía un estudiante y
el asistente abrió el paso de Información Específica.

### Información Específica: diez campos, y una trampa en los ids

Los ids de los campos **no corresponden a sus etiquetas**, y escribir por nombre
habría desordenado la propuesta entera. El mapeo real, resuelto comparando la
posición vertical de cada etiqueta con la de su campo, es este:

| Campo | Sección real | Caracteres |
|---|---|---:|
| `proyectoActualTitulo1` | Línea temática de investigación | 1.123 |
| `proyectoActualJustificacion` | **Lugar de ejecución** | 1.313 |
| `proyectoActualMetodologia` | **Preguntas de investigación** | 2.581 |
| `proyectoActualTitulo4` | Justificación | 2.945 |
| `proyectoActualTitulo5` | Marco conceptual | 2.867 |
| `proyectoActualTitulo6` | Estado del conocimiento | 3.225 |
| `proyectoActualTitulo7a` | Metodología | 31.596 |
| `proyectoActualTitulo8` | Participantes | 5.996 |
| `proyectoActualTitulo9` | Articulación con comunidades | 8.823 |
| `proyectoActualTitulo10` | Apropiación social | 8.302 |

El contenido salió de `kit_formulario.py`, que convierte las secciones LaTeX a
texto pegable. La línea temática y el lugar de ejecución se recortaron del campo
de identificación, que los trae juntos.

**Cuatro campos tienen un tope de ~4.000 caracteres y no lo declaran.** El primer
intento escribió los textos completos y el servidor los cortó a 3.949, a mitad de
palabra: «los modelos vigente», «su operació», «es una me». Los cuatro afectados
son preguntas de investigación, justificación, marco conceptual y estado del
conocimiento. Se reemplazaron por los condensados que el kit ya traía, todos
bajo el tope y cerrando en frase completa. Conviene verificar que el contenido
quedó distinto en cada campo: el corte a 3.949 en los cuatro hacía sospechar
contaminación cruzada, y no la hubo.

Curiosamente el tope no es general: metodología guarda 31.596 caracteres sin
recorte, y participantes, articulación y apropiación guardan entre 6.000 y 8.800.

### «Guardar y avanzar» falla y bloquea los pasos siguientes

El guardado parcial funciona y los 68.771 caracteres persisten tras recargar.
Avanzar, en cambio, devuelve siempre «Error en el Sistema. Ha ocurrido un error,
puede ignorarlo e intentar de nuevo o reportarlo», con un panel que ofrece
«Intentar de nuevo» y remite al soporte de Hermes en la extensión 11111.

Se descartó el tamaño como causa: con la metodología reducida a su condensado de
5.065 caracteres el error se repite igual. El botón «Intentar de nuevo» despeja
el panel pero no habilita el paso. Actividades y Bibliografía siguen cerradas, y
el diagnóstico está del lado del servidor.

### Defecto del entregable: 36 marcadores internos en el PDF

Los campos de Hermes arrastran marcadores que el proceso de redacción usa para
señalar lo que nadie verificó, y que un evaluador no debería leer:

| Sección | `[inferido]` |
|---|---:|
| §9 Equipo de trabajo | 13 |
| §12 Consideraciones éticas | 12 |
| §17 Articulación con comunidades | 7 |
| §18 Apropiación social | 6 |
| §11 Resultados esperados | 3 |
| §1 Título e identificación | 1 |

El PDF compilado los imprime **36 veces**, así que el problema no es de Hermes
sino del documento. A ellos se suman cuatro marcadores `⟨completar: …⟩` dentro
del campo de participantes, que piden la unidad académica básica de cada docente
con su director, el nombre oficial del grupo de Automática de la UTP, la unidad a
la que está adscrito David Augusto Cárdenas y el nombre del representante de la
UTP que firma las cartas.

No se borraron por decisión deliberada. Cada marca señala un dato que nadie
confirmó, y quitarlas en silencio destruiría justo la señal que el operador
necesita antes de radicar. Lo correcto es verificar esos datos y entonces retirar
las marcas.

### La causa del «Error en el Sistema»: el tope de 4.000 caracteres

El operador habilitó el avance, pero la pestaña de Información Específica llegó
con los diez campos en «NA»: el contenido anterior se había perdido. Al
recargarlos y volver a intentar, el error reapareció, y la bisección lo explicó.

**Los diez campos tienen un tope de 4.000 caracteres, y ninguno lo declara.** El
guardado parcial no valida: acepta el exceso y recorta en silencio, que es lo que
produjo los cortes a mitad de palabra. Avanzar sí valida, y ante un campo
excedido devuelve un error genérico del sistema que no nombra el campo ni el
motivo. Esa asimetría es la que hacía parecer que el problema era del servidor.

Longitudes finales, todas bajo el tope:

| Campo | Sección | Caracteres |
|---|---|---:|
| `Titulo1` | Línea temática | 1.123 |
| `Justificacion` | Lugar de ejecución | 1.313 |
| `Metodologia` | Preguntas de investigación | 2.581 |
| `Titulo4` | Justificación | 2.945 |
| `Titulo5` | Marco conceptual | 2.867 |
| `Titulo6` | Estado del conocimiento | 3.225 |
| `Titulo7a` | Metodología | 3.653 |
| `Titulo8` | Participantes | 3.882 |
| `Titulo9` | Articulación con comunidades | 3.899 |
| `Titulo10` | Apropiación social | 3.573 |

La metodología pasó de 31.596 caracteres a 3.653: se tomó el condensado del kit y
se recortó en una frontera de oración real, no en el carácter 4.000. Los textos
completos quedan en `artefactos/kit/infoesp/`, que es la fuente para el documento
técnico; Hermes recibe la versión que su tope admite.

### Actividades y Bibliografía

Las **15 actividades** son las cinco por objetivo que declara §10, con el mes
inicial y la duración derivados de §14. Hermes las reordena por mes de inicio, no
por objetivo, de modo que el orden visible no coincide con el de la propuesta;
cada descripción empieza por «OE1 ·», «OE2 ·» u «OE3 ·» para que la asociación
quede explícita, como pide el TDR. Las dos filas de prueba que traía el registro
se sobrescribieron.

Dos detalles del formulario que cuestan tiempo si no se saben. El id del textarea
de descripción **está duplicado**: lo comparte con el div de error de validación,
así que `getElementById` devuelve el div y la escritura no registra; hay que
seleccionar por etiqueta `textarea`. Y el botón de alta solo agrega una fila
cuando la última está llena, de modo que el ciclo es llenar y luego agregar.

La **bibliografía** quedó con **106 referencias**, una por fila, extraídas del PDF
ya formateadas en APA. Hubo tres correcciones de parsing: los guiones de corte de
línea («representa- tion»), un bloque que fusionaba doce entradas institucionales,
y la deduplicación. La más larga mide 528 caracteres, muy por debajo del tope.
El botón de alta vive en `j_id_j:j_id_1c`, **sin prefijo `form:`**, y su rótulo
lleva un doble espacio: «Agregar  nueva referencia bibliográfica».

### Estado: el formulario está completo y sin enviar

Los cinco pasos quedaron habilitados y recorridos con «Guardar y avanzar» hasta
`SubirArchivo.xhtml`. **No se pulsó «Enviar proyecto para revisión»**, conforme a
la instrucción: el operador revisa y envía a mano. Queda pendiente adjuntar los
anexos en ese último paso.

### El título vuelve al anterior, y Hermes se alinea con los anexos

El operador decidió conservar el título con el que ya están redactados los nueve
anexos, en lugar de corregirlos uno por uno:

> Sistema de inteligencia artificial portable para la identificación de patrones
> de depresión asociados a estrés postraumático en estudiantes universitarios
> afectados por el sismo

Una precisión sobre esa cadena. El operador la citó sin la cola «afectados por el
sismo», pero los nueve anexos sí la traen, y el propósito del cambio era
justamente que todo coincidiera con ellos. Se usó la versión completa de los
anexos, y la diferencia quedó señalada para que la corrija en una palabra si
prefiere la otra.

El anexo 09, que se había escrito con el título vigente, se devolvió al anterior
y se regeneró su `.docx`. Los diez anexos nombran ahora el mismo proyecto. En
Hermes se reemplazó el campo de título del 69693 y quedó verificado tras
recargar; la lista de proyectos también lo muestra actualizado.

**Queda una inconsistencia, y es deliberada.** El documento técnico en LaTeX
conserva el título nuevo en `main.tex:82`, una sola línea de la portada. No se
tocó porque la instrucción fue actualizar Hermes, y cambiar la portada del
documento es una decisión aparte. Mientras no se haga, el PDF que se adjunta
nombra un proyecto distinto del que Hermes registra.

### El reporte de la propuesta

Se generó desde «Reporte proyecto» en la lista de proyectos: `formato-proyecto.pdf`,
**30 páginas**, con el código 69693, la convocatoria focalizada, modalidad única,
tipología 2020100-Investigación aplicada, estado «Ingresando Proyecto», duración
de doce meses y el título ya corregido.

El PDF se sirve como respuesta de un solo uso a un envío de formulario: un GET
posterior a la misma dirección devuelve el HTML de la lista, no el documento. Por
eso no hay enlace estable que compartir ni forma de recuperarlo por URL. Queda
abierto en una pestaña del navegador controlado, y el botón de descarga del visor
abre un diálogo nativo del sistema que esta sesión no puede operar: ese clic lo
da el operador. Una captura de la primera página quedó en
`artefactos/kit/reporte_69693.png` como constancia de lo que el reporte contiene.
