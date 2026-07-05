"""A corpus on disk: a directory of TNR*.md reports, a ground_truth.json (one row
per report with its TRUE event type), and a meta.json describing how it was built
(AOI, radius, area type, dates, callsigns, locations) so the augment commands can
inject hostiles/protesters consistently into the same area and time window."""
import json
import re
import shutil
from pathlib import Path

from .render import render

# per-message attachment folder, e.g. 20260626111626_261116-<sender>
_ATT_DIR = re.compile(r"^\d{14}_\d{6}-")


class Corpus:
    def __init__(self, path):
        self.path = Path(path)
        self.meta = {}
        self.ground_truth = []
        self._seen_tnr = {}

    def clear_attachments(self):
        """Remove the per-message attachment folders kept beside the .md reports."""
        for d in self.path.glob("*"):
            if d.is_dir() and _ATT_DIR.match(d.name):
                shutil.rmtree(d)

    # --- create / load -------------------------------------------------------
    @classmethod
    def create(cls, path, meta):
        c = cls(path)
        c.path.mkdir(parents=True, exist_ok=True)
        for old in c.path.glob("*.md"):
            old.unlink()
        c.clear_attachments()
        c.meta = meta
        return c

    @classmethod
    def load(cls, path):
        c = cls(path)
        if not c.path.exists():
            raise FileNotFoundError(f"corpus not found: {path}")
        c.meta = json.loads((c.path / "meta.json").read_text(encoding="utf-8"))
        gt_path = c.path / "ground_truth.json"
        c.ground_truth = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else []
        for row in c.ground_truth:
            base = row["file"].split("_")[0].replace(".md", "")
            c._seen_tnr[base] = c._seen_tnr.get(base, 0) + 1
        return c

    # --- writing -------------------------------------------------------------
    def add(self, rec, truth, subtype=None, member=None):
        """Write one report + its ground-truth row. Returns the filename."""
        base = f"TNR{rec['tnr']}"
        self._seen_tnr[base] = self._seen_tnr.get(base, 0) + 1
        count = self._seen_tnr[base]
        if count > 1:  # collision: carry the _N suffix into tnr (field, **TNR:**, filename)
            rec = dict(rec)
            rec["tnr"] = f"{rec['tnr']}_{count}"
        fname = f"TNR{rec['tnr']}.md"
        (self.path / fname).write_text(render(rec), encoding="utf-8")
        self.ground_truth.append({
            "file": fname, "id": f"7S-{rec['uuid']}", "tnr": rec["tnr"],
            "tidpunkt": rec["tidpunkt"], "truth": truth, "subtype": subtype,
            "member": member, "plate": rec.get("plate"), "sector": rec.get("sector"),
            "callsign": rec.get("callsign"),
        })
        return fname

    def save(self):
        # ground truth in time order for readability
        self.ground_truth.sort(key=lambda r: (r["tidpunkt"], r["tnr"]))
        (self.path / "ground_truth.json").write_text(
            json.dumps(self.ground_truth, ensure_ascii=False, indent=1), encoding="utf-8")
        (self.path / "meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- summary -------------------------------------------------------------
    def counts(self):
        out = {}
        for r in self.ground_truth:
            key = r["truth"] if not r["subtype"] else f"{r['truth']}:{r['subtype']}"
            out[key] = out.get(key, 0) + 1
        return out
