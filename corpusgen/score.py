"""Score a detector's output against a corpus's ground truth.

The detections file (JSON) is forgiving about shape; all of these work:

  * a list of objects:  [{"file": "TNR261116.md", "label": "hostile"}, …]
    — ``label`` is one of ``hostile`` / ``protester`` (``civil`` is accepted
    and means "explicitly not flagged"); extra keys are ignored.
  * a list of bare filenames: ["TNR261116.md", …] — shorthand for hostile.
  * either of the above wrapped in {"detections": […]}.

Matching is by report filename (basename, case-insensitive), which is stable
across `feed` delivery (reports are copied under the same name).

Metrics: precision/recall/F1 for the label-agnostic *icke-civil* row (did the
detector flag the report at all?) and per label, recall per subtype, and cell
coverage (how many distinct hostile members had at least one report flagged
hostile). The optional ``--min-f1`` gate (CI) checks the icke-civil F1.
"""
import json
from pathlib import Path

_FLAG_LABELS = ("hostile", "protester")
_LABELS = _FLAG_LABELS + ("civil",)


# --- detections file ----------------------------------------------------------
def _norm_name(name):
    """Filename key: basename only (either separator), case-insensitive."""
    return str(name).replace("\\", "/").rsplit("/", 1)[-1].strip().lower()


def load_detections(path):
    """Read a detections file. Returns (dets, duplicates) where `dets` maps the
    normalised filename to its label. Raises ValueError with a Swedish message
    on a malformed file."""
    p = Path(path)
    try:
        # utf-8-sig: tolerate a BOM — PowerShell's `Out-File -Encoding utf8` adds one
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ValueError(f"detektionsfilen hittades inte: {p}")
    except json.JSONDecodeError as e:
        raise ValueError(f"detektionsfilen är inte giltig JSON: {e}")
    if isinstance(data, dict) and "detections" in data:
        data = data["detections"]
    if not isinstance(data, list):
        raise ValueError("detektionsfilen ska vara en JSON-lista "
                         '(eller {"detections": [...]})')
    dets, duplicates = {}, 0
    for i, item in enumerate(data):
        if isinstance(item, str):
            fname, label = item, "hostile"      # bare filename = flagged hostile
        elif isinstance(item, dict):
            if "file" not in item:
                raise ValueError(f'detektion {i} saknar "file": {item!r}')
            fname = item["file"]
            label = str(item.get("label", "hostile")).strip().lower()
            if label not in _LABELS:
                raise ValueError(f'detektion {i}: okänd label {label!r} '
                                 f"(giltiga: {', '.join(_LABELS)})")
        else:
            raise ValueError(f"detektion {i}: förväntade filnamn eller objekt, "
                             f"fick {type(item).__name__}")
        key = _norm_name(fname)
        if key in dets:
            duplicates += 1                     # last one wins
        dets[key] = label
    return dets, duplicates


# --- metrics ------------------------------------------------------------------
def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    if p is None or r is None:
        f1 = None
    else:
        f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def _gate_value(cls):
    """F1 for gating: vacuously perfect when there was nothing to find and
    nothing was flagged; 0.0 when F1 is undefined only on one side."""
    if cls["f1"] is not None:
        return cls["f1"]
    return 1.0 if cls["tp"] == cls["fp"] == cls["fn"] == 0 else 0.0


def score(ground_truth, dets):
    """Pure scoring: ground-truth rows (corpus.ground_truth) × detections map.
    Returns the full result dict (see format_report for the human view)."""
    truth = {_norm_name(r["file"]): r for r in ground_truth}
    unknown = sorted(k for k in dets if k not in truth)
    flagged = {k: v for k, v in dets.items() if k in truth and v in _FLAG_LABELS}

    # icke-civil: any flag counts, label-agnostic
    tp = sum(1 for k in flagged if truth[k]["truth"] != "civil")
    fp = len(flagged) - tp
    fn = sum(1 for k, r in truth.items() if r["truth"] != "civil" and k not in flagged)
    classes = {"icke-civil": _prf(tp, fp, fn)}

    for label in _FLAG_LABELS:                   # per-label: exact label match
        ltp = sum(1 for k, v in flagged.items() if v == label and truth[k]["truth"] == label)
        lfp = sum(1 for k, v in flagged.items() if v == label and truth[k]["truth"] != label)
        lfn = sum(1 for k, r in truth.items()
                  if r["truth"] == label and flagged.get(k) != label)
        classes[label] = _prf(ltp, lfp, lfn)

    subtypes = {}                                # recall per subtyp (label-correct)
    for k, r in truth.items():
        if r["truth"] == "civil":
            continue
        st = f"{r['truth']}:{r['subtype'] or '-'}"
        d = subtypes.setdefault(st, {"detected": 0, "total": 0})
        d["total"] += 1
        d["detected"] += flagged.get(k) == r["truth"]

    members = {}                                 # celltäckning: distinct hostile members
    for k, r in truth.items():
        if r["truth"] != "hostile" or not r.get("member"):
            continue
        m = members.setdefault(r["member"], {"detected": 0, "total": 0})
        m["total"] += 1
        m["detected"] += flagged.get(k) == "hostile"
    coverage = {"detected": sum(1 for m in members.values() if m["detected"]),
                "total": len(members), "members": members}

    per_label = {}
    for v in dets.values():
        per_label[v] = per_label.get(v, 0) + 1
    return {
        "reports": len(truth),
        "detections": {"total": len(dets), "per_label": per_label,
                       "unknown_files": unknown},
        "classes": classes,
        "subtype_recall": dict(sorted(subtypes.items())),
        "member_coverage": coverage,
    }


# --- presentation ---------------------------------------------------------------
def _num(x):
    return "  –  " if x is None else f"{x:.2f} "


def format_report(res, counts, corpus_path):
    d = res["detections"]
    lines = [f"Korpus: {corpus_path}   ({res['reports']} rapporter: "
             + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ")",
             f"Detektioner: {d['total']} ("
             + ", ".join(f"{k} {v}" for k, v in sorted(d["per_label"].items())) + ")"]
    if d["duplicates"]:
        lines.append(f"  obs: {d['duplicates']} dubblettdetektion(er) — sista vann")
    if d["unknown_files"]:
        shown = ", ".join(d["unknown_files"][:5])
        more = f" (+{len(d['unknown_files']) - 5} till)" if len(d["unknown_files"]) > 5 else ""
        lines.append(f"  obs: {len(d['unknown_files'])} okända filer utanför korpusen, "
                     f"exkluderade: {shown}{more}")
    lines += ["", "              prec   recall   F1      TP   FP   FN"]
    for name, c in res["classes"].items():
        lines.append(f"  {name:<11} {_num(c['precision'])}  {_num(c['recall'])}  "
                     f"{_num(c['f1'])}  {c['tp']:>3}  {c['fp']:>3}  {c['fn']:>3}")
    if res["subtype_recall"]:
        parts = [f"{st} {v['detected']}/{v['total']}" for st, v in res["subtype_recall"].items()]
        lines += ["", "  recall per subtyp:  " + "   ".join(parts)]
    cov = res["member_coverage"]
    if cov["total"]:
        parts = [f"{m} {v['detected']}/{v['total']}" for m, v in sorted(cov["members"].items())]
        lines.append(f"  celltäckning: {cov['detected']}/{cov['total']} medlemmar "
                     f"med ≥1 träff   ({', '.join(parts)})")
    return "\n".join(lines)


# --- entry point (CLI + shell) ---------------------------------------------------
def run(corpus, detections_path, json_out=False, min_f1=None, out=print):
    """Score `detections_path` against `corpus` (a loaded Corpus). Prints via
    `out`; returns True when no gate is set or the gate passes."""
    dets, duplicates = load_detections(detections_path)
    res = score(corpus.ground_truth, dets)
    res["detections"]["duplicates"] = duplicates
    res["corpus"] = str(corpus.path)
    gate_val = _gate_value(res["classes"]["icke-civil"])
    passed = True
    if min_f1 is not None:
        passed = gate_val >= min_f1
        res["gate"] = {"min_f1": min_f1, "value": gate_val, "passed": passed}
    if json_out:
        out(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        out(format_report(res, corpus.counts(), corpus.path))
        if min_f1 is not None:
            verdict = "OK" if passed else "UNDERKÄND"
            out(f"\n  grind: icke-civil F1 {gate_val:.2f} mot krav {min_f1:.2f} — {verdict}")
    return passed
