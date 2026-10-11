#!/usr/bin/env python3
"""latex_a_texto.py — convierte una fuente LaTeX de la propuesta en texto plano
pegable en un formulario web.

Para qué sirve
--------------
El formulario de Hermes pide el contenido del proyecto en campos de texto. La
fuente de verdad es LaTeX, que no se puede pegar. Este script produce el texto
equivalente: sin comandos, sin llaves, con los acentos y las comillas tal como
los recibe un `<textarea>`.

Qué convierte
-------------
- Comentarios `%` fuera.
- Comandos de acento a Unicode:  \\'a -> á, \\~n -> ñ, \\c{c} -> ç, \\ss -> ß.
- Comandos de formato que se quedan con su contenido: \\textbf, \\emph, \\textit,
  \\texttt, \\textsuperscript, \\underline, \\mbox.
- Comandos que se eliminan con su argumento: \\label, \\index.
- Citas: \\citep{...} -> (Apellido et al., año); \\citet{...} -> Apellido et al. (año).
  Los datos salen de `refs.bib`, igual que los resolvería apalike.
- Referencias cruzadas \\cref/\\Cref -> el nombre legible del destino, tomado de
  `etiquetas.json` (lo escribe el propio script al leer `main.aux` o, si no existe,
  de una tabla declarada).
- Tablas `tabularx`/`tabular` -> líneas separadas por ` | `.
- Entornos que se omiten por completo: tikzpicture, ganttchart, pgfonlayer.
- Entornos que se recorren quitando solo las marcas: enumerate, itemize, table,
  figure, minipage, center.

Qué NO hace
-----------
No resume ni reordena nada. La salida es el texto del documento, íntegro. La
condensación es una decisión editorial y va aparte.

Contrato
--------
    python3 latex_a_texto.py <archivo.tex> [--bib refs.bib] [--etiquetas map.json]
                             [--json] [--chars]

La salida a stdout es el texto plano, o un objeto JSON con `texto`, `caracteres`
y `caracteres_sin_espacios` cuando se pide `--json`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import unicodedata

# --------------------------------------------------------------------------
# Comandos de acento -> Unicode
# --------------------------------------------------------------------------

# Acentos cuyo comando es un signo de puntuación: no pueden confundirse con el
# nombre de otro comando, así que se admiten en las dos formas, \'a y \'{a}.
ACENTOS_PUNTUACION = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", "\"": "\u0308",
    "~": "\u0303", "=": "\u0304", ".": "\u0307",
}

# Acentos cuyo comando es una LETRA. Estos SOLO se admiten con llaves, \c{c}.
# Sin llaves, \caption se leería como cedilla + "aption". Es un bug real que
# corrompe cualquier palabra que empiece por c, d, b, u, v, k, r o H.
ACENTOS_LETRA = {
    "c": "\u0327", "d": "\u0323", "b": "\u0331", "u": "\u0306",
    "v": "\u030c", "k": "\u0328", "r": "\u030a", "H": "\u030b",
}

ACENTOS = {**ACENTOS_PUNTUACION, **ACENTOS_LETRA}

# Comandos de formato que se quedan con su contenido.
CONSERVA_CONTENIDO = [
    "textbf", "textit", "textsl", "texttt", "textsc", "textrm", "textsf",
    "emph", "underline", "mbox", "textsuperscript", "textsubscript",
    "textnormal", "textup", "textmd", "text",
]

# Comandos que se eliminan con su argumento.
BORRA_CON_ARGUMENTO = ["label", "index", "footnote", "vspace", "hspace", "hypertarget",
                       "phantomsection", "addcontentsline", "protect", "includegraphics"]

# Entornos que se omiten por completo (figuras y diagramas: no van a un formulario).
ENTORNOS_OMITIDOS = ["tikzpicture", "ganttchart", "pgfonlayer", "verbatim", "lstlisting"]

# Entornos cuyas marcas se quitan y se recorre el contenido.
ENTORNOS_RECORRIDOS = ["enumerate", "itemize", "description", "table", "figure",
                       "minipage", "center", "flushleft", "flushright", "small",
                       "footnotesize", "scriptsize", "quotation", "abstract", "tabularx",
                       "tabular", "thebibliography"]


def _compone(base: str, acento: str) -> str:
    """Aplica un acento combinante y normaliza a la forma precompuesta."""
    return unicodedata.normalize("NFC", base + acento)


def convierte_acentos(texto: str) -> str:
    r"""Convierte \'a, \'{a}, \~n, \c{c}, \ss y similares a Unicode."""

    def aplica(cmd: str, arg: str) -> str:
        return _compone(arg, ACENTOS[cmd])

    # Forma con llaves: \'{a}  \~{n}  \c{c}
    letras_llave = "|".join(re.escape(c) for c in ACENTOS_LETRA)
    texto = re.sub(
        r"\\(c|d|b|u|v|k|r|H)\{([A-Za-z])\}", lambda m: aplica(m.group(1), m.group(2)), texto
    )
    texto = re.sub(
        r"\\(['`^\"~=.])\{([A-Za-z])\}", lambda m: aplica(m.group(1), m.group(2)), texto
    )

    # Forma suelta, solo para los acentos que son signo de puntuación.
    # El signo no puede iniciar el nombre de otro comando, así que es seguro.
    texto = re.sub(
        r"\\(['`^\"~=.])([A-Za-z])", lambda m: aplica(m.group(1), m.group(2)), texto
    )

    # Comandos de carácter especial
    texto = texto.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
    texto = texto.replace(r"\#", "#").replace(r"\$", "$")
    # Ángulos de las marcas de hueco, escritas en modo matemático en la fuente.
    # Se convierten a Unicode, no se eliminan: un hueco de contenido tiene que
    # seguir siendo visible al pegar el texto en el formulario.
    texto = texto.replace(r"$\langle$", "⟨").replace(r"$\rangle$", "⟩")
    texto = texto.replace(r"\langle", "⟨").replace(r"\rangle", "⟩")
    texto = texto.replace(r"\textbackslash", "\\")
    texto = texto.replace(r"\dots", "…").replace(r"\ldots", "…")
    texto = texto.replace(r"\ss", "ß").replace(r"\S", "§").replace(r"\P", "¶")
    texto = texto.replace(r"\textasciitilde", "~")
    texto = texto.replace("~", " ")  # espacio duro
    texto = texto.replace(r"\ ", " ")
    texto = texto.replace("``", "«").replace("''", "»")
    return texto


def quita_comandos_de_estilo(texto: str) -> str:
    r"""Quita \fontsize{..}{..}, \selectfont, \bfseries, colores y tamaños."""
    texto = re.sub(r"\\fontsize\{[^}]*\}\{[^}]*\}", "", texto)
    texto = re.sub(r"\\(selectfont|bfseries|itshape|ttfamily|sffamily|rmfamily|"
                   r"normalfont|centering|raggedright|raggedleft|small|footnotesize|"
                   r"scriptsize|tiny|large|Large|LARGE|huge|Huge|noindent|newline|"
                   r"clearpage|newpage|thispagestyle|pagestyle|arraybackslash|"
                   r"toprule|midrule|bottomrule|hline|cline|addlinespace|"
                   r"textwidth|columnwidth|linewidth|baselineskip|strut|par)\b", "", texto)
    texto = re.sub(r"\\textcolor\{[^}]*\}", "", texto)
    texto = re.sub(r"\\rowcolor\{[^}]*\}", "", texto)
    texto = re.sub(r"\\definecolor\{[^}]*\}\{[^}]*\}\{[^}]*\}", "", texto)
    texto = re.sub(r"\\rule\{[^}]*\}\{[^}]*\}", "", texto)
    texto = re.sub(r"\\\\(\[[^\]]*\])?", "\n", texto)
    return texto


def quita_formato_conservando_contenido(texto: str) -> str:
    """\\textbf{X} -> X, anidado incluido."""
    patron = "|".join(CONSERVA_CONTENIDO)
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = re.sub(r"\\(?:" + patron + r")\{([^{}]*)\}", r"\1", texto)
    return texto


def borra_con_argumento(texto: str) -> str:
    patron = "|".join(BORRA_CON_ARGUMENTO)
    # versión con argumento obligatorio y con uno opcional seguido de obligatorio
    texto = re.sub(r"\\(?:" + patron + r")\*?(\[[^\]]*\])?\{[^{}]*\}", "", texto)
    texto = re.sub(r"\\(?:" + patron + r")\*?(\[[^\]]*\])?", "", texto)
    return texto


def omite_entornos(texto: str) -> str:
    """Elimina por completo los entornos de figura y diagrama."""
    for nombre in ENTORNOS_OMITIDOS:
        texto = re.sub(
            r"\\begin\{" + nombre + r"\}.*?\\end\{" + nombre + r"\}",
            "\n",
            texto,
            flags=re.S,
        )
    # Si quedó un \begin sin pareja (fuente recortada), corta desde ahí.
    for nombre in ENTORNOS_OMITIDOS:
        texto = re.sub(r"\\begin\{" + nombre + r"\}.*", "\n", texto, flags=re.S)
    return texto


def recorre_entornos(texto: str) -> str:
    """Quita las marcas de los entornos que sí se recorren.

    En las tablas se descarta además el preámbulo de columnas, que puede ocupar
    varias líneas y no aporta nada al texto plano.
    """
    texto = re.sub(
        r"\\begin\{(tabularx|tabular)\}"          # marca
        r"(\{[^{}]*(\{[^{}]*\}[^{}]*)*\})"       # {ancho}
        r"(\{[^{}]*(\{[^{}]*\}[^{}]*)*\})",      # {especificación de columnas}
        "\n", texto, flags=re.S,
    )
    texto = re.sub(r"\\begin\{(" + "|".join(ENTORNOS_RECORRIDOS) + r")"
                   r"(\[[^\]]*\])?(\{[^{}]*\})?(\\[a-zA-Z]+)?", "\n", texto)
    texto = re.sub(r"\\end\{(" + "|".join(ENTORNOS_RECORRIDOS) + r")\}", "\n", texto)
    return texto


def convierte_tablas(texto: str) -> str:
    """Tablas -> una línea por fila, celdas separadas por ' | '."""

    def celdas(fila: str) -> str:
        fila = fila.strip()
        if fila.endswith(r"\\"):
            fila = fila[:-2]
        partes = [p.strip() for p in fila.split("&")]
        partes = [p for p in partes if p]
        return " | ".join(partes)

    lineas = []
    for linea in texto.splitlines():
        if re.fullmatch(r"\s*\\[a-z]+\s*", linea):  # \midrule, \hline sueltos
            continue
        if "&" in linea:
            lineas.append(celdas(linea))
        else:
            lineas.append(linea)
    return "\n".join(lineas)


def convierte_items(texto: str) -> str:
    """\\item -> viñeta simple."""
    return re.sub(r"\s*\\item(\[[^\]]*\])?\s*", "\n- ", texto)


def carga_bib(ruta: pathlib.Path) -> dict[str, dict]:
    """Lee refs.bib y devuelve clave -> {autores, año}."""
    if not ruta.exists():
        return {}
    bruto = ruta.read_text(encoding="utf-8")
    entradas: dict[str, dict] = {}
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", bruto, re.S):
        clave, cuerpo = m.group(2).strip(), m.group(3)
        aut = re.search(r"author\s*=\s*\{(.*?)\}\s*,?\s*\n", cuerpo, re.S)
        year = re.search(r"year\s*=\s*\{?\s*(\d{4})", cuerpo)
        autores = []
        if aut:
            campo = aut.group(1)
            for a in re.split(r"\s+and\s+", campo):
                a = a.replace("{", "").replace("}", "").strip()
                if not a:
                    continue
                if "," in a:
                    autores.append(a.split(",")[0].strip())
                else:
                    partes = a.split()
                    autores.append(partes[-1] if partes else a)
        entradas[clave] = {"autores": autores, "year": year.group(1) if year else ""}
    return entradas


def _apellido(autores: list[str]) -> str:
    if not autores:
        return "Anónimo"
    if len(autores) == 1:
        return autores[0]
    if len(autores) == 2:
        return f"{autores[0]} y {autores[1]}"
    return f"{autores[0]} et al."


def convierte_citas(texto: str, bib: dict[str, dict]) -> str:
    """\\citep y \\citet a forma autor-año, igual que apalike."""

    def fmt(claves: str) -> str:
        fuera = []
        for k in claves.split(","):
            k = k.strip()
            d = bib.get(k)
            if not d:
                fuera.append(k)
                continue
            ap = _apellido(d["autores"])
            fuera.append(f"{ap}, {d['year']}" if d["year"] else ap)
        return "; ".join(fuera)

    def repl_citep(m: re.Match) -> str:
        pre, claves = m.group(1), m.group(2) or ""
        cuerpo = fmt(claves)
        prefijo = f"{pre[1:-1]} " if pre and pre[1:-1].strip() else ""
        return f"({prefijo}{cuerpo})"

    def repl_citet(m: re.Match) -> str:
        pre, claves = m.group(1), m.group(2) or ""
        partes = [p.strip() for p in claves.split(",")]
        primero = bib.get(partes[0], {})
        ap = _apellido(primero.get("autores", []))
        anio = primero.get("year", "")
        resto = fmt(",".join(partes[1:])) if len(partes) > 1 else ""
        salida = f"{ap} ({anio})" if anio else ap
        if resto:
            salida += f" y {resto}"
        return salida

    texto = re.sub(r"\\citep\*?(\[[^\]]*\])?\{([^}]*)\}", repl_citep, texto)
    texto = re.sub(r"\\citet\*?(\[[^\]]*\])?\{([^}]*)\}", repl_citet, texto)
    return texto


def convierte_cref(texto: str, etiquetas: dict[str, str]) -> str:
    """\\cref{label} -> el nombre legible del destino."""
    def nombre(clave: str) -> str:
        return etiquetas.get(clave.strip(), f"sección «{clave.strip()}»")

    def repl(m: re.Match) -> str:
        claves = [c.strip() for c in m.group(1).split(",")]
        nombres = [nombre(c) for c in claves]
        if len(nombres) == 1:
            return nombres[0]
        return ", ".join(nombres[:-1]) + " y " + nombres[-1]

    texto = re.sub(r"\\[cC]ref\{([^}]*)\}", repl, texto)
    return texto


def carga_etiquetas(ruta: pathlib.Path | None) -> dict[str, str]:
    if ruta and ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {}


def limpia_especificacion_columnas(texto: str) -> str:
    """Quita el preámbulo de columna de tabularx/tabular: p{2.15cm}, @{}, >{...}, |, X.

    El preámbulo puede ocupar varias líneas y terminar mezclado con la primera
    fila, así que se corta de raíz: todo lo que va desde `\\begin{tabularx}` hasta
    el primer `\\toprule` (o el primer texto con contenido) se descarta.
    """
    texto = re.sub(r"\\begin\{tabular(x)?\}.*?(\\toprule|\\midrule|\\hline)", "",
                   texto, flags=re.S)
    lineas = []
    for linea in texto.splitlines():
        # Una especificación de columnas es una línea que solo tiene letras de
        # columna, medidas y decoraciones, sin texto legible.
        if re.fullmatch(r"[\s@{}>|lcrXpm\d.,cmpt]{3,}", linea) and re.search(r"[lcrXpm]", linea):
            continue
        linea = re.sub(r"@\{[^}]*\}", "", linea)
        linea = re.sub(r">\{[^}]*\}", "", linea)
        linea = re.sub(r"p\{[\d.]+\\?[a-z]*\}", "", linea)
        linea = re.sub(r"\\(centering|arraybackslash|raggedright|raggedleft)\b", "", linea)
        linea = re.sub(r"\\textwidth\b", "", linea)
        if linea.strip() and not re.fullmatch(r"[\s|@{}]{1,}", linea):
            lineas.append(linea)
    return "\n".join(lineas)


def limpia_restos(texto: str) -> str:
    """Última pasada: barre los restos estructurales que sobreviven al barrido.

    Las opciones de entorno (`[htbp]`, `[label=...]`, `[leftmargin=...]`) y las
    llaves sueltas no significan nada al pegar el texto en un formulario, y
    dejarlas pasa por error de conversión. Los ángulos ⟨⟩ de los huecos de
    contenido sí se conservan.
    """
    # Marcadores de matemática en bloque.
    texto = texto.replace(r"\[", "").replace(r"\]", "")
    # Opciones de entorno huérfanas.
    texto = re.sub(r"\[(htbp|htb|ht|H|tbp|bp|hbt|hb|tb|b|t|p|!htbp)*\]", "", texto)
    texto = re.sub(r"\[[a-zA-Z]+\s*=\s*[^\]]*\]", "", texto)
    # Llaves y signos de dólar huérfanos.
    texto = re.sub(r"(?<![⟨])\{(?![⟩])", "", texto)
    texto = re.sub(r"(?<![⟨])\}(?![⟩])", "", texto)
    texto = texto.replace("$", "")
    # Marcas de fin de fila de tabla y reglas sueltas.
    texto = re.sub(r"\\(toprule|midrule|bottomrule|hline|cline\{[^}]*\})", "", texto)
    # Espacios de nuevo.
    return texto


def convierte(ruta: pathlib.Path, bib: dict, etiquetas: dict, seccion: str | None = None) -> str:
    texto = ruta.read_text(encoding="utf-8")

    # 0. Si se pide una sección concreta, recorta el archivo a ese bloque.
    if seccion:
        partes = re.split(r"\\section\*?\{([^}]*)\}", texto)
        elegido = None
        for i in range(1, len(partes), 2):
            if seccion.lower() in partes[i].lower():
                elegido = "\\section{" + partes[i] + "}" + partes[i + 1]
                break
        if elegido is None:
            raise SystemExit(f"sección no encontrada: {seccion}")
        texto = elegido
        titulo_elegido = seccion
    else:
        titulo_elegido = None

    # 1. Comentarios: fuera las líneas que son solo comentario y los finales.
    texto = "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("%")
    )
    texto = re.sub(r"(?<!\\)%.*$", "", texto, flags=re.M)

    # 2. Estructura: secciones y entornos.
    texto = omite_entornos(texto)
    texto = recorre_entornos(texto)
    texto = re.sub(r"\\(section|subsection|subsubsection)\*?\{([^}]*)\}", r"\n\n\2\n\n", texto)
    texto = re.sub(r"\\caption\{([^{}]*)\}", r"\1", texto)
    texto = re.sub(r"\\par\b", "\n\n", texto)

    # 3. Citas y referencias cruzadas, antes de barrer comandos.
    texto = convierte_citas(texto, bib)
    texto = convierte_cref(texto, etiquetas)

    # 4. Comandos.
    texto = borra_con_argumento(texto)
    texto = quita_comandos_de_estilo(texto)
    texto = quita_formato_conservando_contenido(texto)
    texto = convierte_items(texto)
    texto = convierte_tablas(texto)
    texto = limpia_especificacion_columnas(texto)

    # 5. Acentos y símbolos, al final para no interferir con el barrido.
    texto = convierte_acentos(texto)

    # 6. Restos: comandos desconocidos con su argumento, y llaves huérfanas.
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{([^{}]*)\}", r"\2", texto)
    texto = re.sub(r"\\[a-zA-Z]+\*?", "", texto)
    texto = re.sub(r"\\([{}&%$#_])", r"\1", texto)
    texto = limpia_restos(texto)

    # 7. Espacios: colapsa, conserva saltos de párrafo.
    #    La fuente LaTeX parte cada párrafo en líneas físicas; en un área de texto
    #    esas líneas son ruido. Un párrafo del documento = un párrafo de la salida,
    #    y el único salto que sobrevive es el de línea en blanco.
    texto = re.sub(r"[ \t]+", " ", texto)
    parrafos = []
    for bloque in re.split(r"\n\s*\n", texto):
        # Dentro del bloque, une las líneas físicas en una sola.
        unido = " ".join(l.strip() for l in bloque.splitlines() if l.strip())
        unido = re.sub(r"\s{2,}", " ", unido).strip()
        if not unido:
            continue
        # Una lista de viñetas son varios párrafos, no uno: cada "- " abre línea.
        piezas = re.split(r"\s+-\s+", unido)
        if len(piezas) > 1:
            primera = piezas[0].strip()
            if primera:
                parrafos.append(primera)
            for pieza in piezas[1:]:
                pieza = pieza.strip()
                if pieza:
                    parrafos.append("- " + pieza)
        else:
            parrafos.append(unido)
    texto = "\n\n".join(parrafos)

    # 8. El título de la sección no es parte del contenido del campo: un formulario
    #    ya tiene su propio rótulo. Se quita del arranque, tenga o no salto de
    #    párrafo detrás, porque la fuente suele pegarlo al primer párrafo.
    titulos = []
    if titulo_elegido:
        titulos.append(titulo_elegido)
    for m in re.finditer(r"\\section\*?\{([^}]*)\}", ruta.read_text(encoding="utf-8")):
        titulos.append(m.group(1))
    for t in sorted(set(titulos), key=len, reverse=True):
        t = convierte_acentos(quita_formato_conservando_contenido(t)).strip()
        if t and texto.startswith(t):
            texto = texto[len(t):].lstrip()
    texto = re.sub(r"^\s*\n+", "", texto)
    return texto.strip()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("latex", type=pathlib.Path)
    p.add_argument("--bib", type=pathlib.Path, default=None)
    p.add_argument("--etiquetas", type=pathlib.Path, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--chars", action="store_true")
    p.add_argument("--seccion", default=None,
                   help="recorta el archivo a la sección cuyo título contenga este texto")
    args = p.parse_args()

    if not args.latex.exists():
        print(f"no existe: {args.latex}", file=sys.stderr)
        return 1

    bib = carga_bib(args.bib) if args.bib else {}
    etiquetas = carga_etiquetas(args.etiquetas)
    texto = convierte(args.latex, bib, etiquetas, args.seccion)

    if args.json:
        print(json.dumps({
            "archivo": str(args.latex),
            "texto": texto,
            "caracteres": len(texto),
            "caracteres_sin_espacios": len(re.sub(r"\s", "", texto)),
            "palabras": len(texto.split()),
        }, ensure_ascii=False, indent=1))
    elif args.chars:
        print(f"{len(texto)} caracteres", file=sys.stderr)
        print(texto)
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
