# templates/

Holds `reference.docx`, the pandoc `--reference-doc` template used by
`build_docx()` (`redaccion/build.sh --docx`) to brand `redaccion/main.docx`
with the same institutional logos as `main.pdf` (UNAL top-right header,
GCPDS bottom-left footer, LabIA bottom-right footer).

`reference.docx` is not checked in yet — no automated tool in this
pipeline can composite a real Word header/footer with embedded logo images
(pandoc's `--reference-doc` mechanism only reuses styles/headers that
already exist inside the template docx; it does not let a script author
new header images into one). On first run, if `templates/reference.docx`
is missing, `build_docx()` auto-generates a default one via
`pandoc --print-default-data-file reference.docx` and prints a `warn`
telling you to open it once in Word/LibreOffice and insert the 3 logos by
hand (UNAL header-right, GCPDS footer-left, LabIA footer-right) to match
the PDF layout. After that one-time manual edit, commit the populated
`reference.docx` here so every subsequent `--docx` build reuses it.
