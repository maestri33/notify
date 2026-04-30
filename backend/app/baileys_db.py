"""Direct read access to the shared Baileys SQLite database.

The database is owned by the Node.js sidecar (writes) but both processes
share the same WAL-mode file for reads.  Python only reads — all writes
go through the sidecar.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Optional

from app.config import settings

# Override via env if needed; default sits next to the main notify.db
BAILEYS_DB_PATH = getattr(settings, "baileys_db_path", "/var/lib/notify/baileys.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(BAILEYS_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ── Contacts ────────────────────────────────────────────────────────────────

@dataclass
class BaileysContact:
    jid: str
    name: Optional[str]
    notify: Optional[str]
    verified_name: Optional[str]
    is_whatsapp_user: bool
    updated_at: str


def get_contact(jid: str) -> BaileysContact | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM baileys_contacts WHERE jid = ?", (jid,)
        ).fetchone()
    return _to_contact(row) if row else None


def list_contacts(limit: int = 100, offset: int = 0) -> list[BaileysContact]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM baileys_contacts ORDER BY notify, name LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_to_contact(r) for r in rows]


def search_contacts(query: str, limit: int = 50, offset: int = 0) -> list[BaileysContact]:
    q = f"%{query}%"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM baileys_contacts "
            "WHERE name LIKE ? OR notify LIKE ? OR jid LIKE ? "
            "ORDER BY notify, name LIMIT ? OFFSET ?",
            (q, q, q, limit, offset),
        ).fetchall()
    return [_to_contact(r) for r in rows]


def count_contacts() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM baileys_contacts").fetchone()[0]


def _to_contact(row: sqlite3.Row) -> BaileysContact:
    return BaileysContact(
        jid=row["jid"],
        name=row["name"],
        notify=row["notify"],
        verified_name=row["verified_name"],
        is_whatsapp_user=bool(row["is_whatsapp_user"]),
        updated_at=row["updated_at"],
    )


# ── Messages ────────────────────────────────────────────────────────────────

@dataclass
class BaileysMessage:
    id: str
    remote_jid: str
    from_me: bool
    body: Optional[str]
    timestamp: Optional[int]
    message_json: str  # full Baileys proto.Message as JSON
    created_at: str  # added by our DB layer

    def parsed(self) -> dict:
        return json.loads(self.message_json)


def get_message(msg_id: str) -> BaileysMessage | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM baileys_messages WHERE id = ?", (msg_id,)
        ).fetchone()
    return _to_message(row) if row else None


def list_messages(jid: str, limit: int = 50, offset: int = 0) -> list[BaileysMessage]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM baileys_messages "
            "WHERE remote_jid = ? "
            "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (jid, limit, offset),
        ).fetchall()
    return [_to_message(r) for r in rows]


def recent_messages(limit: int = 50) -> list[BaileysMessage]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM baileys_messages ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_to_message(r) for r in rows]


def count_messages() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM baileys_messages").fetchone()[0]


def _to_message(row: sqlite3.Row) -> BaileysMessage:
    return BaileysMessage(
        id=row["id"],
        remote_jid=row["remote_jid"],
        from_me=bool(row["from_me"]),
        body=row["body"],
        timestamp=row["timestamp"],
        message_json=row["message_json"],
        created_at=row["created_at"],
    )

def batch_get_contacts(jids: list[str]) -> dict[str, BaileysContact]:
    """Return contacts keyed by JID (empty dict for an empty list)."""
    if not jids:
        return {}
    with _connect() as conn:
        placeholders = ",".join("?" for _ in jids)
        rows = conn.execute(
            f"SELECT * FROM baileys_contacts WHERE jid IN ({placeholders})",
            jids,
        ).fetchall()
    return {r["jid"]: _to_contact(r) for r in rows}

def get_pushnames_for_group(group_jid: str) -> dict[str, str]:
    """Extract participant -> pushName from message history for a group."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT message_json FROM baileys_messages WHERE remote_jid = ?",
            (group_jid,),
        ).fetchall()
    import json as _json
    names: dict[str, str] = {}
    for (msg_json,) in rows:
        try:
            msg = _json.loads(msg_json)
        except _json.JSONDecodeError:
            continue
        pn = msg.get("pushName")
        participant = (msg.get("key", {}) or {}).get("participant")
        if pn and participant and participant not in names:
            names[participant] = pn
    return names
