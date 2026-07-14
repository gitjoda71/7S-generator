# 7S-generator

Ett litet, beroendefritt, **fristående CLI** som genererar syntetiska
**7S-fältrapportkorpusar** för att testa lägesbildsverktyg. Utdata är vanlig
Markdown + en facit-fil (ground truth), användbar var som helst.

Du beskriver ett **område av intresse** (AOI) och ett **tidsfönster**, och verktyget
producerar ett realistiskt flöde av *normala* civila rapporter. Två ytterligare
kommandon lägger på en **fientlig cell** (spaning / sabotage / infiltration /
terrorism) eller **utmanande civila** (demonstranter / miljöaktivister /
fredsaktivister) ovanpå — var och en märkt i facit så att detektion kan poängsättas.

- **Endast standardbiblioteket** — inga beroenden, inget nätverk.
- **Deterministiskt** — samma `--seed` → samma korpus.
- **Formatriktig utdata** — `7S-rapport`-markdown (fritext-Händelse, MGRS-rutor med
  mellanslag, `signal_*`-frontmatter). Bildinbäddningar är portabel standard-Markdown
  som standard, eller Obsidian-wikilänkar (`## Bilagor` + `![[…]]`, identiskt med
  källappen) med `--obsidian`.

## Installation / körning

**Som ett kommando (rekommenderas)** — installerar ett `7s-generator`-kommando direkt
från GitHub. [pipx](https://pipx.pypa.io) håller det i en egen isolerad miljö:
```bash
pipx install git+https://github.com/larsnor/7S-generator.git
7s-generator --help
```
Vanlig `pip` fungerar också (använd en virtuell miljö):
```bash
pip install git+https://github.com/larsnor/7S-generator.git
```
Lägg till tillägget för **skyltfoto-rendering** (`generate --images`, drar in Pillow):
```bash
pipx install "7s-generator[images] @ git+https://github.com/larsnor/7S-generator.git"
```
**Lås en version** genom att lägga till en tagg efter någon av ovanstående, t.ex.
`…/7S-generator.git@v0.1.0`.

**Utan installation** — kör från en klon (endast standardbiblioteket, inget byggsteg):
```bash
python3 -m corpusgen <kommando> …
```
**För utveckling** — redigerbar installation från en klon: `pip install -e ".[images]"`.

## Interaktivt skal (rekommenderas)

Kör `7s-generator` (eller `python3 -m corpusgen`) **utan argument** för att öppna ett
interaktivt skal. Det visar en prompt och en kort hjälptext, och varje åtgärd är ett
eget kommando med egna flaggor — inget behov av en enda lång rad. Skalet **kommer ihåg
den aktiva korpusen**, så du slipper skriva `--corpus` om och om igen, och `feed --auto`
körs **i bakgrunden** medan prompten är kvar (pausa/återuppta/stoppa när du vill).

```text
$ 7s-generator
7S> generate --aoi 60.345,17.422 --area airport --from 2026-06-15 --days 14 --out ./korpus_tierp
  [airport] wrote 370 reports to ./korpus_tierp (…)
  active corpus: ./korpus_tierp   ground truth: {'civil': 370}
7S> add-hostiles --type recon              # ingen --corpus behövs
7S> add-protesters --type demonstranter
7S> feed --dest ./inkorg --auto 10         # matar i bakgrunden; prompten är kvar
7S> pause                                  # håll flödet
7S> resume                                 # fortsätt
7S> status                                 # visa aktiv korpus och pågående flöde
7S> stop
7S> quit
```

Kommandona (`generate`, `add-hostiles`, `add-protesters`, `feed`) tar samma flaggor som
i engångsläget nedan; kör `<kommando> -h` i skalet för detaljer. Sessionskommandon:
`use <mapp>` (sätt aktiv korpus), `status`, `pause` · `resume` · `stop` (styr ett
bakgrundsflöde), `help`, `quit`.

## Grafiskt gränssnitt (GUI)

Kör `7s-generator gui` för att öppna en lokal webb-GUI i webbläsaren — endast
standardbiblioteket, lyssnar bara på 127.0.0.1 och gör inga nätverksanrop
(fungerar air-gapped). Flikar:

- **Generera** — formulär med smarta defaults och **live-förhandsvisning**:
  samma seed ⇒ förhandsvisningen är exakt de första rapporterna ur skarp
  körning. Skyddar mot oavsiktlig överskrivning av befintliga mappar.
- **Korpus** — välj aktiv korpus och se facit-räknarna.
- **Mata ut** — starta/pausa/återuppta/stoppa en matning med progressbar och
  leveranslogg (samma bakgrundsmatning som skalet).

`--port N` byter port, `--no-browser` låter bli att öppna webbläsaren.

## Kommandon

De fem kommandona nedan fungerar både i skalet och som **engångskommandon** för
skript/CI.

### 1. `generate` — normal aktivitet
```bash
python3 -m corpusgen generate \
  --aoi 60.345,17.422 --radius 3 --area airport \
  --from 2026-06-15 --days 14 \
  --callsigns AQ,BQ,CQ,DQ --name "Tierp flygfält" \
  --out ./corpus_tierp
```
- `--aoi LAT,LON` — objektet/området som ska skyddas (närhetscentrum).
- `--radius KM` — namngivna platser sprids ut inom denna radie, var och en tilldelad en
  **anropssignal** efter bäring (en sektor per pluton).
- `--area` — `urban · suburban · rural · airport · port · military · coastal ·
  forest`. Sätter aktivitetsvokabulären **och basfrekvensen för rapporter** (urbant
  livligt, rural/forest glest).
- `--from` + (`--to` | `--days`) — kalenderfönstret. **Årstiden** (från startmånaden)
  påverkar klädsel, dagsljustimmar och civil volym.
- Antalet rapporter härleds från `frekvens × dagar × årstid` (åsidosätt med
  `--reports`).
- `--images` (valfritt) bifogar ett **bekräftande skyltfoto** till varje rapport vars
  text nämner en registreringsskylt — skylten renderas läsbart *och* bäddas in i
  JPEG-kommentaren (`7SPLATE:`) så att en offline-konsument kan läsa den. Kräver
  **`images`-tillägget** (installerar Pillow — se [Installation /
  körning](#installation--körning)); allt annat är endast standardbibliotek.
- `--obsidian` (valfritt) gör utdata **Obsidian-kompatibel och identisk med källappens
  format**: bilder bäddas in som `## Bilagor` + `![[wikilänk]]` i per-meddelande-mappar.
  Utan flaggan används portabel standard-Markdown (`![](attachments/…)`) som renderas i
  vilken Markdown-läsare som helst. Påverkar bara rapporter som har ett foto (`--images`);
  allt annat (frontmatter, MGRS med mellanslag, m.m.) är identiskt i båda lägena.

### 2. `add-hostiles` — en hotcell
```bash
python3 -m corpusgen add-hostiles --corpus ./corpus_tierp --type recon
```
Injicerar **2–10** distinkta fiender (slumpmässigt om inte `--count` anges) av en
`--type` (`recon · sabotage · infiltration · terrorism`), nära AOI, tidsviktade,
återkommande 1–4× var. Detekterbara endast som ett spatio-temporalt / beteendemässigt
mönster.

### 3. `add-protesters` — utmanande civila (brus)
```bash
python3 -m corpusgen add-protesters --corpus ./corpus_tierp --type miljöaktivister
```
Injicerar en **grupp** (`demonstranter · miljöaktivister · fredsaktivister`) som samlas
på en plats under en dag — inte fientlig, men ett spatio-temporalt kluster som prövar en
detektors precision.

### 4. `feed` — droppa en korpus till en målmapp
```bash
python3 -m corpusgen feed --corpus ./corpus_tierp --dest /sökväg/till/inkorg
```
Levererar rapporterna från korpusmappen till valfri målmapp i kronologisk ordning —
antingen **i komprimerad tid** (`--auto MINS`) eller **i satser** (`--send N`) — och
härmar en central app som droppar ut meddelanden över tid. Interaktivt som standard
(`send [n]` · `auto [mins]` · `pause` · `resume` · `stop` · `status` · `reset` ·
`quit`); kopierar refererade bilagor så att bildinbäddningar fungerar. Engångsflaggor
för skript/CI: `--send N` · `--auto MINS` · `--reset` · `--status`. Med `--auto` (i
skalet eller feed-läget) körs flödet i bakgrunden och kan pausas från prompten.

### 5. `score` — poängsätt en detektor mot facit
```bash
python3 -m corpusgen score --corpus ./corpus_tierp --detections utpekningar.json
```
Jämför en detektors utpekningar med `ground_truth.json` och räknar
precision/recall/F1 — totalt (*icke-civil*, label-agnostiskt), per label och per
subtyp — plus **celltäckning** (andel hotcellsmedlemmar med minst en korrekt
flaggad rapport). Detektionsfilen är en JSON-lista av
`{"file": "TNR….md", "label": "hostile"|"protester"}`, eller bara filnamn
(tolkas som `hostile`). `--json` ger maskinläsbart resultat och `--min-f1 X`
gör kommandot till en CI-grind (felkod om icke-civil-F1 < X).

## Utdata

En korpusmapp innehåller:
- `TNR<DDHHMM>.md` — rapporterna (7S-format).
- `ground_truth.json` — en rad per rapport: `truth` (`civil` / `hostile` /
  `protester`), `subtype`, `member`, `plate`, `sector`, `callsign` — så att du kan mäta
  täckning och precision (recall/precision).
- `meta.json` — hur den byggdes (AOI, radie, område, datum, anropssignaler, de placerade
  platserna), så att tilläggskommandona injicerar konsekvent i samma område.

## Utöka

Allt innehåll om "vad en rapport säger" — områdesprofiler, säsongsklädsel och
fiende-/demonstrantrepertoarerna — är deklarativ data i
[`corpusgen/content.py`](corpusgen/content.py). Lägg till en områdestyp eller ett hotläge
genom att redigera den enda filen; genereringslogiken lämnas orörd.

## Rapportformat

Varje rapport är en `7S-rapport`-Markdown-fil med YAML-frontmatter (`id`, `tnr`,
`tidpunkt`, `plats`, valfria `signal_*`-leveransfält och `lat`/`lon`) följt av
7S-kroppen (`Stund`, `Ställe` med MGRS-ruta med mellanslag, `Händelse`, valfri `Symbol`,
`Sagesman`, `Sedan`). Frontmatter och kropp är identiska oavsett läge.

När `--images` används läggs en `## Bilagor`-sektion till. Bildinbäddningen beror på
läget:

- **standard (portabelt):** `![bild.jpg](attachments/bild.jpg)` — vanlig Markdown,
  bilder i `attachments/`, renderas i vilken Markdown-läsare som helst.
- **`--obsidian` (identiskt med källappen):** `![[<signaltid>_<DDHHMM>-<avsändare>/bild.jpg]]`
  — Obsidian-wikilänk, bilder i en per-meddelande-mapp bredvid rapporterna.

I båda fallen skrivs skylten även in i JPEG-kommentaren (markören `7SPLATE:`) så att en
offline-konsument kan läsa den utan OCR. Rapportrenderingen finns i
[`corpusgen/render.py`](corpusgen/render.py) och MGRS-hantering i
[`corpusgen/mgrs.py`](corpusgen/mgrs.py).
