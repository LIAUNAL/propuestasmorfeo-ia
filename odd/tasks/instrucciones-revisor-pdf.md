# Puente de instrucciones del revisor PDF al agente del pipeline

Corrida `2026-09-tept-depresion-ia-portable`. El operador marcó un pasaje del
manuscrito con **Comentario** pidiendo humanizar el resumen y reescribir una
frase para que no nombrara a la psicóloga Camila. Pulsó «Ejecutar cambios y
recompilar» y el documento no cambió.

## Specs

S1. Reporte del operador, textual:

> revisa que los botones de tachar, comentarios, humanizar y demas en
> previsuailzador pdf si esten efectuando lso cambios en los artefactos e
> insumos del manuscrito. por ej, pedi como comentario en resumen que se
> humanizara, y luego que se reescribiera para que no se hiciera mencion
> explicita a la psicologa camila, y el documento no se actualizo al darle
> efectuar cambios y recompilar

S2. Causa reproducida: para una marca de tipo comentario, `apply_pdf_annotations`
insertaba `% [COMENTARIO REVISOR PDF - Pág N]: <instrucción>` arriba del ancla.
La línea se escribía, el PDF se recompilaba y el informe declaraba «1 comentario
incorporado», pero LaTeX ignora lo que empieza por `%`, así que el documento no
podía cambiar. Evidencia: `pdftotext` encuentra el marcador 0 veces en
`main.pdf`, y «psicóloga Camila» seguía apareciendo 29 veces.

S3. Decisión del operador sobre la aplicación, textual: **«Puente al agente del
pipeline»**. El visor deja de afirmar que aplicó un cambio: registra la
instrucción en un archivo de pendientes que el `redactor` consume al continuar
el pipeline.

S4. Decisión del operador sobre el marcador ya escrito, textual: **«Retíralo de
la fuente»**. Se retiró de `redaccion/sections/00_frontmatter.tex`.

S5. Lo que un comentario debe y no debe hacer:
- **No** toca la fuente LaTeX ni el manuscrito compilado.
- **Sí** se registra en `artefactos/pipeline/instrucciones_revisor_pdf.md`, con
  página, texto ancla, instrucción y archivo de sección cuando se pudo ubicar.
- Se registra aunque el ancla no se localice: la localización era requisito de
  las marcas que modifican texto, no de las que instruyen.
- El archivo se anexa y deduplica por firma; nunca se reescribe desde cero,
  porque una instrucción sin ejecutar no se recupera de ningún otro sitio.

S6. Una corrida que solo registra comentarios no recompila: recompilar sin
cambios produce un PDF idéntico y refuerza la ilusión de que algo se aplicó.

S7. El contrato del pipeline incorpora el archivo: antes de cerrar la siguiente
unidad, el `redactor` aplica las instrucciones pendientes y `grant-flow-auditor`
pule el resultado.

## Tareas

- [x] T1 Reproducir el fallo y aislar la causa (S1, S2)
- [x] T2 Retirar el marcador de la fuente (S4)
- [x] T3 Ejecutor: registrar en lugar de escribir, con deduplicación (S3, S5)
- [x] T4 Ejecutor: no recompilar sin cambios y reportar la razón (S6)
- [x] T5 Panel: el resumen y el historial dejan de afirmar un cambio aplicado (S3, S6)
- [x] T6 Contrato del pipeline y puertos regenerados (S7)
- [x] T7 Commits de la unidad

## Log

L1 (2026-10-15, pedido original): revisa que los botones de tachar, comentarios,
humanizar y demas en previsuailzador pdf si esten efectuando lso cambios en los
artefactos e insumos del manuscrito. por ej, pedi como comentario en resumen que
se humanizara, y luego que se reescribiera para que no se hiciera mencion
explicita a la psicologa camila, y el documento no se actualizo al darle efectuar
cambios y recompilar.

L2 (2026-10-15, decisiones): ante la pregunta de cómo deben llegar las
instrucciones al manuscrito, el operador eligió «Puente al agente del pipeline»;
sobre el marcador ya escrito, eligió «Retíralo de la fuente».

L3 (2026-10-15, prueba primero): se escribieron cinco pruebas y se observó el
rojo: 8 pruebas del ejecutor, 2 fallos y 3 errores. Después de la implementación
quedan verdes, y la suite completa pasa de 140 a 144 pruebas.

L4 (2026-10-15, alcance de lo que sí reescribe): **Tachar** borra el texto del
ancla en la fuente, y **Humanizar** pasa el ancla por `_humanize_text_span`, que
retira catorce muletillas de una lista cerrada. Ninguna de las dos reescribe
sentido, así que la instrucción «quitar la mención explícita a la psicóloga
Camila» solo puede ejecutarla un agente.
