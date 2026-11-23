---
description: Busca convocatorias de financiación afines a la idea del proyecto y al banco LIA (Colombia, América Latina e internacionales, en español e inglés), con cobertura nacional obligatoria (Minciencias, SGR, ministerios, UNAL, retos empresariales) y las deja en la pestaña «Convocatorias» del tablero; con `iniciar <id>` baja el TdR de una convocatoria a la corrida activa.
argument-hint: "[buscar] [--alcance proyecto|banco] | iniciar <id>"
---

# /propuesta-convocatorias: convocatorias afines al proyecto

Encuentra convocatorias abiertas o próximas para investigadores, estudiantes,
grupos, centros, universidades y empresas, con el rol que un solicitante
colombiano puede tener en cada una. Sirve en los dos flujos (`base` y `sgr`)
y no necesita una corrida activa para buscar.

En Colombia la búsqueda consulta siempre las fuentes obligatorias del
catálogo (Minciencias, la Asignación para la CTeI del SGR, OCAD Paz,
iNNpulsa, la Vicerrectoría de Investigación de la UNAL, MinEducación y la
Agencia Atenea) y suma las regionales y locales de la sede del perfil, entre
ellas los retos empresariales. Cada convocatoria registra su nivel
(nacional, regional, local o institucional), y `check` falla si falta una
fuente obligatoria, si un conteo no cuadra con lo registrado o si dos
convocatorias comparten URL. Hermes se lee solo con la sesión que el
operador tenga abierta en Chrome.

Entrada:

$ARGUMENTS

## 1. Resolver el espacio de trabajo

1. `WORKSPACE` es la carpeta que contiene `.morfeo/config.json` (o
   `.marco/config.json`), es decir, la raíz de este proyecto.
2. Si `proposals/.current-run` existe y no está vacío, `RUN_ROOT` es
   `proposals/<run-id>/`; si no, no hay corrida activa.

## 2. Modo

- Entrada vacía o `buscar`: modo `buscar` con alcance `proyecto`.
- `buscar --alcance proyecto|banco`: modo `buscar` con ese alcance
  (`proyecto`: afines a la idea del proyecto en formulación; `banco`: afines a
  todo el laboratorio según el banco LIA).
- `iniciar <id>`: modo `iniciar`, con `<id>` en minúsculas, dígitos y guiones.
  Cualquier otra entrada: mostrá el uso (`/propuesta-convocatorias [buscar]
  [--alcance proyecto|banco] | iniciar <id>`) y detenete.

## 3. Despachar

En `buscar`, antes de despachar, corré
`python3 scripts/convocatorias.py progreso <WORKSPACE> --reiniciar --alcance
<alcance>`: deja en cero la barra de avance del tablero para esta búsqueda.

Despachá con `Task` al agente `explorador-convocatorias`, con `WORKSPACE`
absoluto, el modo, el alcance (en `buscar`), el `<id>` si lo hay y `RUN_ROOT` absoluto si hay corrida
activa. El agente escribe solo en `convocatorias/` (y, en `iniciar`, en
`<RUN_ROOT>/insumos/tdr/`).

## 4. Mostrar el resultado

En `buscar`, con el agente de vuelta, corré
`python3 scripts/convocatorias.py datos <WORKSPACE> --alcance <alcance>` y
mostrá:

- vigentes frente al total, por ámbito (Colombia, América Latina,
  internacional), por nivel en Colombia (nacional, regional, local,
  institucional) y por rol de Colombia;
- las diez primeras: match, días para el cierre, rol y título;
- la cobertura nacional: las líneas «cobertura nacional: …» que `datos`
  imprime al final (fuentes obligatorias sin consultar, conteos que no
  cuadran) o, si no hay ninguna, que la cobertura está completa;
- las fuentes `bloqueado`, `requiere_sesion` o `error`;
- el siguiente paso: abrir la pestaña «Convocatorias» del tablero, o
  `/propuesta-convocatorias iniciar <id>` para empezar una propuesta con una
  de ellas.

En `iniciar`, repetí lo que devolvió el agente: dónde quedó el TdR y que el
siguiente comando es `/propuesta-analizar`, o que primero hay que crear la
corrida con `/propuesta-init`.
