import sqlite3
import struct

from litsearch.dedup import deduplicate
from litsearch.endnote import en_make_sort_key, write_library
from litsearch.parsers import parse_medline, parse_ris
from litsearch.project import expand_line
from litsearch.records import new_record, norm_doi, title_key

RIS = """TY  - JOUR
AU  - Doe, A.
AU  - Roe, M.
TI  - Daily vitamin D3 versus placebo for fracture prevention: A double blind randomized controlled trial
T2  - Journal of Example Medicine
PY  - 2012
VL  - 7
SP  - 30
EP  - 35
DO  - https://doi.org/10.1000/ABC.123.
C5  - 12345678
ER  -

TY  - CHAP
AU  - Smith JA
TI  - A chapter
ER  -
"""

MEDLINE = """PMID- 12345678
STAT- MEDLINE
TI  - [Daily vitamin D3 versus placebo for fracture prevention: a double blind
      randomized controlled trial].
FAU - Doe, Alex
AU  - Doe A
DP  - 2012 Winter
JT  - Journal of example medicine
LID - 10.1000/abc.123 [doi]
PT  - Randomized Controlled Trial
"""


def test_parsers():
    r = parse_ris(RIS, "embase")
    assert len(r) == 2
    assert r[0]["doi"] == "10.1000/abc.123"
    assert r[0]["pmid"] == "12345678"
    assert r[0]["pages"] == "30-35"
    assert r[1]["authors"] == ["Smith, J. A."] and r[1]["type"] == "CHAP"
    m = parse_medline(MEDLINE, "pubmed")
    assert m[0]["authors"] == ["Doe, A."] and m[0]["year"] == "2012"
    assert m[0]["title"].startswith("[Daily vitamin D3 versus placebo for fracture prevention: a double blind randomized")


def test_title_key_keeps_bracketed_titles():
    assert title_key("[Comparative efficacy of X]") == title_key("Comparative efficacy of X.")
    assert norm_doi("doi: 10.1002/14651858.CD004857.pub2.") == "10.1002/14651858.cd004857.pub2"


def test_dedup_priority_and_title_match():
    a = new_record("embase", title="Use of vitamin K in osteoporosis", authors=["Smith, P."], year="2008")
    b = new_record("wos", title="USE OF VITAMIN K IN OSTEOPOROSIS", authors=["Smith, P."], year="2008")
    c = new_record("pubmed", title="Something else entirely about calcium", authors=["Doe, J."], year="2001", doi="10.1000/x")
    d = new_record("embase", title="Different title", authors=["Doe, J."], year="2001", doi="10.1000/X", pages="5")
    c["pages"] = "5-9"
    e = new_record("embase", title="Use of vitamin K in osteoporosis", authors=["Other, Q."], year="1995")
    u, dups = deduplicate([a, b, c, d, e], ["pubmed", "embase", "wos"])
    assert len(u) == 3 and len(dups) == 2
    kept = {r["db"] + r["title"][:6] for r in u}
    assert "pubmedSometh" in kept and "embaseUse of" in kept
    assert {x["dup_reason"] for x in dups} == {"DOI", "Title/Year/Author"}


def test_expand_line():
    lines = [{"q": "a[tiab]"}, {"q": "b[tiab]"}, {"q": "#1 OR #2"}, {"q": "c"}, {"q": "#3 AND #4"}]
    assert expand_line(lines, 4) == "((a[tiab]) OR (b[tiab])) AND (c)"


def test_sort_key_matches_endnote():
    assert en_make_sort_key("Du, P.\rChen, X.", 2) == "DU P   CHEN X   "
    assert en_make_sort_key("Al Lihabi, A. A.", 2) == "AL LIHABI AA  "


def test_write_library(tmp_path):
    recs = [new_record("pubmed", title=f"T{i} about vitamin D randomized", authors=["Du, P."], year="2020",
                       doi=f"10.1000/{i % 3}") for i in range(5)]
    u, d = deduplicate(recs, ["pubmed"])
    from litsearch.classify import flags
    fl = {r["uid"]: flags(r) for r in u}
    p = write_library(tmp_path / "lib.enl", u, d, ["pubmed"], {"pubmed": 5}, fl)
    assert (tmp_path / "lib.Data" / "sdb" / "sdb.eni").exists()
    con = sqlite3.connect(p)
    con.create_collation("ENCIN_ko_KR", lambda a, b: (a > b) - (a < b))
    con.create_collation("ENCI_Base", lambda a, b: (a > b) - (a < b))
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert con.execute("select count(*), sum(trash_state) from refs").fetchone() == (5, 2)
    assert con.execute("select count(*) from refs_ord").fetchone()[0] == 5
    spec, mem = con.execute("select spec, members from groups where group_id=1").fetchone()
    assert b"PubMed 5" in spec
    hdr, n = struct.unpack("<ii", mem[:8])
    assert hdr == 0x02000000 and n == 3


def test_dedup_supplement_doi_not_merged():
    # one DOI for a whole conference supplement: distinct abstracts must stay separate
    a = new_record("embase", title="Abstract one about bone density", authors=["Lee, A."], year="2017",
                   doi="10.1000/supp-2017", pages="S10")
    b = new_record("embase", title="Completely different abstract on fracture healing", authors=["Kim, B."],
                   year="2017", doi="10.1000/supp-2017", pages="S55")
    u, d = deduplicate([a, b], ["embase"])
    assert len(u) == 2 and not d


def test_extras_overlap_previous_known_prisma(tmp_path):
    from litsearch.extras import mark_previous, match_known, overlap, parse_known, prisma_svg, write_asreview_csv
    a = new_record("pubmed", title="Vitamin D and hip fracture in older women", authors=["Doe, A."], year="2010",
                   pmid="11111111", doi="10.1000/a")
    b = new_record("embase", title="Vitamin D and hip fracture in older women", authors=["Doe, A."], year="2010",
                   doi="10.1000/a")
    c = new_record("embase", title="Calcium supplements and vertebral fracture", authors=["Roe, B."], year="2012")
    u, d = deduplicate([a, b, c], ["pubmed", "embase"])
    ov = overlap(u, ["pubmed", "embase"])
    assert ov["matrix"]["pubmed"]["embase"] == 1 and ov["only_in_source"]["embase"] == 1
    prev = [new_record("previous", title="Calcium supplements and vertebral fracture", authors=["Roe, B."], year="2012")]
    seen = mark_previous(u, prev)
    assert seen == {r["uid"] for r in u if r["title"].startswith("Calcium")}
    known = parse_known(["11111111", "10.1000/zzz", "# comment"])
    res = match_known(known, u, d)
    assert [k["found"] for k in res] == [True, False]
    ctx = {"db_order": ["pubmed", "embase"], "retrieved": {"pubmed": 1, "embase": 2}, "n_dups": 1, "n_unique": 2}
    assert "Duplicate records removed (n = 1)" in prisma_svg(ctx)
    write_asreview_csv(tmp_path / "a.csv", u, {u[0]["uid"]})
    assert (tmp_path / "a.csv").read_text().splitlines()[1].endswith(",1")


def test_retracted_flag():
    from litsearch.classify import flags
    r = new_record("pubmed", title="Some trial", pubtypes=["Journal Article", "Retracted Publication"])
    assert flags(r)["retracted"]
