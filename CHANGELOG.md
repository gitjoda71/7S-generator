# Changelog — 7S-generator (fork)

Forkad 2026-07-13 från larsnor/7S-generator v0.2.1
(origin = gitjoda71/7S-generator, upstream = larsnor/7S-generator).

## 0.7.0 — 2026-07-14

- Koordinatinmatning i flera format (ny `corpusgen/coords.py`, endast stdlib):
  MGRS (invers UTM, round-trippar < 1 m mot framåt-konverteringen), DMS/DM
  (`59°15'41"N 17°42'49"E`, svenskt Ö/O = öst), SWEREF 99 TM, och decimalgrader.
  `--aoi` och GUI:ts AOI-fält tar nu alla dessa; nytt `/api/parse`-endpoint.
- **Polygon-område**: `generate --polygon 'lat,lon; …'` (och `build_normal(polygon=)`)
  sprider platser inuti en ritad polygon i stället för radie-cirkeln, fortfarande
  sektorindelat per bäring där geometrin tillåter. Polygonen sparas i meta.json.
  Nytt `/api/preview-locations`-endpoint visar var platserna hamnar (för kartan).

## 0.6.0 — 2026-07-14

- GUI förstagångsupplevelse: en tom Korpus-flik var en återvändsgränd (fält
  utan att veta vart man skulle peka). Nu:
  - Utan historik landar appen på **Generera**-fliken — där man skapar sin
    första korpus — i stället för på en tom Korpus-flik.
  - **Senaste korpusar**: aktiverade/genererade mappar kommer ihåg (localStorage)
    och visas som klickbara chips på Korpus-fliken; ett klick öppnar korpusen,
    ✕ tar bort den ur listan. Döda länkar (raderad mapp) rensas automatiskt.
  - Tydligare tom-läge-text beroende på om historik finns.

## 0.5.0 — 2026-07-14

- GUI: Generera-fliken. Formulär med samma förlåtande AOI-parsning som CLI:t,
  smarta defaults (idag som datum, senast använda värden i localStorage),
  live-förhandsvisning som är en exakt prefix av skarp körning (deterministisk
  per seed), uppskattat rapportantal, jobb-API med polling för långkörare
  (--images), och tvåstegsbekräftelse innan en befintlig mapp skrivs över.
  Skyltfoto-kryssrutan inaktiveras med förklaring när Pillow saknas.
- Härdningar efter adversarial granskning (6 bekräftade fynd + egen triage):
  - feed: fel i bakgrundsmatningen dödar inte längre tråden tyst — rapporteras
    till sinken ("fel: … — matningen avbruten") så GUI-loggen ser det.
  - GUI-servern: åtgärdslås serialiserar API-anrop (skydd mot dubbla feeders
    och parallella generate-jobb mot samma mapp från flera flikar); "Skicka 1"
    bygger ny feeder när målmapp eller aktiv korpus bytts i stället för att
    tyst mata den gamla; utmapp som är en fil ger 400; sanningsenlig
    överskrivningsvarning som anger hur många .md-filer som RADERAS när
    utmappen inte är en korpus; jobbhistoriken är begränsad.
  - GUI-appen: overwrite-bekräftelsen är bunden till exakt den
    parameteruppsättning som varnades (ändrad utmapp ärver aldrig ett ok);
    HTML-escaping av all serverdata i innerHTML; "servern svarar inte"-läge
    efter tre missade polls i stället för fryst UI; pollning rör inte
    knappläget mitt i en åtgärd; inaktuell förhandsvisning rensas; lokalt
    datum i stället för UTC som default; vassare varningstext på Återställ.
  - score: celltäckning nycklas på subtyp/medlem (två celler delar
    medlemsnamn); CI-grinden passerar inte vakuöst när detektionsfilen inte
    matchar korpusen alls; korrupta korpus-/detektionsfiler ger felmeddelande
    i stället för traceback (CLI) eller kraschad session (skalet).
  - skalet: `--corpus=SÖKVÄG`-formen känns igen så aktiv korpus inte tyst
    skriver över ett explicit val.

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
