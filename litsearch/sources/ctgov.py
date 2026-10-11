"""ClinicalTrials.gov API v2.

A strategy line is either a string (used as query.term, Essie syntax) or a dict of API parameters
such as {"query.cond": "fracture", "query.intr": "vitamin D OR cholecalciferol"}.
"""
from __future__ import annotations

import sys

from .. import net
from ..records import new_record, split_display_name

API = "https://clinicaltrials.gov/api/v2/studies"


def _params(q) -> dict:
    if isinstance(q, dict):
        return {k: v for k, v in q.items() if v}
    return {"query.term": q}


def describe(q) -> str:
    if isinstance(q, dict):
        names = {"query.cond": "Condition", "query.intr": "Intervention", "query.term": "Other terms",
                 "query.titles": "Title", "query.outc": "Outcome"}
        return "; ".join(f"{names.get(k, k)}: {v}" for k, v in q.items() if v)
    return str(q)


def count(q) -> tuple[int, str]:
    d = net.get_json(API, {**_params(q), "countTotal": "true", "pageSize": 1, "format": "json"}, min_interval=0.3)
    return int(d.get("totalCount", 0)), ""


def fetch(q) -> list[dict]:
    recs, token = [], None
    while True:
        p = {**_params(q), "pageSize": 1000, "format": "json", "countTotal": "true"}
        if token:
            p["pageToken"] = token
        d = net.get_json(API, p, min_interval=0.3, timeout=120)
        recs.extend(_record(s) for s in d.get("studies", []))
        print(f"  ClinicalTrials.gov {len(recs)}/{d.get('totalCount', '?')}", file=sys.stderr)
        token = d.get("nextPageToken")
        if not token:
            break
    return recs


def _record(s: dict) -> dict:
    ps = s.get("protocolSection", {})
    idm = ps.get("identificationModule", {})
    st = ps.get("statusModule", {})
    desc = ps.get("descriptionModule", {})
    cond = ps.get("conditionsModule", {})
    arms = ps.get("armsInterventionsModule", {})
    design = ps.get("designModule", {})
    spons = ps.get("sponsorCollaboratorsModule", {})
    contacts = ps.get("contactsLocationsModule", {})
    nct = idm.get("nctId", "")
    start = (st.get("startDateStruct") or {}).get("date", "")
    officials = [split_display_name(o.get("name", "")) for o in contacts.get("overallOfficials", []) if o.get("name")]
    interventions = [i.get("name", "") for i in arms.get("interventions", [])]
    phases = ", ".join(design.get("phases", []) or [])
    meta = [f"Status: {st.get('overallStatus', '')}", f"Study type: {design.get('studyType', '')}"]
    if phases:
        meta.append(f"Phase: {phases}")
    meta.append(f"Results posted: {'yes' if s.get('hasResults') else 'no'}")
    meta.append(f"Interventions: {'; '.join(interventions)}")
    return new_record(
        "ctgov", type="TRIAL", title=idm.get("officialTitle") or idm.get("briefTitle", ""),
        authors=officials or ([spons.get("leadSponsor", {}).get("name", "")] if spons.get("leadSponsor") else []),
        year=start[:4], journal="ClinicalTrials.gov",
        abstract=(desc.get("briefSummary", "") + "\n\n" + " | ".join(meta)).strip(),
        keywords=cond.get("conditions", []) + cond.get("keywords", []) + interventions,
        pubtypes=["Clinical trial registration"], accession=nct,
        urls=[f"https://clinicaltrials.gov/study/{nct}"], db_label="ClinicalTrials.gov",
        notes=f"{nct}; {st.get('overallStatus', '')}; {phases}",
    )
