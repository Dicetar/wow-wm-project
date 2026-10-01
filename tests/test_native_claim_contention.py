"""Controlled DB proof for the native queue's pending-to-claimed token fence."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import pytest


@pytest.mark.db_integration
def test_only_one_contender_owns_a_pending_native_claim():
    import pymysql

    def connect():
        return pymysql.connect(
            host=os.environ["WM_TEST_DB_HOST"],
            port=int(os.environ.get("WM_TEST_DB_PORT", "33307")),
            user=os.environ.get("WM_TEST_DB_USER", "acore"),
            password=os.environ.get("WM_TEST_DB_PASSWORD", "acore"),
            database=os.environ.get("WM_TEST_DB_NAME", "acore_world"),
            autocommit=True,
        )

    sequence = f"test:claim:{uuid4().hex}"
    ids = []
    conn = connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO wm_bridge_action_request "
                "(IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, ClaimToken, "
                "ClaimExpiresAt, SequenceID, SequenceOrder, WaitForPrior) "
                "VALUES (%s, 0, 'debug_ping', '{}', 'claimed', 'blocking-prior', "
                "DATE_ADD(NOW(), INTERVAL 1 HOUR), %s, 0, 0)",
                (sequence + ":prior", sequence),
            )
            ids.append(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO wm_bridge_action_request "
                "(IdempotencyKey, PlayerGUID, ActionKind, PayloadJSON, Status, "
                "SequenceID, SequenceOrder, WaitForPrior) "
                "VALUES (%s, 0, 'debug_ping', '{}', 'pending', %s, 1, 1)",
                (sequence + ":target", sequence),
            )
            ids.append(cursor.lastrowid)
        barrier = Barrier(2)

        def claim(token):
            worker = connect()
            try:
                barrier.wait(timeout=5)
                with worker.cursor() as cursor:
                    cursor.execute(
                        "UPDATE wm_bridge_action_request SET Status='claimed', ClaimedAt=NOW(), "
                        "ClaimToken=%s, ClaimExpiresAt=DATE_ADD(NOW(), INTERVAL 5 SECOND), "
                        "AttemptCount=AttemptCount+1 WHERE RequestID=%s AND Status='pending'",
                        (token, ids[1]),
                    )
                    updated = cursor.rowcount
                    cursor.execute(
                        "SELECT ClaimToken FROM wm_bridge_action_request "
                        "WHERE RequestID=%s AND Status='claimed' AND ClaimToken=%s",
                        (ids[1], token),
                    )
                    owns_claim = cursor.fetchone() is not None
                return updated, owns_claim
            finally:
                worker.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(claim, (uuid4().hex, uuid4().hex)))
        assert sorted(outcomes) == [(0, False), (1, True)]
        with conn.cursor() as cursor:
            cursor.execute("SELECT AttemptCount FROM wm_bridge_action_request WHERE RequestID=%s", (ids[1],))
            assert cursor.fetchone()[0] == 1
    finally:
        if ids:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM wm_bridge_action_request WHERE RequestID IN (%s,%s)", tuple(ids))
        conn.close()
