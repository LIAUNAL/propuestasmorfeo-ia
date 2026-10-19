# Dashboard UI audit

`dashboard_audit.py` drives a running Command Center dashboard in system Chrome
and checks every tab at several viewports, in dark and light themes. It is a
tool, not a unit test: the file name does not start with `test_`, so
`unittest discover` skips it.

## Run

Start a dashboard first (`morfeo ui --port 8081`), then:

```bash
uv run --quiet --with playwright python -I tests/ui/dashboard_audit.py
uv run --quiet --with playwright python -I tests/ui/dashboard_audit.py --quick   # 1440x900 and 390x844 only
```

Options: `--url` (default `http://127.0.0.1:8081/`), `--out DIR` (report and
screenshots; default a new temp dir), `--viewport`, `--theme`, `--tab` (each
repeatable, to narrow the run) and `--strict-contrast`.

It launches the installed Chrome (`channel="chrome"`). Do not run
`playwright install`; no bundled browser is needed.

## What it checks

The run exits 1 when it finds any of these:

- horizontal page overflow at the configured viewport width;
- overlapping text line boxes;
- text clipped by `overflow: hidden` without an ellipsis;
- content left under the floating CLI button at the end of the page;
- sticky panels taller than the window;
- console errors, page errors, failed requests, HTTP errors or broken links;
- buttons, selects, number inputs and clickable elements under 24 x 24 px.

Low WCAG AA contrast is listed in `report.json`; it fails only with
`--strict-contrast`.

## Side effects

None. Every non-GET request is answered with a stub and the terminal WebSocket
is mocked, so no button reaches the server or the workspace.
