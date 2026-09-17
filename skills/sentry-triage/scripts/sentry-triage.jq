# sentry-triage.jq — turn the raw Sentry issue list and the per-issue latest-event
# extracts (slurped into one array) into the rendered report.
#
# Inputs (--arg / --argjson): $org, $project, $env, $period, $query,
#   $format (md|slack), $mode (list|detail), $title_width.

def level_weight:
  {fatal: 2, error: 1, warning: 0.5, info: 0.2, debug: 0.2}[.] // 1;

def status_weight:
  {escalating: 1.5, regressed: 1.3, new: 1.2, ongoing: 1}[.] // 1;

# Users dominate: 100 events from one user is one broken session, 20 events from
# 20 users is a bug. Fatal, unhandled, escalating or regressed each push it up.
def score:
  ((.userCount * 10 + (.count | tonumber))
   * (.level | level_weight)
   * (if .isUnhandled then 1.5 else 1 end)
   * (.substatus | status_weight))
  | round;

def severity:
  if . >= 400 then "critical" elif . >= 150 then "high" elif . >= 40 then "medium" else "low" end;

# Last third of the period against the third before it, from the daily series.
def trend:
  (.stats | to_entries | first | .value | map(.[1])) as $s
  | ($s | length) as $n
  | if $n < 3 then "→" else
      (($n / 3) | floor) as $w
      | ($s[($n - $w):] | add) as $recent
      | ($s[($n - 2 * $w):($n - $w)] | add) as $before
      | if $recent >= 5 and $recent > $before * 1.5 then "↑"
        elif $before >= 5 and $recent < $before * 0.5 then "↓"
        else "→" end
    end;

def days_since: ((now - (. | sub("\\.[0-9]+"; "") | fromdate)) / 86400 | floor);

def short_path:
  sub("^.*node_modules/"; "") | sub("^webpack://[^/]*/"; "") | sub("^\\./"; "") | sub("^(\\.\\./)+"; "")
  | split("/") | if length > 3 then .[-3:] else . end | join("/");

def is_code_file: test("\\.(m?[jt]sx?|vue|svelte|py|go|rb|java|kt|php|cs|dart|swift)\\b");

# Frames are outermost first; the innermost in-app frame is where the fix lives.
def innermost_app_frame: [.frames[]? | select(.inApp and (.filename | is_code_file))] | last;
def innermost_code_frame: [.frames[]? | select(.filename | is_code_file)] | last;

def where:
  (innermost_app_frame // innermost_code_frame) as $f
  | if $f == null then (.metadata.filename // "" | if is_code_file then short_path else "-" end)
    else ($f.filename | short_path) + (if $f.line then ":\($f.line)" else "" end)
         + (if $f.function != "" and $f.function != "?" then " \($f.function)" else "" end)
    end;

def text: [.title, .metadata.value, .value] | map(select(. != null)) | join(" ");

def is_network:
  test("API Error|ApiClientError|Failed to fetch|NetworkError|Network request failed|Load failed|status code [45][0-9]{2}|\\b(401|403|404|429|5[0-9]{2})\\b|timed? ?out|ECONN|AxiosError"; "i");

def is_browser:
  test("CustomEvent|\\[object (Event|HTML[A-Za-z]*Element)\\]|Loading (CSS )?chunk|ChunkLoadError|Failed to load script|Failed to load (module|resource)|dynamically imported module|Script error|ResizeObserver|Non-Error (promise rejection|exception)|Federation Runtime"; "i");

def vendor_package:
  (.metadata.filename // "") as $m
  | ([.frames[]? | .filename] + [$m]) | map(select(test("node_modules/")))
  | map(capture("node_modules/(?:\\.pnpm/)?(?<pkg>@[^/]+/[^/@]+|[^/@]+)") | .pkg) | last // null;

def origin:
  if (text | is_browser) then "browser"
  elif (text | is_network) then "network"
  elif innermost_app_frame != null then "app"
  elif vendor_package != null then "vendor"
  else "app" end;

# Issues sharing one root cause: same API status, same third-party package, same
# browser-level message, or the same in-app file.
def cluster:
  origin as $o
  | if $o == "network" then "network / " + (text | (capture("(?<c>(API Error|status code)[: ]*[0-9]{3}|Failed to fetch|NetworkError|Load failed|timed? ?out)"; "i") | .c) // (.title | .[:40]))
    elif $o == "vendor" then "vendor / " + vendor_package
    elif $o == "browser" then "browser / " + (text | (capture("(?<c>CustomEvent|\\[object [A-Za-z]+\\]|Loading (CSS )?chunk|ChunkLoadError|Failed to load script|dynamically imported module|Script error|ResizeObserver|Non-Error [a-z ]+|Federation Runtime)"; "i") | .c) // (.title | .[:40]))
    else "app / " + (innermost_app_frame as $f | if $f then ($f.filename | short_path) else (.title | .[:40]) end)
    end;

def truncate($n): if length > $n then .[:$n - 1] + "…" else . end;
def clean: gsub("[|\n\r]"; " ") | gsub(" +"; " ");

def enrich:
  . + {
    score: score,
    sev: (score | severity),
    trend: trend,
    origin: origin,
    where: where,
    cluster: cluster,
    age: (.firstSeen | days_since),
    last: (.lastSeen | days_since)
  };

def header_text:
  "Sentry triage · \($org)/\($project)" + (if $env != "" then " · \($env)" else "" end)
  + " · \($period) · \($query) · \(length) issues";

def issue_link:
  if $format == "slack" then "<\(.permalink)|\(.shortId)>" else "[\(.shortId)](\(.permalink))" end;

def row_md:
  "| \(issue_link) | \(.sev) | \(.score) | \(.userCount) | \(.count) | \(.trend) | \(.substatus) | \(.origin) | \(.where | clean | truncate(48)) | \(.title | clean | truncate($title_width)) |";

def row_slack:
  "• \(issue_link) · \(.sev) \(.score) · \(.userCount) users · \(.count) events \(.trend) · \(.substatus) · \(.origin) · `\(.where | clean | truncate(48))` · \(.title | clean | truncate($title_width))";

def clusters:
  group_by(.cluster) | map({
      cluster: .[0].cluster, n: length,
      users: (map(.userCount) | add), events: (map(.count | tonumber) | add),
      score: (map(.score) | add), ids: (map(.shortId) | join(", "))
    })
  | map(select(.n > 1)) | sort_by(-.score);

def cluster_lines:
  if length == 0 then empty else
    "", (if $format == "slack" then "*Clusters (one root cause, fix once)*" else "Clusters (one root cause, fix once):" end),
    (.[] | (if $format == "slack" then "• " else "- " end)
           + "\(.cluster) — \(.n) issues · \(.users) users · \(.events) events · score \(.score) · \(.ids)")
  end;

def render_list:
  (map(select(.shortId != null))) as $issues
  | (map(select(.shortId == null and .id != null)) | map({(.id): .}) | add // {}) as $frames
  | ($issues | map(. + ($frames[.id] // {frames: [], value: null}) | enrich) | sort_by(-.score, -.userCount)) as $rows
  | if ($rows | length) == 0 then
      (if $format == "slack" then "*" + ($rows | header_text) + "*" else ($rows | header_text) end), "no issues"
    else
      if $format == "slack" then
        "*" + ($rows | header_text) + "*",
        ($rows[] | row_slack),
        ($rows | clusters | cluster_lines)
      else
        ($rows | header_text),
        "",
        "| Issue | Sev | Score | Users | Events | Trend | Status | Origin | Where | Title |",
        "|---|---|---|---|---|---|---|---|---|---|",
        ($rows[] | row_md),
        ($rows | clusters | cluster_lines)
      end
    end;

def render_detail:
  (.[0] + .[1] | enrich) as $i
  | (.[2].tags // []) as $tags
  | "\($i.shortId) · \($i.sev) \($i.score) · \($i.origin) · \($i.permalink)",
    "\($i.title | clean)",
    (if $i.value then "value: \($i.value | clean | truncate(200))" else empty end),
    "users \($i.userCount) · events \($i.count) \($i.trend) · \($i.substatus) · level \($i.level) · unhandled \($i.isUnhandled) · first \($i.firstSeen[:10]) (\($i.age)d) · last \($i.lastSeen[:10]) (\($i.last)d) · latest release \($i.release // "-")",
    "",
    "Frames, innermost first:",
    (if ($i.frames | length) == 0 then "  (no stack trace on the latest event)"
     else ($i.frames | reverse | .[:12][] | "  \(.filename | short_path)" + (if .line then ":\(.line)" else "" end) + " \(.function)" + (if .inApp then "  [app]" else "" end))
     end),
    "",
    "Tags:",
    ($tags[] | "  \(.key): " + ([.topValues[:5][] | "\(.value | clean | truncate(40)) (\(.count))"] | join(", ")) + (if .totalValues > (([.topValues[:5][] | .count] | add) // 0) then " · \(.totalValues) total" else "" end)),
    "",
    "Daily events:",
    "  " + ($i.stats | to_entries | first | .value | map("\(.[1])") | join(" "));

if $mode == "detail" then render_detail else render_list end
