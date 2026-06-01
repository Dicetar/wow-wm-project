"""Autonomous World Master loop (Phase 6).

Decide -> govern -> act -> record. WM wakes on its own cadence, assembles a
per-character decision context, selects a move from a pre-validated candidate
set, applies it within the autonomy governor (no per-action human confirm, full
audit + rollback), and records the outcome.

Everything mutating still flows through the existing typed-action / validate /
policy-gate / apply / audit pipeline; the governor is an *additional* budget and
risk chokepoint layered on top, never a bypass of it.
"""
