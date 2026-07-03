# 7S-generator

A small, dependency-free **CLI** that generates synthetic **7S field-report
corpora** for testing situational-awareness tools (it was built to feed the
[ODEN](https://github.com/larsnor/ODEN-analys) plugin, but the output is plain
Markdown + a ground-truth file, usable anywhere).

You describe an **area of interest** and a **time window**, and it produces a
realistic stream of *normal* civilian reports. Two further commands layer a
**hostile cell** (recon / sabotage / infiltration / terrorism) or **challenging
civilians** (demonstrators / environmentalists / peace activists) on top — each
tagged in the ground truth so detection can be scored.

- **Standard library only** — no dependencies, no network.
- **Deterministic** — same `--seed` → same corpus.
- **Plugin-compatible output** — new-format `7S-rapport` markdown (free-prose
  Händelse, MGRS grids, `signal_*` frontmatter) that ODEN reads directly.

## Install / run

No install needed:
```bash
python3 -m corpusgen <command> …
```
Or `pip install -e .` to get a `7s-generator` command.

## Commands

### 1. `generate` — normal activity
```bash
python3 -m corpusgen generate \
  --aoi 60.345,17.422 --radius 3 --area airport \
  --from 2026-06-15 --days 14 \
  --callsigns AQ,BQ,CQ,DQ --name "Tierp flygfält" \
  --out ./corpus_tierp
```
- `--aoi LAT,LON` — the object/area to protect (proximity centre).
- `--radius KM` — named locations are scattered within this radius, each assigned
  to a **callsign** by bearing (one sector per platoon).
- `--area` — `urban · suburban · rural · airport · port · military · coastal ·
  forest`. Sets the activity vocabulary **and the base report frequency** (urban
  busy, rural/forest sparse).
- `--from` + (`--to` | `--days`) — the calendar window. The **season** (from the
  start month) shifts clothing, daylight hours and civilian volume.
- Report count is derived from `frequency × days × season` (override with
  `--reports`).

### 2. `add-hostiles` — a threat cell
```bash
python3 -m corpusgen add-hostiles --corpus ./corpus_tierp --type recon
```
Injects **2–10** distinct hostiles (random unless `--count`) of one `--type`
(`recon · sabotage · infiltration · terrorism`), near the AOI, time-biased,
recurring 1–4× each. Detectable only as a spatio-temporal / behavioural pattern.

### 3. `add-protesters` — challenging civilians (noise)
```bash
python3 -m corpusgen add-protesters --corpus ./corpus_tierp --type miljöaktivister
```
Injects a **group** (`demonstranter · miljöaktivister · fredsaktivister`) that
gathers at one location on one day — not hostile, but a spatio-temporal cluster
that stresses a detector's precision.

## Output

A corpus directory contains:
- `TNR<DDHHMM>.md` — the reports (new-format 7S).
- `ground_truth.json` — one row per report: `truth` (`civil` / `hostile` /
  `protester`), `subtype`, `member`, `plate`, `sector`, `callsign` — so you can
  measure recall/precision.
- `meta.json` — how it was built (AOI, radius, area, dates, callsigns, the placed
  locations), so the augment commands inject consistently into the same area.

## Extending

All the "what a report says" content — area profiles, seasonal clothing, and the
hostile/protester repertoires — is declarative data in
[`corpusgen/content.py`](corpusgen/content.py). Add an area type or a hostility
mode by editing that one file; the generation logic stays untouched.
