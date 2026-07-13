# Changelog — 7S-generator (fork)

Forkad 2026-07-13 från larsnor/7S-generator v0.2.1
(origin = gitjoda71/7S-generator, upstream = larsnor/7S-generator).

## 0.4.0 — 2026-07-13

- Ny lokal webb-GUI: `7s-generator gui [--port N] [--no-browser]`. Endast
  standardbiblioteket (ThreadingHTTPServer + en enda app.html, inget byggsteg,
  inga nätverksanrop). Binder 127.0.0.1, validerar Host/Origin, cappar
  request-bodies. Flikar: Korpus (välj aktiv korpus, counts) och Mata ut
  (starta/pausa/återuppta/stoppa/återställ, progressbar, leveranslogg,
  1 s-polling). Generera-fliken kommer i nästa version.
- `Feeder` tar en valfri `sink`-parameter för bakgrundsmatningens meddelanden
  (default `print` — CLI-beteendet oförändrat). Skalet ritar nu om prompten
  efter varje bakgrundsleverans i stället för att låta utskriften trampa på
  det man skriver; GUI:n loggar via samma mekanism.

## 0.3.0 — 2026-07-13

- Nytt kommando `score`: jämför en detektors utpekningar med
  `ground_truth.json` — precision/recall/F1 totalt (icke-civil), per label
  och per subtyp, plus celltäckning per hotcellsmedlem. `--json` för
  maskinläsbart resultat, `--min-f1` som CI-grind. Fungerar även i skalet
  (använder aktiv korpus när `--corpus` utelämnas).
- Detektionsfilen läses med `utf-8-sig` — PowerShell 5.1:s
  `Out-File -Encoding utf8` skriver BOM, upptäckt vid röktest på Windows.
