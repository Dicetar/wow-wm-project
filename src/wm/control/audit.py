from __future__ import annotations

import argparse
import json
from typing import Any

from wm.config import Settings
from wm.control.store import ControlAuditRecord
from wm.control.store import ControlAuditStore
from wm.control.summary import execution_status
from wm.control.summary import format_native_request_summary
from wm.control.summary import native_request_refs_from_results
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import WMEvent
from wm.events.store import EventStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect WM control proposal audit rows.")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--source-event-id", type=int)
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    audit_store = ControlAuditStore(client=client, settings=settings)
    event_store = EventStore(client=client, settings=settings)

    if args.idempotency_key:
        record = audit_store.get_record(idempotency_key=args.idempotency_key)
        records = [record] if record is not None else []
        exact_lookup = True
    else:
        records = audit_store.list_records(
            source_event_id=args.source_event_id,
            player_guid=args.player_guid,
            limit=args.limit,
        )
        exact_lookup = False

    payloads = [_audit_payload(record=record, event_store=event_store) for record in records]
    if args.summary:
        _print_summary(payloads)
    else:
        print(json.dumps({"count": len(payloads), "records": payloads}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payloads or not exact_lookup else 1


def _audit_payload(*, record: ControlAuditRecord, event_store: EventStore) -> dict[str, Any]:
    source_event = _load_source_event(record=record, event_store=event_store)
    payload = record.to_dict()
    payload["source_event"] = source_event.to_dict() if source_event is not None else None
    payload["native_requests"] = native_request_refs_from_results(record.apply, record.dry_run)
    return payload


def _load_source_event(*, record: ControlAuditRecord, event_store: EventStore) -> WMEvent | None:
    if record.source_event_id is not None:
        return event_store.get_event(event_id=record.source_event_id)
    raw_source_event = record.raw_proposal.get("source_event")
    if not isinstance(raw_source_event, dict):
        return None
    source = raw_source_event.get("source")
    source_event_key = raw_source_event.get("source_event_key")
    if source in (None, "") or source_event_key in (None, ""):
        return None
    return event_store.get_event_by_source_key(source=str(source), source_event_key=str(source_event_key))


def _print_summary(payloads: list[dict[str, Any]]) -> None:
    print(f"count={len(payloads)}")
    for payload in payloads:
        validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
        issues = validation.get("issues") if isinstance(validation.get("issues"), list) else []
        print(
            f"proposal_id={payload.get('proposal_id')} status={payload.get('status')} "
            f"player_guid={payload.get('player_guid')} source_event_id={payload.get('source_event_id')} "
            f"recipe={payload.get('selected_recipe')} action={payload.get('action_kind')} "
            f"idempotency_key={payload.get('idempotency_key')}"
        )
        print(
            f"validation_ok={validation.get('ok')} validation_issues={len(issues)} "
            f"dry_run_status={execution_status(payload.get('dry_run'))} "
            f"apply_status={execution_status(payload.get('apply'))}"
        )
        source_event = payload.get("source_event")
        if isinstance(source_event, dict):
            print(
                f"source_event id={source_event.get('event_id')} type={source_event.get('event_type')} "
                f"source={source_event.get('source')} key={source_event.get('source_event_key')} "
                f"occurred_at={source_event.get('occurred_at')}"
            )
        elif payload.get("source_event_id") is not None:
            print(f"source_event id={payload.get('source_event_id')} status=missing")
        native_requests = payload.get("native_requests") if isinstance(payload.get("native_requests"), list) else []
        for ref in native_requests:
            if isinstance(ref, dict):
                print(format_native_request_summary(ref))


if __name__ == "__main__":
    raise SystemExit(main())
