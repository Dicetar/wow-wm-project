# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- Create an issue with `gh issue create --title "..." --body "..."`.
- Read an issue with `gh issue view <number> --comments`.
- List issues with `gh issue list`, using JSON and label filters when needed.
- Comment with `gh issue comment <number> --body "..."`.
- Apply or remove labels with `gh issue edit`.
- Close with `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`; `gh` does this automatically inside the clone.

## WM-generated development requests

Agreed product requirement (2026-09-14); runtime implementation is not verified.

- WM may automatically create GitHub issues when a missing capability blocks intended content, without per-issue operator confirmation.
- Detect duplicate requests and reuse the existing issue; enforce a configurable creation rate limit.
- Show the issue and its status in the operator panel.
- Include the originating intent, relevant gameplay context, missing capability, expected behavior, acceptance tests, known client/server requirements, uncertainties, and references to deferred content. Exclude credentials and unnecessary private context.
- Filing or closing an issue does not authorize deployment or prove a capability available. Implementation, verification, and capability registration must precede its use in play.

## Pull requests as a triage surface

PRs as a request surface: no.

GitHub shares one number space across issues and pull requests. Resolve an ambiguous number with `gh pr view <number>` and fall back to `gh issue view <number>`.

## Skill operations

When a skill says to publish to the issue tracker, create a GitHub issue. When it says to fetch a ticket, use `gh issue view <number> --comments`.

## Wayfinding operations

- Map: one issue labelled `wayfinder:map`, containing destination, notes, decisions, fog, and out-of-scope sections.
- Child ticket: GitHub sub-issue labelled `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- Fallback: if sub-issues are unavailable, add children to the map task list and put `Part of #<map>` in each child body.
- Blocking: use native issue dependencies. The blocker value is the blocker's numeric database id, not its issue number or node id.
- Fallback blocking: put `Blocked by: #<number>` at the top of the child body.
- Frontier: open, unblocked, unassigned child issues in map order.
- Claim: `gh issue edit <number> --add-assignee @me` before work.
- Resolve: comment with the decision, close the ticket, then append its linked gist to the map's Decisions-so-far section.
