---
name: wm-harness-task
description: Use when implementing a bounded WM harness or director ticket, or handing one to a local coding agent. Keeps one-task scope, existing ownership, proof levels, and runtime versus development authority explicit.
---

# WM Harness Task

This is a coding-agent workflow, not permission for runtime WM to edit code or live data. The [harness research](../../../docs/plans/wm-harness-2026-09-30/README.md) is proposed design, not an installed tool catalog.

## One Work Card

Before edits, identify:

- One observable outcome and the owning files/symbols.
- Current baseline and user-owned changes to preserve.
- Inputs, outputs, and behavior that must not change.
- One normal case, one failure case, and a stop condition.
- Which checks and live operations the user actually authorized.

Read the project routers, then only the ticket's relevant references. For this research plan, start with the assigned H0-H9 package in [delivery plan](../../../docs/plans/wm-harness-2026-09-30/DELIVERY_PLAN.md). Do not execute the entire roadmap.

## Work

1. Inspect the real implementation. A named tool or proposed API in a document may not exist.
2. Explain the smallest cohesive edit, then implement within its owner.
3. Keep model choice separate from deterministic validation/authorization/execution. Reuse the existing bus and publishers.
4. Preserve effect identity across retries. An uncertain effect needs reconciliation, not a new request key.
5. Use authorized checks only. Never bypass a failing check or label unrun checks passed.
6. Stop at the task boundary. Report changed files, actual evidence, remaining blocker, and next permitted action.

For generated content, load `wm-content-release` and required fields. For live work, load `wm-live-bridge-lab`. Do not invent SQL/GM/shell escape hatches or install a framework as a workaround for missing mechanics.

## When Stuck

Missing facts: name the exact missing fact. Missing capability: write a concrete development task using [local-agent contract](../../../docs/plans/wm-harness-2026-09-30/LOCAL_AGENT_CONTRACT.md), without claiming the proposed task exporter exists. Conflicting local edits: preserve them and clarify ownership. After three failed attempts on the same approach, stop and state the structural cause.

Use `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN` with the applicable proof boundary. A successful enqueue or compiler invocation is not player-visible gameplay proof.
