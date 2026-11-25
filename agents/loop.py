"""Improvement loop: size limits, due failures, acceptance gate, trial launcher.

Exit codes: 0 ok or accepted, 1 over the limit, due or rejected, 2 unusable input.
"""
import argparse, contextlib, datetime, importlib.util, io, json, os, shlex, shutil, subprocess, sys, tempfile, time
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
AGENT_WORDS, SKILL_LINES, MAX_HUNKS, MIN_RUNS, TIMEOUT_S = 1500, 500, 4, 3, 3600
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
        if lines[:1] == ["---"] and "---" in lines[1:]:
            lines = lines[lines.index("---", 1) + 1:]
        if len(lines) > SKILL_LINES:
            over.append(f"{rel}: {len(lines)} lines, limit {SKILL_LINES}")
    print("\n".join(notes + (over or ["size ok"])))
    return 1 if over else 0


def due(root):
    table = [x for x in (root / "agents" / "failures.md").read_text(encoding="utf-8").splitlines() if x.startswith("|")]
    if len(table) < 2:
        raise Unusable("failures.md: no table")
    seen = {}
    for x in table[2:]:
        row = [c.strip() for c in x.strip().removeprefix("|").removesuffix("|").split("|")]
        if len(row) != 6 or not row[1] or not row[2]:
            raise Unusable(f"failures.md: expected 6 cells with agent and error id: {x}")
        seen.setdefault((row[1], row[2]), []).append(row[5])
    late = [f"{agent}: {error} seen {len(cases)} times, no case" for (agent, error), cases in sorted(seen.items()) if len(cases) >= 2 and not any(cases)]
    print("\n".join(late) or "nothing due")
    return 1 if late else 0


def scores(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        model, runs = data["model"], [r["checks"] for r in data["runs"]]
    except (OSError, ValueError, KeyError, TypeError) as e:
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


def gate(root, base, new, agent, base_rev):
    (model_a, a), (model_b, b) = scores(base), scores(new)
    reserved = {x.strip() for x in (root / "agents/trials/data/reserved.txt").read_text(encoding="utf-8").splitlines() if x.strip()}
    if not reserved or not reserved <= a.keys():
        raise Unusable(f"reserved checks absent from {base}: {sorted(reserved - a.keys()) or 'reserved.txt is empty'}")
    try:
        path = Path(agent).resolve()
        rel = path.relative_to(root.resolve()).as_posix()
        new_words = words(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Unusable(f"{agent}: {e}")
    sha = git(root, "rev-parse", "--verify", "--end-of-options", f"{base_rev}^{{commit}}").strip()
    old_words = words(git(root, "show", f"{sha}:{rel}"))
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
    short_enough = new_words < old_words if old_words > AGENT_WORDS else new_words <= old_words
    rules = [
        (model_a == model_b, f"same model: {model_a} -> {model_b}"),
        (not differ, f"checks missing from one file: {', '.join(differ) or 'none'}"),
        (r1 > r0, f"reserved mean must rise: {float(r0):.3f} -> {float(r1):.3f}"),
        (not lower, f"checks with a lower pass rate: {', '.join(lower) or 'none'}"),
        (short_enough, f"words: {old_words} -> {new_words}"),
        (hunks <= MAX_HUNKS, f"changed hunks: {hunks}, limit {MAX_HUNKS}"),
    ]
    failed = [text for ok, text in rules if not ok]
    print("REJECT" if failed else "ACCEPT")
    for ok, text in rules:
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if failed:
        cells = [datetime.date.today().isoformat(), rel, f"{hunks} hunks, {old_words} -> {new_words} words since {sha[:7]}", "; ".join(failed),
                 f"reserved {float(r0):.3f} -> {float(r1):.3f}, visible {float(v0):.3f} -> {float(v1):.3f}"]
        print("\nRow for agents/rejected.md:\n| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return 1 if failed else 0


def load_bench(root):
    spec = importlib.util.spec_from_file_location("bench", root / "agents/trials/data/bench.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    return bench


def run(root, candidate, role, runs, model, out, yes, claude=None):
    cmd = [*(claude or [shutil.which("claude") or "claude"]), *FLAGS, "--model", model]
    if role:
        role = Path(role).resolve()
        if not role.is_file():
            raise Unusable(f"{role}: no such file")
        cmd += ["--append-system-prompt-file", str(role)]
    out = Path(out).resolve()
    if out.exists() or not out.parent.is_dir():
        raise Unusable(f"{out}: already exists, or its folder does not")
    if not yes:
        bench = "python agents/trials/data/bench.py"
        print(f"dry run, nothing executed. Each run:\n  {bench} make WORKSPACE   (new temporary folder outside the repository)")
        print(f"  cd WORKSPACE && {shlex.join(cmd)}\n    stdin: {PROMPT}\n  {bench} grade WORKSPACE\nmodel runs: {runs}. Add --yes to execute.")
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
            raise Unusable(f"run {i} not scored: {e}")
        seconds = round(time.monotonic() - start, 1)
        try:
            reply = json.loads(p.stdout)
        except ValueError:
            reply = None
        reply = reply if isinstance(reply, dict) else {}
        if p.returncode or reply.get("is_error"):
            raise Unusable(f"run {i} not scored, claude failed ({p.returncode}): {(p.stderr or p.stdout)[-300:]}")
        checks = {f"{t}:{k}": v is True for t, res in bench.grade(ws).items() for k, v in res.items() if k not in ("why", "score")}
        done.append({"checks": checks, "seconds": seconds, "usage": reply.get("usage"), "model_usage": reply.get("modelUsage"), "workspace": str(ws)})
        out.write_text(json.dumps({"candidate": candidate, "role": str(role) if role else None, "model": model, "runs": done}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"run {i}/{runs}: {sum(checks.values())}/{len(checks)} checks, {seconds} s, {ws}")
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
print(json.dumps({"is_error": False, "usage": {"output_tokens": 7}, "modelUsage": {"stub": {}}}))
"""


def selftest():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as x:
        walk(Path(x).resolve())
    print("selftest ok")


def walk(x):
    root, agent = x / "repo", x / "repo/skills/demo/agents/data.md"
    (root / "agents/trials/data").mkdir(parents=True)
    agent.parent.mkdir(parents=True)
    for f in ("agents/trials/data/bench.py", "agents/trials/data/reserved.txt"):
        shutil.copy(ROOT / f, root / f)
    log = root / "agents/failures.md"
    log.write_text("# Failures\n\n| date | agent | id | task | failure | case |\n|---|---|---|---|---|---|\n", encoding="utf-8")
    lines = [f"Rule {i} — check every thing." for i in range(30)]

    def write(**edits):
        agent.write_text("\n".join(edits.get(f"l{i}", s) for i, s in enumerate(lines)) + "\n", encoding="utf-8", newline="\n")

    def commit():
        git(root, "add", "-A")
        git(root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=none", "commit", "-qm", "x")

    def call(code, *argv, claude=None, has=""):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            got = main([str(a) for a in argv], root, claude)
        assert got == code and has in buf.getvalue(), f"expected exit {code} with {has!r}, got {got}: {argv}\n{buf.getvalue()}"
        return buf.getvalue()

    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    call(0, "size")
    write()
    commit()

    row = "| 2026-01-01 | data | purge-missing | T3 | purge.py absent | {} |\n"
    once = log.read_text(encoding="utf-8") + row.format("")
    call(0, "due")
    log.write_text(once, encoding="utf-8")
    call(0, "due")
    log.write_text(once + row.format("").replace("| data |", "| other |"), encoding="utf-8")
    call(0, "due")
    log.write_text(once + row.format(""), encoding="utf-8")
    call(1, "due", has="data: purge-missing seen 2 times")
    log.write_text(once + row.format("T3:purge.py runs"), encoding="utf-8")
    call(0, "due")
    log.write_text(once + "| broken |\n", encoding="utf-8")
    call(2, "due")

    bench = load_bench(root)
    bench.solution(x / "good", bench.REF_MASK, bench.REF_PURGE)
    for d in ("bad", "broken"):
        shutil.copytree(x / "good", x / d)
        (x / d / "purge.py").unlink()
    (x / "stub.py").write_text(STUB, encoding="utf-8")

    def launch(code, d, out, *more, has=""):
        stub = [sys.executable, str(x / "stub.py"), str(x / d)]
        call(code, "run", "--candidate", d, "--role", agent, "--runs", 3, "--model", "stub-1", "--out", x / out, *more, claude=stub, has=has)

    def calls():
        return [json.loads(s) for s in (x / "calls.jsonl").read_text(encoding="utf-8").splitlines()]

    launch(0, "bad", "base.json", has="model runs: 3")
    assert not (x / "base.json").exists() and not (x / "calls.jsonl").exists(), "a dry run must not execute"
    launch(0, "bad", "base.json", "--yes")
    launch(0, "good", "new.json", "--yes")
    launch(2, "good", "new.json", "--yes", has="already exists")
    made = calls()
    assert len({c[0] for c in made}) == 6 and not any(Path(c[0]).is_relative_to(root) for c in made), "one fresh workspace per run, outside"
    assert all(str(agent) in c and "stub-1" in c and not any("dangerously" in s or "bypass" in s for s in c) for c in made)
    (x / "calls.jsonl").unlink()
    launch(2, "broken", "partial.json", "--yes", has="run 2 not scored")
    assert len(json.loads((x / "partial.json").read_text(encoding="utf-8"))["runs"]) == 1, "finished runs are kept"
    for c in made + calls():
        shutil.rmtree(c[0], ignore_errors=True)

    base, new = (json.loads((x / f).read_text(encoding="utf-8")) for f in ("base.json", "new.json"))
    assert new["runs"][0]["usage"] == {"output_tokens": 7} and new["runs"][0]["seconds"] >= 0 and new["model"] == "stub-1"
    assert all(new["runs"][0]["checks"].values()) and not base["runs"][0]["checks"]["T3:purge.py runs"]

    def judge(code, has, b=base, n=new):
        for f, d in (("b.json", b), ("n.json", n)):
            (x / f).write_text(json.dumps(d), encoding="utf-8")
        text = call(code, "gate", "--base", x / "b.json", "--new", x / "n.json", "--agent", agent, "--base-rev", "HEAD", has=has)
        fails = [s for s in text.splitlines() if s.startswith("  FAIL")]
        assert len(fails) == (code == 1) and ("| skills/demo/agents/data.md |" in text) == (code == 1), text

    def edited(d, change, only=None):
        d = json.loads(json.dumps(d))
        for r in d["runs"][:only]:
            change(r["checks"])
        return d

    log_text = log.read_text(encoding="utf-8")
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
    assert log.read_text(encoding="utf-8") == log_text and not (root / "agents/rejected.md").exists(), "the gate writes nothing"

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


def positive(s):
    if int(s) < 1:
        raise ValueError
    return int(s)


def main(argv, root=ROOT, claude=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for c in ("size", "due", "selftest"):
        sub.add_parser(c)
    g = sub.add_parser("gate")
    for o in ("--base", "--new", "--agent", "--base-rev"):
        g.add_argument(o, required=True)
    r = sub.add_parser("run")
    for o in ("--candidate", "--model", "--out"):
        r.add_argument(o, required=True)
    r.add_argument("--runs", required=True, type=positive)
    r.add_argument("--role")
    r.add_argument("--yes", action="store_true")
    a = vars(p.parse_args(argv))
    cmd = a.pop("cmd")
    try:
        if cmd == "selftest":
            return selftest()
        if cmd == "run":
            return run(root, **a, claude=claude)
        return {"size": size, "due": due, "gate": gate}[cmd](root, **a)
    except Unusable as e:
        print(f"unusable: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
