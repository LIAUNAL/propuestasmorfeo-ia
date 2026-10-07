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
