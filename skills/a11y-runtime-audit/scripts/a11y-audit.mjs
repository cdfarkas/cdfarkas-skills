/**
 * a11y-runtime-audit: audit one rendered page (dev server or Storybook iframe URL) for
 * WCAG 2.2 A/AA issues that need a browser. Prints a Markdown report on stdout, optionally
 * writes the full JSON with --json. Exit 0 = no blocking finding, 1 = critical/serious
 * finding, 2 = usage error, 3 = the page could not be audited.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';

const HERE = new URL('.', import.meta.url);
const SC = JSON.parse(readFileSync(new URL('wcag22.json', HERE), 'utf8'));
const VERSIONS = {
  axe: JSON.parse(readFileSync(new URL('node_modules/axe-core/package.json', HERE), 'utf8')).version,
  playwright: JSON.parse(readFileSync(new URL('node_modules/playwright/package.json', HERE), 'utf8')).version,
};
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const SEVERITIES = ['critical', 'serious', 'moderate', 'minor', 'advisory'];
const OVERLAY_TIMEOUT = 2000;

const USAGE = `Usage: a11y-runtime-audit.sh <url> [--json <file>] [--wait-for <css>] [--max-tabs N] [--max-overlays N]

  <url>             http(s):// or file:// URL of the rendered page (a Storybook story: its iframe.html URL)
  --json <file>     also write the full result as JSON
  --wait-for <css>  wait for this selector after load (e.g. "#storybook-root > *")
  --max-tabs N      Tab presses in the keyboard walk (default 60)
  --max-overlays N  popup triggers opened and closed with Escape (default 10)`;

function parseArgs(argv) {
  const o = { maxTabs: 60, maxOverlays: 10 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-h' || a === '--help') { console.log(USAGE); process.exit(0); }
    else if (a === '--json') o.json = argv[++i];
    else if (a === '--wait-for') o.waitFor = argv[++i];
    else if (a === '--max-tabs') o.maxTabs = Number(argv[++i]);
    else if (a === '--max-overlays') o.maxOverlays = Number(argv[++i]);
    else if (a.startsWith('--')) usageError(`unknown flag: ${a}`);
    else if (!o.url) o.url = a;
    else usageError(`unexpected argument: ${a}`);
  }
  if (!o.url || !/^(https?|file):\/\//.test(o.url)) usageError('a http(s):// or file:// URL is required');
  if (!(o.maxTabs > 0) || !(o.maxOverlays >= 0)) usageError('--max-tabs and --max-overlays take a number');
  return o;
}

function usageError(msg) {
  console.error(USAGE);
  console.error(msg);
  process.exit(2);
}

function scRef(num) {
  const s = SC[num];
  return s
    ? { sc: num, name: s.name, level: s.level, understanding: `https://www.w3.org/WAI/WCAG22/Understanding/${s.slug}.html` }
    : { sc: num, name: 'not in WCAG 2.2', level: '', understanding: '' };
}

function helpers() {
  const FOCUSABLE = 'a[href],area[href],button,input:not([type=hidden]),select,textarea,summary,iframe,[tabindex],[contenteditable=""],[contenteditable=true]';
  const OVERLAY = '[role=dialog],[role=alertdialog],dialog[open],[role=menu],[role=listbox],[role=tooltip],[aria-modal=true],[popover]';
  const STYLE_PROPS = ['outline-style', 'outline-width', 'outline-color', 'box-shadow', 'border-top-color', 'border-top-width', 'background-color', 'color', 'text-decoration-line'];
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const sel = (el) => {
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && parts.length < 4; n = n.parentElement) {
      if (n.id) { parts.unshift(`#${CSS.escape(n.id)}`); break; }
      let p = n.localName + [...n.classList].slice(0, 2).map((c) => `.${CSS.escape(c)}`).join('');
      const sibs = n.parentElement ? [...n.parentElement.children].filter((s) => s.localName === n.localName) : [];
      if (sibs.length > 1) p += `:nth-of-type(${sibs.indexOf(n) + 1})`;
      parts.unshift(p);
      if (n.localName === 'body') break;
    }
    return parts.join(' > ');
  };
  const label = (el) => (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || el.getAttribute('alt') || el.getAttribute('placeholder') || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const snap = (el, pseudo) => { const cs = getComputedStyle(el, pseudo); return STYLE_PROPS.map((p) => cs.getPropertyValue(p)).join('|'); };
  const styles = (el) => [snap(el), snap(el, '::before'), snap(el, '::after'), el.parentElement ? snap(el.parentElement) : ''].join('#');
  const tabbables = () => [...document.querySelectorAll(FOCUSABLE)].filter((el) => el.tabIndex >= 0 && !el.disabled && visible(el) && !el.closest('[inert],[hidden]'));
  const unfocused = new WeakMap();
  const overlays = () => [...document.querySelectorAll(OVERLAY)].filter((el) => visible(el) && (!el.matches('[popover]') || el.matches(':popover-open')));
  window.__a11y = {
    sel,
    tabbableCount: () => tabbables().length,
    snapshotUnfocused: () => { for (const el of tabbables()) unfocused.set(el, styles(el)); },
    focusInfo: () => {
      const el = document.activeElement;
      if (!el || el === document.body || el === document.documentElement) return { body: true };
      const r = el.getBoundingClientRect();
      const pts = [[r.left + r.width / 2, r.top + r.height / 2], [r.left + 2, r.top + 2], [r.right - 2, r.top + 2], [r.left + 2, r.bottom - 2], [r.right - 2, r.bottom - 2]]
        .filter(([x, y]) => x >= 0 && y >= 0 && x < innerWidth && y < innerHeight);
      const hits = pts.map(([x, y]) => document.elementFromPoint(x, y));
      const shown = hits.some((h) => h && (h === el || el.contains(h) || h.contains(el)));
      const before = unfocused.get(el);
      return {
        body: false,
        selector: sel(el),
        label: label(el),
        indicator: before === undefined ? null : before !== styles(el),
        obscuredBy: pts.length && r.width > 0 && !shown && hits[0] ? sel(hits[0]) : null,
        inModal: !!el.closest('[aria-modal=true],dialog:modal'),
        popup: el.matches('[aria-haspopup]:not([aria-haspopup=false]),[aria-expanded],[popovertarget]'),
      };
    },
    overlayCount: () => overlays().length,
    isOpen: (s, before) => { const t = document.querySelector(s); return (t && t.getAttribute('aria-expanded') === 'true') || overlays().length > before; },
    isClosed: (s, before) => { const t = document.querySelector(s); return !(t && t.getAttribute('aria-expanded') === 'true') && overlays().length <= before; },
    focusReturned: (s) => { const t = document.querySelector(s); return { ok: !!t && t.contains(document.activeElement), at: document.activeElement === document.body ? 'body' : sel(document.activeElement) }; },
    pointerOnly: () => {
      const native = 'a[href],button,input,select,textarea,summary,label,option,[tabindex],[contenteditable]';
      const out = [];
      for (const el of document.body.querySelectorAll('*')) {
        if (el.matches(native) || el.closest(native) || !visible(el)) continue;
        const handler = typeof el.onclick === 'function';
        const pointer = getComputedStyle(el).cursor === 'pointer' && !(el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer');
        if (handler || pointer) out.push({ selector: sel(el), label: label(el), handler });
      }
      return out;
    },
    overflowCulprits: () => {
      const w = document.documentElement.clientWidth;
      const over = [...document.body.querySelectorAll('*')].filter((el) => visible(el) && el.getBoundingClientRect().right > w + 1);
      return { scrollWidth: document.documentElement.scrollWidth, clientWidth: w, culprits: over.filter((el) => !over.includes(el.parentElement)).slice(0, 3).map(sel) };
    },
    clipped: () => [...document.body.querySelectorAll('*')].filter((el) => {
      const cs = getComputedStyle(el);
      const hides = /hidden|clip/.test(cs.overflowX + cs.overflowY);
      return hides && el.innerText && el.innerText.trim() && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1);
    }).map(sel),
    runningAnimations: () => {
      const seen = new Map();
      for (const a of document.getAnimations()) {
        if (a.playState !== 'running' || !a.effect || !a.effect.target) continue;
        const name = a.animationName || (a.transitionProperty ? `transition:${a.transitionProperty}` : 'web-animation');
        const key = `${sel(a.effect.target)}|${name}`;
        if (!seen.has(key)) seen.set(key, { selector: sel(a.effect.target), name, infinite: a.effect.getTiming().iterations === Infinity });
      }
      return [...seen.values()];
    },
  };
}

async function load(page, url, waitFor) {
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
  if (waitFor) await page.waitForSelector(waitFor, { state: 'visible' });
  await page.evaluate(helpers);
}

function finding(f) {
  return { advisory: false, heuristic: false, ...f, ...(f.sc ? scRef(f.sc) : { sc: null, name: '', level: '', understanding: '' }) };
}

async function axeCheck(page) {
  const res = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  const scs = (tags) => tags.map((t) => t.match(/^wcag(\d)(\d)(\d+)$/)).filter(Boolean).map((m) => `${m[1]}.${m[2]}.${m[3]}`);
  const findings = res.violations.map((v) => {
    const node = v.nodes[0];
    const more = v.nodes.length > 1 ? ` (+${v.nodes.length - 1} more)` : '';
    const hint = (node.failureSummary || '').split('\n').map((l) => l.trim()).filter((l) => l && !/^Fix (any|all)/.test(l))[0] || v.help;
    return finding({
      check: `axe/${v.id}`,
      severity: v.impact || 'moderate',
      sc: scs(v.tags)[0],
      also: scs(v.tags).slice(1),
      target: `${node.target.join(' ')}${more}`,
      detail: v.help,
      repro: `Open the URL and inspect \`${node.target.join(' ')}\`: ${hint}`,
      help: v.helpUrl,
      nodes: v.nodes.map((n) => n.target.join(' ')),
    });
  });
  const incomplete = res.incomplete.map((v) => ({ rule: v.id, nodes: v.nodes.length, help: v.helpUrl }));
  return { findings, incomplete };
}

async function tabWalk(page, maxTabs) {
  await page.evaluate(() => window.__a11y.snapshotUnfocused());
  const total = await page.evaluate(() => window.__a11y.tabbableCount());
  const stops = [];
  const findings = [];
  let end = 'max-tabs';
  let still = 0;
  for (let i = 1; i <= maxTabs; i++) {
    await page.keyboard.press('Tab');
    const f = await page.evaluate(() => window.__a11y.focusInfo());
    if (f.body) { if (stops.length) { end = 'left-page'; break; } continue; }
    const last = stops[stops.length - 1];
    if (last && last.selector === f.selector) {
      if (++still >= 2 && total > 1) {
        findings.push(finding({ check: 'keyboard-trap', severity: 'critical', sc: '2.1.2', target: f.selector,
          detail: 'Focus does not move on Tab.', repro: `Open the URL, press Tab ${i} times: focus stays on \`${f.selector}\`.` }));
        end = 'trapped';
        break;
      }
      continue;
    }
    still = 0;
    if (stops.some((s) => s.selector === f.selector)) {
      end = 'wrapped';
      const cycle = stops.slice(stops.findIndex((s) => s.selector === f.selector));
      if (stops.length < total && !cycle.every((s) => s.inModal)) {
        findings.push(finding({ check: 'keyboard-trap', severity: 'critical', sc: '2.1.2', target: f.selector,
          detail: `Tab cycles through ${cycle.length} elements and never reaches the other ${total - stops.length} tabbable ones.`,
          repro: `Open the URL, press Tab ${i} times: focus loops back to \`${f.selector}\`.` }));
      }
      break;
    }
    stops.push({ n: stops.length + 1, ...f });
    if (f.indicator === false) {
      findings.push(finding({ check: 'focus-visible', severity: 'serious', sc: '2.4.7', target: f.selector,
        detail: 'No computed style changes on focus (outline, box-shadow, border, background, colour, underline, ::before/::after, parent).',
        repro: `Open the URL, press Tab ${i} times: \`${f.selector}\` "${f.label}" is focused with no visible change.` }));
    }
    if (f.obscuredBy) {
      findings.push(finding({ check: 'focus-obscured', severity: 'serious', sc: '2.4.11', target: f.selector,
        detail: `Focused element entirely covered by \`${f.obscuredBy}\`.`,
        repro: `Open the URL, press Tab ${i} times: \`${f.selector}\` is focused but hidden under \`${f.obscuredBy}\`.` }));
    }
  }
  return { stops, total, end, findings };
}

async function overlayCheck(page, opts, triggers) {
  const tested = [];
  const findings = [];
  for (const s of triggers.slice(0, opts.maxOverlays)) {
    await load(page, opts.url, opts.waitFor);
    const before = await page.evaluate(() => window.__a11y.overlayCount());
    const loc = page.locator(s).first();
    if (!(await loc.count())) continue;
    await loc.focus();
    await page.keyboard.press('Enter');
    const opened = await page.waitForFunction(([q, b]) => window.__a11y.isOpen(q, b), [s, before], { timeout: OVERLAY_TIMEOUT }).then(() => true, () => false);
    if (!opened) { tested.push({ trigger: s, result: 'did not open on Enter' }); continue; }
    await page.keyboard.press('Escape');
    const closed = await page.waitForFunction(([q, b]) => window.__a11y.isClosed(q, b), [s, before], { timeout: OVERLAY_TIMEOUT }).then(() => true, () => false);
    if (!closed) {
      tested.push({ trigger: s, result: 'stays open on Escape' });
      findings.push(finding({ check: 'overlay-escape', severity: 'moderate', target: s, apg: true,
        detail: 'The popup opened from this trigger does not close on Escape (WAI-ARIA APG dialog and menu button patterns).',
        repro: `Open the URL, focus \`${s}\`, press Enter, then Escape: the popup stays open.` }));
      continue;
    }
    const ret = await page.evaluate((q) => window.__a11y.focusReturned(q), s);
    tested.push({ trigger: s, result: ret.ok ? 'closes on Escape, focus returns' : `closes on Escape, focus lands on ${ret.at}` });
    if (!ret.ok) {
      findings.push(finding({ check: 'overlay-focus-return', severity: 'moderate', sc: '2.4.3', target: s,
        detail: `After Escape, focus lands on \`${ret.at}\` instead of the trigger.`,
        repro: `Open the URL, focus \`${s}\`, press Enter, then Escape: focus goes to \`${ret.at}\`, not back to the trigger.` }));
    }
  }
  return { tested, findings };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const browser = await chromium.launch({ headless: true });
  const out = { url: opts.url, date: new Date().toISOString().slice(0, 10), versions: VERSIONS, viewport: '1280x800' };
  try {
    const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
    try {
      await load(page, opts.url, opts.waitFor);
    } catch (e) {
      console.error(`could not load ${opts.url}: ${e.message.split('\n')[0]}`);
      process.exitCode = 3;
      return;
    }
    const axe = await axeCheck(page);
    const pointer = (await page.evaluate(() => window.__a11y.pointerOnly())).map((p) => finding({
      check: 'pointer-only', severity: p.handler ? 'serious' : 'moderate', sc: '2.1.1', heuristic: !p.handler, target: p.selector,
      detail: p.handler ? 'Has a click handler but cannot receive keyboard focus.' : 'Looks clickable (cursor: pointer) but cannot receive keyboard focus.',
      repro: `Open the URL and Tab through the page: \`${p.selector}\` "${p.label}" is never focused, so it cannot be activated without a pointer.`,
    }));
    const walk = await tabWalk(page, opts.maxTabs);
    const overlays = await overlayCheck(page, opts, walk.stops.filter((s) => s.popup).map((s) => s.selector));

    await load(page, opts.url, opts.waitFor);
    const clippedBefore = new Set(await page.evaluate(() => window.__a11y.clipped()));
    await page.addStyleTag({ content: '* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }' });
    const spacing = (await page.evaluate(() => window.__a11y.clipped())).filter((s) => !clippedBefore.has(s)).map((s) => finding({
      check: 'text-spacing', severity: 'moderate', sc: '1.4.12', heuristic: true, target: s,
      detail: 'Text is clipped once WCAG 1.4.12 text spacing is applied.',
      repro: `Open the URL, apply the 1.4.12 spacing (line-height 1.5, letter 0.12em, word 0.16em, paragraph 2em): \`${s}\` clips its text.`,
    }));

    await page.setViewportSize({ width: 320, height: 800 });
    await load(page, opts.url, opts.waitFor);
    const flow = await page.evaluate(() => window.__a11y.overflowCulprits());
    const reflow = flow.scrollWidth > flow.clientWidth + 1 ? [finding({
      check: 'reflow-320', severity: 'serious', sc: '1.4.10', target: flow.culprits.join(', ') || 'html',
      detail: `Horizontal scroll at 320 CSS px (content ${flow.scrollWidth} px wide).`,
      repro: `Open the URL in a 320 px wide viewport: the page scrolls horizontally; widest: ${flow.culprits.map((c) => `\`${c}\``).join(', ')}.`,
    })] : [];

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await load(page, opts.url, opts.waitFor);
    const motion = (await page.evaluate(() => window.__a11y.runningAnimations())).map((a) => finding({
      check: 'reduced-motion', severity: 'advisory', advisory: true, sc: '2.3.3', target: a.selector,
      detail: `Animation \`${a.name}\`${a.infinite ? ' (infinite)' : ''} keeps running with prefers-reduced-motion: reduce.`,
      repro: `Enable "reduce motion" in the OS, open the URL: \`${a.selector}\` still animates (${a.name}).`,
    }));

    const findings = [...axe.findings, ...pointer, ...walk.findings, ...overlays.findings, ...reflow, ...spacing, ...motion]
      .sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity));
    Object.assign(out, {
      findings,
      needsReview: axe.incomplete,
      focusOrder: { stops: walk.stops.map(({ n, selector, label }) => ({ n, selector, label })), tabbable: walk.total, end: walk.end },
      overlays: overlays.tested,
    });
    const blocking = findings.filter((f) => !f.advisory && (f.severity === 'critical' || f.severity === 'serious')).length;
    if (opts.json) writeFileSync(opts.json, `${JSON.stringify(out, null, 2)}\n`);
    console.log(render(out, blocking));
    process.exitCode = blocking ? 1 : 0;
  } finally {
    await browser.close();
  }
}

function render(out, blocking) {
  const count = (s) => out.findings.filter((f) => f.severity === s).length;
  const tally = SEVERITIES.map((s) => `${count(s)} ${s}`).join(', ');
  const cell = (s) => String(s).replace(/\|/g, '\\|').replace(/\n/g, ' ');
  const lines = [
    `a11y-runtime-audit · ${out.url} · ${out.date} · axe-core ${out.versions.axe} · Playwright ${out.versions.playwright} · Chromium headless ${out.viewport}`,
    '',
    blocking ? `Result: FAIL · ${tally}` : `Result: PASS (no critical or serious finding) · ${tally}`,
    '',
  ];
  if (out.findings.length) {
    lines.push('| # | Severity | WCAG 2.2 | Check | Element | Repro |', '|---|---|---|---|---|---|');
    out.findings.forEach((f, i) => {
      const sc = f.sc
        ? (f.understanding ? `[${f.sc} ${f.name} (${f.level})](${f.understanding})` : `${f.sc} (${f.name})`)
        : '[APG](https://www.w3.org/WAI/ARIA/apg/patterns/)';
      const sev = f.heuristic ? `${f.severity} (heuristic)` : f.severity;
      lines.push(`| ${i + 1} | ${sev} | ${sc} | ${f.check} | \`${cell(f.target)}\` | ${cell(f.repro)} |`);
    });
    lines.push('');
  }
  if (out.needsReview.length) {
    lines.push(`Needs review (axe incomplete, not counted): ${out.needsReview.map((r) => `${r.rule} (${r.nodes})`).join(', ')}`, '');
  }
  const stops = out.focusOrder.stops;
  lines.push(`Focus order (${stops.length} of ${out.focusOrder.tabbable} tabbable, walk ended: ${out.focusOrder.end}): ${stops.slice(0, 30).map((s) => `${s.n}. \`${s.selector}\`${s.label ? ` "${s.label}"` : ''}`).join(' · ') || 'none'}`, '');
  lines.push(`Popups tested: ${out.overlays.length ? out.overlays.map((o) => `\`${o.trigger}\` ${o.result}`).join(' · ') : 'none found'}`, '');
  lines.push('Not checked by this script, a human must: a screen-reader pass, whether alt text and labels are meaningful, whether reading and focus order make sense. See reference.md.');
  return lines.join('\n');
}

main().catch((e) => {
  console.error(`audit failed: ${e.message.split('\n')[0]}`);
  process.exitCode = 3;
});
