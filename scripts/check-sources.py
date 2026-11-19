#!/usr/bin/env python3
"""Check that the official pages quoted in skills/*/sources.json still contain their quote.

Run by hand by the owner; reads the network, writes nothing.
  python3 scripts/check-sources.py [skill ...] [--root DIR] [--json] [--self-test]

Statuses: CHANGED (page fetched, quote missing), UNREACHABLE, BLOCKED (the site refuses
automated clients: check by hand), UNREAD (manifest says unread), UNCHANGED.
Exit 1 if any CHANGED, 2 if a manifest is invalid, else 0.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True

UA = "cdfarkas-skills-source-check"
TIMEOUT = 30
ORDER = ["CHANGED", "UNREACHABLE", "BLOCKED", "UNREAD", "UNCHANGED"]
FIELDS = ("id", "url", "title", "used_in", "quote", "retrieved", "method", "status")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BOT_RE = re.compile(r"just a moment|captcha|access denied|enable javascript|cf-chl|are you a robot", re.I)
MANUAL = (
    "open the URL with a web-fetch tool from Claude and ask whether the page still contains the quote"
    " (Legifrance: and whether the article version is still 'en vigueur')"
)
QUOTES = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    }
)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(QUOTES)
    return re.sub(r"\s+", " ", text).strip().casefold()


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    return html.unescape("".join(p.parts))


def pdf_text(data: bytes) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as d:
        src, out = Path(d) / "in.pdf", Path(d) / "out.txt"
        src.write_bytes(data)
        subprocess.run([exe, "-q", "-enc", "UTF-8", str(src), str(out)], check=False, timeout=120)
        return out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""


def extract(url: str, ctype: str, body: bytes) -> tuple[str | None, str]:
    """Return (text, detail); text None means it could not be extracted."""
    if body[:5] == b"%PDF-" or "pdf" in ctype.lower() or url.lower().split("?")[0].endswith(".pdf"):
        text = pdf_text(body)
        return (None, "pdf, pdftotext missing") if text is None else (text, "")
    return html_text(body.decode("utf-8", errors="replace")), ""


def fetch(url: str) -> tuple[str, str, bytes, str]:
    """Return (outcome, detail, body, content-type); outcome is ok|blocked|unreachable."""
    last = ""
    for _ in range(2):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read()
                if r.status == 202 and not body.strip():
                    return "blocked", "HTTP 202 with empty body", b"", ""
                return "ok", f"HTTP {r.status}", body, r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return "blocked", f"HTTP {e.code}", b"", ""
            last = f"HTTP {e.code}"
            if e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
    return "unreachable", last, b"", ""


def classify(quote: str, outcome: str, detail: str, text: str | None) -> tuple[str, str]:
    if outcome == "blocked":
        return "BLOCKED", detail
    if outcome != "ok" or text is None:
        return "UNREACHABLE", detail
    page = norm(text)
    if norm(quote) in page:
        return "UNCHANGED", ""
    if not page:
        return "UNREACHABLE", "empty body"
    if BOT_RE.search(text[:5000]) and len(page) < 3000:
        return "UNREACHABLE", "bot-protection page"
    return "CHANGED", "quote not found in the fetched page"


def validate(path: Path, data) -> list[str]:
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        return [f"{path}: `sources` must be a list"]
    errs: list[str] = []
    ids: set = set()
    for i, s in enumerate(sources):
        label = f"{path}: source #{i}" + (f" ({s.get('id')})" if isinstance(s, dict) and s.get("id") else "")
        if not isinstance(s, dict):
            errs.append(f"{label}: not an object")
            continue
        errs += [f"{label}: missing `{f}`" for f in FIELDS if f not in s]
        if s.get("id") in ids:
            errs.append(f"{label}: duplicate id")
        ids.add(s.get("id"))
        if not isinstance(s.get("used_in"), list):
            errs.append(f"{label}: `used_in` must be a list")
        if s.get("status") not in ("read", "unread"):
            errs.append(f"{label}: status must be read or unread")
        if s.get("method") not in ("webfetch", "curl"):
            errs.append(f"{label}: method must be webfetch or curl")
        q = s.get("quote", "")
        if not isinstance(q, str) or len(q) > 300:
            errs.append(f"{label}: quote must be a string of at most 300 chars")
        elif s.get("status") == "read" and not q.strip():
            errs.append(f"{label}: status read needs a non-empty quote")
        if not DATE_RE.match(str(s.get("retrieved", ""))):
            errs.append(f"{label}: retrieved must be YYYY-MM-DD")
        if not str(s.get("url", "")).startswith(("http://", "https://")):
            errs.append(f"{label}: url must be http(s)")
    return errs


def run(root: Path, skills: list[str]) -> tuple[list[dict], list[str]]:
    manifests = sorted(root.glob("skills/*/sources.json"))
    if skills:
        manifests = [m for m in manifests if m.parent.name in skills]
    errors: list[str] = []
    entries: list[dict] = []
    for m in manifests:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"{m}: {exc}")
            continue
        errs = validate(m, data)
        errors += errs
        if not errs:
            entries += [dict(s, skill=m.parent.name) for s in data["sources"]]
    if errors:
        return [], errors
    cache: dict[str, tuple[str, str, str | None]] = {}
    for e in entries:
        if e["status"] == "unread":
            e["result"], e["detail"] = "UNREAD", "never read: read it and record a quote"
            continue
        url = e["url"]
        if url not in cache:
            outcome, detail, body, ctype = fetch(url)
            text = None
            if outcome == "ok":
                text, pdetail = extract(url, ctype, body)
                detail = pdetail or detail
            cache[url] = (outcome, detail, text)
        e["result"], e["detail"] = classify(e["quote"], *cache[url])
        if e["result"] == "BLOCKED":
            e["detail"] = f"{e['detail']}; {MANUAL}"
    return entries, []


def render(entries: list[dict]) -> str:
    out: list[str] = []
    for st in ORDER:
        rows = [e for e in entries if e["result"] == st]
        if not rows:
            continue
        out.append(f"\n## {st} ({len(rows)})\n")
        out.append("| id | skill | url | used_in | note |\n|---|---|---|---|---|")
        out += [f"| {e['id']} | {e['skill']} | {e['url']} | {', '.join(e['used_in'])} | {e['detail']} |" for e in rows]
    counts = ", ".join(f"{st}={sum(e['result'] == st for e in entries)}" for st in ORDER)
    out.append(f"\ntotal {len(entries)}: {counts}")
    return "\n".join(out)


def self_test() -> int:
    import unittest

    class T(unittest.TestCase):
        def test_norm(self):
            self.assertEqual(norm("L’Hébergeur  “X”\n y"), "l'hébergeur \"x\" y")
            self.assertEqual(norm("ﬁn"), "fin")

        def test_html(self):
            t = html_text("<p>Hello&nbsp;<b>wor</b>ld</p><script>var q='secret'</script>")
            self.assertNotIn("secret", t)
            self.assertIn("hello", norm(t))

        def test_local_files(self):
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "a.html"
                f.write_text("<html><body><p>The  quote\nis here</p></body></html>", encoding="utf-8")
                text, _ = extract("http://x/a.html", "text/html", f.read_bytes())
                self.assertEqual(classify("the quote is here", "ok", "", text)[0], "UNCHANGED")
                text, detail = extract("http://x/a.pdf", "application/pdf", b"%PDF-1.4 not a pdf")
                if shutil.which("pdftotext"):
                    self.assertEqual(classify("zzz", "ok", detail, text)[0], "UNREACHABLE")
                else:
                    self.assertEqual((text, detail), (None, "pdf, pdftotext missing"))

        def test_classify(self):
            q = "exact words"
            self.assertEqual(classify(q, "ok", "", "some exact  WORDS here")[0], "UNCHANGED")
            self.assertEqual(classify(q, "ok", "", "other content entirely")[0], "CHANGED")
            self.assertEqual(classify(q, "ok", "", "   ")[0], "UNREACHABLE")
            self.assertEqual(classify(q, "ok", "", "Just a moment... captcha")[0], "UNREACHABLE")
            self.assertEqual(classify(q, "blocked", "HTTP 403", None)[0], "BLOCKED")
            self.assertEqual(classify(q, "unreachable", "HTTP 503", None)[0], "UNREACHABLE")
            self.assertEqual(classify(q, "ok", "pdf, pdftotext missing", None)[0], "UNREACHABLE")

        def test_validate(self):
            good = {"id": "a", "url": "https://x", "title": "t", "used_in": [], "quote": "q",
                    "retrieved": "2026-01-02", "method": "curl", "status": "read"}
            self.assertEqual(validate(Path("m"), {"sources": [good]}), [])
            bad = [dict(good, quote=""), dict(good, id="b", quote="x" * 301), dict(good, id="c", retrieved="2026/01/02")]
            self.assertEqual(len(validate(Path("m"), {"sources": bad})), 3)
            self.assertEqual(validate(Path("m"), {"sources": [dict(good, status="unread", quote="")]}), [])

    res = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(T))
    return 0 if res.wasSuccessful() else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skills", nargs="*")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    entries, errors = run(Path(a.root), a.skills)
    if errors:
        print("\n".join(f"ERROR {e}" for e in errors), file=sys.stderr)
        return 2
    print(json.dumps(entries, ensure_ascii=False, indent=2) if a.json else render(entries))
    return 1 if any(e["result"] == "CHANGED" for e in entries) else 0


if __name__ == "__main__":
    sys.exit(main())
