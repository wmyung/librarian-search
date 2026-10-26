"""Project folder layout, strategy file and database registry."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# id -> display info. "auto" sources are searched by litsearch; "manual" sources are searched by the
# user on the vendor platform (institutional access) and imported as RIS / MEDLINE export files.
DATABASES = {
    "pubmed":       {"name": "MEDLINE (PubMed)", "short": "PubMed", "platform": "PubMed, U.S. National Library of Medicine", "mode": "auto"},
    "ovid_medline": {"name": "Ovid MEDLINE", "short": "Ovid MEDLINE", "platform": "Ovid (Wolters Kluwer)", "mode": "manual"},
    "embase":       {"name": "Embase", "short": "Embase", "platform": "Embase.com (Elsevier)", "mode": "manual"},
    "cochrane":     {"name": "Cochrane Library", "short": "Cochrane", "platform": "Cochrane Library (Wiley): CDSR and CENTRAL", "mode": "manual"},
    "wos":          {"name": "Web of Science Core Collection", "short": "WoS", "platform": "Web of Science (Clarivate)", "mode": "manual"},
    "scopus":       {"name": "Scopus", "short": "Scopus", "platform": "Scopus (Elsevier)", "mode": "manual"},
    "psycinfo":     {"name": "APA PsycInfo", "short": "PsycInfo", "platform": "Ovid or EBSCOhost", "mode": "manual"},
    "cinahl":       {"name": "CINAHL", "short": "CINAHL", "platform": "EBSCOhost", "mode": "manual"},
    "koreamed":     {"name": "KoreaMed", "short": "KoreaMed", "platform": "KoreaMed (Korean Association of Medical Journal Editors)", "mode": "manual"},
    "kmbase":       {"name": "KMbase", "short": "KMbase", "platform": "KMbase (Korean Medical Database)", "mode": "manual"},
    "ictrp":        {"name": "WHO ICTRP", "short": "ICTRP", "platform": "WHO International Clinical Trials Registry Platform", "mode": "manual"},
    "europepmc":    {"name": "Europe PMC", "short": "Europe PMC", "platform": "Europe PMC (EMBL-EBI) REST API", "mode": "auto"},
    "ctgov":        {"name": "ClinicalTrials.gov", "short": "CT.gov", "platform": "ClinicalTrials.gov API v2 (U.S. NLM)", "mode": "auto"},
    "citation":     {"name": "Citation searching", "short": "Citation", "platform": "OpenAlex (backward and forward citation searching)", "mode": "auto"},
    "citation_scopus": {"name": "Citation searching (Scopus)", "short": "Citation (Scopus)", "platform": "Scopus (Elsevier): references and citing documents of key articles", "mode": "manual"},
    "citation_wos": {"name": "Citation searching (Web of Science)", "short": "Citation (WoS)", "platform": "Web of Science Core Collection (Clarivate): cited references and citing articles of key articles", "mode": "manual"},
}
DEFAULT_PRIORITY = ["pubmed", "ovid_medline", "embase", "cochrane", "wos", "scopus", "psycinfo", "cinahl",
                    "koreamed", "kmbase", "europepmc", "ctgov", "ictrp", "citation_scopus", "citation_wos", "citation"]
CITATION_SOURCES = ("citation", "citation_scopus", "citation_wos")


def db_info(db_id: str) -> dict:
    base = db_id.split(":")[0]
    info = dict(DATABASES.get(base, {"name": db_id, "short": db_id, "platform": "", "mode": "manual"}))
    info["id"] = db_id
    return info


@dataclass
class Project:
    root: Path

    @property
    def strategy_path(self) -> Path:
        return self.root / "strategy.json"

    @property
    def records_dir(self) -> Path:
        return self.root / "records"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    @property
    def out_dir(self) -> Path:
        return self.root / "out"

    def load(self) -> dict:
        if not self.strategy_path.exists():
            raise SystemExit(f"strategy.json not found: {self.strategy_path}")
        return json.loads(self.strategy_path.read_text(encoding="utf-8"))

    def save(self, strategy: dict) -> None:
        self.strategy_path.write_text(json.dumps(strategy, ensure_ascii=False, indent=2), encoding="utf-8")

    def db_entry(self, strategy: dict, db_id: str) -> dict:
        for d in strategy.get("databases", []):
            if d["id"] == db_id:
                return d
        d = {"id": db_id, "lines": []}
        strategy.setdefault("databases", []).append(d)
        return d


_REF = re.compile(r"#(\d+)\b")


def expand_line(lines: list[dict], idx: int, _depth: int = 0) -> str:
    """Expand '#3 OR #5' style references into a single self-contained query (1-based numbering)."""
    if _depth > 50:
        raise ValueError("Circular line reference in search strategy")
    q = lines[idx]["q"]
    if not isinstance(q, str):
        return q

    def sub(m):
        n = int(m.group(1))
        if not 1 <= n <= len(lines) or n - 1 == idx:
            raise ValueError(f"line {idx + 1}: invalid reference #{n}")
        return "(" + expand_line(lines, n - 1, _depth + 1) + ")"

    return _REF.sub(sub, q)


def final_index(entry: dict) -> int:
    lines = entry.get("lines", [])
    f = entry.get("final")
    return (int(f) - 1) if f else len(lines) - 1


SKELETON = {
    "title": "",
    "review_type": "narrative review",
    "profile": "comprehensive",
    "objective": "",
    "concepts": [
        {"name": "", "description": "", "terms": []}
    ],
    "limits": "No limits on study design, language, or publication date.",
    "search_date": "",
    "databases": [
        {"id": "pubmed", "lines": [{"q": "", "note": ""}], "final": None},
        {"id": "europepmc", "lines": [{"q": ""}], "final": None},
        {"id": "ctgov", "lines": [{"q": {"query.cond": "", "query.intr": ""}}], "final": None},
        {"id": "embase", "lines": [{"q": "", "results": None}], "final": None},
        {"id": "cochrane", "lines": [{"q": "", "results": None}], "final": None},
        {"id": "wos", "lines": [{"q": "", "results": None}], "final": None},
    ],
    "priority": DEFAULT_PRIORITY,
    "citation": {"seeds": [], "direction": "both", "filter": ""},
}
