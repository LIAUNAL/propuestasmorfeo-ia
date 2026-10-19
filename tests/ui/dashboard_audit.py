"""Playwright layout audit for the Morfeo Command Center dashboard.

Not a unittest module (the name does not start with ``test_``): it drives a
running dashboard in system Chrome and exits non-zero when it finds layout
defects. See ``tests/ui/README.md``.

    uv run --quiet --with playwright python -I tests/ui/dashboard_audit.py \
        [--url http://127.0.0.1:8081/] [--quick] [--out DIR]

It never causes side effects: every non-GET request is answered with a stub
and the terminal WebSocket is mocked.

Failing findings (exit 1):
  - horizontal page overflow (document wider than the viewport);
  - confirmed text overlaps (two painted text line boxes intersecting);
  - clipped text (overflow hidden without ellipsis);
  - text left under the floating CLI button at the end of the page;
  - sticky panels taller than the viewport;
  - console errors, page errors, failed requests, HTTP >= 400;
  - primary controls (buttons, selects, number inputs, clickable elements)
    smaller than 24 x 24 px.
Low contrast (WCAG AA) is reported; it fails only with ``--strict-contrast``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

TABS = ["flow", "pipeline", "trees", "sections", "atlas", "preview", "artifacts", "telemetria"]
VIEWPORTS = {"1440x900": (1440, 900), "1280x720": (1280, 720), "1920x1080": (1920, 1080), "390x844": (390, 844)}
QUICK_VIEWPORTS = ["1440x900", "390x844"]
THEMES = ["dark", "light"]
WAIT_MS = {"preview": 4000, "atlas": 3500, "flow": 2000, "trees": 2000}

# Navigations aborted by the page itself (an iframe whose src changes while it
# loads) are not failures.
BENIGN_REQUEST_ERRORS = ("net::ERR_ABORTED",)

ANALYZE_JS = r"""
([paneId, viewportWidth]) => {
  // Mobile emulation widens the layout viewport to fit overflowing content, so
  // overflow is measured against the configured viewport width.
  const vw = viewportWidth, vh = innerHeight;
  const pane = document.getElementById(paneId);
  const roots = [document.querySelector('header.topbar'), document.querySelector('.meta-strip'),
                 document.querySelector('nav.tabs-nav'), pane, document.querySelector('footer')].filter(Boolean);
  const sel = (el) => {
    if (el.id) return '#' + el.id;
    let s = el.tagName.toLowerCase();
    if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    const p = el.parentElement;
    if (p) s = (p.id ? '#' + p.id : p.tagName.toLowerCase() + (p.classList[0] ? '.' + p.classList[0] : '')) + ' > ' + s;
    return s;
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    // Visually hidden labels (1px clip, e.g. icon-only buttons on phones) are not painted text.
    return r.width > 1 && r.height > 1;
  };
  const ownText = (el) => [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
  const clipBox = (el, box) => {
    let {l, t, r, b} = box;
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const c = p.getBoundingClientRect();
        l = Math.max(l, c.left); r = Math.min(r, c.right); t = Math.max(t, c.top); b = Math.min(b, c.bottom);
      }
    }
    return {l, t, r, b};
  };
  // Text leaves, one entry per painted line box (a wrapped inline span has
  // several; their union would falsely overlap its neighbours).
  const texts = [];
  for (const root of roots) for (const el of root.querySelectorAll('*')) {
    if (['SCRIPT', 'STYLE', 'OPTION'].includes(el.tagName)) continue;
    if (el.closest('svg') || el.closest('[id^="pdfTextLayer"], .textLayer')) continue;
    const t = ownText(el);
    if (!t || !visible(el)) continue;
    const range = document.createRange();
    const lines = [];
    for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) {
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        const c = clipBox(el, {l: r.left, t: r.top, r: r.right, b: r.bottom});
        if (c.r - c.l >= 1 && c.b - c.t >= 1) lines.push(c);
      }
    }
    if (lines.length) texts.push({el, text: t.slice(0, 60), lines});
  }
  const overlaps = [];
  outer: for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const A = texts[i], B = texts[j];
    if (A.el.contains(B.el) || B.el.contains(A.el)) continue;
    for (const a of A.lines) for (const b of B.lines) {
      const ix = Math.min(a.r, b.r) - Math.max(a.l, b.l), iy = Math.min(a.b, b.b) - Math.max(a.t, b.t);
      if (ix > 3 && iy > 3) {
        overlaps.push({a: sel(A.el), at: A.text, b: sel(B.el), bt: B.text, ix: Math.round(ix), iy: Math.round(iy), y: Math.round(a.t + scrollY)});
        if (overlaps.length > 40) break outer;
        continue outer;
      }
    }
  }
  const clipped = [], ellipsized = [];
  for (const {el, text} of texts) {
    const cs = getComputedStyle(el);
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      const hid = ['hidden', 'clip'].includes(cs.overflowX);
      if (hid && cs.textOverflow === 'ellipsis') ellipsized.push({sel: sel(el), text, sw: el.scrollWidth, cw: el.clientWidth});
      else if (hid) clipped.push({sel: sel(el), text, sw: el.scrollWidth, cw: el.clientWidth});
    }
    if (el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 0 && ['hidden', 'clip'].includes(cs.overflowY) && cs.webkitLineClamp === 'none')
      clipped.push({sel: sel(el), text, sh: el.scrollHeight, ch: el.clientHeight, axis: 'y'});
  }
  const inScroller = (el) => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      if (getComputedStyle(p).overflowX !== 'visible') return p; } return null; };
  const vpOverflow = [], smallBtns = [], stickyClipped = [];
  for (const root of roots) for (const el of root.querySelectorAll('*')) {
    if (el.closest('svg') && el.tagName !== 'svg') continue;
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if ((r.right > vw + 1 || r.left < -1) && !inScroller(el) && cs.position !== 'fixed')
      vpOverflow.push({sel: sel(el), text: (ownText(el) || '').slice(0, 40), left: Math.round(r.left), right: Math.round(r.right), vw});
    if (cs.position === 'sticky' && r.height > vh - Math.max(0, parseFloat(cs.top) || 0) + 1)
      stickyClipped.push({sel: sel(el), h: Math.round(r.height), vh, top: cs.top});
    if (el.matches('button, a.btn, [onclick], input[type=number], select')) {
      if (r.width < 24 || r.height < 24) smallBtns.push({sel: sel(el), text: (el.textContent || '').trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height)});
    }
  }
  const parseC = (s) => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = (c) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bgOf = (el) => { for (let p = el; p; p = p.parentElement) { const cs = getComputedStyle(p);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && !cs.backgroundImage.startsWith('url')) return {grad: true};
      const c = parseC(cs.backgroundColor); if (c && c.a > 0.5) return c; } return parseC(getComputedStyle(document.body).backgroundColor); };
  const lowContrast = [];
  for (const {el, text} of texts) {
    const cs = getComputedStyle(el); const fg = parseC(cs.color); const bg = bgOf(el);
    if (!fg || !bg || bg.grad) continue;
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const big = parseFloat(cs.fontSize) >= 18.6 || (parseFloat(cs.fontSize) >= 14 && parseInt(cs.fontWeight) >= 700);
    if (ratio < (big ? 3 : 4.5)) lowContrast.push({sel: sel(el), text, ratio: +ratio.toFixed(2), fg: cs.color, fs: cs.fontSize});
  }
  return {
    hOverflow: {scrollWidth: document.scrollingElement.scrollWidth, innerWidth: vw},
    nText: texts.length, overlaps, clipped: clipped.slice(0, 30), ellipsized: ellipsized.slice(0, 30),
    vpOverflow: vpOverflow.slice(0, 30), smallBtns: smallBtns.slice(0, 40), stickyClipped,
    lowContrast: lowContrast.slice(0, 40), lowContrastCount: lowContrast.length,
  };
}
"""

# Text that stays under the floating CLI button once the page is scrolled to
# its end: the page must reserve a gutter for it.
FAB_JS = r"""
() => {
  const fab = document.getElementById('morfeoAssistantFab');
  if (!fab) return [];
  const f = fab.getBoundingClientRect();
  const hits = [];
  for (const el of document.querySelectorAll('main *, footer *')) {
    if (el.closest('svg') || el.closest('.textLayer') || el.closest('iframe')) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own && !el.matches('button, a, input, select')) continue;
    let b = el.getBoundingClientRect();
    if (b.width <= 1 || b.height <= 1) continue;
    // Content scrolled away inside an overflow container is not painted there.
    const r = {left: b.left, right: b.right, top: b.top, bottom: b.bottom};
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const pcs = getComputedStyle(p);
      if (pcs.overflowX !== 'visible' || pcs.overflowY !== 'visible') {
        const c = p.getBoundingClientRect();
        r.left = Math.max(r.left, c.left); r.right = Math.min(r.right, c.right);
        r.top = Math.max(r.top, c.top); r.bottom = Math.min(r.bottom, c.bottom);
      }
    }
    if (r.right - r.left < 1 || r.bottom - r.top < 1) continue;
    const ix = Math.min(r.right, f.right) - Math.max(r.left, f.left), iy = Math.min(r.bottom, f.bottom) - Math.max(r.top, f.top);
    if (ix > 2 && iy > 2) hits.push({sel: el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + [...el.classList].join('.'), text: (el.textContent || '').trim().slice(0, 40)});
  }
  return hits.slice(0, 10);
}
"""


def make_context(browser, url, vw, vh, theme, log):
    ctx = browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1,
                              is_mobile=vw < 500, has_touch=vw < 500)
    ctx.add_init_script(f"try{{localStorage.setItem('morfeo-theme','{theme}')}}catch(e){{}}")

    def stub_non_get(route, request):
        if request.method in ("GET", "HEAD"):
            route.continue_()
            return
        log["intercepted"].append({"method": request.method, "url": request.url})
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"ok": True, "stub": True, "status": "ok", "message": "stub"}))

    ctx.route("**/*", stub_non_get)
    ctx.route_web_socket("**/ws/**", lambda ws: log["ws"].append({"url": ws.url}))
    return ctx


def attach(page, log, tag):
    page.on("console", lambda m: m.type == "error" and log["console"].append({"tag": tag(), "text": m.text[:300]}))
    page.on("pageerror", lambda e: log["pageerror"].append({"tag": tag(), "text": str(e)[:300]}))
    page.on("response", lambda r: r.status >= 400 and log["http"].append({"tag": tag(), "status": r.status, "url": r.url}))
    page.on("requestfailed", lambda r: (r.failure or "") not in BENIGN_REQUEST_ERRORS
            and log["reqfailed"].append({"tag": tag(), "url": r.url, "err": r.failure}))
    page.on("dialog", lambda d: (log["dialogs"].append({"tag": tag(), "msg": d.message[:200]}), d.dismiss()))


def goto_tab(page, tab):
    page.evaluate(f"navigateTab('{tab}')")
    page.wait_for_timeout(WAIT_MS.get(tab, 900))


def check_links(page, base):
    hrefs = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))"
                          ".filter(h => h && !h.startsWith('#') && !h.startsWith('javascript'))")
    broken = {}
    for h in sorted(set(hrefs)):
        url = h if h.startswith("http") else base.rstrip("/") + (h if h.startswith("/") else "/" + h)
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                if resp.status >= 400:
                    broken[h] = resp.status
        except Exception as exc:  # noqa: BLE001 - any failure is a broken link
            broken[h] = str(exc)[:80]
    return broken


def failures_of(a, strict_contrast):
    found = []
    if a["hOverflow"]["scrollWidth"] > a["hOverflow"]["innerWidth"]:
        found.append(f"horizontal overflow {a['hOverflow']['scrollWidth']}px > {a['hOverflow']['innerWidth']}px")
    if a["overlaps"]:
        found.append(f"{len(a['overlaps'])} text overlaps")
    if a["clipped"]:
        found.append(f"{len(a['clipped'])} clipped texts")
    if a["smallBtns"]:
        found.append(f"{len(a['smallBtns'])} controls under 24px")
    if a["stickyClipped"]:
        found.append(f"{len(a['stickyClipped'])} sticky panels taller than the viewport")
    if a.get("fabCovered"):
        found.append(f"{len(a['fabCovered'])} elements under the CLI button")
    if strict_contrast and a["lowContrastCount"]:
        found.append(f"{a['lowContrastCount']} low-contrast texts")
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:8081/")
    ap.add_argument("--quick", action="store_true", help="only 1440x900 and 390x844")
    ap.add_argument("--out", default=None, help="report and screenshots directory (default: a temp dir)")
    ap.add_argument("--viewport", action="append", choices=sorted(VIEWPORTS), help="restrict to these viewports")
    ap.add_argument("--theme", action="append", choices=THEMES, help="restrict to these themes")
    ap.add_argument("--tab", action="append", choices=TABS, help="restrict to these tabs")
    ap.add_argument("--strict-contrast", action="store_true", help="fail on low contrast too")
    args = ap.parse_args(argv)

    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="morfeo-ui-audit-"))
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    viewports = args.viewport or (QUICK_VIEWPORTS if args.quick else list(VIEWPORTS))
    themes = args.theme or THEMES
    tabs = args.tab or TABS
    base = args.url if args.url.endswith("/") else args.url + "/"

    log = {k: [] for k in ["console", "pageerror", "http", "reqfailed", "dialogs", "intercepted", "ws"]}
    report = {"url": base, "layout": {}, "failures": []}
    cur = {"tag": ""}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for vpn in viewports:
            vw, vh = VIEWPORTS[vpn]
            for theme in themes:
                ctx = make_context(browser, base, vw, vh, theme, log)
                page = ctx.new_page()
                attach(page, log, lambda: cur["tag"])
                cur["tag"] = f"{vpn}/{theme}/load"
                page.goto(base, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1500)
                for tab in tabs:
                    key = f"{tab}|{vpn}|{theme}"
                    cur["tag"] = key
                    goto_tab(page, tab)
                    page.evaluate("scrollTo(0, 0)")
                    shot = shots / f"{tab}_{vpn}_{theme}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    page.screenshot(path=str(shots / f"{tab}_{vpn}_{theme}_vp.png"))
                    a = page.evaluate(ANALYZE_JS, [f"pane-{tab}", vw])
                    page.evaluate("scrollTo(0, document.scrollingElement.scrollHeight)")
                    page.wait_for_timeout(150)
                    a["fabCovered"] = page.evaluate(FAB_JS)
                    page.evaluate("scrollTo(0, 0)")
                    a["shot"] = str(shot)
                    report["layout"][key] = a
                    fails = failures_of(a, args.strict_contrast)
                    if fails:
                        report["failures"].append({"where": key, "problems": fails})
                    print(f"{vpn} {theme} {tab}: width={a['hOverflow']['scrollWidth']}/{a['hOverflow']['innerWidth']} "
                          f"overlaps={len(a['overlaps'])} clipped={len(a['clipped'])} small={len(a['smallBtns'])} "
                          f"sticky={len(a['stickyClipped'])} fab={len(a['fabCovered'])} lowContrast={a['lowContrastCount']}",
                          flush=True)
                if vpn == viewports[0] and theme == themes[0]:
                    report["broken_links"] = check_links(page, base)
                ctx.close()
        browser.close()

    report["log"] = log
    for kind in ("console", "pageerror", "http", "reqfailed"):
        if log[kind]:
            report["failures"].append({"where": kind, "problems": [f"{len(log[kind])} {kind} events"]})
    if report.get("broken_links"):
        report["failures"].append({"where": "links", "problems": [f"{len(report['broken_links'])} broken links"]})
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"report: {out / 'report.json'}")
    if report["failures"]:
        print(f"FAIL: {len(report['failures'])} findings")
        for f in report["failures"]:
            print(f"  - {f['where']}: {'; '.join(f['problems'])}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
