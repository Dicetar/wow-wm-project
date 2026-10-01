Status: PARTIAL
Last verified: 2026-09-24
Verified by: Codex
Doc type: implementation handoff

# Rebuild Implementation Status

## Implemented and Tested

- The DLL guard hashes the runtime DLL with .NET SHA-256 in child PowerShell, without relying on `Get-FileHash`. Its regression test passes.
- Automatic generation now receives the configured runtime settings and carries character profile, active memory, recent events, native snapshot, and missing-data flags into the model request. Forgotten notes and other-character packs are excluded. Missing character or memory evidence defers generation and preserves the source event for retry.
- Direct-chat context uses the same runtime DB settings, includes filtered active memory, and redacts raw database errors. Both chat voice and automatic generation prefer that filtered memory over older steering fields, so suppressed or forgotten notes do not re-enter through those fields. Presence and ambient perception require a recent database-clock heartbeat; stale location and counts are not presented as live facts.
- A narrow native-action ledger pilot exists in `wm.autoplay.durable_native`, with parameterized PyMySQL transactions and world-DB schema `sql/bootstrap/wm_director_request.sql`. The event-origin `world_announce_to_player` auto intent can use it when `durable_native_intent_enabled=true`. The default is **false**. The pilot records dispatch before effect, fences stale transitions, reconciles native receipts, and never blindly resubmits after an ambiguous result. Unit tests cover duplicate delivery, restart, uncertain submission, and fail-closed DB access.
- Confirmed single-action intents now keep their pending record until `_apply_compiled` reports an applied effect. Failed or interrupted attempts remain inspectable instead of being cleared before execution.

## Not Proven or Released

- An unverified write-path guard now keeps inactive conversation-steering rows unchanged when a later journey/model upsert reuses their key. `pin` may reactivate a suppressed note but refuses a forgotten note; the dedicated forget action remains the only way to set the redaction marker. Conversation extraction now reads back the row before reporting success and journals only the note key/kind, not its body. The generic journey applier can still report overall success when a guarded duplicate upsert makes no change.
- Newly generated automatic drafts carry a hash of the full active/excluded memory snapshot. Before apply, a changed or unavailable memory snapshot parks the draft; old automatic drafts without the hash are also parked. This is a pre-apply check, not a transaction spanning memory and world effects, so a concurrent edit between the check and the effect remains possible.
- `forget` removes the active steering body, **not** all historical copies: chat event rows, older chat/memory journals, stored drafts, and model/runtime traces may still retain the original text. Re-extraction under a different model-generated key may also recreate a semantically similar note. Do not represent this action as full data erasure yet.
- No tests or live DB check were run for the current memory/revision changes under the user's current no-test instruction.
- The new SQL has **not** been applied to BridgeLab. MySQL/SOAP were unreachable in the latest doctor check. No real MySQL multi-process test, native receipt test, or in-client outcome proof has been run. Keep the pilot flag off until backup/restore, migration, scoped live test, and recovery drill pass.
- The opt-in pilot handles one auto verb from an event. Direct chat without a source-event token, confirmation actions, scene steps, generated content publication, rewards, and world mutations still use legacy paths. The legacy JSON status/pending files are not a transactional director store; pending confirmations still expire after their TTL and scene confirmation still clears before multi-step apply.
- The chat-event loop can still consume a source event after a successful text reply while a later intent fails. Reply and action need one durable logical request before pilot cutover. Do not interpret the present pilot as an end-to-end exactly-once chat workflow.
- M1 is partial. M2-M5 (reviewed personal arc, distinctive powers, shared-world transitions, full-session release) have not been implemented by this packet. No player-facing quality claim follows from these unit tests.

## Next Verification and Work

1. Back up BridgeLab data and rehearse restore to an isolated target. Confirm explicit character scope and the configured DB profile. Apply the additive SQL in a test world database.
2. Run real two-process tests: duplicate origin, stale transition, crash before/after native submission, late completion, and mismatched proposal. Observe the native queue's deduplication and expiry before enabling the pilot flag.
3. Make chat reply and intent share one durable event receipt, with persisted output/continuation across retries. Add client-generated tokens for direct commands and recover pending confirmations before clearing them.
4. Continue M1 with note revision/suppression, native snapshot correlation, multi-character fairness, pacing, and capability evidence. Then prove one reviewed personal arc through an actual client session before expanding content vocabulary.

Do not delete durable ledger or native request records under the five-latest disposable-log policy. Run logs and diagnostic bundles are a separate retention class.
