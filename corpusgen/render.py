"""Render a report record into 7S-rapport markdown: Händelse free-prose, a spaced
MGRS grid in Ställe, signal_* frontmatter, an optional Symbol, and (when a photo is
attached) a `## Bilagor` section with an Obsidian wikilink embed — matching the
format of reports captured by the source app."""


def tnr_from(dt):
    return dt.strftime("%d%H%M")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def render(rec):
    tnr = rec["tnr"]
    lines = ["---", f"id: 7S-{rec['uuid']}", "typ: 7S-rapport", f'tnr: "{tnr}"',
             f'tidpunkt: "{rec["tidpunkt"]}"']
    if rec.get("signal_tidpunkt"):
        lines.append(f'signal_tidpunkt: "{rec["signal_tidpunkt"]}"')
    if rec.get("sender"):
        lines += [f'signal_avsandare_nummer: "{rec["sender"]}"',
                  f'signal_avsandare_id: "{rec["sender"]}"']
    lines.append(f'plats: "{rec["plats"]}"')
    if rec.get("lat") is not None:
        lines += [f"lat: {rec['lat']:.5f}", f"lon: {rec['lon']:.5f}",
                  f'location: "{rec["lat"]:.5f},{rec["lon"]:.5f}"']
    lines += [f"sagesman: {rec['callsign']}", "---", ""]

    lines += [f"**TNR:** {tnr}", "", f"**Stund:** {rec['stund']}", "",
              f"**Ställe:** {rec['stalle']}", "", f"**Händelse:** {rec['handelse']}", ""]
    if rec.get("symbol"):
        lines += [f"**Symbol:** {rec['symbol']}", ""]
    lines += [f"**Sagesman:** {rec['callsign']}", "", "**Sedan:** -", ""]
    if rec.get("image"):
        lines += ["## Bilagor", "", f"![[{rec['image']}]]", ""]
    return "\n".join(lines) + "\n"
