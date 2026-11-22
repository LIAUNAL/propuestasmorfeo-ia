"""The dashboard speaks Spanish by default and English on request.

The page served at ``/`` reads its visible strings from catalogues under
``static/i18n/<lang>/<namespace>.js`` through ``static/i18n.js`` (ported from
papersmith-ai); a selector in the top bar switches between them. Spanish is the
default language and the fallback of every key, so a Spanish user sees the
dashboard exactly as it was. These tests hold the catalogues in parity, check
that every key the page asks for exists, and run the runtime under node.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from morfeo.dashboard.server import MorfeoDashboardHandler

STATIC = Path(__file__).resolve().parent.parent / "src" / "morfeo" / "dashboard" / "static"
PAGE = (STATIC / "index.html").read_text(encoding="utf-8")
CATALOGUES = STATIC / "i18n"
LANGS = ("es", "en")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
SPANISH_ACCENTS = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]")
# English texts that quote a Spanish name verbatim (a block title, the TDR chapters).
ENGLISH_QUOTES_SPANISH = {"evaluatePhaseExecutionCore.checkControlDeEjecucionBlock",
                          "sectionsStructureData.threeSubsectionsWithVerbatimTitles"}
FILE = re.compile(
    r"\(window\.MORFEO_I18N = window\.MORFEO_I18N \|\| \{\}\)\.(?P<lang>[a-z]{2}) = "
    r"Object\.assign\(window\.MORFEO_I18N\.(?P=lang) \|\| \{\}, (?P<body>\{.*\})\);\s*\Z", re.S)


def namespace(lang: str, name: str) -> dict[str, str]:
    """The ``{key: text}`` object one catalogue file merges into its language."""
    text = (CATALOGUES / lang / f"{name}.js").read_text(encoding="utf-8")
    match = FILE.search(text)
    assert match, f"i18n/{lang}/{name}.js merges one JSON object into window.MORFEO_I18N.{lang}"
    assert match.group("lang") == lang
    return json.loads(match.group("body"))


def namespaces(lang: str) -> list[str]:
    return sorted(path.stem for path in (CATALOGUES / lang).glob("*.js"))


def merged(lang: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for name in namespaces(lang):
        table.update(namespace(lang, name))
    return table


ES = merged("es")
EN = merged("en")


def body_markup() -> str:
    return PAGE[PAGE.index("<body>"):PAGE.index("<script>", PAGE.index("<body>"))]


def inline_script() -> str:
    start = PAGE.index("<script>", PAGE.index("<body>"))
    return PAGE[start:PAGE.index("</script>", start)]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class CatalogueTests(unittest.TestCase):
    def test_every_language_has_the_same_namespaces(self) -> None:
        self.assertEqual(namespaces("es"), namespaces("en"))
        self.assertIn("core", namespaces("es"))

    def test_each_namespace_holds_the_same_keys_in_every_language(self) -> None:
        for name in namespaces("es"):
            with self.subTest(namespace=name):
                es, en = namespace("es", name), namespace("en", name)
                self.assertEqual(sorted(set(es) - set(en)), [], f"keys missing from i18n/en/{name}.js")
                self.assertEqual(sorted(set(en) - set(es)), [], f"keys missing from i18n/es/{name}.js")
        self.assertGreater(len(ES), 1500)

    def test_a_key_lives_in_one_namespace_only(self) -> None:
        for lang in LANGS:
            seen: dict[str, str] = {}
            for name in namespaces(lang):
                for key in namespace(lang, name):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn(key, seen, f"{key} is in {seen.get(key)} and {name}")
                    seen[key] = name

    def test_no_text_is_empty_and_placeholders_agree(self) -> None:
        for key, spanish in ES.items():
            with self.subTest(key=key):
                self.assertTrue(spanish.strip())
                self.assertTrue(EN[key].strip())
                self.assertEqual(set(PLACEHOLDER.findall(spanish)), set(PLACEHOLDER.findall(EN[key])))

    def test_markup_tags_agree_between_languages(self) -> None:
        tags = re.compile(r"</?([a-zA-Z]+)")
        for key, spanish in ES.items():
            with self.subTest(key=key):
                self.assertEqual(sorted(tags.findall(spanish)), sorted(tags.findall(EN[key])))

    def test_the_english_catalogue_is_english(self) -> None:
        accented = {key: text for key, text in EN.items()
                    if SPANISH_ACCENTS.search(text) and key not in ENGLISH_QUOTES_SPANISH}
        self.assertEqual(accented, {})

    def test_keys_are_plain_dotted_identifiers(self) -> None:
        for key in ES:
            with self.subTest(key=key):
                self.assertRegex(key, r"^[a-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)+$")


class PageKeyTests(unittest.TestCase):
    def test_every_markup_key_exists(self) -> None:
        # Templates in the inline script also carry data-i18n attributes.
        keys = set(re.findall(r'data-i18n(?:-html)?="([A-Za-z0-9.]+)"', PAGE))
        for spec in re.findall(r'data-i18n-attr="([^"]+)"', PAGE):
            keys |= {pair.split(":", 1)[1].strip() for pair in spec.split(";") if ":" in pair}
        self.assertGreater(len(keys), 250)
        self.assertEqual(sorted(keys - set(ES)), [])

    def test_every_key_the_inline_script_asks_for_exists(self) -> None:
        script = inline_script()
        called = set(re.findall(r"(?<![\w.$])t[l]?\(\s*'([A-Za-z0-9.]+)'", script))
        self.assertGreater(len(called), 1000)
        self.assertEqual(sorted(called - set(ES)), [])
        # Keys picked by a condition (t(a ? 'x.y' : 'x.z')) or written into data-i18n.
        prefixes = {key.split(".", 1)[0] for key in ES}
        literal = {key for key in re.findall(r"'([a-z][A-Za-z0-9]*\.[A-Za-z0-9]+)'", script)
                   if key.split(".", 1)[0] in prefixes}
        self.assertEqual(sorted(literal - set(ES)), [])

    def test_the_spanish_catalogue_reproduces_the_shipped_markup(self) -> None:
        # The markup ships the Spanish text, so the page shows it before any
        # script runs; the catalogue must say exactly the same.
        markup = body_markup()
        for key, text in re.findall(r'data-i18n="([A-Za-z0-9.]+)"[^>]*>([^<]*)<', markup):
            with self.subTest(key=key):
                self.assertEqual(norm(ES[key]), norm(text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")))
        for match in re.finditer(r'<[a-zA-Z][^>]*data-i18n-attr="([^"]+)"[^>]*>', markup):
            tag = match.group(0)
            for pair in match.group(1).split(";"):
                attr, key = pair.split(":", 1)
                value = re.search(rf'\s{re.escape(attr)}="([^"]*)"', tag)
                with self.subTest(key=key, attr=attr):
                    self.assertIsNotNone(value, tag[:120])
                    self.assertEqual(ES[key], value.group(1).replace("&amp;", "&"))

    def test_machine_values_are_not_translated(self) -> None:
        # Commands, file names and section ids stay the same in every language.
        for key, spanish in ES.items():
            for token in re.findall(r"/propuesta-[a-z-]+|\b\d\d_[a-z_]+\b|artefactos/[\w/._-]+", spanish):
                with self.subTest(key=key, token=token):
                    self.assertIn(token, EN[key])


class PageTests(unittest.TestCase):
    def test_the_page_starts_in_spanish(self) -> None:
        self.assertRegex(PAGE, r'<html lang="es"')

    def test_the_top_bar_has_an_accessible_language_selector_after_the_text_size(self) -> None:
        start = PAGE.index('<div class="topbar__actions">')
        actions = PAGE[start:PAGE.index("</header>", start)]
        match = re.search(r"<select\b[^>]*\bid=\"langSelect\"[^>]*>(.*?)</select>", actions, re.S)
        self.assertIsNotNone(match, "the top bar holds the #langSelect selector")
        self.assertIn("data-lang-select", match.group(0))
        self.assertRegex(match.group(0), r'aria-label="[^"]*Idioma[^"]*Language[^"]*"')
        self.assertEqual(re.findall(r'<option value="(\w+)"', match.group(1)), ["es", "en"])
        order = [actions.index(f'id="{name}"') for name in ("runSelector", "themeBtn", "textSizeSelect", "langSelect", "boardRefreshBtn")]
        self.assertEqual(order, sorted(order))

    def test_the_runtime_and_catalogues_load_in_head_before_the_page_scripts(self) -> None:
        head = PAGE[:PAGE.index("</head>")]
        order = re.findall(r'<script src="/static/([^"?]+)"', head)
        runtime = order.index("i18n.js")
        for lang in LANGS:
            for name in namespaces(lang):
                with self.subTest(catalogue=f"{lang}/{name}"):
                    self.assertIn(f"i18n/{lang}/{name}.js", order)
        self.assertLess(order.index("text-size.js"), runtime)
        self.assertLess(order.index("i18n/es/core.js"), runtime)
        self.assertIn("html[data-i18n-pending] body { visibility: hidden; }", head)

    def test_the_runtime_persists_the_choice_and_announces_it(self) -> None:
        runtime = (STATIC / "i18n.js").read_text(encoding="utf-8")
        for needle in ("localStorage", "documentElement.lang", "'languagechange'", "function setLanguage",
                       "function getLanguage", "function t(", "DEFAULT_LANGUAGE = 'es'", "'morfeo.lang'"):
            with self.subTest(needle=needle):
                self.assertIn(needle, runtime)


class ServingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": Path(tmp.name)})
        handler.log_message = lambda *a, **k: None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def test_runtime_and_catalogues_are_served_fresh(self) -> None:
        paths = ["/static/i18n.js", "/static/text-size.js"]
        paths += [f"/static/i18n/{lang}/{name}.js" for lang in LANGS for name in namespaces(lang)]
        for path in paths:
            with self.subTest(path=path), urllib.request.urlopen(self.base + path) as res:
                self.assertEqual(res.read(), (STATIC / path.removeprefix("/static/")).read_bytes())
                self.assertIn("javascript", res.headers["Content-Type"])
                self.assertIn("no-cache", res.headers["Cache-Control"])


@unittest.skipUnless(shutil.which("node"), "node is required to run the runtime")
class RuntimeTests(unittest.TestCase):
    def run_node(self, body: str, saved: str | None = None) -> str:
        store = json.dumps({"morfeo.lang": saved} if saved else {})
        files = [CATALOGUES / lang / f"{name}.js" for lang in LANGS for name in namespaces(lang)]
        script = (
            "const fs=require('fs');const events=[];"
            f"const store={store};"
            "global.window={localStorage:{getItem:(k)=>store[k]??null,setItem:(k,v)=>{store[k]=v;}},"
            "location:{href:'http://127.0.0.1:8765/',origin:'http://127.0.0.1:8765'},"
            "fetch:(u)=>Promise.resolve(u)};"
            "global.CustomEvent=class{constructor(type,init){this.type=type;this.detail=init.detail;}};"
            "global.document={readyState:'complete',documentElement:{lang:'xx',dataset:{}},"
            "querySelectorAll:()=>[],addEventListener(){},dispatchEvent:(e)=>events.push(e)};"
            + "".join(f"eval(fs.readFileSync({json.dumps(str(path))},'utf8'));" for path in files)
            + f"eval(fs.readFileSync({json.dumps(str(STATIC / 'i18n.js'))},'utf8'));"
            + body
        )
        return subprocess.run(["node", "-e", script], capture_output=True, text=True,
                              cwd=tempfile.gettempdir(), check=True).stdout.strip()

    def test_spanish_is_the_default_and_english_persists(self) -> None:
        key = "page.overview"
        out = self.run_node(
            "const a=[window.i18n.getLanguage(),document.documentElement.lang,window.t('page.overview'),"
            "'i18nPending' in document.documentElement.dataset];"
            "window.i18n.setLanguage('en');"
            "a.push(window.i18n.getLanguage(),document.documentElement.lang,window.t('page.overview'),"
            "store['morfeo.lang'],events.length,events[0].type,events[0].detail.lang);"
            "console.log(JSON.stringify(a));")
        self.assertEqual(json.loads(out), ["es", "es", ES[key], False, "en", "en", EN[key], "en", 1,
                                           "languagechange", "en"])
        self.assertEqual(self.run_node("console.log(window.i18n.getLanguage(), document.documentElement.lang)", saved="en"), "en en")
        self.assertEqual(self.run_node("console.log(window.i18n.getLanguage())", saved="fr"), "es")
        self.assertEqual(self.run_node("window.i18n.setLanguage('de');console.log(window.i18n.getLanguage(),store['morfeo.lang'])"), "es es")

    def test_a_missing_key_falls_back_to_spanish_then_to_the_key(self) -> None:
        out = self.run_node(
            "window.MORFEO_I18N.es['only.es']='solo';window.i18n.setLanguage('en');"
            "console.log(JSON.stringify([window.t('only.es'),window.t('no.such.key'),window.i18n.has('no.such.key')]))")
        self.assertEqual(json.loads(out), ["solo", "no.such.key", False])

    def test_placeholders_are_filled_and_unknown_ones_kept(self) -> None:
        out = self.run_node(
            "window.MORFEO_I18N.es['x.run']='Corrida {run} · {other}';"
            "console.log(JSON.stringify([window.t('x.run',{run:'r1'}),window.t('x.run'),window.t('x.run',{run:0,other:null})]))")
        self.assertEqual(json.loads(out), ["Corrida r1 · {other}", "Corrida {run} · {other}", "Corrida 0 · {other}"])

    def test_api_requests_carry_the_language_only_when_it_is_not_spanish(self) -> None:
        out = self.run_node(
            "Promise.all([window.fetch('/api/status'),"
            "(window.i18n.setLanguage('en'),window.fetch('/api/status')),window.fetch('/api/x?a=1'),"
            "window.fetch('/static/i18n.js'),window.fetch('https://example.org/api/x'),window.fetch('/api/x?lang=es')])"
            ".then(r=>console.log(JSON.stringify(r)))")
        self.assertEqual(json.loads(out), ["/api/status", "/api/status?lang=en", "/api/x?a=1&lang=en",
                                           "/static/i18n.js", "https://example.org/api/x", "/api/x?lang=es"])

    def test_live_data_reads_the_active_language(self) -> None:
        out = self.run_node(
            "const d={a:{label:window.tl('page.overview')},list:[window.tl('page.sections'),'machine']};window.i18n.live(d);"
            "const before=[d.a.label,d.list[0],d.list[1]];window.i18n.setLanguage('en');"
            "console.log(JSON.stringify([before,[d.a.label,d.list[0],d.list[1]],Object.keys(d.a),JSON.stringify(d.list)]))")
        before, after, keys, as_json = json.loads(out)
        self.assertEqual(before, [ES["page.overview"], ES["page.sections"], "machine"])
        self.assertEqual(after, [EN["page.overview"], EN["page.sections"], "machine"])
        self.assertEqual(keys, ["label"])
        self.assertEqual(json.loads(as_json), [EN["page.sections"], "machine"])


if __name__ == "__main__":
    unittest.main()
