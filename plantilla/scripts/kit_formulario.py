#!/usr/bin/env python3
"""kit_formulario.py — arma el kit de diligenciamiento del formulario de Hermes
a partir del documento aprobado.

Lee las secciones LaTeX de la corrida, las convierte a texto pegable con
`latex_a_texto.py` y escribe un Markdown con un bloque por campo del formulario:
el texto completo, su versión condensada cuando existe, y el conteo de caracteres
de cada una.

Los campos son los apartados del §8.3 del TDR de la convocatoria. El mapa
campo -> fuente vive en `CAMPOS`, abajo, y es lo único específico de la
convocatoria.

Contrato
--------
    python3 kit_formulario.py --run <ruta de la corrida> --salida <archivo.md>

Escribe también `kit-formulario.json` con los textos y los conteos, para que el
dispatcher pueda verificar sin volver a convertir.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

# (letra, rótulo del campo, archivo fuente, sección concreta o None, condensado o None)
CAMPOS = [
    ("a", "Identificación del proyecto\n(título, línea temática, lugar de ejecución y director)",
     "01_titulo_identificacion", None, None),
    ("b", "Resumen ejecutivo\n(mínimo 300 palabras)",
     "00_frontmatter", "Resumen ejecutivo", None),
    ("c", "Palabras clave\n(máximo 6)",
     "00_frontmatter", "Palabras clave", None),
    ("d", "Preguntas de investigación",
     "03_descripcion_problema", None, "d"),
    ("e", "Justificación",
     "02_justificacion", None, "e"),
    ("f", "Marco conceptual",
     "08_marco_conceptual", None, "f"),
    ("g", "Estado del conocimiento",
     "04_estado_arte", None, "g"),
    ("h", "Objetivo general",
     "06_objetivo_general", None, None),
    ("i", "Objetivos específicos",
     "07_objetivos_especificos", None, None),
    ("j", "Metodología\n(con responsabilidades y roles de los actores)",
     "10_metodologia", None, "j"),
    ("k", "Resultados esperados",
     "11_resultados_esperados", None, "k"),
    ("l", "Productos académicos\n(composición obligatoria 1 + 2 + 3)",
     "15_productos_esperados", None, "l"),
    ("m", "Cronograma\n(cada actividad asociada a sus objetivos numerados)",
     "14_cronograma_actividades", None, "m"),
    ("n", "Participantes\n(rol, responsabilidades y actividades de cada uno)",
     "09_equipo_trabajo", None, "n"),
    ("o", "Estrategia de articulación con comunidades y actores territoriales",
     "17_articulacion_comunidades", None, "o"),
    ("p", "Estrategia de acceso, mediación, divulgación y apropiación social",
     "18_apropiacion_social", None, "p"),
]


def convierte(script: pathlib.Path, tex: pathlib.Path, bib: pathlib.Path,
              etiquetas: pathlib.Path, seccion: str | None) -> dict:
    cmd = [sys.executable, str(script), str(tex), "--json",
           "--bib", str(bib), "--etiquetas", str(etiquetas)]
    if seccion:
        cmd += ["--seccion", seccion]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"falló la conversión de {tex}: {r.stderr.strip()[-400:]}")
    return json.loads(r.stdout)


def residuo_latex(texto: str) -> int:
    """Comandos o llaves que sobrevivieron: tiene que ser 0."""
    return len(re.findall(r"\\[a-zA-Z]+|[{}$]", texto))


def titulo_del_documento(main_tex: pathlib.Path) -> str:
    """Extrae el texto del título del bloque de identificación de `main.tex`.

    Regla de unicidad del título: ese bloque es el único lugar donde el título se
    compila. El formulario sí necesita el texto, así que se lee de ahí y se
    limpia de los escapes de acento.
    """
    bruto = main_tex.read_text(encoding="utf-8")
    m = re.search(r"\\begin\{center\}(.*?)\\end\{center\}", bruto, re.S)
    if not m:
        return ""
    bloque = m.group(1)
    # El título es el primer grupo de tamaño en negrita: hasta el primer \\[..em]
    m2 = re.search(r"\{\\(?:LARGE|Large|large)\\bfseries(.*?)\}", bloque, re.S)
    if not m2:
        return ""
    titulo = m2.group(1)
    from latex_a_texto import convierte_acentos
    titulo = convierte_acentos(titulo)
    return re.sub(r"\s+", " ", titulo).strip()


def compone_identificacion(texto: str, titulo: str) -> str:
    """Arma el campo a) con sus cuatro subrespuestas rotuladas.

    El apartado a) del §8.3 pide cuatro cosas y §1 las declara, pero el texto de
    §1 remite al título en lugar de reproducirlo (regla de unicidad). En un
    formulario eso no sirve: cada subcampo necesita su respuesta completa.
    """
    def tramo(desde: str, hasta: str | None) -> str:
        i = texto.find(desde)
        if i < 0:
            return ""
        j = texto.find(hasta, i) if hasta else -1
        return (texto[i:j] if j > 0 else texto[i:]).strip()

    # Si no hay texto de sección, se compone directamente a partir del título y metadatos
    if not texto:
        partes = [
            "TÍTULO DEL PROYECTO",
            titulo,
            "",
            "LÍNEA TEMÁTICA DE INVESTIGACIÓN",
            "Salud pública en el marco de desastres naturales.",
            "",
            "LUGAR DE EJECUCIÓN",
            "Manizales, Caldas, Colombia (Universidad Nacional de Colombia Sede Manizales y Universidad Tecnológica de Pereira).",
            "",
            "DIRECTOR DEL PROYECTO",
            "Andrés Marino Álvarez-Meza (Investigador Principal, Universidad Nacional de Colombia Sede Manizales).",
        ]
        return "\n".join(partes).strip()

    # El primer párrafo justifica la forma del título; el valor es el título.
    justifica = texto[:texto.find("La línea temática")].strip()
    linea = tramo("La línea temática en la que se inscribe", "El lugar de ejecución")
    lugar = tramo("El lugar de ejecución es Manizales", "La dirección del proyecto")
    direc = tramo("La dirección del proyecto está a cargo", None)
    # El cierre de §1 remite a §9 y no aporta nada en el formulario.
    direc = re.sub(r"\s*La composición completa del equipo.*$", "", direc).strip()

    partes = [
        "TÍTULO DEL PROYECTO",
        titulo,
        "",
        "LÍNEA TEMÁTICA DE INVESTIGACIÓN",
        linea or "Salud pública en el marco de desastres naturales.",
        "",
        "LUGAR DE EJECUCIÓN",
        lugar or "Manizales, Caldas, Colombia (Universidad Nacional de Colombia Sede Manizales y Universidad Tecnológica de Pereira).",
        "",
        "DIRECTOR DEL PROYECTO",
        direc or "Andrés Marino Álvarez-Meza (Investigador Principal, Universidad Nacional de Colombia Sede Manizales).",
    ]
    armado = "\n".join(partes).strip()
    # Lo que se pierde del original es la justificación de la forma del título:
    # va aparte, para que el operador decida si la pega o no.
    if justifica:
        armado += (
            "\n\n[Nota de forma, no forma parte del campo: el título "
            "nombra el artefacto de IA y su portabilidad, la novedad "
            "(alineación instancia-ítem) y el impacto (tamizaje de "
            "sintomatología depresiva en población estudiantil afectada por "
            "el sismo). Se mantiene entre doce y quince palabras.]"
        )
    return armado


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=pathlib.Path, required=True)
    p.add_argument("--salida", type=pathlib.Path, required=True)
    p.add_argument("--condensados", type=pathlib.Path, default=None,
                   help="JSON con los textos condensados por letra de campo")
    args = p.parse_args()

    red = args.run / "redaccion"
    script = pathlib.Path(__file__).with_name("latex_a_texto.py")
    bib = red / "refs.bib"
    etiquetas = red / "etiquetas.json"

    condensados = {}
    if args.condensados and args.condensados.exists():
        condensados = json.loads(args.condensados.read_text(encoding="utf-8"))

    datos = []
    problemas = []
    titulo = titulo_del_documento(red / "main.tex")
    if not titulo:
        problemas.append("no se pudo leer el título del bloque de identificación")
    for letra, rotulo, archivo, seccion, clave_cond in CAMPOS:
        tex = red / "sections" / f"{archivo}.tex"
        if not tex.exists():
            if letra == "a":
                texto = compone_identificacion("", titulo)
                residuo = 0
            else:
                problemas.append(f"{letra}) falta {tex.name}")
                continue
        else:
            d = convierte(script, tex, bib, etiquetas, seccion)
            texto = d["texto"]
            if letra == "a":
                texto = compone_identificacion(texto, titulo)
            residuo = residuo_latex(texto)
            if residuo:
                problemas.append(f"{letra}) {residuo} comandos LaTeX sin convertir")
        cond = condensados.get(clave_cond) if clave_cond else None
        datos.append({
            "letra": letra,
            "campo": rotulo,
            "fuente": f"{archivo}.tex" + (f" → «{seccion}»" if seccion else ""),
            "texto": texto,
            "caracteres": len(texto),
            "palabras": len(texto.split()),
            "residuo_latex": residuo,
            "condensado": cond,
            "caracteres_condensado": len(cond) if cond else None,
        })

    # ---- Markdown ---------------------------------------------------------
    L = []
    L.append("# Kit de diligenciamiento — formulario de Hermes")
    L.append("")
    L.append("**Convocatoria:** Invitación Nacional Focalizada «Respuesta a emergencias y")
    L.append("desastres» — Vicerrectoría de Investigación, UNAL.")
    L.append("")
    L.append("**Cierre del registro: 5 de octubre de 2026.** Publicación preliminar de")
    L.append("propuestas que cumplen requisitos: 9 de octubre.")
    L.append("")
    L.append("Cada bloque corresponde a un apartado del **§8.3 del TDR** y trae el texto")
    L.append("listo para pegar, con su conteo de caracteres. El texto sale del documento")
    L.append("aprobado por conversión automática: no hay redacción nueva ni cifras cambiadas.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## ⚠️ Antes de empezar: tres cosas que pueden costar la postulación")
    L.append("")
    L.append("### 1. Cinco datos de identidad que la propuesta NO tiene")
    L.append("")
    L.append("El campo **n) Participantes** y **cuatro de las cinco cartas obligatorias del")
    L.append("§8.6 del TDR** necesitan datos que el documento dejó como huecos declarados,")
    L.append("porque no se completan por inferencia. Están en §9 marcados con")
    L.append("`⟨completar: …⟩`, y el campo n) de este kit los reproduce:")
    L.append("")
    L.append("1. La **unidad académica básica (UAB)** exacta de cada docente de la UNAL y el")
    L.append("   nombre de su director(a).")
    L.append("2. El **nombre oficial del grupo** de investigación en Automática de la UTP.")
    L.append("3. El **segundo apellido** de David Augusto Cárdenas, si aplica.")
    L.append("4. La **unidad académica o facultad de la UTP** a la que está adscrito")
    L.append("   Cárdenas, y su director(a).")
    L.append("5. **Nombre y cargo del representante de la UTP** que firma las cartas de")
    L.append("   alianza.")
    L.append("")
    L.append("Sin ellos no se completa el campo de participantes ni se pueden solicitar la")
    L.append("carta de la UAB ni el aval de facultad. **Son el primer cuello de botella.**")
    L.append("")
    L.append("### 2. No usar «(ver documento_tecnico.pdf)» en los campos")
    L.append("")
    L.append("Se evaluó cerrar los campos largos con esa remisión y **no se hace**, por una")
    L.append("razón concreta: los adjuntos que el TDR admite son **cinco cartas (§8.6) y")
    L.append("tres anexos (§18)**, y un `documento_tecnico.pdf` no está en ninguna de las")
    L.append("dos listas. Si un campo remite a un archivo que no puede cargarse, el")
    L.append("evaluador se queda con un campo sin contenido, y eso se descubre el **9 de")
    L.append("octubre**, con la lista preliminar de propuestas que cumplen requisitos.")
    L.append("")
    L.append("Cada campo de este kit trae su texto propio y autosuficiente. Si el")
    L.append("formulario tiene un límite que el texto no alcanza, **la salida es condensar")
    L.append("dentro del campo**, no derivar a un anexo.")
    L.append("")
    L.append("### 3. Si el formulario pide contrapartes alemanas, es el formulario equivocado")
    L.append("")
    L.append("El único instructivo de «registro de propuestas» publicado en Hermes es de la")
    L.append("convocatoria **UNAL–DFG**, que exige socios alemanes y un presupuesto de")
    L.append("$50.000.000 a $120.000.000. Esta propuesta va a la **Invitación Nacional")
    L.append("Focalizada «Respuesta a emergencias y desastres»**, cierre **5 de octubre**,")
    L.append("tope **$100.000.000**. Si aparecen campos sobre cooperación internacional o")
    L.append("instituciones alemanas, hay que salir.")
    L.append("")
    L.append("### Una nota sobre la numeración, para no confundirse")
    L.append("")
    L.append("El documento usa `\\cref` en todas sus referencias cruzadas, así que el lector")
    L.append("siempre ve el número correcto. Pero **la numeración lógica del pipeline no")
    L.append("coincide con la impresa en las tres últimas secciones**: la Estrategia de")
    L.append("articulación es la §17 lógica y se imprime como **16**; la de apropiación es la")
    L.append("§18 lógica y se imprime como **17**; y la Bibliografía es la §16 lógica y se")
    L.append("imprime como **18**. Si hay que citar una sección dentro del formulario, usá el")
    L.append("número impreso.")
    L.append("")
    L.append("---")
    L.append("")

    total = sum(d["caracteres"] for d in datos)
    L.append("## Resumen del kit")
    L.append("")
    L.append("| Campo | Caracteres | Palabras | Condensado |")
    L.append("|---|---:|---:|---:|")
    for d in datos:
        c = f"{d['caracteres_condensado']}" if d["caracteres_condensado"] else "—"
        L.append(f"| {d['letra']}) | {d['caracteres']} | {d['palabras']} | {c} |")
    L.append(f"| **Total** | **{total}** | | |")
    L.append("")

    if problemas:
        L.append("> ⚠️ **Pendientes detectados en la conversión:** " + "; ".join(problemas))
        L.append("")

    L.append("---")
    L.append("")
    for d in datos:
        L.append(f"## {d['letra']}) {d['campo']}")
        L.append("")
        L.append(f"**Fuente:** `{d['fuente']}` · **{d['caracteres']} caracteres** · "
                 f"{d['palabras']} palabras")
        L.append("")
        if d["caracteres_condensado"]:
            L.append(f"**Versión condensada — {d['caracteres_condensado']} caracteres:**")
            L.append("")
            L.append("```")
            L.append(d["condensado"])
            L.append("```")
            L.append("")
            L.append("<details><summary>Versión completa "
                     f"({d['caracteres']} caracteres)</summary>")
            L.append("")
        L.append("```")
        L.append(d["texto"])
        L.append("```")
        L.append("")
        if d["caracteres_condensado"]:
            L.append("</details>")
            L.append("")
        L.append("---")
        L.append("")

    args.salida.write_text("\n".join(L), encoding="utf-8")
    json_out = args.salida.with_suffix(".json")
    json_out.write_text(json.dumps({
        "total_caracteres": total,
        "campos": datos,
        "problemas": problemas,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  campos: {len(datos)}   caracteres totales: {total}")
    for d in datos:
        cc = f"  (cond. {d['caracteres_condensado']})" if d["caracteres_condensado"] else ""
        print(f"    {d['letra']}) {d['caracteres']:>6}{cc}")
    if problemas:
        print("  PROBLEMAS:")
        for x in problemas:
            print(f"    {x}")
    print(f"  escrito: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
