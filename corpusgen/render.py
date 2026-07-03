"""Render a report record into new-format 7S-rapport markdown (the format the ODEN
plugin reads): Händelse free-prose, MGRS grid in Ställe, signal_* frontmatter, an
optional Symbol, no wikilinks."""


def tnr_from(dt):
    return dt.strftime("%d%H%M")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def render(rec):
    tnr = rec["tnr"]
    fm = ["---", f"id: 7S-{rec['uuid']}", "typ: 7S-rapport", f'tnr: "{tnr}"',
          f'tidpunkt: "{rec["tidpunkt"]}"']
    if rec.get("signal_tidpunkt"):
        fm.append(f'signal_tidpunkt: "{rec["signal_tidpunkt"]}"')
    if rec.get("sender"):
        fm += [f'signal_avsandare_nummer: "{rec["sender"]}"',
               f'signal_avsandare_id: "{rec["sender"]}"']
    fm.append(f'plats: "{rec["plats"]}"')
    if rec.get("lat") is not None:
        fm += [f"lat: {rec['lat']}", f"lon: {rec['lon']}",
               f'location: "{rec["lat"]},{rec["lon"]}"']
    fm += [f"sagesman: {rec['callsign']}", "---", ""]

    body = [f"**TNR:** {tnr}", "", f"**Stund:** {rec['stund']}", "",
            f"**Ställe:** {rec['stalle']}", "", f"**Händelse:** {rec['handelse']}", ""]
    if rec.get("symbol"):
        body += [f"**Symbol:** {rec['symbol']}", ""]
    body += [f"**Sagesman:** {rec['callsign']}", "", "**Sedan:** -", ""]
    return "\n".join(fm) + "\n".join(body) + "\n"
