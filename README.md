# 7S-generator

A small, dependency-free, **standalone CLI** that generates synthetic **7S
field-report corpora** for testing situational-awareness tools. The output is
plain Markdown + a ground-truth file, usable anywhere.

You describe an **area of interest** and a **time window**, and it produces a
realistic stream of *normal* civilian reports. Two further commands layer a
**hostile cell** (recon / sabotage / infiltration / terrorism) or **challenging
civilians** (demonstrators / environmentalists / peace activists) on top — each
tagged in the ground truth so detection can be scored.

- **Standard library only** — no dependencies, no network.
- **Deterministic** — same `--seed` → same corpus.
- **Portable output** — `7S-rapport` markdown (free-prose Händelse, MGRS grids,
  `signal_*` frontmatter, standard-Markdown image embeds) that renders in any
  Markdown viewer.

## Install / run

**As a command (recommended)** — installs a `7s-generator` command straight from
GitHub. [pipx](https://pipx.pypa.io) keeps it in its own isolated environment:
```bash
pipx install git+https://github.com/larsnor/7S-generator.git
7s-generator --help
```
Plain `pip` works too (use a virtual environment):
```bash
pip install git+https://github.com/larsnor/7S-generator.git
```
Add the **plate-photo rendering** extra (`generate --images`, pulls in Pillow):
```bash
pipx install "7s-generator[images] @ git+https://github.com/larsnor/7S-generator.git"
```
**Pin a version** by appending a tag to any of the above, e.g.
`…/7S-generator.git@v0.1.0`.

**Without installing** — run from a clone (standard library only, no build step):
```bash
python3 -m corpusgen <command> …
```
**For development** — editable install from a clone: `pip install -e ".[images]"`.

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
- `--images` (optional) attaches a **corroborating plate photo** to each report
  whose text names a plate — the plate is rendered legibly *and* embedded in the
  JPEG comment (`7SPLATE:`) so an offline consumer can read it. Needs the
  **`images` extra** (installs Pillow — see [Install / run](#install--run));
  everything else is stdlib-only.

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

### 4. `feed` — drip a corpus into a destination folder
```bash
python3 -m corpusgen feed --corpus ./corpus_tierp --dest /path/to/inbox
```
Delivers the reports from the corpus folder into any destination folder in
chronological order — either **in compressed time** (`--auto MINS`) or **in
batches** (`--send N`) — mimicking a central app trickling messages out over
time. Interactive by default (`send [n]` · `auto [mins]` · `status` · `reset` ·
`quit`); copies referenced attachments so image embeds resolve. One-shot flags
for scripts/CI: `--send N` · `--auto MINS` · `--reset` · `--status`.

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

## Report format

Each report is a `7S-rapport` Markdown file with YAML frontmatter (`id`, `tnr`,
`tidpunkt`, `plats`, optional `signal_*` delivery fields and `lat`/`lon`) followed
by the 7S body (`Stund`, `Ställe`, `Händelse`, optional `Symbol`, `Sagesman`).
When `--images` is used, a plate photo is attached as a standard-Markdown embed
(`![...](attachments/…)`) with the plate also written into the JPEG comment
(marker `7SPLATE:`) so an offline consumer can read it without OCR. The report
rendering lives in [`corpusgen/render.py`](corpusgen/render.py) and MGRS handling
in [`corpusgen/mgrs.py`](corpusgen/mgrs.py).
