"""SQLite profile store. Facts are append-only: nothing is overwritten, only superseded,
so every value on a profile can be traced to the words it came from and undone.

The phone number lives in exactly one table (contacts) and is only read to send a
human-approved reply. Everything else is keyed by the pseudonym.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS families (
  uid TEXT PRIMARY KEY, label TEXT, base_condition_area TEXT DEFAULT 'ANC_EDD', condition_area TEXT DEFAULT 'ANC_EDD',
  consent INTEGER DEFAULT 1, paused INTEGER DEFAULT 0, synthetic INTEGER DEFAULT 1, created_at TEXT,
  name TEXT, state TEXT, language TEXT, noora_program TEXT, onboarding_method TEXT, onboarding_date TEXT,
  high_risk TEXT, last_read_id INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS copilot (
  uid TEXT PRIMARY KEY, bio TEXT, reply TEXT, language TEXT, still_needed TEXT, message_id INTEGER, ts TEXT, model TEXT);
CREATE TABLE IF NOT EXISTS contacts (uid TEXT PRIMARY KEY, phone TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, direction TEXT, author TEXT, text TEXT,
  redacted_text TEXT, ts TEXT, wa_id TEXT UNIQUE, purged INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, signal TEXT, value TEXT, status TEXT, lane TEXT,
  review_status TEXT, message_id INTEGER, evidence TEXT, speaker TEXT, confidence TEXT,
  checks TEXT, reason TEXT, extractor TEXT, created_at TEXT,
  reviewed_by TEXT, reviewed_at TEXT, review_note TEXT, replaced_by INTEGER);
CREATE TABLE IF NOT EXISTS traces (id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, message_id INTEGER, ts TEXT, trace TEXT);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, uid TEXT, kind TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS golden_pending (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, fact_id INTEGER, uid TEXT, message_text TEXT,
  msg_day TEXT, signal TEXT, wrong_value TEXT, correct_value TEXT, reviewer TEXT, deidentified INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS upe_writes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, ts TEXT, message_id INTEGER, payload TEXT);
CREATE TABLE IF NOT EXISTS flags (
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, ts TEXT, kind TEXT, message_id INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, tokens_in INTEGER, tokens_out INTEGER, calls INTEGER);
CREATE TABLE IF NOT EXISTS settings_kv (k TEXT PRIMARY KEY, v TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path=None):
        self.path = str(path or settings.db_path)
        if self.path != ":memory:":
            settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._in_tx = False
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()

    # ------------------------------------------------------------ helpers
    def q(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql: str, args=()) -> int:
        with self.lock:
            cur = self.db.execute(sql, args)
            if not self._in_tx:
                self.db.commit()
            return cur.lastrowid

    def audit(self, uid: str | None, kind: str, **detail) -> None:
        """Audit entries never contain message text or phone numbers."""
        self.x("INSERT INTO audit (ts, uid, kind, detail) VALUES (?,?,?,?)", (now(), uid, kind, json.dumps(detail)))

    def get_setting(self, k: str, default: str) -> str:
        rows = self.q("SELECT v FROM settings_kv WHERE k=?", (k,))
        return rows[0]["v"] if rows else default

    def set_setting(self, k: str, v: str) -> None:
        self.x("INSERT INTO settings_kv (k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ------------------------------------------------------------ families
    def upsert_family(self, uid: str, label: str, condition_area: str = "ANC_EDD", consent: bool = True,
                      synthetic: bool = True, **details):
        self.x("""INSERT INTO families (uid, label, base_condition_area, condition_area, consent, synthetic, created_at,
                  name, state, language, noora_program, onboarding_method, onboarding_date, high_risk)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO NOTHING""",
               (uid, label, condition_area, condition_area, int(consent), int(synthetic), now(),
                details.get("name", label), details.get("state"), details.get("language"), details.get("noora_program"),
                details.get("onboarding_method"), details.get("onboarding_date"), details.get("high_risk")))

    def set_copilot(self, uid: str, bio: str, reply: str, language: str, still_needed: list, message_id, model: str):
        self.x("""INSERT INTO copilot (uid, bio, reply, language, still_needed, message_id, ts, model)
                  VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET bio=excluded.bio, reply=excluded.reply,
                  language=excluded.language, still_needed=excluded.still_needed, message_id=excluded.message_id,
                  ts=excluded.ts, model=excluded.model""",
               (uid, bio, reply, language, json.dumps(still_needed), message_id, now(), model))

    def copilot(self, uid: str) -> dict | None:
        rows = self.q("SELECT * FROM copilot WHERE uid=?", (uid,))
        if not rows:
            return None
        rows[0]["still_needed"] = json.loads(rows[0]["still_needed"] or "[]")
        return rows[0]

    def family(self, uid: str) -> dict | None:
        rows = self.q("SELECT * FROM families WHERE uid=?", (uid,))
        return rows[0] if rows else None

    def families(self) -> list[dict]:
        return self.q("SELECT * FROM families ORDER BY created_at")

    def set_contact(self, uid: str, phone: str) -> None:
        self.x("INSERT INTO contacts (uid, phone) VALUES (?,?) ON CONFLICT(uid) DO UPDATE SET phone=excluded.phone",
               (uid, phone))

    def contact(self, uid: str) -> str | None:
        rows = self.q("SELECT phone FROM contacts WHERE uid=?", (uid,))
        return rows[0]["phone"] if rows else None

    # ------------------------------------------------------------ messages
    def add_message(self, uid, direction, author, text, redacted_text, ts, wa_id=None) -> int | None:
        try:
            return self.x("""INSERT INTO messages (uid, direction, author, text, redacted_text, ts, wa_id)
                             VALUES (?,?,?,?,?,?,?)""", (uid, direction, author, text, redacted_text, ts, wa_id))
        except sqlite3.IntegrityError:
            return None  # duplicate webhook delivery: Meta retries, we process once

    def messages(self, uid: str, limit: int = 50) -> list[dict]:
        return self.q("SELECT * FROM messages WHERE uid=? ORDER BY id DESC LIMIT ?", (uid, limit))[::-1]

    def context_for(self, uid: str, before_id: int, n: int = 3) -> list[tuple[str, str]]:
        rows = self.q("""SELECT author, redacted_text FROM messages WHERE uid=? AND id<? AND purged=0
                         ORDER BY id DESC LIMIT ?""", (uid, before_id, n))[::-1]
        return [(r["author"], r["redacted_text"]) for r in rows]

    def last_inbound_ts(self, uid: str) -> str | None:
        rows = self.q("SELECT ts FROM messages WHERE uid=? AND direction='in' ORDER BY id DESC LIMIT 1", (uid,))
        return rows[0]["ts"] if rows else None

    def add_flag(self, uid: str, kind: str, message_id=None, detail: str = "") -> None:
        """Safety flags the nurse sees in the chat. Never holds message text."""
        self.x("INSERT INTO flags (uid, ts, kind, message_id, detail) VALUES (?,?,?,?,?)",
               (uid, now(), kind, message_id, detail[:200]))

    def flags(self, uid: str, limit: int = 20) -> list[dict]:
        return self.q("SELECT * FROM flags WHERE uid=? ORDER BY id DESC LIMIT ?", (uid, limit))[::-1]

    def inbound_since(self, uid: str, since_iso: str) -> list[dict]:
        return self.q("SELECT id, text, ts FROM messages WHERE uid=? AND direction='in' AND ts>=? ORDER BY id",
                      (uid, since_iso))

    def recent_extractions_all(self, minutes: int = 60) -> int:
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        return self.q("SELECT COUNT(*) n FROM traces WHERE ts>=?", (since,))[0]["n"]

    def recent_extractions(self, uid: str, minutes: int = 60) -> int:
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        return self.q("SELECT COUNT(*) n FROM traces WHERE uid=? AND ts>=?", (uid, since))[0]["n"]

    # ------------------------------------------------------------ facts
    def add_fact(self, uid, signal, value, status, lane, message_id, evidence, speaker, confidence,
                 checks, reason, extractor, review_status=None) -> int:
        return self.x("""INSERT INTO facts (uid, signal, value, status, lane, review_status, message_id, evidence,
                         speaker, confidence, checks, reason, extractor, created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (uid, signal, value, status, lane, review_status, message_id, evidence, speaker, confidence,
                       json.dumps(checks), reason, extractor, now()))

    def fact(self, fid: int) -> dict | None:
        rows = self.q("SELECT * FROM facts WHERE id=?", (fid,))
        return rows[0] if rows else None

    def active_facts(self, uid: str) -> dict[str, dict]:
        rows = self.q("SELECT * FROM facts WHERE uid=? AND status='active' ORDER BY id", (uid,))
        return {r["signal"]: r for r in rows}  # latest wins

    def profile(self, uid: str) -> dict[str, str]:
        return {k: v["value"] for k, v in self.active_facts(uid).items()}

    def supersede(self, uid: str, signal: str, new_id: int) -> None:
        self.x("UPDATE facts SET status='superseded', replaced_by=? WHERE uid=? AND signal=? AND status='active' AND id<>?",
               (new_id, uid, signal, new_id))

    def queue(self, uid: str | None = None) -> list[dict]:
        """What needs a nurse: things the AI judge couldn't decide, and clinical cases."""
        sql = """SELECT f.*, fam.label FROM facts f JOIN families fam ON fam.uid=f.uid WHERE f.status='held'"""
        args: tuple = ()
        if uid:
            sql += " AND f.uid=?"
            args = (uid,)
        return self.q(sql + " ORDER BY CASE f.lane WHEN 'clinical' THEN 0 ELSE 1 END, f.id DESC", args)

    def recompute_condition_area(self, uid: str) -> tuple[str, str]:
        """Condition area + a date is the campaign (Noora UPE). The only switch made here is
        ANC_EDD → PNC_DOB, and only when 'delivered' and a baby DOB are both on file, so the
        two always land together. Other areas (HRPW, SNCU, ...) are never changed automatically."""
        fam = self.family(uid)
        if not fam:
            return "", ""
        before, base = fam["condition_area"], fam["base_condition_area"]
        p = self.profile(uid)
        after = base
        if base == "ANC_EDD" and p.get("stage") == "delivered" and p.get("baby_dob"):
            after = "PNC_DOB"
        if after != before:
            self.x("UPDATE families SET condition_area=? WHERE uid=?", (after, uid))
            self.audit(uid, "condition_area_changed", before=before, after=after)
        return before, after

    @contextmanager
    def tx(self):
        """Group several writes into one commit, so a UPE write lands whole or not at all."""
        with self.lock:
            self._in_tx = True
            try:
                yield
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            finally:
                self._in_tx = False

    def add_upe_write(self, uid: str, message_id: int | None, payload: dict) -> int:
        return self.x("INSERT INTO upe_writes (uid, ts, message_id, payload) VALUES (?,?,?,?)",
                      (uid, now(), message_id, json.dumps(payload, ensure_ascii=False)))

    def upe_writes(self, uid: str, limit: int = 10) -> list[dict]:
        rows = self.q("SELECT * FROM upe_writes WHERE uid=? ORDER BY id DESC LIMIT ?", (uid, limit))
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    # ------------------------------------------------------------ traces
    def add_trace(self, uid: str, message_id: int, trace: dict) -> int:
        return self.x("INSERT INTO traces (uid, message_id, ts, trace) VALUES (?,?,?,?)",
                      (uid, message_id, now(), json.dumps(trace, ensure_ascii=False)))

    def traces(self, uid: str, limit: int = 10) -> list[dict]:
        rows = self.q("SELECT * FROM traces WHERE uid=? ORDER BY id DESC LIMIT ?", (uid, limit))
        for r in rows:
            r["trace"] = json.loads(r["trace"])
        return rows

    # ------------------------------------------------------------ usage / cost cap
    def add_usage(self, tin: int, tout: int) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        self.x("""INSERT INTO usage (day, tokens_in, tokens_out, calls) VALUES (?,?,?,1)
                  ON CONFLICT(day) DO UPDATE SET tokens_in=tokens_in+excluded.tokens_in,
                  tokens_out=tokens_out+excluded.tokens_out, calls=calls+1""", (day, tin, tout))

    def usage_today(self) -> dict:
        day = datetime.now(timezone.utc).date().isoformat()
        rows = self.q("SELECT * FROM usage WHERE day=?", (day,))
        return rows[0] if rows else {"day": day, "tokens_in": 0, "tokens_out": 0, "calls": 0}

    # ------------------------------------------------------------ privacy operations
    def erase_family(self, uid: str) -> None:
        """Right to erasure: remove everything about this family except a content-free audit line."""
        with self.lock:
            for table in ("messages", "facts", "traces", "contacts", "golden_pending", "upe_writes", "copilot", "flags",
                          "families"):
                self.db.execute(f"DELETE FROM {table} WHERE uid=?", (uid,))
            self.db.commit()
        self.audit(uid, "erased")

    def purge_old_messages(self, hours: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.lock:
            cur = self.db.execute("""UPDATE messages SET text='[deleted after retention period]',
                                     redacted_text='', purged=1 WHERE purged=0 AND ts<?""", (cutoff,))
            self.db.execute("DELETE FROM traces WHERE ts<?", (cutoff,))
            self.db.commit()
            n = cur.rowcount
        if n:
            self.audit(None, "retention_purge", messages=n)
        return n

    def reset(self) -> None:
        with self.lock:
            for table in ("families", "contacts", "messages", "facts", "traces", "audit", "golden_pending", "usage", "upe_writes",
                          "copilot"):
                self.db.execute(f"DELETE FROM {table}")
            self.db.commit()
