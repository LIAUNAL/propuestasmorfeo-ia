# Pendientes al cierre del tablero y los lotes

Documento de traspaso. Recoge lo entregado, lo que quedó pendiente y por qué,
para que otra sesión pueda continuar sin releer la conversación.

## Entregado

`main` está en `d072399` y empujado. Contiene, en orden:

- **Trozo 1** (`8b20dff`): el visor de tira continua, el cierre de sus carreras de
  render y el arnés jsdom que las observa.
- **Trozo 2** (`3788dcd`): el puente al revisor PDF, con la cola de instrucciones
  anexada y nunca truncada, el ancla vacía que falla en voz alta y los contadores
  honestos.
- **Marcador** (`904ba3d`): `.marco/version`, para que `morfeo ui` arranque.
- **Documentos** (`d072399`): el campo «Reemplazar por» y la cola visible en el
  contrato del pipeline, con los puertos y el kit regenerados.

Suites en `main`: 14 pruebas en el arnés jsdom y 154 en Python, en verde.

## Pendiente, con el paso exacto

### 1. El panel sobre `main`: conflicto de tres archivos

El cherry-pick de `59aa20f` choca en `src/morfeo/core/pdf_annotator.py`,
`src/morfeo/dashboard/static/index.html` y `tests/test_pdf_annotator.py`. No es
elegir un lado, hay que combinar.

- En el ejecutor: conservar la reparación (cola anexada, `comments_duplicated`,
  `annotations_failed`, ancla vacía que falla) y sumar el reemplazo determinista.
- En el tablero: conservar el resumen que nombra lo no aplicado y sumar la tarjeta
  con «Reemplazar por» y el contador de pendientes.
- En las pruebas: quedarse con los dos juegos, recordando que la reparación
  sustituyó la aserción vacía `comments_failed == 0`.

### 2. Los trozos 3, 4 y 5

Cherry-pick por unidad, cada uno con su verificación independiente antes de
fusionar: `U1+U2` (`740bbed`, `310e93f`), `U4+U5+U3` (`83dad4f`, `2358aa4`,
`377b0c3`) y `U6a` solo (`eb6a967`).

### 3. Los huecos defensivos del sellado del visor

Cuatro, ya enumerados: la guarda de reentrada del recargado concurrente, la tira
que no se reconstruye en el camino de error, dos pruebas de carrera que pasan de
forma vacía contra el código original, y las escrituras de solo liberación que
dispara el desplazamiento.

### 4. Las tres del grafo y el panel del PDF

`U6b` (paleta, aristas punteadas e iluminación del contrato), `U7` (grafo del
manuscrito con spec autorizada y auditoría mecánica de los cuatro pares de
trazabilidad) y mostrar el último PDF compilado en el panel del manuscrito.

## Notas operativas

- **El marcador no lleva manifiesto, y es deliberado.** `morfeo ui` solo exige que
  `.marco` sea un directorio; `audit` y `upgrade` piden además `manifest.json`
  para tratar el directorio como un kit instalado, y `upgrade` podría sobrescribir
  las fuentes del marco. Sin manifiesto esos comandos se niegan en lugar de tocar
  nada. Si molesta el error, el arreglo sano es que `morfeo ui` reconozca el
  repositorio del marco por su estructura.
- **El proveedor de revisión declinó cinco candidatos seguidos.** No es cuestión
  de tamaño: trocear más no compra su revisión. Para esa segunda opinión, la
  palanca es el interruptor del clon.
- **`proposals/` no está versionado**, así que los `.tex` de la corrida no tienen
  `git diff`. Lo que se cambie ahí solo se recupera del archivo de instrucciones o
  del respaldo que se haga antes.
- **El PDF de la corrida** se recompiló tras generalizar el nombre propio: 59
  páginas, con dos advertencias de paquete anteriores a estos cambios.

## Recuperar la rama pendiente

`feat/visor-pdf-scroll-continuo` quedó empujada a `origin` antes de borrar la
copia local, porque sostenía el panel y los trozos 3 a 5. Su punta es `6318c0b`.
Para recuperarla:

```bash
git switch -c feat/visor-pdf-scroll-continuo origin/feat/visor-pdf-scroll-continuo
```

## Log

- **L1** (operador, literal): «deja la anotacion, comit, elimina ramas y push,
  necesitamos cerrar aca».
