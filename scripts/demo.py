"""QuoteMate PS05 in-process demo script.

Replays sample_data/events.json against a FastAPI TestClient backed by a tmp
SQLite database, then diffs actual responses against sample_data/expected_outputs.json.
Exits non-zero on any mismatch so it can be wired into pytest/CI.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.services.catalogue_service import catalogue_service  # noqa: E402

EVENTS_PATH = ROOT / "sample_data" / "events.json"
EXPECTED_PATH = ROOT / "sample_data" / "expected_outputs.json"


def _make_test_engine():
    """Create an isolated tmp SQLite engine with FK enforcement."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="quotemate-demo-"))
    db_file = tmp_dir / "demo.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    Base.metadata.create_all(bind=engine)
    return engine


def _override_get_db(engine):
    """Return a dependency override that yields sessions bound to *engine*."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    return _get_db


def _seed(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        catalogue_service.seed_catalogue_if_empty(db=db)
    finally:
        db.close()


def _check_contains(haystack: str, needles):
    """Case-insensitive substring check for all needles in haystack."""
    lower = haystack.lower()
    missing = [n for n in needles if n.lower() not in lower]
    return missing


def run_demo():
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))["events"]
    expected_list = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["expected"]
    expected_by_key = {
        (e["event_id"], e["message_id"]): e for e in expected_list
    }

    engine = _make_test_engine()
    app.dependency_overrides[get_db] = _override_get_db(engine)
    _seed(engine)

    client = TestClient(app)

    failures = []
    total_checks = 0

    # Build expected lookup: (event_id, message_index_within_event) -> expected
    expected_by_key = {}
    for exp in expected_list:
        key = (exp["event_id"], exp.get("_msg_index", 0))
        expected_by_key[key] = exp

    for evt in events:
        sender_id = evt["sender_id"]
        for msg_index, msg in enumerate(evt["messages"]):
            mid = msg["message_id"]
            key = (evt["id"], msg_index)
            exp = expected_by_key.get(key, {})
            expected_status = exp.get("expected_status", 200)

            total_checks += 1

            # Invalid input cases expect a non-200 status (no response body to diff)
            if expected_status != 200:
                resp = client.post(
                    "/messages",
                    json={
                        "message_id": mid,
                        "sender_id": sender_id,
                        "text": msg["text"],
                        "timestamp": msg["timestamp"],
                    },
                )
                if resp.status_code != expected_status:
                    failures.append(
                        f"[{evt['id']}/{mid}] expected status {expected_status}, "
                        f"got {resp.status_code}: {resp.text}"
                    )
                continue

            resp = client.post(
                "/messages",
                json={
                    "message_id": mid,
                    "sender_id": sender_id,
                    "text": msg["text"],
                    "timestamp": msg["timestamp"],
                },
            )

            if resp.status_code != 200:
                failures.append(
                    f"[{evt['id']}/{mid}] expected 200, got {resp.status_code}: "
                    f"{resp.text}"
                )
                continue

            body = resp.json()

            # --- intent ---
            exp_intent = exp.get("expected_intent")
            if exp_intent is not None:
                actual = body.get("intent")
                if isinstance(exp_intent, (list, tuple)):
                    if actual not in exp_intent:
                        failures.append(
                            f"[{evt['id']}/{mid}] intent expected one of "
                            f"{exp_intent}, got {actual}"
                        )
                elif actual != exp_intent:
                    failures.append(
                        f"[{evt['id']}/{mid}] intent expected {exp_intent}, "
                        f"got {actual}"
                    )

            # --- needs_clarification ---
            exp_clar = exp.get("expected_needs_clarification")
            if exp_clar is not None:
                actual = body.get("needs_clarification")
                if actual != exp_clar:
                    failures.append(
                        f"[{evt['id']}/{mid}] needs_clarification expected "
                        f"{exp_clar}, got {actual}"
                    )

            # --- is_unsupported ---
            exp_unsup = exp.get("expected_is_unsupported")
            if exp_unsup is not None:
                actual = body.get("is_unsupported")
                if actual != exp_unsup:
                    failures.append(
                        f"[{evt['id']}/{mid}] is_unsupported expected {exp_unsup}, "
                        f"got {actual}"
                    )

            # --- duplicated ---
            exp_dup = exp.get("expected_duplicated")
            if exp_dup is not None:
                actual = body.get("duplicated")
                if actual != exp_dup:
                    failures.append(
                        f"[{evt['id']}/{mid}] duplicated expected {exp_dup}, "
                        f"got {actual}"
                    )

            # --- reply_contains keywords ---
            reply_text = body.get("reply_text", "") or ""
            needles = exp.get("reply_contains", [])
            missing = _check_contains(reply_text, needles)
            if missing:
                failures.append(
                    f"[{evt['id']}/{mid}] reply missing keywords {missing}; "
                    f"reply_text={reply_text!r}"
                )

            # --- cart_should_contain product IDs ---
            cart = body.get("cart") or {}
            cart_items = [i.get("product_id", "") for i in cart.get("items", [])]
            for pid in exp.get("cart_should_contain", []):
                if pid not in cart_items:
                    failures.append(
                        f"[{evt['id']}/{mid}] cart expected to contain {pid}, "
                        f"got {cart_items}"
                    )

            # --- reply must NOT contain (e.g. no enquiry ID before confirmation) ---
            for needle in exp.get("reply_not_contains", []):
                if needle.lower() in reply_text.lower():
                    failures.append(
                        f"[{evt['id']}/{mid}] reply must not contain {needle!r}; "
                        f"reply_text={reply_text!r}"
                    )

            # --- enquiry_id absent (Requirement 7: no ID before confirmation) ---
            if exp.get("expected_enquiry_id_absent") is True:
                if body.get("enquiry_id"):
                    failures.append(
                        f"[{evt['id']}/{mid}] expected no enquiry_id, "
                        f"got {body.get('enquiry_id')!r}"
                    )

            # --- enquiry_id matches regex (random ID verified by pattern) ---
            enq_pattern = exp.get("enquiry_id_matches_regex")
            if enq_pattern is not None:
                enq = body.get("enquiry_id")
                if not enq or not re.search(enq_pattern, str(enq)):
                    failures.append(
                        f"[{evt['id']}/{mid}] enquiry_id {enq!r} does not match "
                        f"pattern {enq_pattern!r}"
                    )

    app.dependency_overrides.clear()
    engine.dispose()

    print("\n=== QuoteMate Demo Results ===")
    print(f"Total checks: {total_checks}")
    print(f"Failures: {len(failures)}")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())