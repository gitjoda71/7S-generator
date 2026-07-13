# Changelog — 7S-generator (fork)

Forkad 2026-07-13 från larsnor/7S-generator v0.2.1
(origin = gitjoda71/7S-generator, upstream = larsnor/7S-generator).

## 0.3.0 — 2026-07-13

- Nytt kommando `score`: jämför en detektors utpekningar med
  `ground_truth.json` — precision/recall/F1 totalt (icke-civil), per label
  och per subtyp, plus celltäckning per hotcellsmedlem. `--json` för
  maskinläsbart resultat, `--min-f1` som CI-grind. Fungerar även i skalet
  (använder aktiv korpus när `--corpus` utelämnas).
- Detektionsfilen läses med `utf-8-sig` — PowerShell 5.1:s
  `Out-File -Encoding utf8` skriver BOM, upptäckt vid röktest på Windows.
