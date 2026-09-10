# pr-todo.jq — turn the raw GraphQL PullRequest nodes (one role stamped per node,
# slurped into one array) into the rendered report.
#
# Inputs (--arg / --argjson): $user, $org, $format (md|slack), $title_width.

def failing_conclusion: ["FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"];

# Names of the CI checks that failed on the head commit (CheckRun and legacy StatusContext).
def failed_checks:
  [ (.commits.nodes[0].commit.statusCheckRollup.contexts.nodes // [])[]
    | if .__typename == "CheckRun" then
        select(.conclusion as $c | failing_conclusion | index($c)) | .name
      else
        select(.state == "FAILURE" or .state == "ERROR") | .context
      end
  ] | unique;

def rollup_state: .commits.nodes[0].commit.statusCheckRollup.state // "NONE";

# Reviewers still requested (users by login, teams by slug). Bots (renovate[bot],
# renovate[bot], ...) are dropped: their approval is automatic, never a to-do.
def pending_reviewers:
  [ (.reviewRequests.nodes // [])[] | .requestedReviewer | select(. != null)
    | if .__typename == "Team" then .slug else .login end
    | select(test("bot(\\[bot\\])?$"; "i") | not) ];

# The reported user's own request reads "you": on a re-requested review it is
# their earlier verdict, not someone else's.
def changes_requesters:
  [ (.latestOpinionatedReviews.nodes // [])[] | select(.state == "CHANGES_REQUESTED") | .author.login
    | if . == $user then "you" else . end ];

def unresolved_threads: [ (.reviewThreads.nodes // [])[] | select(.isResolved == false) ] | length;

# Cap a name list to 3 items, "+N" for the rest.
def cap3: if length > 3 then (.[:3] | join(", ")) + " +\(length - 3)" else join(", ") end;

# Single status token, worst first.
def status:
  if .isDraft then "draft"
  elif .mergeable == "CONFLICTING" or .mergeStateStatus == "DIRTY" then "conflict"
  elif (failed_checks | length) > 0 or .mergeStateStatus == "UNSTABLE" then "ci-failing"
  elif .mergeStateStatus == "BEHIND" then "behind"
  elif .mergeStateStatus == "BLOCKED" then "blocked"
  elif .mergeStateStatus == "CLEAN" or .mergeStateStatus == "HAS_HOOKS" then "ready"
  else "unknown" end;

# Every concrete reason the PR is stuck. The reported user's own pending review
# is not listed: the "reviewer" role already says it.
def blockers:
  . as $pr
  | (pending_reviewers) as $pending
  | (failed_checks) as $failed
  | [
      (if .mergeable == "CONFLICTING" or .mergeStateStatus == "DIRTY" then "conflicts" else empty end),
      (if ($failed | length) > 0 then "ci: " + ($failed | cap3)
       elif (rollup_state == "PENDING" or rollup_state == "EXPECTED") then "ci: pending"
       else empty end),
      (if (changes_requesters | length) > 0 then "changes requested: " + (changes_requesters | cap3) else empty end),
      (if unresolved_threads > 0 then "\(unresolved_threads) unresolved thread\(if unresolved_threads > 1 then "s" else "" end)"
       else empty end),
      (($pending | map(select(. != $user))) as $others
       | if ($others | length) > 0 then "awaiting review: " + ($others | cap3) else empty end),
      (if .reviewDecision == "REVIEW_REQUIRED" and ($pending | length) == 0 and (changes_requesters | length) == 0
       then "review required" else empty end),
      (if .mergeStateStatus == "BEHIND" then "behind base" else empty end)
    ]
  # BLOCKED with no visible cause = branch protection waiting for an approval
  # (CODEOWNERS): GitHub exposes no reviewDecision for that rule. A draft is
  # BLOCKED by its draft state alone, which the status column already says.
  | if length == 0 and $pr.mergeStateStatus == "BLOCKED" and ($pr.isDraft | not) then ["needs approval"] else . end;

def repo_short: .repository.nameWithOwner | split("/")[1];
def pr_ref: "\(repo_short)#\(.number)";
def age_days: ((now - (.updatedAt | fromdateiso8601)) / 86400 | floor);
def clean_title: .title | gsub("[|\n\r]"; " ") | if length > $title_width then .[:($title_width - 1)] + "…" else . end;

# Own PRs (author / assignee) first: unblocking them is the developer's job;
# reviews owed to others come next.
def role_rank: if (.roles | index("author")) or (.roles | index("assignee")) then 0 else 1 end;

# "reviewer" when the user is requested directly, "reviewer(team)" when the
# search matched through a team the user belongs to.
def role_label($pr):
  if . == "reviewer" then (if ($pr | pending_reviewers | index($user)) then "reviewer" else "reviewer(team)" end) else . end;

# --- join mergeability onto search nodes, merge roles per PR --------------------
# Search nodes carry a role; mergeability records carry only id + merge fields.
( ( map(select(.role == null)) | map({(.id): {mergeable, mergeStateStatus}}) | add // {} ) as $merge
  | map(select(.role != null))
  | group_by(.url)
  | map( (.[0]) + ($merge[.[0].id] // {})
         + { roles: (map(.role) | unique | sort_by(if . == "author" then 0 elif . == "assignee" then 1 else 2 end)) } )
  | map(. + { roles: (. as $pr | .roles | map(role_label($pr))) })
  | map(. + { status: status, blockers: blockers, age: age_days, ref: pr_ref, ttl: clean_title })
  | sort_by([role_rank, .age * -1])
) as $prs
| ($prs | length) as $n
| (now | strftime("%Y-%m-%d")) as $today
| if $format == "slack" then
    "*PR to-do · @\($user) · \($org) · \($today) · \($n)*",
    (if $n == 0 then "nothing to do" else
      $prs[] | "• <\(.url)|\(.ref)> · \(.roles | join(",")) · \(.status) · \(if (.blockers | length) > 0 then (.blockers | join("; ")) else "-" end) · \(.age)d · \(.ttl)"
    end)
  else
    "PR to-do · @\($user) · \($org) · \($today) · \($n)",
    "",
    (if $n == 0 then "nothing to do" else
      "| PR | Role | Status | Blockers | Age | Title |",
      "|---|---|---|---|---|---|",
      ($prs[] | "| [\(.ref)](\(.url)) | \(.roles | join(",")) | \(.status) | \(if (.blockers | length) > 0 then (.blockers | join("; ")) else "-" end) | \(.age)d | \(.ttl) |")
    end)
  end
