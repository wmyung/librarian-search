"""OpenAlex for backward (reference list) and forward (cited-by) citation searching."""
from __future__ import annotations

import os
import re
import sys

from .. import net
from ..records import new_record, norm_doi, split_display_name

API = "https://api.openalex.org"


def _p(extra: dict | None = None) -> dict:
    p = dict(extra or {})
    if os.environ.get("OPENALEX_API_KEY"):
        p["api_key"] = os.environ["OPENALEX_API_KEY"]
    return p


def resolve(seed: str) -> dict:
    s = seed.strip()
    if re.fullmatch(r"\d{5,9}", s) or s.lower().startswith("pmid:"):
        key = "pmid:" + re.sub(r"\D", "", s)
    elif s.upper().startswith("W") and s[1:].isdigit():
        key = s.upper()
    else:
        d = norm_doi(s)
        if not d:
            raise ValueError(f"Cannot resolve seed: {seed}")
        key = "doi:" + d
    return net.get_json(f"{API}/works/{key}", _p(), min_interval=0.12)


def _batch(ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        chunk = [x.rsplit("/", 1)[-1] for x in ids[i:i + 50]]
        d = net.get_json(f"{API}/works", _p({"filter": "openalex_id:" + "|".join(chunk), "per-page": 50}),
                         min_interval=0.12)
        out.extend(d.get("results", []))
    return out


def citing(work_id: str, limit: int = 5000) -> list[dict]:
    wid = work_id.rsplit("/", 1)[-1]
    cursor, out = "*", []
    while cursor and len(out) < limit:
        d = net.get_json(f"{API}/works", _p({"filter": f"cites:{wid}", "per-page": 200, "cursor": cursor}),
                         min_interval=0.12)
        out.extend(d.get("results", []))
        cursor = d.get("meta", {}).get("next_cursor")
        if not d.get("results"):
            break
    return out


def citation_search(seeds: list[str], direction: str = "both") -> tuple[list[dict], list[dict]]:
    """Return (records, per-seed log)."""
    recs, log = [], []
    for seed in seeds:
        try:
            w = resolve(seed)
        except Exception as e:  # noqa: BLE001 - report and continue with other seeds
            log.append({"seed": seed, "error": str(e)})
            print(f"  ! seed {seed}: {e}", file=sys.stderr)
            continue
        label = f"{(w.get('authorships') or [{}])[0].get('author', {}).get('display_name', '?')} {w.get('publication_year', '')}"
        back, fwd = [], []
        if direction in ("both", "backward"):
            back = _batch(w.get("referenced_works", []))
        if direction in ("both", "forward"):
            fwd = citing(w["id"])
        for x in back:
            recs.append(to_record(x, f"Reference of {label} ({seed})"))
        for x in fwd:
            recs.append(to_record(x, f"Cites {label} ({seed})"))
        log.append({"seed": seed, "openalex": w["id"], "title": w.get("display_name", ""),
                    "backward": len(back), "forward": len(fwd)})
        print(f"  {seed}: references {len(back)}, cited-by {len(fwd)}", file=sys.stderr)
    return recs, log


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


TYPE_MAP = {"article": "JOUR", "review": "JOUR", "book-chapter": "CHAP", "book": "BOOK",
            "dissertation": "THES", "preprint": "PREPRINT", "report": "RPRT"}


def to_record(w: dict, note: str = "") -> dict:
    ids = w.get("ids") or {}
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    b = w.get("biblio") or {}
    pages = b.get("first_page") or ""
    if b.get("last_page") and b.get("last_page") != pages:
        pages = f"{pages}-{b['last_page']}"
    pmid = (ids.get("pmid") or "").rsplit("/", 1)[-1]
    return new_record(
        "citation", type=TYPE_MAP.get(w.get("type", ""), "JOUR"), title=w.get("display_name") or "",
        authors=[split_display_name(a.get("author", {}).get("display_name", "")) for a in w.get("authorships", [])],
        year=str(w.get("publication_year") or ""), journal=src.get("display_name", ""),
        volume=b.get("volume") or "", issue=b.get("issue") or "", pages=pages,
        abstract=_abstract(w.get("abstract_inverted_index")),
        keywords=[k.get("display_name", "") for k in w.get("keywords", [])],
        pubtypes=[w.get("type", "")], doi=w.get("doi") or "", pmid=pmid,
        issn=(src.get("issn_l") or ""), urls=[w.get("doi") or w.get("id", "")],
        language=w.get("language") or "", accession=w.get("id", "").rsplit("/", 1)[-1],
        db_label="OpenAlex", notes=note,
    )
