"""Improvement loop: size limits, due errors and report of a ledger, skill eval scores, acceptance gate, trial launcher.

Exit codes: 0 ok or accepted, 1 over the limit, due or rejected, 2 unusable input.
"""
import argparse, contextlib, datetime, difflib, hashlib, importlib.util, io, itertools, json, os, re, shlex, shutil, subprocess, sys, tempfile, time
from fractions import Fraction
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
AGENT_WORDS, SKILL_LINES, MAX_HUNKS, MIN_RUNS, TIMEOUT_S, WINDOW_DAYS, ALIKE = 1500, 500, 4, 3, 3600, 30, 0.8
ID = r"(?!.{41})[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
FIELDS = {
    "date": r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
    "project": r"[a-z0-9._-]{1,100}",
    "target": ID,
    "error": ID,
    "source": r"https://github\.com/[A-Za-z0-9-]{1,39}/(?!\.{1,2}/)[A-Za-z0-9._-]{1,100}/(?:(?:pull|issues)/[1-9][0-9]{0,8}|commit/[0-9a-f]{40})",
    "case": r"(?! )[A-Za-z0-9 .,:/_-]{1,120}(?<! )",
}
KEYS = {"date", "project", "target", "error"}
# Files already over the limit: the word count each may not exceed. Lower it when a file shrinks, never raise it.
CEILINGS = {"skills/pr-guardian/agents/pr-guardian.md": 2038}
PROMPT = "Do all the work described in TASKS.md. Write only in this folder."
FLAGS = ["-p", "--output-format", "json", "--no-session-persistence", "--safe-mode", "--restricted", "--strict-mcp-config",
         "--permission-prompts", "none", "--tools", "Read,Edit,Write,Glob,Grep", "--allowedTools", "Edit(*)", "Write(*)"]


class Unusable(Exception):
    pass


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    p = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise Unusable(f"git {args[0]}: {p.stderr.strip()}")
    return p.stdout


def words(text):
    return len(text.split())


def body(lines):
    return lines[lines.index("---", 1) + 1:] if lines[:1] == ["---"] and "---" in lines[1:] else lines


def tracked(root, *globs):
    for rel in git(root, "ls-files", "-z", "--", *(f":(glob){g}" for g in globs)).split("\0"):
        if rel and (root / rel).is_file():
            yield rel, (root / rel).read_text(encoding="utf-8").splitlines()


def size(root):
    over, notes = [], []
    for rel, lines in tracked(root, "skills/*/agents/*.md", "agents/**/*.md"):
        if rel.startswith("agents/") and ("/candidates/" in rel or lines[:1] != ["---"]):
            continue
        n, limit = words("\n".join(lines)), max(AGENT_WORDS, CEILINGS.get(rel, 0))
        if n > limit:
            over.append(f"{rel}: {n} words, limit {limit}")
        elif n > AGENT_WORDS:
            notes.append(f"{rel}: {n} words, over the limit {AGENT_WORDS}, ceiling {limit}")
    for rel, lines in tracked(root, "**/SKILL.md"):
        n = len(body(lines))
        if n > SKILL_LINES:
            over.append(f"{rel}: {n} lines, limit {SKILL_LINES}")
    over += [f"{rel}: no ledger in this repository" for rel in git(root, "ls-files", "--", "*.jsonl", ":!skills/").splitlines()]
    print("\n".join(notes + (over or ["size ok"])))
    return 1 if over else 0


def distinct(pairs):
    if len(dict(pairs)) < len(pairs):
        raise ValueError
    return dict(pairs)


def entries(path):
    try:
        *lines, rest = Path(path).read_bytes().split(b"\n")
    except OSError as e:
        raise Unusable(str(e))
    if not lines and not rest:
        raise Unusable(f"{path}: empty ledger")
    for n, raw in enumerate([*lines, *filter(None, [rest])], 1):
        where = f"{path}, line {n}"
        if n > len(lines):
            raise Unusable(f"{where}: no end of line, so it may be truncated")
        try:
            x = json.loads(raw.decode("utf-8"), object_pairs_hook=distinct)
        except (ValueError, RecursionError):
            raise Unusable(f"{where}: not one JSON object in UTF-8 with distinct keys")
        if not isinstance(x, dict) or (x.keys() - {"source"} != KEYS and x.keys() != KEYS | {"case"}):
            raise Unusable(f"{where}: an occurrence has the keys date, project, target, error and an optional source; a coverage has case instead of source")
        wrong = [k for k, v in x.items() if not isinstance(v, str) or not re.fullmatch(FIELDS[k], v)]
        if wrong:
            raise Unusable(f"{where}: invalid {', '.join(wrong)}")
        try:
            datetime.date.fromisoformat(x["date"])
        except ValueError:
            raise Unusable(f"{where}: no such date")
        yield where, x


def read_ledger(path):
    found, known, repeated = {}, set(), 0
    for where, x in entries(path):
        pair = x["project"], x["target"], x["error"]
        key = (pair, x["case"], x["date"]) if "case" in x else (pair, x.get("source", x["date"]))
        if key in known:
            repeated += 1
            continue
        known.add(key)
        if "case" not in x:
            e = found.setdefault(pair, {"rows": [], "case": None, "since": 0})
            e["rows"].append(x)
            e["since"] += bool(e["case"]) and x["date"] >= e["case"]["date"]
        elif pair in found:
            found[pair].update(case=x, since=0)
        else:
            raise Unusable(f"{where}: a case for an error with no occurrence above")
    return sorted(found.items()), repeated


def state(e):
    if e["case"]:
        return f"came back after its case: {e['since']}" if e["since"] else ""
    return f"seen {len(e['rows'])} times, no case" if len(e["rows"]) >= 2 else ""


def due(root, ledger):
    late = [f"{project}/{target}: {error} {state(e)}" for (project, target, error), e in read_ledger(ledger)[0] if state(e)]
    print("\n".join(late) or "nothing due")
    return 1 if late else 0


def links(e):
    urls = [x["source"] for x in e["rows"] if "source" in x]
    return " ".join(f"[{u.rsplit('/', 1)[1][:7] if '/commit/' in u else '#' + u.rsplit('/', 1)[1]}]({u})" for u in urls)


def report(root, ledger, date):
    found, repeated = read_ledger(ledger)
    today = date or datetime.datetime.now(datetime.timezone.utc).date()
    days = [(today - datetime.timedelta(n)).isoformat() for n in range(2 * WINDOW_DAYS)]
    last, before = days[:WINDOW_DAYS], days[WINDOW_DAYS:]
    names = {key: " ".join(f"`{part}`" for part in key) for key, _ in found}
    late = [f"- {names[key]}: {state(e)} {links(e)}".rstrip() for key, e in found if state(e)]
    alike = [f"- {names[a]} and `{b[2]}`" for (a, _), (b, _) in itertools.combinations(found, 2)
             if a[:2] == b[:2] and difflib.SequenceMatcher(None, a[2], b[2]).ratio() >= ALIKE]
    out = [f"## Improvement loop, {today}", "", f"{sum(len(e['rows']) for _, e in found)} occurrences, {len(found)} errors, {repeated} repeated lines counted once.",
           f"Last {WINDOW_DAYS} days: {last[-1]} to {last[0]}. Before: {before[-1]} to {before[0]}.",
           "", "### Due", "", *(late or ["Nothing due."]), "", "### Counts", "",
           f"| project | target | error id | all | last {WINDOW_DAYS} days | {WINDOW_DAYS} days before | case | sources |", "|---|---|---|---|---|---|---|---|"]
    for key, e in found:
        cells = [*(f"`{part}`" for part in key), len(e["rows"]), *(sum(x["date"] in window for x in e["rows"]) for window in (last, before)),
                 f"`{e['case']['case']}`" if e["case"] else "no", links(e)]
        out.append(f"| {' | '.join(map(str, cells))} |")
    print("\n".join(out + ["", "### Ids spelled alike", "", *(alike or ["None."])]))
    return 0


def fresh(out):
    out = Path(out).resolve()
    if out.exists() or not out.parent.is_dir():
        raise Unusable(f"{out}: already exists, or its folder does not")
    return out


def load_scores(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return (data.get("skill"), data.get("evals")), *check_scores(path, data)
    except (OSError, ValueError, AttributeError) as e:
        raise Unusable(f"{path}: {e!r}")


def check_scores(path, data):
    try:
        model, runs = data["model"], [r["checks"] for r in data["runs"]]
    except (KeyError, TypeError) as e:
        raise Unusable(f"{path}: {e!r}")
    if not isinstance(model, str) or not model:
        raise Unusable(f"{path}: no model name")
    if len(runs) < MIN_RUNS:
        raise Unusable(f"{path}: {len(runs)} runs, at least {MIN_RUNS} needed")
    if not all(isinstance(r, dict) and r and all(isinstance(v, bool) for v in r.values()) for r in runs):
        raise Unusable(f"{path}: every run needs checks valued true or false")
    if any(r.keys() != runs[0].keys() for r in runs):
        raise Unusable(f"{path}: runs do not hold the same checks")
    return model, {k: Fraction(sum(r[k] for r in runs), len(runs)) for k in runs[0]}


def evals_dir(root, skill):
    if skill not in [p.parts[-3] for p in root.glob("skills/*/evals/grade.py")]:
        raise Unusable(f"unknown skill: {skill!r}")
    return root / "skills" / skill / "evals"


def grade(script, run, extra):
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, str(script), str(run), "--json", *extra], env=env, capture_output=True)
    checks = {}
    try:
        for case, res in json.loads(p.stdout).items():
            if "error" in res or not res.get("expectations"):
                raise Unusable(f"{run}: case {case} not measured: {res.get('error', 'no assertion')}")
            for e in res["expectations"]:
                key = f"{case}:{e['text']}"
                if key in checks:
                    raise Unusable(f"{run}: two assertions named {key}")
                checks[key] = e["passed"]
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise Unusable(f"{run}: grade.py exit {p.returncode}, {e!r}: {p.stderr.decode('utf-8', 'replace').strip()[-300:]}")
    if not checks or p.returncode != (not all(checks.values())):
        raise Unusable(f"{run}: grade.py exit {p.returncode} with {sum(map(bool, checks.values()))}/{len(checks)} assertions passed")
    return checks


def scores(root, skill, model, out, runs, extra):
    evals, out, runs = evals_dir(root, skill), fresh(out), [Path(r).resolve() for r in runs]
    try:
        tests = "".join((evals / f).read_text(encoding="utf-8") for f in ("evals.json", "grade.py"))
        folders = {(s.st_dev, s.st_ino) for s in (r.stat() for r in runs)}
    except OSError as e:
        raise Unusable(str(e))
    if len(folders) < len(runs):
        raise Unusable("the same run folder is given twice")
    done = [{"checks": grade(evals / "grade.py", r, extra), "run": r.name} for r in runs]
    data = {"skill": skill, "evals": hashlib.sha256(tests.encode()).hexdigest(), "model": model, "runs": done}
    check_scores("scores", data)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in done:
        print(f"{r['run']}: {sum(r['checks'].values())}/{len(r['checks'])} checks")
    return 0


def gate(root, base, new, agent, base_rev):
    (source, model_a, a), (source_b, model_b, b) = load_scores(base), load_scores(new)
    if source != source_b:
        raise Unusable(f"two different tests (skill, digest of its evals): {source}, {source_b}")
    skill, home = source[0], f"skills/{source[0]}/"
    listed = root / "agents/trials/data/reserved.txt" if skill is None else evals_dir(root, skill) / "reserved.txt"
    if not listed.is_file():
        raise Unusable(f"no reserved list: {listed}")
    reserved = {x.strip() for x in listed.read_text(encoding="utf-8").splitlines() if x.strip()}
    if not reserved or not reserved <= a.keys():
        raise Unusable(f"reserved checks absent from {base}: {sorted(reserved - a.keys()) or 'reserved.txt is empty'}")
    try:
        path = Path(agent).resolve()
        rel = path.relative_to(root.resolve()).as_posix()
        new_text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        raise Unusable(f"{agent}: {e}")
    sha = git(root, "rev-parse", "--verify", "--end-of-options", f"{base_rev}^{{commit}}").strip()
    if skill is not None:
        if not rel.startswith(home) or rel.startswith(home + "evals/"):
            raise Unusable(f"{rel}: not an agent or a SKILL.md of {home}")
        changed = git(root, "diff", "--name-only", "-z", sha, "--", home)
        changed += git(root, "ls-files", "-o", "-x", "node_modules", "-x", "__pycache__", "--exclude-standard", "-z", "--", home)
        others = sorted({*changed.split("\0")} - {"", rel})
        if others:
            raise Unusable(f"other changes since {base_rev}, so the scores do not judge {rel} alone: {', '.join(others)}")
    old_text = git(root, "show", f"{sha}:{rel}")
    old_words, new_words = words(old_text), words(new_text)
    diff = git(root, "diff", "-U0", "--inter-hunk-context=0", "--no-color", "--no-ext-diff", "--no-textconv", sha, "--", rel)
    hunks = sum(x.startswith("@@") for x in diff.splitlines())
    if not hunks:
        raise Unusable(f"{rel}: no text change since {base_rev}")

    def mean(s, keys):
        return sum((s.get(k, Fraction(0)) for k in keys), Fraction(0)) / len(keys) if keys else Fraction(0)

    visible = a.keys() - reserved
    r0, r1, v0, v1 = mean(a, reserved), mean(b, reserved), mean(a, visible), mean(b, visible)
    lower = sorted(k for k in a.keys() & b.keys() if b[k] < a[k])
    differ = sorted(a.keys() ^ b.keys())
    length, n, old_n, limit = f"words: {old_words} -> {new_words}", new_words, old_words, AGENT_WORDS
    if path.name == "SKILL.md":
        n, old_n, limit = len(body(new_text.splitlines())), len(body(old_text.splitlines())), SKILL_LINES
        length += f", body lines: {old_n} -> {n}"
    rules = [
        (model_a == model_b, f"same model: {model_a} -> {model_b}"),
        (not differ, f"checks missing from one file: {', '.join(differ) or 'none'}"),
        (r1 > r0, f"reserved mean must rise: {float(r0):.3f} -> {float(r1):.3f}"),
        (not lower, f"checks with a lower pass rate: {', '.join(lower) or 'none'}"),
        (new_words <= old_words and (n <= limit or n < old_n), length),
        (hunks <= MAX_HUNKS, f"changed hunks: {hunks}, limit {MAX_HUNKS}"),
    ]
    failed = [text for ok, text in rules if not ok]
    print("REJECT" if failed else "ACCEPT")
    for ok, text in rules:
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if failed:
        row = {"date": datetime.date.today().isoformat(), "agent": rel, "change": f"{hunks} hunks, {old_words} -> {new_words} words since {sha[:7]}", "reason": "; ".join(failed),
               "scores": f"reserved {float(r0):.3f} -> {float(r1):.3f}, visible {float(v0):.3f} -> {float(v1):.3f}"}
        print("\nLine for the log of rejected changes:\n" + json.dumps(row))
    return 1 if failed else 0


def load_bench(root):
    spec = importlib.util.spec_from_file_location("bench", root / "agents/trials/data/bench.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    return bench


def run(root, candidate, role, runs, model, out, yes, max_budget_usd, claude=None):
    cap = max_budget_usd
    if yes and cap is None:
        raise Unusable("--yes needs --max-budget-usd")
    cmd = [*(claude or [shutil.which("claude") or "claude"]), *FLAGS, "--model", model]
    if role:
        role = Path(role).resolve()
        if not role.is_file():
            raise Unusable(f"{role}: no such file")
        cmd += ["--append-system-prompt-file", str(role)]
    if cap is not None:
        cmd += ["--max-budget-usd", str(cap)]
    out = fresh(out)
    if not yes:
        budget = "no cap" if cap is None else f"cap {cap:g} USD each, {runs * cap:g} USD in all"
        bench = "python agents/trials/data/bench.py"
        print(f"dry run, nothing executed. Each run:\n  {bench} make WORKSPACE   (new temporary folder outside the repository)")
        print(f"  cd WORKSPACE && {shlex.join(cmd)}\n    stdin: {PROMPT}\n  {bench} grade WORKSPACE\nmodel runs: {runs}, {budget}. Add --yes and --max-budget-usd to execute.")
        return 0
    bench, done = load_bench(root), []
    for i in range(1, runs + 1):
        ws = Path(tempfile.mkdtemp(prefix="trial-")).resolve()
        if ws.is_relative_to(root.resolve()):
            raise Unusable(f"temporary folder is inside the repository: {ws}")
        bench.make(ws)
        start = time.monotonic()
        try:
            p = subprocess.run(cmd, cwd=ws, input=PROMPT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise Unusable(f"run {i} not measured, not scored, cost unknown: {e}")
        seconds = round(time.monotonic() - start, 1)
        try:
            reply = json.loads(p.stdout)
        except ValueError:
            reply = None
        reply = reply if isinstance(reply, dict) else {}
        cost, subtype = reply.get("total_cost_usd"), reply.get("subtype")
        cost = cost if type(cost) in (int, float) else None
        if p.returncode or not reply or reply.get("is_error") or subtype not in (None, "success") or (cost is not None and cost >= cap):
            raise Unusable(f"run {i} not measured, not scored: claude exit {p.returncode}, subtype {subtype}, "
                           f"cost {'unknown' if cost is None else cost}, cap {cap:g} USD: {(p.stderr or p.stdout)[-300:]}")
        checks = {f"{t}:{k}": v is True for t, res in bench.grade(ws).items() for k, v in res.items() if k not in ("why", "score")}
        done.append({"checks": checks, "seconds": seconds, "cost_usd": cost, "usage": reply.get("usage"), "model_usage": reply.get("modelUsage"), "workspace": str(ws)})
        out.write_text(json.dumps({"candidate": candidate, "role": str(role) if role else None, "model": model, "runs": done}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"run {i}/{runs}: {sum(checks.values())}/{len(checks)} checks, {seconds} s, cost {'unknown' if cost is None else cost} USD, {ws}")
    return 0


STUB = """
import json, shutil, sys
from pathlib import Path
assert Path("TASKS.md").exists() and "TASKS.md" in sys.stdin.buffer.read().decode("utf-8")
src = Path(sys.argv[1])
log = src.parent / "calls.jsonl"
with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps([str(Path.cwd()), *sys.argv[2:]]) + chr(10))
if src.name == "broken" and len(log.read_text(encoding="utf-8").splitlines()) == 2:
    sys.exit("stub failure")
shutil.copytree(src, ".", dirs_exist_ok=True)
reply = {"is_error": False, "total_cost_usd": 0.25, "usage": {"output_tokens": 7}, "modelUsage": {"stub": {}}}
if src.name == "free":
    del reply["total_cost_usd"]
reply.update({"capped": {"is_error": True, "subtype": "error_max_budget_usd"}, "flagged": {"is_error": True}, "subtype": {"subtype": "error_other"},
              "over": {"total_cost_usd": 0.5}}.get(src.name, {}))
print("no JSON" if src.name == "mute" else json.dumps(reply))
sys.exit(src.name == "failed")
"""

GRADER = """
import argparse, json, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("run_dir", type=Path)
ap.add_argument("--mode", default="")
ap.add_argument("--json", action="store_true")
args = ap.parse_args()
CASES = {"letter": ["names the café", "keeps | the arrow →"], "reply": ["signs: Élodie", "adds no promise"]}
WORDS = {"names the café": "café", "keeps | the arrow →": "→", "signs: Élodie": "Élodie", "adds no promise": "no promise"}
if args.mode == "crash":
    raise RuntimeError("grader broke")
if args.mode == "text":
    sys.exit("not JSON")
report, failed = {}, 0
for name, texts in CASES.items():
    answer = args.run_dir / f"{name}.md"
    if not answer.exists():
        report[name], failed = {"error": f"missing {answer}"}, failed + 1
        continue
    text = answer.read_text()
    results = [(t, WORDS[t] in text) for t in texts]
    report[name] = {"expectations": [{"text": t, "passed": ok, "evidence": text[:200]} for t, ok in results]}
    failed += sum(not ok for _, ok in results)
if args.mode == "error":
    report["reply"]["error"] = "interrupted"
if args.mode == "twice":
    report["reply"]["expectations"] *= 2
if args.mode == "empty":
    report["reply"]["expectations"] = []
if args.mode == "shape":
    report["reply"]["expectations"] = [{"text": "t"}]
if args.mode == "none":
    report = {}
print(json.dumps(report, indent=2, ensure_ascii=False))
sys.exit(3 if args.mode == "exit" else 1 if failed and args.mode != "zero" else 0)
"""


def selftest():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as x:
        walk(Path(x).resolve())
    print("selftest ok")


SOURCE = "https://github.com/example/demo/pull/{}"


def entry(**more):
    return {"date": "2026-01-01", "project": "demo", "target": "data", "error": "no-signature", **more}


def walk_ledger(x, call):
    ledger = x / "walk.jsonl"
    one, two, three = (entry(source=SOURCE.format(n)) for n in (1, 2, 3))
    case, bare = entry(case="evals.json: reply, 2"), entry()

    def check(code, *lines, has="", cmd=("due",), end="\n"):
        ledger.write_bytes("".join((s if isinstance(s, str) else json.dumps(s)) + end for s in lines).encode("utf-8"))
        return call(code, *cmd, "--ledger", ledger, has=has)

    seen, back = "demo/data: no-signature seen 2 times, no case\n", "demo/data: no-signature came back after its case: 1\n"
    for code, lines, want in (
            (0, [one], "nothing due\n"), (1, [one, two], seen), (1, [one, bare], seen), (1, [bare, {**bare, "date": "2026-01-02"}], seen),
            (0, [one, {**one, "date": "2026-01-02"}], "nothing due\n"), (0, [bare, bare], "nothing due\n"),
            (0, [one, {**two, "target": "other"}], "nothing due\n"), (0, [one, {**two, "error": "other"}], "nothing due\n"), (0, [one, {**two, "project": "other"}], "nothing due\n"),
            (0, [one, two, case], "nothing due\n"), (0, [one, case], "nothing due\n"), (1, [one, two, {**case, "target": "data"}, {**two, "target": "other"}, {**one, "target": "other"}],
                                                                                     "demo/other: no-signature seen 2 times, no case\n"),
            (1, [one, case, two], back), (1, [one, case, two, three], back.replace(": 1", ": 2")), (0, [one, case, one], "nothing due\n"),
            (0, [one, {**case, "date": "2026-01-02"}, two], "nothing due\n"), (1, [one, case, {**two, "date": "2026-01-02"}], back),
            (0, [one, case, two, {**case, "case": "a harder one"}], "nothing due\n"), (0, [one, case, two, {**case, "date": "2026-01-02"}], "nothing due\n"),
            (1, [one, case, two, case], back), (0, [one, case, {**case, "date": "2026-01-03"}, two], "nothing due\n"), (1, [one, case, two, {**case, "case": "a harder one"}, three], back)):
        assert check(code, *lines) == want, lines
        assert check(code, *lines, end="\r\n") == want, lines

    for bad in ({}, [], "x", 1, None, {k: v for k, v in bare.items() if k != "project"}, {**bare, "note": "x"}, {**one, "case": "x"}, {**bare, "sources": "x"}):
        check(2, bare, json.dumps(bad), bare, has="line 2: an occurrence has the keys")
    for key in bare:
        check(2, {k: v for k, v in bare.items() if k != key}, has="line 1: an occurrence has the keys")
        check(2, {k: v for k, v in case.items() if k != key}, has="line 1: an occurrence has the keys")
    for bad in ("", "  ", "{", "{}{}", "# note", "﻿" + json.dumps(bare), json.dumps(bare)[:-1] + ', "date": "2026-01-01"}', "[" * 200000, "1" * 5000):
        check(2, bare, bad, bare, has="line 2: not one JSON object in UTF-8 with distinct keys")
    ids = ("", "X", "x_y", "x--y", "-x", "x-", "1x", "x.y", "x y", "x\n", "é", "@me", "#1", "[x](y)", "`x`", "x|y", "x/y", "<b>", "x" * 41, 1, None, [], {}, True)
    for key, values in (("target", ids), ("error", ids), ("project", ("", "Demo", "démo", "a b", "a/b", "@me", "a|b", "a`b", "[a]", "a\n", "x" * 101, 1, None)),
                        ("date", ("", "2026-1-01", "20260101", "2026-01-01T00:00", "2026-W01-1", "2026-01-01\n", "٢٠٢٦-01-01", 20260101, None)),
                        ("source", ("", "x", "http://github.com/a/b/pull/1", "https://example.com/a/b/pull/1", "https://github.com.evil/a/b/pull/1", "https://github-com/a/b/pull/1", "https://github.com/a/b", "https://github.com/a/b/pull/0",
                                    "https://github.com/a/../pull/1", "https://github.com/a/./pull/1", "https://github.com/a/b/pull/1/files", "https://github.com/a/b/pull/1#x", "https://github.com/a/b/pull/1?x",
                                    "https://github.com/a/b/pull/1)", "https://github.com/a/b](x)/pull/1", "https://github.com/a_b/c/pull/1", "https://github.com/a/b/tree/x", "https://github.com/a/b/pull/1 ",
                                    "https://github.com/a/b/commit/" + "a" * 39, "https://github.com/a/b/commit/" + "a" * 41, f"https://github.com/{'a' * 40}/b/pull/1", f"https://github.com/a/{'b' * 101}/pull/1",
                                    "https://github.com/a/b/pull/1234567890", " https://github.com/a/b/pull/1", "https://github.com/a/b/pull/1\n", None, ["x"])),
                        ("case", ("", " ", " x", "x ", "x`y", "x|y", "x[y", "x]y", "x<y", "x>y", "x@y", "x(y", "x*y", "x#y", "x\ny", "x\n", "é", "x" * 121, 1, None))):
        for value in values:
            check(2, bare, {**bare, key: value}, has=f"line 2: invalid {key}")
    check(2, {**bare, "target": "X", "date": "x"}, has="line 1: invalid date, target")
    for date in ("2026-02-30", "2026-13-01", "0000-01-01"):
        check(2, bare, {**bare, "date": date}, has="line 2: no such date")
    for key, value in (("target", "x" * 40), ("error", "a11y-tab-2"), ("project", "x" * 100), ("project", ".my_repo-1.x"), ("source", "https://github.com/a-b/.git_hub/issues/123456789"),
                       ("source", "https://github.com/a/b/commit/" + "0a" * 20), ("date", "2024-02-29")):
        check(0, {**bare, key: value}, has="nothing due")
    for text in ("x" * 120, ".github/workflows/ci.yml: windows job, step_2"):
        check(0, bare, {**case, "case": text}, has="nothing due")
    check(2, one, {**case, "target": "other"}, has="line 2: a case for an error with no occurrence above")
    check(2, case, one, has="line 1: a case for an error with no occurrence above")
    check(2, has="empty ledger")
    check(2, "", has="line 1: not one JSON object")
    for data, has in ((json.dumps(bare).encode(), "line 1: no end of line"), ((json.dumps(bare) + "\n" + json.dumps(two)).encode(), "line 2: no end of line"),
                      ((json.dumps(bare) + "\n").encode() + json.dumps(bare).encode().replace(b"demo", b"d\xe9mo") + b"\n", "line 2: not one JSON object in UTF-8"),
                      ((json.dumps(bare) + "\n").encode("utf-16"), "line 1: not one JSON object in UTF-8"), ((json.dumps(bare) + "\r" + json.dumps(two) + "\n").encode(), "line 1: not one JSON")):
        ledger.write_bytes(data)
        for cmd in ("due", "report"):
            call(2, cmd, "--ledger", ledger, has=has)
    for cmd in ("due", "report"):
        call(2, cmd, "--ledger", x / "absent.jsonl", has="absent.jsonl")
        call(2, cmd, "--ledger", x, has="unusable")
        call(2, cmd, has="--ledger")

    for day, want in (("2026-03-02", "100"), ("2026-03-01", "110"), ("2026-01-31", "110"), ("2026-01-30", "101"), ("2026-01-01", "101"), ("2025-12-31", "100")):
        text = check(0, {**bare, "date": day}, cmd=("report", "--date", "2026-03-01"))
        assert f"| `demo` | `data` | `no-signature` | {' | '.join(want)} | no |  |\n" in text, (day, text)
    commit = "https://github.com/example/demo/commit/" + "0123456789" * 4
    lines = [one, {**bare, "target": "b"}, {**two, "date": "2025-12-01"}, two, {**one, "target": "c", "error": "no-signatures"}, {**three, "target": "c", "source": commit}, {**case, "target": "c"},
             {**one, "target": "c", "source": SOURCE.format(4)}, {**bare, "target": "b", "error": "other"}, {**bare, "target": "d", "error": "no-signatures"}, {**bare, "target": "d", "project": "a.b"}, {**case, "target": "b"}]
    text = check(0, *lines, cmd=("report", "--date", "2026-01-30"))
    assert text == check(0, *lines, cmd=("report", "--date", "2026-01-30")) == f"""## Improvement loop, 2026-01-30

9 occurrences, 7 errors, 1 repeated lines counted once.
Last 30 days: 2026-01-01 to 2026-01-30. Before: 2025-12-02 to 2025-12-31.

### Due

- `demo` `c` `no-signature`: came back after its case: 1 [0123456]({commit}) [#4]({SOURCE.format(4)})
- `demo` `data` `no-signature`: seen 2 times, no case [#1]({SOURCE.format(1)}) [#2]({SOURCE.format(2)})

### Counts

| project | target | error id | all | last 30 days | 30 days before | case | sources |
|---|---|---|---|---|---|---|---|
| `a.b` | `d` | `no-signature` | 1 | 1 | 0 | no |  |
| `demo` | `b` | `no-signature` | 1 | 1 | 0 | `evals.json: reply, 2` |  |
| `demo` | `b` | `other` | 1 | 1 | 0 | no |  |
| `demo` | `c` | `no-signature` | 2 | 2 | 0 | `evals.json: reply, 2` | [0123456]({commit}) [#4]({SOURCE.format(4)}) |
| `demo` | `c` | `no-signatures` | 1 | 1 | 0 | no | [#1]({SOURCE.format(1)}) |
| `demo` | `d` | `no-signatures` | 1 | 1 | 0 | no |  |
| `demo` | `data` | `no-signature` | 2 | 1 | 0 | no | [#1]({SOURCE.format(1)}) [#2]({SOURCE.format(2)}) |

### Ids spelled alike

- `demo` `c` `no-signature` and `no-signatures`
""", text
    check(0, bare, {**bare, "error": "no-capture"}, cmd=("report",), has="### Due\n\nNothing due.\n")
    check(0, bare, {**bare, "error": "no-capture"}, cmd=("report",), has="### Ids spelled alike\n\nNone.\n")
    check(0, bare, cmd=("report",), has=f"## Improvement loop, {datetime.datetime.now(datetime.timezone.utc).date()}\n")
    check(2, bare, cmd=("report", "--date", "soon"), has="invalid")
    check(2, bare, cmd=("due", "--date", "2026-01-01"), has="unrecognized arguments")


def walk(x):
    root, agent = x / "repo", x / "repo/skills/demo/agents/data.md"
    (root / "agents/trials/data").mkdir(parents=True)
    agent.parent.mkdir(parents=True)
    for f in ("agents/trials/data/bench.py", "agents/trials/data/reserved.txt"):
        shutil.copy(ROOT / f, root / f)
    ledger = x / "errors.jsonl"
    lines = [f"Rule {i} — check every thing." for i in range(30)]

    def write(**edits):
        agent.write_text("\n".join(edits.get(f"l{i}", s) for i, s in enumerate(lines)) + "\n", encoding="utf-8", newline="\n")

    def commit():
        git(root, "add", "-A")
        git(root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=none", "commit", "-qm", "x")

    def call(code, *argv, claude=None, has=""):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                got = main([str(a) for a in argv], root, claude)
            except SystemExit as e:
                got = e.code
        assert got == code and has in buf.getvalue(), f"expected exit {code} with {has!r}, got {got}: {argv}\n{buf.getvalue()}"
        return buf.getvalue()

    def log(*entries):
        ledger.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")

    def rejected(text, code, rel):
        tail = text.partition("Line for the log of rejected changes:\n")[2]
        assert (tail.count("\n"), tail[-2:]) == ((1, "}\n") if code == 1 else (0, "")), text
        row = json.loads(tail or "{}")
        assert not row or ([*row], row["date"], row["agent"]) == (["date", "agent", "change", "reason", "scores"], datetime.date.today().isoformat(), rel), row
        return row

    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    call(0, "size")
    write()
    commit()

    walk_ledger(x, call)

    bench = load_bench(root)
    bench.solution(x / "good", bench.REF_MASK, bench.REF_PURGE)
    for d in ("bad", "broken", "free", "mute", "capped", "flagged", "failed", "subtype", "over"):
        shutil.copytree(x / "good", x / d)
        (x / d / "purge.py").unlink()
    (x / "stub.py").write_text(STUB, encoding="utf-8")

    def launch(code, d, out, *more, has=""):
        stub = [sys.executable, str(x / "stub.py"), str(x / d)]
        call(code, "run", "--candidate", d, "--role", agent, "--runs", 3, "--model", "stub-1", "--out", x / out, *more, claude=stub, has=has)

    def calls():
        return [json.loads(s) for s in (x / "calls.jsonl").read_text(encoding="utf-8").splitlines()]

    cap = ("--max-budget-usd", 0.5)
    launch(0, "bad", "base.json", has="model runs: 3, no cap")
    launch(0, "bad", "base.json", *cap, has="model runs: 3, cap 0.5 USD each, 1.5 USD in all")
    launch(2, "bad", "base.json", "--yes", has="--yes needs --max-budget-usd")
    for bad in ("0", "-1", "nan", "inf", "x"):
        launch(2, "bad", "base.json", "--yes", f"--max-budget-usd={bad}", has="invalid dollars value")
    assert not (x / "base.json").exists() and not (x / "calls.jsonl").exists(), "a dry run must not execute"
    launch(0, "bad", "base.json", "--yes", *cap)
    launch(0, "good", "new.json", "--yes", *cap, has="cost 0.25 USD")
    launch(2, "good", "new.json", "--yes", *cap, has="already exists")
    made = calls()
    assert all(c[c.index("--max-budget-usd") + 1] == "0.5" for c in made), "every call carries the cap"
    assert len({c[0] for c in made}) == 6 and not any(Path(c[0]).is_relative_to(root) for c in made), "one fresh workspace per run, outside"
    assert all(str(agent) in c and "stub-1" in c and not any("dangerously" in s or "bypass" in s for s in c) for c in made)
    (x / "calls.jsonl").unlink()
    launch(2, "broken", "partial.json", "--yes", *cap, has="run 2 not measured, not scored: claude exit 1, subtype None, cost unknown, cap 0.5 USD")
    assert len(json.loads((x / "partial.json").read_text(encoding="utf-8"))["runs"]) == 1, "finished runs are kept"
    for d, has in (("capped", "claude exit 0, subtype error_max_budget_usd, cost 0.25"), ("flagged", "cost 0.25"), ("failed", "claude exit 1"), ("subtype", "error_other, cost 0.25"), ("over", "cost 0.5, cap 0.5"), ("mute", "cost unknown")):
        n = len(calls())
        launch(2, d, "stopped.json", "--yes", *cap, has=has)
        assert len(calls()) == n + 1 and not (x / "stopped.json").exists(), f"{d}: a stopped run is not scored and stops the series"
    launch(0, "free", "free.json", "--yes", *cap, has="cost unknown USD")
    assert json.loads((x / "free.json").read_text(encoding="utf-8"))["runs"][0]["cost_usd"] is None, "an absent cost is not zero"
    for c in made + calls():
        shutil.rmtree(c[0], ignore_errors=True)

    base, new = (json.loads((x / f).read_text(encoding="utf-8")) for f in ("base.json", "new.json"))
    assert new["runs"][0]["usage"] == {"output_tokens": 7} and new["runs"][0]["cost_usd"] == 0.25 and new["runs"][0]["seconds"] >= 0 and new["model"] == "stub-1"
    assert all(new["runs"][0]["checks"].values()) and not base["runs"][0]["checks"]["T3:purge.py runs"]

    def judge(code, has, b=base, n=new):
        for f, d in (("b.json", b), ("n.json", n)):
            (x / f).write_text(json.dumps(d), encoding="utf-8")
        text = call(code, "gate", "--base", x / "b.json", "--new", x / "n.json", "--agent", agent, "--base-rev", "HEAD", has=has)
        fails = [s for s in text.splitlines() if s.startswith("  FAIL")]
        assert len(fails) == (code == 1), text
        row = rejected(text, code, "skills/demo/agents/data.md")
        assert not row or (has in row["reason"] and "-> " in row["change"] and row["scores"].startswith("reserved 0.")), row

    def edited(d, change, only=None):
        d = json.loads(json.dumps(d))
        for r in d["runs"][:only]:
            change(r["checks"])
        return d

    clean = git(root, "status", "--porcelain")
    write(l3="Rule 3 — write purge.py.")
    judge(0, "ACCEPT")
    seen, kept = "T1:schema loads", "T2:06.txt no leak"
    judge(1, "lower pass rate: " + seen, n=edited(new, lambda c: c.update({seen: False}), 1))
    judge(1, "lower pass rate: " + kept, n=edited(new, lambda c: c.update({kept: False}), 1))
    judge(1, "reserved mean must rise", n=base)
    judge(1, "model: stub-1 -> stub-2", n={**new, "model": "stub-2"})
    judge(1, "missing from one file: " + seen, n=edited(new, lambda c: c.pop(seen)))
    judge(2, "reserved checks absent", b=edited(base, lambda c: c.pop(kept)))
    judge(2, "2 runs", n={**new, "runs": new["runs"][:2]})
    judge(2, "same checks", n=edited(new, lambda c: c.pop(seen), 1))
    write(l3=lines[3] + " Again.")
    judge(1, "words: 180 -> 181")
    write(**{f"l{i}": f"Rule {i} — check all." for i in (1, 5, 9, 13)})
    judge(0, "hunks: 4")
    write(**{f"l{i}": f"Rule {i} — check all." for i in (1, 5, 9, 13, 17)})
    judge(1, "hunks: 5")
    write()
    judge(2, "no text change")
    assert git(root, "status", "--porcelain") == clean, "the gate writes nothing"

    lines.append("word " * AGENT_WORDS)
    write()
    commit()
    call(1, "size", has="data.md: 1680 words, limit 1500")
    CEILINGS["skills/demo/agents/data.md"] = 1679
    call(1, "size", has="data.md: 1680 words, limit 1679")
    CEILINGS["skills/demo/agents/data.md"] = 1680
    call(0, "size", has="data.md: 1680 words, over the limit 1500, ceiling 1680")
    del CEILINGS["skills/demo/agents/data.md"]
    write(l3="Rule 3 — check each thing.")
    judge(1, "words: 1680 -> 1680")
    write(l3="Rule 3 — check.")
    judge(0, "ACCEPT")
    write(l30="")

    def put(rel, text, add=True):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
        if add:
            git(root, "add", rel)

    head, long = "---\nname: s\n---\n", "word " * (AGENT_WORDS + 1)
    put("skills/demo/SKILL.md", head + "x\n" * SKILL_LINES)
    put("skills/demo/scripts/node_modules/p/SKILL.md", head + "x\n" * 600, add=False)
    put("agents/README.md", long)
    put("agents/trials/data/candidates/c.md", head + long)
    call(0, "size", has="size ok")
    put("skills/demo/SKILL.md", head + "x\n" * (SKILL_LINES + 1))
    call(1, "size", has="SKILL.md: 501 lines")
    put("skills/demo/SKILL.md", head)
    put("agents/kept.md", head + long)
    call(1, "size", has="agents/kept.md: 1505 words")
    put("agents/kept.md", head)
    put("skills/demo/evals/answers.jsonl", "{}\n")
    put("ledger/errors.jsonl", "{}\n", add=False)
    call(0, "size", has="size ok")
    for rel in ("ledger/errors.jsonl", "agents/errors.jsonl", "errors.jsonl"):
        put(rel, "{}\n")
        call(1, "size", has=f"{rel}: no ledger in this repository")
        git(root, "rm", "-q", "-f", rel)

    evals, skill = "skills/tone/evals/", root / "skills/tone/SKILL.md"
    first, second = (entry(target="tone", source=SOURCE.format(n)) for n in (1, 2))
    log(first)
    call(0, "due", "--ledger", ledger, has="nothing due")
    log(first, second)
    call(1, "due", "--ledger", ledger, has="demo/tone: no-signature seen 2 times, no case")
    put(evals + "evals.json", json.dumps({"skill_name": "tone", "evals": [{"name": "letter"}, {"name": "reply"}]}))
    put(evals + "grade.py", GRADER)
    put(evals + "reserved.txt", "reply:signs: Élodie\n\nreply:adds no promise\n")
    put("skills/tone/reference.md", "Keep.\n")
    text = head + long + "\n" + "Be polite at all times.\n" * 10
    put("skills/tone/SKILL.md", text)
    log(first, second, entry(target="tone", case="skills/tone/evals/evals.json: reply"))
    call(0, "due", "--ledger", ledger, has="nothing due")
    commit()

    letter, good = "Le café → ouvert", "Élodie, no promise"
    for d, first, second in (("b1", letter, "no promise"), ("b2", letter, "Élodie"), ("b3", letter, ""),
                             ("n1", letter, good), ("n2", letter, good), ("n3", letter, good), ("w", "", good)):
        put(f"../{d}/letter.md", first, add=False)
        put(f"../{d}/reply.md", second, add=False)
    put("../gone/letter.md", letter, add=False)

    def score(code, out, *runs, mode=(), has="", skill="tone", model="m-1"):
        kept = (x / out).exists()
        with mock.patch.dict(os.environ, {"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"}):
            call(code, "scores", "--skill", skill, "--model", model, "--out", x / out, *(x / r for r in runs), *mode, has=has)
        assert (x / out).exists() == (code == 0 or kept), f"{out}: written with exit {code}"

    new3 = ("n1", "n2", "n3")
    score(0, "before.json", "b1", "b2", "b3", has="b1: 3/4 checks")
    score(0, "after.json", *new3, has="n3: 4/4 checks")
    score(0, "worse.json", "n1", "n2", "w", mode=("--", "--mode", "other"), has="w: 2/4 checks")
    after = json.loads((x / "after.json").read_text(encoding="utf-8"))
    assert after["skill"] == "tone" and after["runs"][0] == {"run": "n1", "checks": {k: True for k in (
        "letter:names the café", "letter:keeps | the arrow →", "reply:signs: Élodie", "reply:adds no promise")}}, after
    assert str(x) not in json.dumps(after) and x.as_posix() not in json.dumps(after), "no local path in the scores"
    score(2, "after.json", *new3, has="already exists")
    score(2, "no.json", "n1", "n2", "gone", has="case reply not measured: missing")
    score(2, "no.json", "n1", "n2", "nowhere", has="nowhere")
    score(2, "no.json", "n1", "n2", has="2 runs, at least 3")
    score(2, "no.json", "n1", "n2", "n1", has="given twice")
    score(2, "no.json", "n1", "n2", "n2/../n1", has="given twice")
    if (x / "N1").exists():
        score(2, "no.json", "n1", "n2", "N1", has="given twice")
    for name in ("nope", "../tone", "tone/../tone", "..", ".", "", str(root / "skills/tone")):
        score(2, "no.json", *new3, skill=name, has="unknown skill")
    score(2, "no.json", *new3, model="", has="no model name")
    for mode, has in (("crash", "grader broke"), ("text", "not JSON"), ("error", "case reply not measured: interrupted"), ("twice", "two assertions named reply:signs: Élodie"),
                      ("empty", "case reply not measured: no assertion"), ("none", "with 0/0"), ("shape", "KeyError('passed')"), ("exit", "grade.py exit 3")):
        score(2, "no.json", *new3, mode=("--", "--mode", mode), has=has)
    score(2, "no.json", "b1", "b2", "b3", mode=("--", "--mode", "zero"), has="grade.py exit 0 with 3/4")
    score(2, "no.json", *new3, mode=("--", "--unknown"), has="grade.py exit 2")
    for f in ("evals.json", "grade.py"):
        kept = (root / evals / f).read_text(encoding="utf-8")
        put(evals + f, kept + "\n")
        score(0, f + ".after", *new3)
        put(evals + f, kept)

    def verdict(code, has, b="before.json", n="after.json", target=skill):
        text = call(code, "gate", "--base", x / b, "--new", x / n, "--agent", target, "--base-rev", "HEAD", has=has)
        return rejected(text, code, "skills/tone/SKILL.md")

    verdict(2, "no text change")
    changed = text.replace("Be polite at all times.", "Sign Élodie, with no promise.", 1)
    put("skills/tone/SKILL.md", changed)
    put("skills/tone/scripts/node_modules/p/index.js", "x", add=False)
    put("skills/tone/scripts/__pycache__/p.pyc", "x", add=False)
    put("skills/demo/SKILL.md", head + "x")
    verdict(0, "ok   words: 1555 -> 1555, body lines: 11 -> 11")
    row = verdict(1, "FAIL checks with a lower pass rate: letter:keeps | the arrow →, letter:names the café", n="worse.json")
    assert row["reason"] == "checks with a lower pass rate: letter:keeps | the arrow →, letter:names the café" and row["change"].startswith("1 hunks, 1555 -> 1555 words"), row
    verdict(1, "reserved mean must rise: 0.333 -> 0.333", n="before.json")
    verdict(2, "two different tests", b="base.json")
    verdict(2, "two different tests", n="new.json")
    verdict(2, "two different tests", n="evals.json.after")
    verdict(2, "two different tests", n="grade.py.after")
    verdict(2, "not an agent or a SKILL.md of skills/tone/", target=agent)
    verdict(2, "not an agent or a SKILL.md of skills/tone/", target=root / evals / "grade.py")
    (x / "nope.json").write_text(json.dumps({**after, "skill": "nope"}), encoding="utf-8")
    verdict(2, "unknown skill: 'nope'", b="nope.json", n="nope.json")
    verdict(2, "two different tests", n="nope.json")
    put("skills/tone/SKILL.md", changed.replace("no promise", "no promise at all"))
    verdict(1, "FAIL words: 1555 -> 1557, body lines: 11 -> 11")

    reserved = (root / evals / "reserved.txt").read_text(encoding="utf-8")
    for content, has in (("\n \n", "is empty"), (reserved + "reply:absent\n", "reserved checks absent"), (reserved + "reply\n", "reserved checks absent")):
        put(evals + "reserved.txt", content)
        verdict(2, has)
    put(evals + "reserved.txt", reserved.splitlines()[0])
    put("skills/tone/SKILL.md", changed)
    verdict(2, "other changes since HEAD, so the scores do not judge skills/tone/SKILL.md alone: skills/tone/evals/reserved.txt")
    git(root, "rm", "-q", "--cached", evals + "reserved.txt")
    (root / evals / "reserved.txt").unlink()
    verdict(2, "no reserved list")
    put(evals + "reserved.txt", reserved)
    put("skills/tone/reference.md", "Keep it.\n")
    verdict(2, "alone: skills/tone/reference.md")
    put("skills/tone/reference.md", "Keep.\n")
    put("skills/tone/new.md", "x", add=False)
    verdict(2, "alone: skills/tone/new.md")
    (root / "skills/tone/new.md").unlink()
    verdict(0, "ACCEPT")

    for n, code in ((SKILL_LINES, 0), (SKILL_LINES + 1, 1)):
        put("skills/tone/SKILL.md", head + "x y\n" * n)
        commit()
        put("skills/tone/SKILL.md", head + "z y\n" + "x y\n" * (n - 1))
        verdict(code, f"body lines: {n} -> {n}")
    put("skills/tone/SKILL.md", head + "x y\n" * SKILL_LINES)
    verdict(0, "body lines: 501 -> 500")


def positive(s):
    if int(s) < 1:
        raise ValueError
    return int(s)


def dollars(s):
    if not 0 < float(s) < float("inf"):
        raise ValueError
    return float(s)


def main(argv, root=ROOT, claude=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for c in ("size", "selftest"):
        sub.add_parser(c)
    for c in ("due", "report"):
        e = sub.add_parser(c)
        e.add_argument("--ledger", required=True)
    e.add_argument("--date", type=datetime.date.fromisoformat)
    s = sub.add_parser("scores", usage="%(prog)s --skill NAME --model MODEL --out FILE RUN RUN RUN... [-- GRADER_ARGS...]")
    for o in ("--skill", "--model", "--out"):
        s.add_argument(o, required=True)
    s.add_argument("runs", nargs="+")
    g = sub.add_parser("gate")
    for o in ("--base", "--new", "--agent", "--base-rev"):
        g.add_argument(o, required=True)
    r = sub.add_parser("run")
    for o in ("--candidate", "--model", "--out"):
        r.add_argument(o, required=True)
    r.add_argument("--runs", required=True, type=positive)
    r.add_argument("--role")
    r.add_argument("--max-budget-usd", type=dollars)
    r.add_argument("--yes", action="store_true")
    cut = argv.index("--") if argv[:1] == ["scores"] and "--" in argv else len(argv)
    a = vars(p.parse_args(argv[:cut]))
    cmd = a.pop("cmd")
    if cmd == "scores":
        a["extra"] = argv[cut + 1:]
    try:
        if cmd == "selftest":
            return selftest()
        if cmd == "run":
            return run(root, **a, claude=claude)
        return {"size": size, "due": due, "report": report, "scores": scores, "gate": gate}[cmd](root, **a)
    except Unusable as e:
        print(f"unusable: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
