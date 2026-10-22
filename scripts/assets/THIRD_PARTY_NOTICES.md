# Activos de terceros

## three.js r128

| Campo | Valor |
|---|---|
| Archivo | `scripts/assets/three-r128.min.js` |
| Origen | `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js` |
| Tamaño | 603 445 bytes |
| SHA-256 | `9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2` |
| Licencia | MIT, Copyright 2010-2021 Three.js Authors |

`scripts/graph_html.py` lo empotra en el HTML que genera, de modo que el grafo se
abre sin conexión. Antes el template lo cargaba desde ese CDN con un comentario que
prometía un «fallback interno» que nunca existió: sin red, el grafo no se dibujaba
y nada lo decía.

Para actualizarlo: descargar la versión nueva, reemplazar el archivo, actualizar
aquí el tamaño y el `SHA-256`, y regenerar los grafos. El bundle no debe contener
la secuencia `</script`, porque rompería el HTML que lo empotra; el generador lo
verifica y se niega si aparece.

## papersmith-ai: constelación SOTA (visor `atlas3d` y scripts)

| Campo | Valor |
|---|---|
| Archivos | `scripts/assets/atlas3d.bundle.js`, `scripts/check_atlas.py`, `scripts/render_atlas.py` |
| Origen | `https://github.com/LIAUNAL/papersmith-ai` (commit `0f71a7dc`): `skills/plausibility/assets/atlas3d.bundle.js`, `skills/plausibility/scripts/check_atlas.py` y `skills/plausibility/scripts/render_atlas.py` |
| SHA-256 del bundle original | `6844f195f1a5b46e9461fd36b1879bd7dd688ccdea3c61e04a4045352af3b7e0` |
| SHA-256 del bundle en Morfeo | `ae4b872c7a4945d87b6dbda50540facd07101ef12eeed1c7f6ce8f3f74373778` |
| Licencia | Apache License 2.0 |

El bundle se copia sin cambios; solo se le antepone un comentario de una línea que
nombra su origen y esta licencia. Los dos scripts son adaptaciones: ids `paper-N`,
fidelidad de citas contra `artefactos/scoping/papers/paper-N.md`, de 1 a 7
familias, interfaz en español, mensaje `atlas-control` del tablero y el panel
«Estudio de constelaciones». Cada archivo portado conserva en su cabecera la nota
de origen y licencia, como pide la sección 4 de la Apache License 2.0.

### three.js y OrbitControls (dentro de `atlas3d.bundle.js`)

- Versión: 0.186.1 (npm `three`)
- Origen: https://github.com/mrdoob/three.js
- Módulos: el núcleo `three` y `three/examples/jsm/controls/OrbitControls.js`
- Licencia: MIT, Copyright © 2010-2026 three.js authors

```text
The MIT License

Copyright © 2010-2026 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

Para actualizar el bundle: copiar el de papersmith-ai, volver a anteponer el
comentario de origen y actualizar aquí ambos `SHA-256`. Igual que el bundle de
three.js r128, no debe contener la secuencia `</script`; `render_atlas.py` lo
verifica y se niega a empotrarlo si aparece.
