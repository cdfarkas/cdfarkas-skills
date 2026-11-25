"""Data-role trial on invented data.

make DIR        build the visible workspace given to a candidate
grade DIR       grade a candidate's files with hidden notes and a hidden store
selftest        a reference solution must pass, naive ones must fail
"""
import csv, json, sqlite3, subprocess, sys, tempfile, unicodedata
from pathlib import Path

TASKS = """# Assignment (invented data only)

Python, standard library only. Write only in this folder.

## T1. Data model
`schema.sql` (SQLite) for: advisor, client, note, transcript, report, export, audit event.
Several advisors share the database. Every table except the advisors table (`advisor`) carries `advisor_id`.
`datamap.csv`: one row per column, header `table,column,personal,purpose,retention,delete_path`, `personal` is yes or no.

## T2. Masking
`mask.py --notes DIR --roster FILE --out DIR`: writes each masked `.txt` note, same file name.
The roster lists the known forms and their pseudonym. Replace them, and also mask phone numbers, e-mails and birth dates.
Useful facts (durations, activities, ordinary words) must remain. Examples in `notes/` and `roster.json`.

## T3. Purge
`purge.py --root DIR --client ID`: erases every trace of the client in a store like `store/`, without damaging the other clients.
A file shared between clients must stay, minus the erased client's rows. Write `purge-proof.json` in DIR, with no personal data.
"""

VISIBLE = {
    "roster": [["CLIENT_1", ["Océane Valmier", "Océane"]], ["CONTACT_1", ["Didier Valmier", "Didier"]], ["PLACE_1", ["agence Grand-Pré"]]],
    "notes": {
        "a.txt": "Océane a relu le budget pendant 20 minutes. Didier Valmier est arrivé à 16 h. Téléphone : 06 39 98 12 34.",
        "b.txt": "Réunion calme à l'agence Grand-Pré. Océane a choisi le placement prudent.",
        "c.txt": "Née le 12/03/1984, Océane parle peu. Écrire à didier.v@example.org.",
    },
}

HIDDEN_ROSTER = [
    ["CLIENT_1", ["Claire Montbrun", "Claire", "Clairou"]], ["CLIENT_2", ["Édith Rocval", "Édith"]],
    ["CONTACT_1", ["Paul-Émile Montbrun", "Paul-Émile"]], ["CONTACT_2", ["Olivier Rocval", "Olivier"]],
    ["PLACE_1", ["UTB Les Cèdres", "Les Cèdres"]], ["ADVISOR_1", ["Maïwenn Le Drec", "Maïwenn"]],
]
# file: (text, strings that must disappear, strings that must stay)
HIDDEN = {
    "01.txt": ("Claire a présenté une offre claire pendant 25 minutes.", ["Claire "], ["offre claire", "25 minutes"]),
    "02.txt": ("CLAIRE MONTBRUN a ri. Clairou a signé le devis.", ["CLAIRE", "MONTBRUN", "Clairou"], ["a ri", "devis"]),
    "03.txt": ("Le contrat d'Édith et le dossier d’Édith sont rangés.", ["Édith"], ["contrat", "dossier", "rangés"]),
    "04.txt": ("Edith Rocval a planté un olivier devant la porte.", ["Edith", "Rocval"], ["un olivier devant la porte"]),
    "05.txt": (unicodedata.normalize("NFD", "Édith et Maïwenn ont relu 15 minutes le bilan."), ["Édith", "Maïwenn"], ["15 minutes", "bilan"]),
    "06.txt": ("Paul-Émile\nMontbrun a signé. Paul Émile rappellera mardi.", ["Paul-Émile", "Paul Émile", "Montbrun"], ["a signé", "mardi"]),
    "07.txt": ("À l'UTB\u00a0 Les Cèdres, Olivier ROCVAL attend. L'oliveraie est dessinée.", ["Les Cèdres", "Olivier ROCVAL"], ["oliveraie est dessinée"]),
    "08.txt": ("Appeler le +33 6 39 98 54 32 ou le 02.61.91.22.33, dossier 2026.", ["39 98 54 32", "61.91.22.33"], ["dossier 2026"]),
    "09.txt": ("Né le 3 mai 1979 ; mail : pe.montbrun+utb@example.org. Durée 40 min.", ["3 mai 1979", "pe.montbrun"], ["40 min"]),
    "10.txt": ("La lampe éclaire la pièce, il parle clairement. Maiwenn Le Drec valide 3 objectifs.", ["Maiwenn", "Le Drec"], ["éclaire la pièce", "parle clairement", "3 objectifs"]),
}


def norm(s):
    return unicodedata.normalize("NFC", s)


def make(d):
    d = Path(d)
    (d / "notes").mkdir(parents=True)
    (d / "TASKS.md").write_text(TASKS, encoding="utf-8")
    (d / "roster.json").write_text(json.dumps([{"pseudonym": p, "forms": f} for p, f in VISIBLE["roster"]], ensure_ascii=False, indent=1), encoding="utf-8")
    for n, t in VISIBLE["notes"].items():
        (d / "notes" / n).write_text(t, encoding="utf-8")
    store(d / "store", [(1, "Océane", "Valmier"), (2, "Basile", "Corvenne")])


def store(root, clients):
    root = Path(root)
    for s in ("recordings", "transcripts", "exports", "logs", "backup"):
        (root / s).mkdir(parents=True)
    db = sqlite3.connect(root / "app.db")
    db.executescript("""PRAGMA journal_mode=WAL;
    CREATE TABLE client(id INTEGER PRIMARY KEY, first TEXT, last TEXT);
    CREATE TABLE meeting(id INTEGER PRIMARY KEY, client_id INT REFERENCES client(id), recording TEXT, transcript TEXT);
    CREATE TABLE report(id INTEGER PRIMARY KEY, meeting_id INT REFERENCES meeting(id), body TEXT);
    CREATE TABLE audit_event(id INTEGER PRIMARY KEY, at TEXT, detail TEXT);""")
    rows, log = ["client_id;first;text"], []
    for i, f, l in clients:
        db.execute("INSERT INTO client VALUES(?,?,?)", (i, f, l))
        for k in (1, 2):
            mid = i * 100 + k
            a, t = f"recordings/m{mid}.wav", f"transcripts/m{mid}.txt"
            db.execute("INSERT INTO meeting VALUES(?,?,?,?)", (mid, i, a, t))
            db.execute("INSERT INTO report VALUES(?,?,?)", (mid, mid, f"{f} {l} a validé son dossier, réunion {mid}. " * 40))
            db.execute("INSERT INTO audit_event(at,detail) VALUES('2026-01-01',?)", (f"rapport de {f} {l} relu",))
            (root / a).write_bytes(b"RIFF" + f"title={f} {l}".encode())
            (root / t).write_text(f"{f} a présenté son budget, réunion {mid}.", encoding="utf-8")
            rows.append(f"{i};{f};réunion {mid}")
            log.append(f"2026-01-01 INFO envoi {f} {l} m{mid}")
    db.commit()
    (root / "exports" / "all.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (root / "logs" / "app.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    b = sqlite3.connect(root / "backup" / "app-2026-01-01.db")
    db.backup(b)
    b.close()
    db.close()


def run(script, *args):
    try:
        p = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=Path(script).parent)
        return p.returncode == 0, (p.stderr or "")[-300:]
    except Exception as e:
        return False, repr(e)


def t1(d):
    r = dict.fromkeys(["schema loads", "at least 7 tables", "tenant key everywhere", "foreign keys used", "every column mapped", "personal columns have retention and delete path"], False)
    try:
        db = sqlite3.connect(":memory:")
        db.executescript((d / "schema.sql").read_text(encoding="utf-8"))
    except Exception as e:
        return {**r, "why": str(e)}
    r["schema loads"] = True
    tabs = [x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    cols = {(t.lower(), c[1].lower()) for t in tabs for c in db.execute(f'PRAGMA table_info("{t}")')}
    r["at least 7 tables"] = len(tabs) >= 7
    r["tenant key everywhere"] = "advisor" in [t.lower() for t in tabs] and all((t.lower(), "advisor_id") in cols for t in tabs if t.lower() != "advisor")
    r["foreign keys used"] = sum(len(db.execute(f'PRAGMA foreign_key_list("{t}")').fetchall()) for t in tabs) >= len(tabs) - 1
    try:
        with open(d / "datamap.csv", encoding="utf-8-sig", newline="") as fh:
            m = [{(k or "").strip().lower(): (v or "").strip() if isinstance(v, str) else "" for k, v in x.items()} for x in csv.DictReader(fh)]
        r["every column mapped"] = cols <= {(x["table"].lower(), x["column"].lower()) for x in m}
        pers = [x for x in m if x["personal"].lower() == "yes"]
        r["personal columns have retention and delete path"] = bool(pers) and all(x["retention"] and x["delete_path"] and x["purpose"] for x in pers)
    except Exception as e:
        r["every column mapped"] = r["personal columns have retention and delete path"] = False
        r["why"] = repr(e)
    return r


def t2(d, tmp):
    n, o = tmp / "n", tmp / "o"
    n.mkdir()
    for f, (t, _, _) in HIDDEN.items():
        (n / f).write_text(t, encoding="utf-8")
    ro = tmp / "r.json"
    ro.write_text(json.dumps([{"pseudonym": p, "forms": f} for p, f in HIDDEN_ROSTER], ensure_ascii=False), encoding="utf-8")
    ok, err = run(d / "mask.py", "--notes", n, "--roster", ro, "--out", o)
    r = {"mask.py runs": ok}
    if not ok:
        r["why"] = err
    for f, (_, gone, stay) in HIDDEN.items():
        try:
            t = norm((o / f).read_text(encoding="utf-8"))
            leaks = [g for g in gone if norm(g) in t]
            lost = [s for s in stay if norm(s) not in t]
        except Exception:
            leaks, lost = ["no output"], ["no output"]
        r[f"{f} no leak"], r[f"{f} facts kept"] = (not leaks) or leaks, (not lost) or lost
    return r


def traces(root, words):
    hits = []
    for p in Path(root).rglob("*"):
        if p.is_file():
            b = p.read_bytes()
            for w in words:
                if any(v.encode(enc) in b for v in {w, unicodedata.normalize("NFD", w)} for enc in ("utf-8", "utf-16-le")):
                    hits.append(f"{p.relative_to(root).as_posix()}:{w}")
    return hits


def t3(d, tmp):
    root = tmp / "s"
    store(root, [(7, "Gaëlle", "Fontvert"), (8, "Hugo", "Marlois"), (70, "Zoé", "Pelcastre")])
    ok, err = run(d / "purge.py", "--root", root, "--client", 7)
    r = {"purge.py runs": ok}
    if not ok:
        r["why"] = err
    h = traces(root, ["Gaëlle", "Fontvert", "m701", "m702", "réunion 701", "réunion 702"])
    r["no trace left"] = (not h) or h
    try:
        good = True
        for p in (root / "app.db", root / "backup" / "app-2026-01-01.db"):
            db = sqlite3.connect(p)
            good &= db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            good &= [x[0] for x in db.execute("SELECT id FROM client ORDER BY id")] == [8, 70]
            good &= db.execute("SELECT count(*) FROM meeting").fetchone()[0] == 4 and db.execute("SELECT count(*) FROM report").fetchone()[0] == 4
            good &= db.execute("SELECT count(*) FROM audit_event WHERE detail LIKE '%Hugo%' OR detail LIKE '%Zoé%'").fetchone()[0] == 4
            db.close()
        r["other clients intact in databases"] = good
    except Exception as e:
        r["other clients intact in databases"] = repr(e)
    try:
        c, g = (root / "exports/all.csv").read_text(encoding="utf-8"), (root / "logs/app.log").read_text(encoding="utf-8")
        r["other clients intact in files"] = all(f"réunion {m}" in c and f"m{m}" in g and (root / f"recordings/m{m}.wav").exists() and (root / f"transcripts/m{m}.txt").exists() for m in (801, 802, 7001, 7002)) and c.startswith("client_id;first;text")
    except Exception as e:
        r["other clients intact in files"] = repr(e)
    if not ok:  # nothing ran: leaving the others intact earns no credit
        r["other clients intact in databases"] = r["other clients intact in files"] = False
    try:
        json.loads((root / "purge-proof.json").read_text(encoding="utf-8"))
        r["proof written"] = True
    except Exception:
        r["proof written"] = False
    return r


def grade(d):
    d = Path(d).resolve()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as x:
        out = {}
        for name, f in (("T1", lambda t: t1(d)), ("T2", lambda t: t2(d, t)), ("T3", lambda t: t3(d, t))):
            t = Path(x) / name
            t.mkdir()
            out[name] = f(t)
    for v in out.values():
        checks = [k for k in v if k != "why"]
        v["score"] = f"{sum(v[k] is True for k in checks)}/{len(checks)}"
    return out


REF_MASK = r'''
import argparse,json,re,unicodedata
from pathlib import Path
a=argparse.ArgumentParser();[a.add_argument(x,required=True) for x in("--notes","--roster","--out")];a=a.parse_args()
A={"a":"aàâä","e":"eéèêë","i":"iîï","o":"oôö","u":"uùûü","c":"cç"}
def base(c): return unicodedata.normalize("NFD",c)[0].lower()
def pat(f):
    out=[]
    for k,c in enumerate(f):
        if c in " -": out.append(r"[\s-]+"); continue
        b=base(c); s=A.get(b,b)
        cls=s.upper() if (k==0 or f[k-1] in " -") and c.isupper() else s+s.upper()
        out.append("["+re.escape(cls)+"]")
    return r"(?<!\w)"+"".join(out)+r"(?!\w)"
R=json.loads(Path(a.roster).read_text(encoding="utf-8")); P=[]
for r in R:
    fs=set(r["forms"])|{f.split(" ",1)[1] for f in r["forms"] if " " in f and not r["pseudonym"].startswith("PLACE")}
    P+=[(f,r["pseudonym"]) for f in fs]
P.sort(key=lambda x:-len(x[0])); o=Path(a.out); o.mkdir(parents=True,exist_ok=True)
for p in Path(a.notes).glob("*.txt"):
    t=unicodedata.normalize("NFC",p.read_text(encoding="utf-8"))
    t=re.sub(r"[\w.+-]+@[\w.-]+\w","[EMAIL]",t); t=re.sub(r"(?:\+33|\b0)\s?\d(?:[ .-]?\d{2}){4}\b","[TEL]",t)
    t=re.sub(r"\b\d{1,2}(?:/\d{1,2}/|\s+[a-zéû]+\s+)\d{4}\b","[DATE]",t)
    for f,s in P: t=re.sub(pat(f),s,t)
    (o/p.name).write_text(t,encoding="utf-8")
'''
REF_PURGE = r'''
import argparse,json,re,sqlite3
from pathlib import Path
a=argparse.ArgumentParser();a.add_argument("--root");a.add_argument("--client",type=int);a=a.parse_args()
root=Path(a.root); files=set(); words=set()
for p in list(root.rglob("*.db")):
    d=sqlite3.connect(p,isolation_level=None); d.execute("PRAGMA secure_delete=ON")
    for f,l in d.execute("SELECT first,last FROM client WHERE id=?",(a.client,)): words|={f,l}
    S=d.execute("SELECT id,recording,transcript FROM meeting WHERE client_id=?",(a.client,)).fetchall()
    for i,x,y in S:
        files|={x,y}; words.add(f"m{i}"); d.execute("DELETE FROM report WHERE meeting_id=?",(i,))
    d.execute("DELETE FROM meeting WHERE client_id=?",(a.client,)); d.execute("DELETE FROM client WHERE id=?",(a.client,))
    for w in words: d.execute("DELETE FROM audit_event WHERE detail LIKE ?",(f"%{w}%",))
    d.execute("VACUUM"); d.execute("PRAGMA wal_checkpoint(TRUNCATE)"); d.close()
for f in files: (root/f).unlink(missing_ok=True)
for p in list(root.rglob("*.csv"))+list(root.rglob("*.log")):
    L=p.read_text(encoding="utf-8").splitlines(True)
    p.write_text("".join(x for x in L if not x.startswith(f"{a.client};") and not any(re.search(rf"\b{re.escape(w)}\b",x) for w in words)),encoding="utf-8")
(root/"purge-proof.json").write_text(json.dumps({"files":len(files)}))
'''
REF_TABLES = ["advisor", "client", "note", "transcript", "report", "export", "audit_event"]


def solution(d, mask, purge, good_map=True):
    d.mkdir(parents=True)
    sql = ["CREATE TABLE advisor(id INTEGER PRIMARY KEY, name TEXT);"]
    sql += [f"CREATE TABLE {t}(id INTEGER PRIMARY KEY, advisor_id INT NOT NULL REFERENCES advisor(id), body TEXT);" for t in REF_TABLES[1:]]
    (d / "schema.sql").write_text("\n".join(sql), encoding="utf-8")
    rows = ["table,column,personal,purpose,retention,delete_path"]
    for t in REF_TABLES:
        for c in ["id", "name"] if t == "advisor" else ["id", "advisor_id", "body"]:
            rows.append(f"{t},{c},yes,follow-up,{'30 days' if good_map else ''},purge.py")
    (d / "datamap.csv").write_text("\n".join(rows), encoding="utf-8")
    (d / "mask.py").write_text(mask, encoding="utf-8")
    (d / "purge.py").write_text(purge, encoding="utf-8")


def selftest():
    naive_mask = 'import argparse,json\nfrom pathlib import Path\na=argparse.ArgumentParser();[a.add_argument(x) for x in("--notes","--roster","--out")];a=a.parse_args()\no=Path(a.out);o.mkdir()\nfor p in Path(a.notes).glob("*.txt"):\n t=p.read_text(encoding="utf-8")\n for r in json.loads(Path(a.roster).read_text(encoding="utf-8")):\n  for f in r["forms"]: t=t.replace(f,r["pseudonym"])\n (o/p.name).write_text(t,encoding="utf-8")\n'
    naive_purge = 'import argparse,sqlite3\na=argparse.ArgumentParser();a.add_argument("--root");a.add_argument("--client");a=a.parse_args()\nd=sqlite3.connect(a.root+"/app.db");d.execute("DELETE FROM client WHERE id=?",(a.client,));d.commit()\n'
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as x:
        x = Path(x)
        solution(x / "ref", REF_MASK, REF_PURGE)
        solution(x / "naive", naive_mask, naive_purge, good_map=False)
        (x / "empty").mkdir()
        g = {k: grade(x / k) for k in ("ref", "naive", "empty")}
        make(x / "ws")
        assert (x / "ws" / "TASKS.md").exists() and (x / "ws" / "store" / "app.db").exists()
    for k, v in g.items():
        print(k, {t: s["score"] for t, s in v.items()})
    full = lambda v: all(a == b for a, b in (s["score"].split("/") for s in v.values()))
    if not full(g["ref"]):
        print(json.dumps(g["ref"], ensure_ascii=False, indent=1))
    assert full(g["ref"]), "reference must pass"
    assert g["naive"]["T1"]["personal columns have retention and delete path"] is False
    assert g["naive"]["T2"]["01.txt no leak"] is True and g["naive"]["T2"]["04.txt no leak"] is not True
    assert g["naive"]["T3"]["no trace left"] is not True
    assert not any(v is True for s in g["empty"].values() for v in s.values()), "empty must score zero"
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "selftest":
        selftest()
    elif cmd == "make":
        make(sys.argv[2])
    else:
        print(json.dumps(grade(sys.argv[2]), ensure_ascii=False, indent=1))
