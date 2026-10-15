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
