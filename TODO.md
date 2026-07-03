# 7S-generator — TODO

Deferred work for the corpus generator (separate from the
[ODEN](https://github.com/larsnor/ODEN-analys) plugin).

- [ ] **More area types** — industrial estate, power plant, border crossing,
      railway yard, hospital. Add a profile to `corpusgen/content.py` (frequency,
      place names, civilian templates); the logic is untouched.
- [ ] **Richer hostility realism** — a shared team vehicle linking distinct
      hostiles; multi-phase campaigns (recon → sabotage); escalating tempo over the
      window; day/night patterns per type.
- [ ] **More varied prose** — broaden civilian/hostile/protester phrasings and
      per-area idioms so a corpus stresses open-vocabulary detectors, not just the
      fixed keyword list.
- [ ] **Offline gazetteer** — optional place-name → coordinate lookup for the AOI
      (so `--aoi` could take a name), usable air-gapped.
- [ ] **Packaging** — verify the `7s-generator` console entry point; consider PyPI.

## Sync contract (keep in parity with ODEN)

`corpusgen/mgrs.py` and `corpusgen/render.py` are **copied from / mirror** the ODEN
plugin, and the output format + the `7SPLATE:` image marker are a **shared
contract**. Change the report format / marker / MGRS in one repo → mirror it in the
other. There is no build coupling — only this contract. (Same note in ODEN's
`TODO.md`.)
